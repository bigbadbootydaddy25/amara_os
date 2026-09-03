/**
 * Agent 2 — Instrument Retrieval (browser agent)
 *
 * Logs into the configured portal (TexasFile by default — see
 * src/browser/portals/texasfile.ts), searches for recorded instruments
 * against the project's survey tract (Section/Block/Township + County), and
 * downloads each hit into the project's Dropbox "recorded instruments"
 * folder. Every hit is logged to `portal_search_results`; every downloaded
 * file also gets a `documents` row (source = recorded_instrument) so the
 * abstracting agent picks it up.
 */
import { chromium } from 'playwright';
import { env, missingCredentialsFor } from '../config/env.js';
import { ensureFolder, uploadFile } from '../dropbox/client.js';
import { getPortalDriver } from '../browser/portals/index.js';
import type { PortalSearchHit } from '../browser/types.js';
import { insertPortalSearchResult, setProjectStatus, upsertDocument } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';

function slugForInstrument(hit: PortalSearchHit, index: number): string {
  const parts = [
    hit.recordingDate ?? 'undated',
    hit.instrumentNumber ?? `hit-${index}`,
    hit.instrumentType ?? 'instrument',
  ];
  return parts
    .join('_')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .slice(0, 150);
}

export async function runInstrumentRetrievalAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;

  const missing = missingCredentialsFor('portal');
  if (missing.length > 0) {
    throw new Error(`Cannot run instrument retrieval — missing ${missing.join(', ')}.`);
  }

  return withAgentRun(project.id, 'instrument_retrieval', async () => {
    const driver = getPortalDriver(env.portal.name());
    const browser = await chromium.launch({ headless: env.portal.headless() });

    let downloaded = 0;
    let failed = 0;

    try {
      const page = await browser.newPage();
      await driver.login(page);

      const hits = await driver.search(page, {
        state: project.state,
        county: project.county,
        surveySection: project.survey_section,
        surveyBlock: project.survey_block,
        surveyTownship: project.survey_township,
        surveyAbstractNo: project.survey_abstract_no,
      });

      await ensureFolder(project.dropbox_recorded_instruments_path);

      for (const [index, hit] of hits.entries()) {
        try {
          const content = await driver.downloadInstrument(page, hit);
          const fileName = `${slugForInstrument(hit, index)}.pdf`;
          const dropboxPath = `${project.dropbox_recorded_instruments_path}/${fileName}`;

          await uploadFile(dropboxPath, content);
          await upsertDocument({
            projectId: project.id,
            source: 'recorded_instrument',
            dropboxPath,
            fileName,
            mimeType: 'application/pdf',
          });
          await insertPortalSearchResult({
            project_id: project.id,
            portal: driver.name,
            instrument_number: hit.instrumentNumber,
            instrument_type: hit.instrumentType,
            recording_date: hit.recordingDate,
            grantor: hit.grantor,
            grantee: hit.grantee,
            download_status: 'downloaded',
            dropbox_path: dropboxPath,
            error_message: null,
          });
          downloaded++;
        } catch (err) {
          failed++;
          await insertPortalSearchResult({
            project_id: project.id,
            portal: driver.name,
            instrument_number: hit.instrumentNumber,
            instrument_type: hit.instrumentType,
            recording_date: hit.recordingDate,
            grantor: hit.grantor,
            grantee: hit.grantee,
            download_status: 'failed',
            dropbox_path: null,
            error_message: err instanceof Error ? err.message : String(err),
          });
        }
      }

      await setProjectStatus(project.id, 'retrieving');

      return {
        agentName: 'instrument_retrieval',
        summary:
          `Portal "${driver.name}" search for ${project.county} County ` +
          `Sec ${project.survey_section ?? '?'} Blk ${project.survey_block ?? '?'} ` +
          `${project.survey_township ?? ''}: ${hits.length} hit(s), ${downloaded} downloaded, ${failed} failed.`,
        metadata: { hits: hits.length, downloaded, failed },
      };
    } finally {
      await browser.close();
    }
  });
}
