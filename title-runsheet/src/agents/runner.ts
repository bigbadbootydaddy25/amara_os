import { finishAgentRun, startAgentRun } from '../db/repository.js';
import type { AgentName, AgentResult } from '../types/index.js';

/**
 * Wraps a single agent's work with an audit-log row in `agent_runs`: starts
 * the row, runs the agent function, and marks it succeeded/failed with
 * whatever summary/metadata the agent returns (or the error message).
 */
export async function withAgentRun(
  projectId: string,
  agentName: AgentName,
  fn: () => Promise<AgentResult>,
): Promise<AgentResult> {
  const runId = await startAgentRun(projectId, agentName);
  try {
    const result = await fn();
    await finishAgentRun(runId, 'succeeded', result.summary, undefined, result.metadata);
    return result;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await finishAgentRun(runId, 'failed', undefined, message);
    throw err;
  }
}
