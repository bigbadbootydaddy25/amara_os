/**
 * Disposition Matcher — Hermes Agent 2
 *
 * Given a deal (zip + strategy + MAO + ARV), finds the best active buyers
 * from graph + vector stores and produces an outreach recommendation.
 *
 * State flow:
 *   loadSimulation → matchBuyers → formatRecommendation
 */

import { StateGraph, Annotation } from '@langchain/langgraph';
import { runDispositionMatcher } from '../tools/hermes-tools.js';
import { SimulationRepo } from '../../memory/postgres/simulation-repo.js';
import type { MatcherOutput } from '../tools/hermes-tools.js';
import type { MarketRegime } from '../../types.js';

// ─── State ────────────────────────────────────────────────────────────────────

const DispositionState = Annotation.Root({
  propertyId:     Annotation<string>(),
  zip:            Annotation<string>(),
  strategy:       Annotation<string>({ default: () => 'wholesale', reducer: (_, v) => v }),
  mao:            Annotation<number>({ default: () => 0, reducer: (_, v) => v }),
  arv:            Annotation<number>({ default: () => 0, reducer: (_, v) => v }),
  matcherResult:  Annotation<MatcherOutput | null>({ default: () => null, reducer: (_, v) => v }),
  summary:        Annotation<string>({ default: () => '', reducer: (_, v) => v }),
  error:          Annotation<string | null>({ default: () => null, reducer: (_, v) => v }),
});

// ─── Nodes ────────────────────────────────────────────────────────────────────

async function loadSimulation(state: typeof DispositionState.State) {
  if (state.mao > 0) return {}; // already provided
  try {
    const sim = await SimulationRepo.findLatestForProperty(state.propertyId);
    if (!sim) return { error: `No simulation found for property ${state.propertyId}` };
    return {
      mao:      sim.recommendedMao,
      arv:      sim.features.arvMidpoint,
      strategy: sim.recommendedStrategy,
    };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

async function matchBuyers(state: typeof DispositionState.State) {
  if (state.error) return {};
  try {
    const result = await runDispositionMatcher({
      zip:      state.zip,
      strategy: state.strategy,
      mao:      state.mao,
      arv:      state.arv,
    });
    return { matcherResult: result };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

function formatRecommendation(state: typeof DispositionState.State) {
  if (state.error) {
    return { summary: `Matcher error: ${state.error}` };
  }
  const r = state.matcherResult!;
  const lines = [
    `DISPOSITION MATCH: ${r.totalFound} buyer(s) found in ZIP ${state.zip}`,
    r.recommendation,
  ];

  if (r.topPick) {
    lines.push(`Top buyer ID: ${r.topPick.id}${r.topPick.name ? ` (${r.topPick.name})` : ''}`);
  }

  if (r.totalFound > 1) {
    lines.push(`${r.totalFound - 1} additional buyer(s) in pipeline.`);
  }

  return { summary: lines.join('\n') };
}

// ─── Graph ────────────────────────────────────────────────────────────────────

const graph = new StateGraph(DispositionState)
  .addNode('loadSimulation',      loadSimulation)
  .addNode('matchBuyers',         matchBuyers)
  .addNode('formatRecommendation',formatRecommendation)
  .addEdge('__start__',           'loadSimulation')
  .addEdge('loadSimulation',      'matchBuyers')
  .addEdge('matchBuyers',         'formatRecommendation')
  .addEdge('formatRecommendation','__end__');

const dispositionMatcherGraph = graph.compile();

// ─── Public entry point ───────────────────────────────────────────────────────

export interface DispositionMatcherResult {
  totalBuyers:   number;
  summary:       string;
  matcherResult: MatcherOutput | null;
}

export async function runDispositionMatcherAgent(input: {
  propertyId: string;
  zip:        string;
  mao?:       number;
  arv?:       number;
  strategy?:  string;
}): Promise<DispositionMatcherResult> {
  const result = await dispositionMatcherGraph.invoke({
    propertyId: input.propertyId,
    zip:        input.zip,
    mao:        input.mao ?? 0,
    arv:        input.arv ?? 0,
    strategy:   input.strategy ?? 'wholesale',
  });

  return {
    totalBuyers:   result.matcherResult?.totalFound ?? 0,
    summary:       result.summary,
    matcherResult: result.matcherResult,
  };
}
