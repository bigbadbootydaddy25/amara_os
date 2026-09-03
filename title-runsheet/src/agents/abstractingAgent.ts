/**
 * Agent 3 — Abstracting
 *
 * Reads every unprocessed `recorded_instrument` document for the project,
 * pulls its text out of Dropbox, extracts runsheet fields (grantor/grantee,
 * dates, volume/page or instrument number, legal description) with the
 * heuristic extractor in extraction/fieldExtractor.ts, and writes an
 * `instruments` row per document. Low-confidence extractions are still
 * written (so nothing silently drops) but flagged via `confidence` for the
 * curative/QC agent and for human review.
 */
import { downloadFile } from '../dropbox/client.js';
import { extractPdfText } from './extraction/pdfText.js';
import { extractFields } from './extraction/fieldExtractor.js';
import { insertInstrument, listDocuments, setDocumentOcrText, setDocumentStatus, setProjectStatus } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';

export async function runAbstractingAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;

  return withAgentRun(project.id, 'abstracting', async () => {
    const documents = await listDocuments(project.id, 'new');
    const recordedInstruments = documents.filter((doc) => doc.source === 'recorded_instrument');

    let processed = 0;
    let lowConfidence = 0;
    let errored = 0;

    for (const doc of recordedInstruments) {
      await setDocumentStatus(doc.id, 'processing');
      try {
        const buffer = await downloadFile(doc.dropbox_path);
        const text = await extractPdfText(buffer);
        await setDocumentOcrText(doc.id, text);

        if (!text.trim()) {
          await setDocumentStatus(
            doc.id,
            'error',
            'No extractable text (likely a scanned/image-only PDF) — needs OCR, not yet configured.',
          );
          errored++;
          continue;
        }

        const fields = extractFields(text);
        if (fields.confidence < 0.5) lowConfidence++;

        await insertInstrument({
          project_id: project.id,
          document_id: doc.id,
          instrument_type: fields.instrumentType,
          grantors: fields.grantors,
          grantees: fields.grantees,
          execution_date: fields.executionDate,
          recording_date: fields.recordingDate,
          county: project.county,
          state: project.state,
          volume: fields.volume,
          page: fields.page,
          instrument_number: fields.instrumentNumber,
          legal_description: fields.legalDescription,
          raw_extraction: { ...fields, sourceTextLength: text.length },
          confidence: fields.confidence,
        });

        await setDocumentStatus(doc.id, 'processed');
        processed++;
      } catch (err) {
        errored++;
        await setDocumentStatus(doc.id, 'error', err instanceof Error ? err.message : String(err));
      }
    }

    await setProjectStatus(project.id, 'abstracting');

    return {
      agentName: 'abstracting',
      summary:
        `Abstracted ${processed}/${recordedInstruments.length} recorded instrument(s) ` +
        `(${lowConfidence} low-confidence, ${errored} errored).`,
      metadata: { processed, lowConfidence, errored, total: recordedInstruments.length },
    };
  });
}
