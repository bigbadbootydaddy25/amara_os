import type {
  Property,
  MiroFishFeatures,
  MiroFishWeights,
  MarketRegime,
} from '../../types.js';

const DISTRESS_FLAGS: Array<keyof Property> = [
  'taxDelinquent',
  'bankruptcy',
  'liens',
  'vacant',
  'preForeclosure',
];

const DISTRESS_WEIGHTS: Record<string, number> = {
  taxDelinquent: 0.25,
  bankruptcy: 0.30,
  liens: 0.20,
  vacant: 0.15,
  preForeclosure: 0.10,
};

// Conservative buy-box parameters by strategy
const MAO_FORMULA = {
  wholesale: { maxPctArv: 0.70, rehabMultiplier: 1.0, minMargin: 10_000 },
  flip:      { maxPctArv: 0.75, rehabMultiplier: 1.1, minMargin: 20_000 },
  brrrr:     { maxPctArv: 0.75, rehabMultiplier: 1.0, minMargin: 15_000 },
};

export function computeFeatures(
  property: Property,
  weights: MiroFishWeights,
  marketRegime: MarketRegime = 'neutral',
): MiroFishFeatures {
  const arv = resolveArv(property);
  const asking = property.askingPrice ?? arv * 0.9;
  const rehab = property.rehabEstimate ?? 0;

  const arvMidpoint = arv;
  const discountDepth = arv > 0 ? Math.max(0, (arv - asking) / arv) : 0;
  const rehabRisk = arv > 0 ? Math.min(1, rehab / arv) : 0;

  const distressScore = computeDistressScore(property);
  const liquidityScore = computeLiquidityScore(marketRegime, weights, property.zip);
  const buyerDemandHeat = computeBuyerDemandHeat(property.zip, weights, marketRegime);
  const exitVelocity = estimateExitVelocity(marketRegime, weights, property.zip);
  const assignmentProbability = computeAssignmentProbability(
    discountDepth,
    liquidityScore,
    buyerDemandHeat,
  );

  const maoCeiling = computeMaoCeiling(arv, rehab, 'wholesale');

  return {
    arvMidpoint,
    discountDepth,
    rehabRisk,
    liquidityScore,
    buyerDemandHeat,
    exitVelocity,
    distressScore,
    assignmentProbability,
    maoCeiling,
    marketRegime,
    zipMedianArv: weights.zipPriors[property.zip]?.medianArv,
    zipAvgDom: weights.zipPriors[property.zip]?.avgDom,
  };
}

function resolveArv(property: Property): number {
  if (property.arvEstimate) return property.arvEstimate;
  if (property.arvLow && property.arvHigh) {
    return (property.arvLow + property.arvHigh) / 2;
  }
  if (property.arvLow) return property.arvLow * 1.05;
  if (property.arvHigh) return property.arvHigh * 0.95;
  // Fallback: use asking price inflated by regime-based factor
  return (property.askingPrice ?? 0) * 1.25;
}

function computeDistressScore(property: Property): number {
  let score = 0;
  for (const flag of DISTRESS_FLAGS) {
    if (property[flag] === true) {
      score += DISTRESS_WEIGHTS[flag as string] ?? 0;
    }
  }
  return Math.min(1, score);
}

function computeLiquidityScore(
  regime: MarketRegime,
  weights: MiroFishWeights,
  zip: string,
): number {
  const regimeBase: Record<MarketRegime, number> = {
    hot: 0.85,
    neutral: 0.60,
    cold: 0.35,
    distressed: 0.20,
  };
  const base = regimeBase[regime];
  const zipPrior = weights.zipPriors[zip];
  if (!zipPrior) return base;

  // Adjust by ZIP avg DOM — lower DOM = higher liquidity
  const domFactor = zipPrior.avgDom > 0
    ? Math.max(0, 1 - zipPrior.avgDom / 120)
    : 0;
  return Math.min(1, base * 0.7 + domFactor * 0.3);
}

function computeBuyerDemandHeat(
  zip: string,
  weights: MiroFishWeights,
  regime: MarketRegime,
): number {
  const regimeBase: Record<MarketRegime, number> = {
    hot: 0.80,
    neutral: 0.55,
    cold: 0.30,
    distressed: 0.40,   // distressed markets attract cash buyers
  };
  const base = regimeBase[regime];
  const zipPrior = weights.zipPriors[zip];
  if (!zipPrior) return base;

  // More samples in ZIP = more known buyer demand
  const sampleFactor = Math.min(1, zipPrior.sampleCount / 50);
  return Math.min(1, base * 0.8 + sampleFactor * 0.2);
}

function estimateExitVelocity(
  regime: MarketRegime,
  weights: MiroFishWeights,
  zip: string,
): number {
  const regimeDays: Record<MarketRegime, number> = {
    hot: 14,
    neutral: 30,
    cold: 60,
    distressed: 45,
  };
  const base = regimeDays[regime];
  const zipPrior = weights.zipPriors[zip];
  if (!zipPrior?.avgDom) return base;
  return Math.round(base * 0.4 + zipPrior.avgDom * 0.6);
}

function computeAssignmentProbability(
  discountDepth: number,
  liquidityScore: number,
  buyerDemandHeat: number,
): number {
  // Deeper discount + more liquid market + hot buyer demand = higher assignment chance
  const score = discountDepth * 0.4 + liquidityScore * 0.35 + buyerDemandHeat * 0.25;
  return Math.min(0.99, Math.max(0.01, score));
}

function computeMaoCeiling(
  arv: number,
  rehab: number,
  strategy: keyof typeof MAO_FORMULA,
): number {
  const params = MAO_FORMULA[strategy];
  const raw = arv * params.maxPctArv - rehab * params.rehabMultiplier - params.minMargin;
  return Math.max(0, Math.round(raw / 500) * 500); // round to nearest $500
}
