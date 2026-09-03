/**
 * Agent 1 — Intake
 *
 * Watches the project's Dropbox "seller package" folder, registers every
 * file found there as a `documents` row (source = seller_package), and
 * advances the project out of `new` once intake has run at least once.
 *
 * This agent only *indexes* the seller package (name, path, hash) — it does
 * not attempt to parse deal terms out of it. That keeps it safe to re-run on
 * a schedule as new files land in the folder (e.g. a Dropbox file request
 * from the seller) without duplicating work: `upsertDocument` is keyed on
 * (project_id, dropbox_path).
 */
import { listFolder } from '../dropbox/client.js';
import { setProjectStatus, upsertDocument } from '../db/repository.js';
import { withAgentRun } from './runner.js';
import type { AgentContext, AgentResult } from '../types/index.js';

export async function runIntakeAgent(ctx: AgentContext): Promise<AgentResult> {
  const { project } = ctx;
  return withAgentRun(project.id, 'intake', async () => {
    const entries = await listFolder(project.dropbox_seller_package_path, true);

    for (const entry of entries) {
      await upsertDocument({
        projectId: project.id,
        source: 'seller_package',
        dropboxPath: entry.path,
        dropboxRev: entry.rev,
        fileName: entry.name,
        contentHash: entry.contentHash,
      });
    }

    if (project.status === 'new') {
      await setProjectStatus(project.id, 'intake');
    }

    return {
      agentName: 'intake',
      summary: `Indexed ${entries.length} file(s) from ${project.dropbox_seller_package_path}`,
      metadata: { fileCount: entries.length },
    };
  });
}
