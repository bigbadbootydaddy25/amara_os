/**
 * Deal Analysis Agent — LangGraph StateGraph
 *
 * Flow:
 *   classify_market → run_simulation → find_comps → find_buyers → synthesize
 *
 * Each node is a pure async function operating on typed state.
 * No LLM calls required — all deterministic domain logic.
 */

import { StateGraph, Annotation, END } from '@langchain/langgraph';
import {
  runSimulateTool,
  classifyMarketRegime,
  findCompsTool,
  findActiveBuyersTool,
  searchMarketIntelTool,
} from '../tools/deal-tools.js';
import type {
  Property,
  SimulationResult,
  MarketRegime,
  MiroFishWeights,
} from '../../types.js';

// ─── State schema ─────────────────────────────────────────────────────────────

const DealAnalysisState = Annotation.Root({
  // Input
  property: Annotation<Property>(),
  marketOverride: Annotation<MarketRegime | undefined>(),

  // Populated by nodes
  marketRegime:  Annotation<MarketRegime>({ default: () => 'neutral', reducer: (_, v) => v }),
  marketIntel:   Annotation<unknown[]>({ default: () => [], reducer: (_, v) => v }),
  simulation:    Annotation<SimulationResult | null>({ default: () => null, reducer: (_, v) => v }),
  weights:       Annotation<MiroFishWeights | null>({ default: () => null, reducer: (_, v) => v }),
  comps:         Annotation<unknown[]>({ default: () => [], reducer: (_, v) => v }),
  buyers:        Annotation<{ graphBuyers: unknown[]; vectorBuyers: unknown[]; totalSignals: number } | null>({
    default: () => null, reducer: (_, v) => v,
  }),
  recommendation: Annotation<DealRecommendation | null>({ default: () => null, reducer: (_, v) => v }),
  errors:        Annotation<string[]>({ default: () => [], reducer: (a, b) => [...a, ...b] }),
});

export type DealAnalysisStateType = typeof DealAnalysisState.State;

export interface DealRecommendation {
  action:           'pursue' | 'pass' | 'needs_more_data';
  recommendedMao:   number;
  strategy:         string;
  riskScore:        number;
  confidenceScore:  number;
  reasoning:        string[];
  buyerDemand:      'high' | 'moderate' | 'low';
  marketContext:    MarketRegime;
}

// ─── Nodes ────────────────────────────────────────────────────────────────────

async function classifyMarket(state: DealAnalysisStateType): Promise<Partial<DealAnalysisStateType>> {
  if (state.marketOverride) {
    return { marketRegime: state.marketOverride };
  }

  try {
    const intel = await searchMarketIntelTool(state.property.zip);
    const payload = intel[0]?.payload as Record<string, unknown> | undefined;

    const regime = classifyMarketRegime({
      zip:               state.property.zip,
      avgDom:            payload?.avg_dom as number | undefined,
      inventoryCount:    payload?.inventory_count as number | undefined,
      foreclosureRate:   undefined,
      priceReductionPct: undefined,
    });

    return { marketRegime: regime, marketIntel: intel };
  } catch (err) {
    return {
      marketRegime: 'neutral',
      errors: [`classifyMarket: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

async function runSimulation(state: DealAnalysisStateType): Promise<Partial<DealAnalysisStateType>> {
  try {
    const { simulation, weights } = await runSimulateTool({
      property:     state.property,
      marketRegime: state.marketRegime,
    });
    return { simulation, weights };
  } catch (err) {
    return {
      errors: [`runSimulation: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

async function findComps(state: DealAnalysisStateType): Promise<Partial<DealAnalysisStateType>> {
  try {
    const comps = await findCompsTool({
      zip:    state.property.zip,
      arvMin: (state.property.arvEstimate ?? 0) * 0.8,
      arvMax: (state.property.arvEstimate ?? 0) * 1.2,
      limit:  5,
    });
    return { comps };
  } catch (err) {
    return {
      comps:  [],
      errors: [`findComps: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

async function findBuyers(state: DealAnalysisStateType): Promise<Partial<DealAnalysisStateType>> {
  try {
    const buyers = await findActiveBuyersTool(state.property.zip);
    return { buyers };
  } catch (err) {
    return {
      buyers: { graphBuyers: [], vectorBuyers: [], totalSignals: 0 },
      errors: [`findBuyers: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

function synthesize(state: DealAnalysisStateType): Partial<DealAnalysisStateType> {
  const sim = state.simulation;

  if (!sim) {
    return {
      recommendation: {
        action: 'needs_more_data',
        recommendedMao: 0,
        strategy: 'unknown',
        riskScore: 1,
        confidenceScore: 0,
        reasoning: ['Simulation failed — insufficient data to make recommendation'],
        buyerDemand: 'low',
        marketContext: state.marketRegime,
      },
    };
  }

  const reasoning: string[] = [];

  // MAO viability
  const asking = state.property.askingPrice ?? Infinity;
  const maoViable = sim.recommendedMao >= asking * 0.90;
  if (maoViable) reasoning.push(`MAO $${fmt(sim.recommendedMao)} is within range of asking $${fmt(asking)}`);
  else reasoning.push(`MAO $${fmt(sim.recommendedMao)} is below asking $${fmt(asking)} — spread is thin`);

  // Risk
  if (sim.riskScore < 0.35) reasoning.push('Risk is low — favorable deal profile');
  else if (sim.riskScore < 0.60) reasoning.push('Moderate risk — proceed with due diligence');
  else reasoning.push('High risk — consider passing or renegotiating');

  // Market
  reasoning.push(`Market: ${state.marketRegime} | Exit velocity: ~${sim.base.exitDays} days`);

  // Buyer demand
  const totalSignals = state.buyers?.totalSignals ?? 0;
  const buyerDemand: 'high' | 'moderate' | 'low' =
    totalSignals >= 5 ? 'high' : totalSignals >= 2 ? 'moderate' : 'low';
  reasoning.push(`Buyer demand: ${buyerDemand} (${totalSignals} active signals in ZIP ${state.property.zip})`);

  // Comps
  if (state.comps.length > 0) reasoning.push(`${state.comps.length} comparable properties found in ZIP`);

  // Confidence
  if (sim.confidenceScore < 0.3) reasoning.push('Low confidence — limited historical data for this ZIP');

  // Decision
  const action: DealRecommendation['action'] =
    sim.riskScore < 0.50 && maoViable && sim.confidenceScore > 0.2
      ? 'pursue'
      : sim.riskScore > 0.70 || (!maoViable && sim.riskScore > 0.50)
        ? 'pass'
        : 'needs_more_data';

  return {
    recommendation: {
      action,
      recommendedMao:  sim.recommendedMao,
      strategy:        sim.recommendedStrategy,
      riskScore:       sim.riskScore,
      confidenceScore: sim.confidenceScore,
      reasoning,
      buyerDemand,
      marketContext:   state.marketRegime,
    },
  };
}

// ─── Graph assembly ───────────────────────────────────────────────────────────

function buildDealAnalysisGraph() {
  const graph = new StateGraph(DealAnalysisState)
    .addNode('classify_market', classifyMarket)
    .addNode('run_simulation',  runSimulation)
    .addNode('find_comps',      findComps)
    .addNode('find_buyers',     findBuyers)
    .addNode('synthesize',      synthesize)
    .addEdge('__start__',       'classify_market')
    .addEdge('classify_market', 'run_simulation')
    .addEdge('run_simulation',  'find_comps')
    .addEdge('find_comps',      'find_buyers')
    .addEdge('find_buyers',     'synthesize')
    .addEdge('synthesize',      END);

  return graph.compile();
}

export const dealAnalysisGraph = buildDealAnalysisGraph();

export async function analyzeDeal(
  property: Property,
  marketOverride?: MarketRegime,
): Promise<DealAnalysisStateType> {
  return dealAnalysisGraph.invoke({ property, marketOverride });
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}
