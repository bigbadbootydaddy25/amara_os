/**
 * Agent 6 — Report
 *
 * Renders the final title report (chain-of-title table + curative findings)
 * to a Word document and uploads it to the project's Dropbox report-export
 * path. Runs last, after the runsheet export, and marks the project complete.
 */
import { ensureFolder, uploadFile } from '../dropbox/client.js';
import { env } from '../config/env.js';
import { buildTitleReportDocx } from '../export/word.js';
import { listCurativeItems, listInstruments, setProjectStatus } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';

export async function runReportAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;

  return withAgentRun(project.id, 'report', async () => {
    const instruments = await listInstruments(project.id);
    const sequenced = instruments.map((instrument, index) => ({ ...instrument, sequence_no: index + 1 }));
    const curativeItems = await listCurativeItems(project.id);

    const docxBuffer = await buildTitleReportDocx(project, sequenced, curativeItems);

    const exportRoot = project.dropbox_report_export_path ?? env.dropbox.reportExportRoot();
    const fileName = `${project.name.replace(/[^a-zA-Z0-9._-]+/g, '-')}_title_report.docx`;
    const dropboxPath = `${exportRoot}/${fileName}`;

    await ensureFolder(exportRoot);
    await uploadFile(dropboxPath, docxBuffer);

    await setProjectStatus(project.id, 'complete');

    return {
      agentName: 'report',
      summary: `Generated title report (${sequenced.length} instruments, ${curativeItems.length} curative items) to ${dropboxPath}`,
      metadata: { dropboxPath, instrumentCount: sequenced.length, curativeItemCount: curativeItems.length },
    };
  });
}
