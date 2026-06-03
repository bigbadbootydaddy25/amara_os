import { randomUUID } from 'crypto';
import type {
  Property,
  SimulationResult,
  MiroFishWeights,
  MarketRegime,
  DealStrategy,
} from '../../types.js';
import { computeFeatures } from '../features/feature-engine.js';
import { runScenario } from '../scenarios/scenario-engine.js';

export const MODEL_VERSION = 'v1.0.0';

export const DEFAULT_WEIGHTS: MiroFishWeights = {
  version: MODEL_VERSION,
  arvDiscountWeight: 0.35,
  rehabRiskWeight: 0.20,
  liquidityWeight: 0.20,
  buyerDemandWeight: 0.15,
  distressWeight: 0.10,
  zipPriors: {},
  trainingSamples: 0,
};

export function simulate(
  property: Property,
  weights: MiroFishWeights = DEFAULT_WEIGHTS,
  marketRegime: MarketRegime = 'neutral',
  dealId?: string,
): SimulationResult {
  const propertyId = property.id ?? randomUUID();

  const features = computeFeatures(property, weights, marketRegime);

  const conservative = runScenario(features, 'conservative');
  const base = runScenario(features, 'base');
  const aggressive = runScenario(features, 'aggressive');

  // Recommended MAO is a weighted blend toward conservative
  const recommendedMao = Math.round(
    (conservative.mao * 0.50 + base.mao * 0.35 + aggressive.mao * 0.15) / 500,
  ) * 500;

  const recommendedStrategy = selectRecommendedStrategy(
    conservative.strategy,
    base.strategy,
    features.assignmentProbability,
  );

  const riskScore = parseFloat(
    (conservative.riskScore * 0.50 + base.riskScore * 0.35 + aggressive.riskScore * 0.15).toFixed(4),
  );

  const confidenceScore = computeConfidence(weights, property.zip, features);

  return {
    propertyId,
    dealId,
    features,
    conservative,
    base,
    aggressive,
    recommendedMao,
    recommendedStrategy,
    riskScore,
    confidenceScore,
    modelVersion: weights.version,
    createdAt: new Date(),
  };
}

function selectRecommendedStrategy(
  conservativeStrategy: DealStrategy,
  baseStrategy: DealStrategy,
  assignmentProbability: number,
): DealStrategy {
  // If both agree, use that
  if (conservativeStrategy === baseStrategy) return baseStrategy;
  // If assignment probability is high, lean wholesale
  if (assignmentProbability > 0.65) return 'wholesale';
  // Default to conservative strategy for safety
  return conservativeStrategy;
}

function computeConfidence(
  weights: MiroFishWeights,
  zip: string,
  features: ReturnType<typeof computeFeatures>,
): number {
  const zipPrior = weights.zipPriors[zip];
  const zipSamples = zipPrior?.sampleCount ?? 0;

  // More training data in this ZIP = higher confidence
  const dataMass = Math.min(1, zipSamples / 30);

  // ARV was provided explicitly (not estimated)
  const arvConfidence = features.zipMedianArv ? 0.8 : 0.5;

  // More training overall
  const globalMass = Math.min(1, weights.trainingSamples / 200);

  return parseFloat(
    (dataMass * 0.40 + arvConfidence * 0.35 + globalMass * 0.25).toFixed(4),
  );
}
