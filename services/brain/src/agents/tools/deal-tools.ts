/**
 * Agent tools — pure functions that the LangGraph nodes call.
 * No LLM required; these are deterministic domain tools.
 */

import { simulate, DEFAULT_WEIGHTS } from '../../mirofish/engine/simulator.js';
import { WeightsRepo } from '../../memory/postgres/weights-repo.js';
import { PropertyRepo } from '../../memory/postgres/property-repo.js';
import { SimulationRepo } from '../../memory/postgres/simulation-repo.js';
import { searchProperties, searchMarketIntel, searchBuyers } from '../../memory/qdrant/vector-store.js';
import { findBuyersForZip } from '../../memory/neo4j/graph-sync.js';
import type {
  Property,
  SimulationResult,
  MarketRegime,
  MiroFishWeights,
} from '../../types.js';

// ─── Simulation tool ─────────────────────────────────────────────────────────

export interface SimulateToolInput {
  property: Property;
  marketRegime?: MarketRegime;
}

export interface SimulateToolOutput {
  simulation: SimulationResult;
  weights: MiroFishWeights;
}

export async function runSimulateTool(input: SimulateToolInput): Promise<SimulateToolOutput> {
  const weights = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;
  const simulation = simulate(input.property, weights, input.marketRegime ?? 'neutral');
  return { simulation, weights };
}

// ─── Property lookup tool ─────────────────────────────────────────────────────

export async function lookupPropertyTool(propertyId: string): Promise<Property | null> {
  return PropertyRepo.findById(propertyId).catch(() => null);
}

// ─── Latest simulation tool ───────────────────────────────────────────────────

export async function getLatestSimulationTool(propertyId: string): Promise<SimulationResult | null> {
  return SimulationRepo.findLatestForProperty(propertyId).catch(() => null);
}

// ─── Comparable properties tool ───────────────────────────────────────────────

export interface CompsToolInput {
  zip: string;
  arvMin?: number;
  arvMax?: number;
  limit?: number;
}

export async function findCompsTool(input: CompsToolInput) {
  return searchProperties(
    `comparable properties in ${input.zip}`,
    { zip: input.zip, minArv: input.arvMin },
    input.limit ?? 5,
  ).catch(() => []);
}

// ─── Market regime classification tool ───────────────────────────────────────

export interface MarketClassifyInput {
  zip: string;
  avgDom?: number;
  inventoryCount?: number;
  priceReductionPct?: number;
  foreclosureRate?: number;
}

export function classifyMarketRegime(input: MarketClassifyInput): MarketRegime {
  const { avgDom, inventoryCount, priceReductionPct, foreclosureRate } = input;

  let score = 0;

  if (avgDom !== undefined) {
    if (avgDom < 20)  score += 2;
    else if (avgDom < 40) score += 1;
    else if (avgDom > 80) score -= 2;
    else score -= 1;
  }

  if (inventoryCount !== undefined) {
    if (inventoryCount < 500)  score += 1;
    else if (inventoryCount > 2000) score -= 1;
  }

  if (priceReductionPct !== undefined) {
    if (priceReductionPct > 0.20) score -= 2;
    else if (priceReductionPct < 0.05) score += 1;
  }

  if (foreclosureRate !== undefined) {
    if (foreclosureRate > 0.05) { return 'distressed'; }
  }

  if (score >= 3)  return 'hot';
  if (score >= 0)  return 'neutral';
  return 'cold';
}

// ─── Buyer demand tool ────────────────────────────────────────────────────────

export async function findActiveBuyersTool(zip: string) {
  const [graphBuyers, vectorBuyers] = await Promise.all([
    findBuyersForZip(zip).catch(() => []),
    searchBuyers(`cash buyer active ${zip}`, { zip }, 10).catch(() => []),
  ]);
  return { graphBuyers, vectorBuyers, totalSignals: graphBuyers.length + vectorBuyers.length };
}

// ─── Market intel search tool ─────────────────────────────────────────────────

export async function searchMarketIntelTool(zip: string, regime?: MarketRegime) {
  return searchMarketIntel(`market conditions ${zip}`, { zip, regime }, 3).catch(() => []);
}
