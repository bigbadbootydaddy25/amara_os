import type {
  MiroFishFeatures,
  ScenarioOutput,
  ScenarioType,
  DealStrategy,
} from '../../types.js';

interface ScenarioParams {
  arvMultiplier: number;         // applied to arvMidpoint
  rehabMultiplier: number;       // applied to rehabRisk component
  domMultiplier: number;         // applied to exitVelocity
  discountFloor: number;         // minimum discount depth required
  assignFeeRange: [number, number];
  riskAdjustment: number;        // additive to base risk
}

const SCENARIO_PARAMS: Record<ScenarioType, ScenarioParams> = {
  conservative: {
    arvMultiplier: 0.93,
    rehabMultiplier: 1.25,
    domMultiplier: 1.40,
    discountFloor: 0.30,
    assignFeeRange: [5_000, 10_000],
    riskAdjustment: 0.15,
  },
  base: {
    arvMultiplier: 1.00,
    rehabMultiplier: 1.00,
    domMultiplier: 1.00,
    discountFloor: 0.20,
    assignFeeRange: [10_000, 20_000],
    riskAdjustment: 0,
  },
  aggressive: {
    arvMultiplier: 1.07,
    rehabMultiplier: 0.85,
    domMultiplier: 0.70,
    discountFloor: 0.15,
    assignFeeRange: [15_000, 35_000],
    riskAdjustment: -0.10,
  },
};

const FLIP_CARRY_COST_PCT = 0.04;      // 4% of ARV for holding costs
const CLOSING_COST_PCT = 0.03;         // 3% of ARV
const WHOLESALE_MARGIN = 0.70;         // max 70% ARV for wholesale MAO

export function runScenario(
  features: MiroFishFeatures,
  scenarioType: ScenarioType,
): ScenarioOutput {
  const params = SCENARIO_PARAMS[scenarioType];

  const arv = features.arvMidpoint * params.arvMultiplier;
  const rehab = features.rehabRisk * arv * params.rehabMultiplier;
  const exitDays = Math.round(features.exitVelocity * params.domMultiplier);

  const strategy = selectStrategy(features, scenarioType);
  const mao = computeMao(arv, rehab, exitDays, strategy, params);
  const assignFee = midpoint(params.assignFeeRange);
  const netProfit = computeProfit(arv, mao, rehab, exitDays, strategy, assignFee);

  const roiMin = mao > 0 ? (netProfit * 0.80) / mao : 0;
  const roiMax = mao > 0 ? (netProfit * 1.20) / mao : 0;

  const riskScore = computeRiskScore(features, params);

  const reasoning = buildReasoning(
    scenarioType,
    arv,
    mao,
    rehab,
    netProfit,
    exitDays,
    strategy,
    riskScore,
  );

  return {
    scenario: scenarioType,
    mao: Math.round(mao / 500) * 500,
    roiMin: parseFloat(roiMin.toFixed(4)),
    roiMax: parseFloat(roiMax.toFixed(4)),
    netProfit: Math.round(netProfit),
    exitDays,
    riskScore: parseFloat(Math.min(1, Math.max(0, riskScore)).toFixed(4)),
    strategy,
    reasoning,
  };
}

function selectStrategy(
  features: MiroFishFeatures,
  scenario: ScenarioType,
): DealStrategy {
  const { discountDepth, rehabRisk, assignmentProbability, marketRegime } = features;

  // Thin margin → wholesale only
  if (discountDepth < 0.15 || scenario === 'conservative') return 'wholesale';

  // High rehab + good discount + hot market → BRRRR candidate
  if (rehabRisk > 0.15 && discountDepth > 0.35 && marketRegime !== 'cold') return 'brrrr';

  // Strong assignment probability → wholesale
  if (assignmentProbability > 0.70) return 'wholesale';

  // Moderate discount + rehabable → flip
  if (discountDepth > 0.25 && rehabRisk < 0.20) return 'flip';

  return 'wholesale';
}

function computeMao(
  arv: number,
  rehab: number,
  exitDays: number,
  strategy: DealStrategy,
  params: ScenarioParams,
): number {
  const closingCosts = arv * CLOSING_COST_PCT;

  if (strategy === 'wholesale') {
    return Math.max(0, arv * WHOLESALE_MARGIN - rehab - closingCosts);
  }

  if (strategy === 'flip') {
    const holdingCost = arv * FLIP_CARRY_COST_PCT * (exitDays / 30);
    const flipMargin = arv * 0.15; // target 15% profit
    return Math.max(0, arv - rehab - holdingCost - closingCosts * 2 - flipMargin);
  }

  if (strategy === 'brrrr') {
    const afterRepairRefinance = arv * 0.75;
    const targetEquity = arv * 0.20;
    return Math.max(0, afterRepairRefinance - rehab - targetEquity - closingCosts);
  }

  // Fallback: conservative wholesale
  return Math.max(0, arv * 0.65 - rehab - closingCosts);
}

function computeProfit(
  arv: number,
  mao: number,
  rehab: number,
  exitDays: number,
  strategy: DealStrategy,
  assignFee: number,
): number {
  if (strategy === 'wholesale') {
    return assignFee;
  }

  if (strategy === 'flip') {
    const holdingCost = arv * FLIP_CARRY_COST_PCT * (exitDays / 30);
    const closingCosts = arv * CLOSING_COST_PCT * 2;
    return arv - mao - rehab - holdingCost - closingCosts;
  }

  // BRRRR: equity capture after refinance
  return arv * 0.20;
}

function computeRiskScore(
  features: MiroFishFeatures,
  params: ScenarioParams,
): number {
  const base =
    features.rehabRisk * 0.30 +
    (1 - features.liquidityScore) * 0.25 +
    (1 - features.buyerDemandHeat) * 0.20 +
    (1 - features.discountDepth) * 0.15 +
    (1 - features.assignmentProbability) * 0.10;

  return base + params.riskAdjustment;
}

function buildReasoning(
  scenario: ScenarioType,
  arv: number,
  mao: number,
  rehab: number,
  profit: number,
  exitDays: number,
  strategy: DealStrategy,
  risk: number,
): string {
  const pctArv = arv > 0 ? ((mao / arv) * 100).toFixed(1) : '0';
  return [
    `[${scenario.toUpperCase()}] Strategy: ${strategy}.`,
    `ARV: $${fmt(arv)} | MAO: $${fmt(mao)} (${pctArv}% of ARV) | Rehab: $${fmt(rehab)}.`,
    `Projected net profit: $${fmt(profit)} | Exit: ~${exitDays} days | Risk: ${(risk * 100).toFixed(0)}%.`,
  ].join(' ');
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function midpoint([lo, hi]: [number, number]): number {
  return (lo + hi) / 2;
}
