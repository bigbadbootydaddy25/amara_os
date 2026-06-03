/**
 * Market Classification Agent — LangGraph StateGraph
 *
 * Flow:
 *   ingest_signals → classify_regime → update_intel → emit_regime
 *
 * Takes raw market signals (DOM, inventory, prices) and produces
 * a classified MarketRegime + stores the intel in Qdrant.
 */

import { StateGraph, Annotation, END } from '@langchain/langgraph';
import { classifyMarketRegime } from '../tools/deal-tools.js';
import { upsertMarketIntel } from '../../memory/qdrant/vector-store.js';
import type { MarketRegime } from '../../types.js';

// ─── State ────────────────────────────────────────────────────────────────────

const MarketClassificationState = Annotation.Root({
  // Input
  zip:               Annotation<string>(),
  metro:             Annotation<string | undefined>(),
  avgDom:            Annotation<number | undefined>(),
  inventoryCount:    Annotation<number | undefined>(),
  priceReductionPct: Annotation<number | undefined>(),
  foreclosureRate:   Annotation<number | undefined>(),
  medianArv:         Annotation<number | undefined>(),
  notes:             Annotation<string | undefined>(),

  // Computed
  regime:   Annotation<MarketRegime>({ default: () => 'neutral', reducer: (_, v) => v }),
  stored:   Annotation<boolean>({ default: () => false, reducer: (_, v) => v }),
  errors:   Annotation<string[]>({ default: () => [], reducer: (a, b) => [...a, ...b] }),
});

export type MarketClassificationStateType = typeof MarketClassificationState.State;

// ─── Nodes ────────────────────────────────────────────────────────────────────

function classifyRegime(
  state: MarketClassificationStateType,
): Partial<MarketClassificationStateType> {
  const regime = classifyMarketRegime({
    zip:               state.zip,
    avgDom:            state.avgDom,
    inventoryCount:    state.inventoryCount,
    priceReductionPct: state.priceReductionPct,
    foreclosureRate:   state.foreclosureRate,
  });
  return { regime };
}

async function updateIntel(
  state: MarketClassificationStateType,
): Promise<Partial<MarketClassificationStateType>> {
  try {
    await upsertMarketIntel({
      zip:           state.zip,
      metro:         state.metro,
      regime:        state.regime,
      medianArv:     state.medianArv,
      avgDom:        state.avgDom,
      inventoryCount: state.inventoryCount,
      notes:         state.notes,
    });
    return { stored: true };
  } catch (err) {
    return {
      stored: false,
      errors: [`updateIntel: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

// ─── Graph ────────────────────────────────────────────────────────────────────

function buildMarketClassificationGraph() {
  return new StateGraph(MarketClassificationState)
    .addNode('classify_regime', classifyRegime)
    .addNode('update_intel',    updateIntel)
    .addEdge('__start__',       'classify_regime')
    .addEdge('classify_regime', 'update_intel')
    .addEdge('update_intel',    END)
    .compile();
}

export const marketClassificationGraph = buildMarketClassificationGraph();

export async function classifyMarket(
  input: Omit<MarketClassificationStateType, 'regime' | 'stored' | 'errors'>,
): Promise<MarketClassificationStateType> {
  return marketClassificationGraph.invoke(input);
}
