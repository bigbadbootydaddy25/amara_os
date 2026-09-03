/**
 * Agent 4 — Curative / QC
 *
 * Walks the project's instruments in chronological (recording date) order
 * and flags chain-of-title problems a landman/abstractor would want to see
 * before the runsheet goes out: gaps between a conveyance's grantee and the
 * next conveyance's grantor, missing recording data, and low-confidence
 * extractions that need a human look. This is a heuristic first pass, not a
 * substitute for attorney review — it is meant to shrink the manual QC
 * surface, not replace it.
 */
import { insertCurativeItem, listInstruments, setProjectStatus } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';
import type { InstrumentRow } from '../types/index.js';

function normalizeName(name: string): string {
  return name.trim().toLowerCase().replace(/[.,]/g, '').replace(/\s+/g, ' ');
}

function namesOverlap(a: string[], b: string[]): boolean {
  const setB = new Set(b.map(normalizeName));
  return a.some((name) => setB.has(normalizeName(name)));
}

export async function runCurativeAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;

  return withAgentRun(project.id, 'curative_qc', async () => {
    const instruments = await listInstruments(project.id);
    let flagged = 0;

    const conveyances: InstrumentRow[] = instruments.filter(
      (i) => i.grantors.length > 0 || i.grantees.length > 0,
    );

    for (const instrument of instruments) {
      if (!instrument.recording_date) {
        await insertCurativeItem({
          project_id: project.id,
          instrument_id: instrument.id,
          severity: 'warning',
          category: 'missing_recording_data',
          description: `Instrument ${instrument.instrument_number ?? instrument.id} has no recording date — verify against the county clerk record.`,
        });
        flagged++;
      }

      if (!instrument.instrument_number && !(instrument.volume && instrument.page)) {
        await insertCurativeItem({
          project_id: project.id,
          instrument_id: instrument.id,
          severity: 'warning',
          category: 'missing_recording_data',
          description: 'No instrument number and no volume/page recorded — cannot cite this instrument in the runsheet.',
        });
        flagged++;
      }

      if (instrument.confidence !== null && instrument.confidence < 0.5) {
        await insertCurativeItem({
          project_id: project.id,
          instrument_id: instrument.id,
          severity: 'info',
          category: 'low_confidence_extraction',
          description: `Automated field extraction confidence is low (${instrument.confidence.toFixed(2)}) — have an abstractor confirm the parsed fields against the source document.`,
        });
        flagged++;
      }
    }

    // Chain-of-title continuity: each conveyance's grantee should show up as
    // a grantor (or be explained — heirship, probate, etc.) somewhere later.
    for (let i = 0; i < conveyances.length - 1; i++) {
      const current = conveyances[i];
      if (current.grantees.length === 0) continue;

      const laterGrantors = conveyances.slice(i + 1).flatMap((c) => c.grantors);
      if (laterGrantors.length === 0) continue; // nothing later to compare against yet

      if (!namesOverlap(current.grantees, laterGrantors)) {
        await insertCurativeItem({
          project_id: project.id,
          instrument_id: current.id,
          severity: 'critical',
          category: 'gap_in_chain',
          description:
            `Grantee(s) ${current.grantees.join('; ') || '(none extracted)'} on instrument ` +
            `${current.instrument_number ?? current.id} do not appear as grantor(s) on any later instrument in ` +
            `this runsheet — possible gap in chain of title, or a missed/heirship conveyance.`,
        });
        flagged++;
      }
    }

    await setProjectStatus(project.id, 'curative');

    return {
      agentName: 'curative_qc',
      summary: `Reviewed ${instruments.length} instrument(s); flagged ${flagged} curative item(s).`,
      metadata: { instrumentCount: instruments.length, flagged },
    };
  });
}
