/**
 * train.ts — THE SELF-IMPROVEMENT FILE
 *
 * This file is the agent's continuous improvement target — the AMARA equivalent
 * of Karpathy's train.py. The self-improvement engine reads this, evaluates it
 * against deal outcomes, and rewrites it nightly to improve performance.
 *
 * Contains: LangChain reasoning chains, agent prompts, scoring weights,
 * buyer match logic, signal thresholds.
 *
 * Training metric: deals closed per agent run + buyer match accuracy
 */

export { dealDiscoveryChain } from '@/lib/pipeline/deal-discovery-chain';
export { buyerMatchChain } from '@/lib/pipeline/buyer-match-chain';
export { dailyPipelineChain } from '@/lib/pipeline/daily-pipeline-chain';
export { BuyerAgent } from '@/lib/hermes/buyer-agent';
export { SfrDomAgent } from '@/lib/hermes/sfr-dom-agent';
export { LandSubdivisionAgent } from '@/lib/hermes/land-subdivision-agent';
export { OsintAgent } from '@/lib/hermes/osint-agent';

// Scoring weights — self-improvement engine may tune these
export const MATCH_WEIGHTS = {
  priceRangeMatch:    0.40,
  zipCodeMatch:       0.30,
  repeatBuyerBonus:   0.20,
  whaleLandMatch:     0.10,
} as const;

export const SIGNAL_THRESHOLDS = {
  dom90:              90,   // days on market → distress signal
  killShotWeight:     0.80, // MiroFish weight → kill shot
  minSpread:          15_000, // min profit spread to pursue
} as const;

export const AGENT_PROMPTS = {
  buyerAnalysis: `Market: {market}\nTop buyers:\n{buyerSummary}\n\nWhich buyers should Scott call first this week and why?`,
  sfrOpportunity: `Market: {market}\nSFR 90+ DOM properties:\n{dealSummary}\n\nWhich properties show the strongest distress signals and best MAO opportunity?`,
  landAnalysis: `Market: {market}\nLand/Subdivision deals:\n{dealSummary}\n\nCalculate MAO estimates (70% ARV minus repairs), rank by opportunity, identify ghost subdivision plays.`,
  callList: `Top buyer-deal matches:\n{matchList}\n\nProduce today's call list with a one-sentence pitch for each buyer.`,
} as const;
