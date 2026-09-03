/**
 * Agent 5 — Runsheet Export
 *
 * Orders the project's instruments chronologically (recording date, falling
 * back to execution date, falling back to insert order), persists that order
 * as `runsheet_entries`, renders it to CSV, and uploads the CSV to the
 * project's Dropbox runsheet-export path.
 */
import { ensureFolder, uploadFile } from '../dropbox/client.js';
import { env } from '../config/env.js';
import { buildRunsheetCsv } from '../export/csv.js';
import { listInstruments, replaceRunsheetEntries, setProjectStatus } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';

function summarize(instrument: { instrument_type: string | null; grantors: string[]; grantees: string[] }): string {
  const type = instrument.instrument_type ?? 'Instrument';
  const grantors = instrument.grantors.join(', ') || 'Unknown Grantor';
  const grantees = instrument.grantees.join(', ') || 'Unknown Grantee';
  return `${type}: ${grantors} to ${grantees}`;
}

export async function runRunsheetExportAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;

  return withAgentRun(project.id, 'runsheet_export', async () => {
    const instruments = await listInstruments(project.id); // already ordered by recording/execution date
    const sequenced = instruments.map((instrument, index) => ({ ...instrument, sequence_no: index + 1 }));

    await replaceRunsheetEntries(
      project.id,
      sequenced.map((row) => ({
        instrumentId: row.id,
        sequenceNo: row.sequence_no,
        summary: summarize(row),
      })),
    );

    const csvBuffer = buildRunsheetCsv(sequenced);
    const exportRoot = project.dropbox_runsheet_export_path ?? env.dropbox.runsheetExportRoot();
    const fileName = `${project.name.replace(/[^a-zA-Z0-9._-]+/g, '-')}_runsheet.csv`;
    const dropboxPath = `${exportRoot}/${fileName}`;

    await ensureFolder(exportRoot);
    await uploadFile(dropboxPath, csvBuffer);

    await setProjectStatus(project.id, 'exporting');

    return {
      agentName: 'runsheet_export',
      summary: `Exported ${sequenced.length}-row runsheet CSV to ${dropboxPath}`,
      metadata: { rowCount: sequenced.length, dropboxPath },
    };
  });
}
