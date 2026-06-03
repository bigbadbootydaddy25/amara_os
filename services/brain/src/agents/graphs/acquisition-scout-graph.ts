/**
 * Acquisition Scout — Hermes Agent 1
 *
 * Given a property (from address lookup, CSV, or OpenClaw capture),
 * produces a deal verdict: green / yellow / red with a plain-English summary.
 *
 * State flow:
 *   classifyMarket → scout → formatVerdict
 */

import { StateGraph, Annotation } from '@langchain/langgraph';
import { runAcquisitionScout } from '../tools/hermes-tools.js';
import { classifyMarketRegime } from '../tools/deal-tools.js';
import type { Property, MarketRegime } from '../../types.js';
import type { ScoutOutput } from '../tools/hermes-tools.js';

// ─── State ────────────────────────────────────────────────────────────────────

const AcquisitionState = Annotation.Root({
  property:      Annotation<Property>(),
  marketRegime:  Annotation<MarketRegime>({ default: () => 'neutral', reducer: (_, v) => v }),
  scoutResult:   Annotation<ScoutOutput | null>({ default: () => null, reducer: (_, v) => v }),
  summary:       Annotation<string>({ default: () => '', reducer: (_, v) => v }),
  error:         Annotation<string | null>({ default: () => null, reducer: (_, v) => v }),
});

// ─── Nodes ────────────────────────────────────────────────────────────────────

async function classifyMarket(state: typeof AcquisitionState.State) {
  const regime = classifyMarketRegime({ zip: state.property.zip ?? '' });
  return { marketRegime: regime };
}

async function scout(state: typeof AcquisitionState.State) {
  try {
    const result = await runAcquisitionScout({
      property:    state.property,
      marketRegime: state.marketRegime,
    });
    return { scoutResult: result };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

function formatVerdict(state: typeof AcquisitionState.State) {
  if (state.error) {
    return { summary: `Scout error: ${state.error}` };
  }
  const r = state.scoutResult!;
  const lines = [
    `ACQUISITION VERDICT: ${r.verdict.toUpperCase()}`,
    r.verdictReason,
    `MAO: $${r.simulation.recommendedMao.toLocaleString()} (${r.simulation.recommendedStrategy})`,
    `ARV: $${r.simulation.features.arvMidpoint.toLocaleString()}  Risk: ${(r.simulation.riskScore * 100).toFixed(0)}%  Confidence: ${(r.simulation.confidenceScore * 100).toFixed(0)}%`,
  ];

  if (r.priorDeals.length > 0) {
    lines.push(`Prior deals in ZIP: ${r.priorDeals.length} found in memory.`);
  }
  if (r.marketContext.length > 0) {
    lines.push(`Market context: ${r.marketContext[0].memory}`);
  }

  return { summary: lines.join('\n') };
}

// ─── Graph ────────────────────────────────────────────────────────────────────

const graph = new StateGraph(AcquisitionState)
  .addNode('classifyMarket', classifyMarket)
  .addNode('scout',          scout)
  .addNode('formatVerdict',  formatVerdict)
  .addEdge('__start__',     'classifyMarket')
  .addEdge('classifyMarket', 'scout')
  .addEdge('scout',          'formatVerdict')
  .addEdge('formatVerdict',  '__end__');

const acquisitionScoutGraph = graph.compile();

// ─── Public entry point ───────────────────────────────────────────────────────

export interface AcquisitionScoutResult {
  verdict:    'green' | 'yellow' | 'red' | 'error';
  summary:    string;
  scoutResult: ScoutOutput | null;
}

export async function runAcquisitionScoutAgent(property: Property): Promise<AcquisitionScoutResult> {
  const result = await acquisitionScoutGraph.invoke({ property });
  const verdict = result.error
    ? 'error'
    : (result.scoutResult?.verdict ?? 'error');

  return {
    verdict: verdict as AcquisitionScoutResult['verdict'],
    summary: result.summary,
    scoutResult: result.scoutResult,
  };
}
