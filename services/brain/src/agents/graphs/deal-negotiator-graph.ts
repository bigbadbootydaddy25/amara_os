/**
 * Deal Negotiator — Hermes Agent 3
 *
 * Given a current offer and seller ask, models the counter-offer range
 * using MiroFish conservative/base/aggressive outputs.
 *
 * State flow:
 *   negotiate → formatCounter
 */

import { StateGraph, Annotation } from '@langchain/langgraph';
import { runDealNegotiator } from '../tools/hermes-tools.js';
import type { NegotiatorOutput } from '../tools/hermes-tools.js';
import type { Property, MarketRegime } from '../../types.js';

// ─── State ────────────────────────────────────────────────────────────────────

const NegotiatorState = Annotation.Root({
  property:       Annotation<Property>(),
  currentOffer:   Annotation<number>(),
  sellerAsk:      Annotation<number>(),
  marketRegime:   Annotation<MarketRegime>({ default: () => 'neutral', reducer: (_, v) => v }),
  negotiation:    Annotation<NegotiatorOutput | null>({ default: () => null, reducer: (_, v) => v }),
  summary:        Annotation<string>({ default: () => '', reducer: (_, v) => v }),
  error:          Annotation<string | null>({ default: () => null, reducer: (_, v) => v }),
});

// ─── Nodes ────────────────────────────────────────────────────────────────────

async function negotiate(state: typeof NegotiatorState.State) {
  try {
    const result = await runDealNegotiator({
      property:     state.property,
      currentOffer: state.currentOffer,
      sellerAsk:    state.sellerAsk,
      marketRegime: state.marketRegime,
    });
    return { negotiation: result };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

function formatCounter(state: typeof NegotiatorState.State) {
  if (state.error) {
    return { summary: `Negotiator error: ${state.error}` };
  }
  const n = state.negotiation!;
  const cr = n.counterRange;
  const lines = [
    n.shouldCounter ? 'COUNTER RECOMMENDED' : 'DO NOT COUNTER',
    n.rationale,
    `Floor: $${cr.floor.toLocaleString()}  |  Target: $${cr.target.toLocaleString()}  |  Ceiling: $${cr.ceiling.toLocaleString()}`,
    `Seller ask: $${state.sellerAsk.toLocaleString()}  |  Your current offer: $${state.currentOffer.toLocaleString()}`,
    `Risk: ${(n.simulation.riskScore * 100).toFixed(0)}%  Strategy: ${n.simulation.recommendedStrategy}`,
  ];
  return { summary: lines.join('\n') };
}

// ─── Graph ────────────────────────────────────────────────────────────────────

const graph = new StateGraph(NegotiatorState)
  .addNode('negotiate',    negotiate)
  .addNode('formatCounter',formatCounter)
  .addEdge('__start__',   'negotiate')
  .addEdge('negotiate',   'formatCounter')
  .addEdge('formatCounter','__end__');

const dealNegotiatorGraph = graph.compile();

// ─── Public entry point ───────────────────────────────────────────────────────

export interface DealNegotiatorResult {
  shouldCounter: boolean;
  summary:       string;
  negotiation:   NegotiatorOutput | null;
}

export async function runDealNegotiatorAgent(input: {
  property:     Property;
  currentOffer: number;
  sellerAsk:    number;
  marketRegime?: MarketRegime;
}): Promise<DealNegotiatorResult> {
  const result = await dealNegotiatorGraph.invoke({
    property:     input.property,
    currentOffer: input.currentOffer,
    sellerAsk:    input.sellerAsk,
    marketRegime: input.marketRegime ?? 'neutral',
  });

  return {
    shouldCounter: result.negotiation?.shouldCounter ?? false,
    summary:       result.summary,
    negotiation:   result.negotiation,
  };
}
