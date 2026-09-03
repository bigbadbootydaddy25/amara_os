import { getProject, setProjectStatus } from '../db/repository.js';
import { runIntakeAgent } from '../agents/intakeAgent.js';
import { runInstrumentRetrievalAgent } from '../agents/instrumentRetrievalAgent.js';
import { runAbstractingAgent } from '../agents/abstractingAgent.js';
import { runCurativeAgent } from '../agents/curativeAgent.js';
import { runRunsheetExportAgent } from '../agents/runsheetExportAgent.js';
import { runReportAgent } from '../agents/reportAgent.js';
import type { AgentResult } from '../types/index.js';

export type PipelineStage =
  | 'intake'
  | 'retrieval'
  | 'abstracting'
  | 'curative'
  | 'runsheet'
  | 'report';

export const PIPELINE_STAGES: PipelineStage[] = [
  'intake',
  'retrieval',
  'abstracting',
  'curative',
  'runsheet',
  'report',
];

/**
 * Runs the six agents in order for a project: Intake -> Instrument
 * Retrieval -> Abstracting -> Curative/QC -> Runsheet Export -> Report.
 * Stops at the first failing stage (each agent already logs its own
 * success/failure to `agent_runs`) so a project never silently skips ahead
 * on bad data.
 */
export async function runPipeline(projectId: string, fromStage: PipelineStage = 'intake'): Promise<AgentResult[]> {
  const project = await getProject(projectId);
  if (!project) throw new Error(`No project found with id ${projectId}`);

  const results: AgentResult[] = [];
  const startIndex = PIPELINE_STAGES.indexOf(fromStage);

  for (const stage of PIPELINE_STAGES.slice(startIndex)) {
    // Re-fetch the project each stage so agents see status/paths updated by
    // the previous stage.
    const current = await getProject(projectId);
    if (!current) throw new Error(`Project ${projectId} disappeared mid-pipeline`);
    const ctx = { project: current };

    try {
      switch (stage) {
        case 'intake':
          results.push(await runIntakeAgent(ctx));
          break;
        case 'retrieval':
          results.push(await runInstrumentRetrievalAgent(ctx));
          break;
        case 'abstracting':
          results.push(await runAbstractingAgent(ctx));
          break;
        case 'curative':
          results.push(await runCurativeAgent(ctx));
          break;
        case 'runsheet':
          results.push(await runRunsheetExportAgent(ctx));
          break;
        case 'report':
          results.push(await runReportAgent(ctx));
          break;
      }
    } catch (err) {
      await setProjectStatus(projectId, 'error');
      throw err;
    }
  }

  return results;
}
