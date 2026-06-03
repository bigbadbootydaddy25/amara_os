import type {
  MiroFishWeights,
  DealOutcomeInput,
  WeightUpdate,
  ZipPrior,
} from '../../types.js';

const LEARNING_RATE = 0.05;
const MIN_WEIGHT = 0.05;
const MAX_WEIGHT = 0.60;

/**
 * Updates MiroFish weights from a single deal outcome using online gradient descent.
 * Returns a new weights object (immutable — never mutates input).
 */
export function updateWeights(
  current: MiroFishWeights,
  outcome: DealOutcomeInput,
  predictedMao: number,
  predictedArv: number,
  predictedRehab: number,
  zip: string,
): { weights: MiroFishWeights; update: WeightUpdate } {
  const maoError = outcome.actualContractPrice - predictedMao;
  const arvError = (outcome.actualArv ?? predictedArv) - predictedArv;
  const rehabError = (outcome.actualRehab ?? predictedRehab) - predictedRehab;
  const profitError = outcome.actualProfit - estimatePredictedProfit(predictedMao, predictedArv, predictedRehab);

  // Direction of corrections
  const maoMissHigh = maoError < 0;  // we offered too much
  const arvMissHigh = arvError < 0;  // we over-estimated ARV
  const rehabMissLow = rehabError > 0; // we under-estimated rehab

  const adjustments: Record<string, number> = {};

  // If MAO was too high (we overpaid), increase rehab and reduce discount weights
  const arvAdj = maoMissHigh ? -LEARNING_RATE * 0.5 : LEARNING_RATE * 0.3;
  const rehabAdj = rehabMissLow ? LEARNING_RATE * 0.4 : -LEARNING_RATE * 0.2;

  adjustments.arvDiscountWeight = clamp(
    current.arvDiscountWeight + arvAdj,
    MIN_WEIGHT,
    MAX_WEIGHT,
  ) - current.arvDiscountWeight;

  adjustments.rehabRiskWeight = clamp(
    current.rehabRiskWeight + rehabAdj,
    MIN_WEIGHT,
    MAX_WEIGHT,
  ) - current.rehabRiskWeight;

  const newWeights: MiroFishWeights = {
    ...current,
    version: bumpVersion(current.version),
    arvDiscountWeight: clamp(current.arvDiscountWeight + adjustments.arvDiscountWeight, MIN_WEIGHT, MAX_WEIGHT),
    rehabRiskWeight: clamp(current.rehabRiskWeight + adjustments.rehabRiskWeight, MIN_WEIGHT, MAX_WEIGHT),
    zipPriors: updateZipPrior(current.zipPriors, zip, outcome, predictedArv),
    trainingSamples: current.trainingSamples + 1,
    lastTrainedAt: new Date(),
    validationMae: computeRollingMae(current.validationMae, Math.abs(profitError)),
  };

  const mae = Math.abs(profitError);

  return {
    weights: newWeights,
    update: {
      previousVersion: current.version,
      newVersion: newWeights.version,
      adjustments,
      trainingSamples: newWeights.trainingSamples,
      mae,
    },
  };
}

function updateZipPrior(
  priors: Record<string, ZipPrior>,
  zip: string,
  outcome: DealOutcomeInput,
  predictedArv: number,
): Record<string, ZipPrior> {
  const existing = priors[zip] ?? {
    medianArv: predictedArv,
    avgDom: outcome.actualDom ?? 30,
    avgDiscountDepth: 0.25,
    sampleCount: 0,
  };

  const n = existing.sampleCount + 1;
  const actualArv = outcome.actualArv ?? predictedArv;
  const actualDom = outcome.actualDom ?? existing.avgDom;

  const updated: ZipPrior = {
    medianArv: rollingAvg(existing.medianArv, actualArv, n),
    avgDom: rollingAvg(existing.avgDom, actualDom, n),
    avgDiscountDepth: existing.avgDiscountDepth, // updated separately via market ingestion
    sampleCount: n,
  };

  return { ...priors, [zip]: updated };
}

function estimatePredictedProfit(mao: number, arv: number, rehab: number): number {
  return arv * 0.70 - mao - rehab * 0.03; // rough wholesale profit estimate
}

function rollingAvg(current: number, newVal: number, n: number): number {
  return parseFloat(((current * (n - 1) + newVal) / n).toFixed(2));
}

function computeRollingMae(current: number | undefined, newError: number): number {
  if (current === undefined) return parseFloat(newError.toFixed(2));
  return parseFloat(((current * 0.9 + newError * 0.1)).toFixed(2));
}

function bumpVersion(version: string): string {
  const match = version.match(/^v(\d+)\.(\d+)\.(\d+)$/);
  if (!match) return version;
  const patch = parseInt(match[3], 10) + 1;
  return `v${match[1]}.${match[2]}.${patch}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
