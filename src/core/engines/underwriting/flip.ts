/**
 * AMARA OS — Flip Underwriting Engine
 * Strategy B: Wholesale to a flipper
 * Logic: ARV → minus rehab → minus costs → minus flipper margin → minus fee → MAO
 */

export interface FlipInput {
  arvEstimate: number;
  rehabEstimate: number;
  listPrice: number | null;
}

export interface FlipOutput {
  strategy: "FLIP";
  arvUsed: number;
  rehabUsed: number;
  holdingCosts: number;
  closingCostsBuy: number;
  closingCostsSell: number;
  flipperMargin: number;            // flipper's profit target
  flipperMaxBuy: number;            // max the flipper will pay
  assignmentFee: number;
  mao: number;
  projectedSpread: number;
  flipProfit: number;               // flipper's net if they buy at MAO
  flipROI: number;
  meetsMinimumFee: boolean;
  feeSurplus: number;
  passesUnderwriting: boolean;
  rejectReason: string | null;
  calcBreakdown: string;
}

// Cost constants
const HOLDING_COST_PCT   = 0.04;    // 4% of ARV (6 months carry)
const CLOSING_BUY_PCT    = 0.01;    // 1% buy-side closing costs
const CLOSING_SELL_PCT   = 0.08;    // 8% sell-side (agent 6% + misc 2%)
const FLIPPER_MARGIN_PCT = 0.15;    // 15% net profit target for flipper
const MIN_ASSIGNMENT_FEE = 10_000;
const TRANSACTION_BUFFER = 5_000;   // flat buffer for title/misc

export function underwriteFlip(input: FlipInput): FlipOutput {
  const arv = input.arvEstimate;

  if (!arv || arv <= 0) {
    return failFlip("no ARV estimate — cannot underwrite flip");
  }
  if (!input.rehabEstimate || input.rehabEstimate <= 0) {
    return failFlip("no rehab estimate — cannot underwrite flip");
  }

  const rehab = input.rehabEstimate;
  const holdingCosts = Math.round(arv * HOLDING_COST_PCT);
  const closingBuy = Math.round(arv * CLOSING_BUY_PCT);
  const closingSell = Math.round(arv * CLOSING_SELL_PCT);
  const flipperMargin = Math.round(arv * FLIPPER_MARGIN_PCT);

  // Flipper max buy = ARV - rehab - all costs - profit target
  const flipperMaxBuy = arv - rehab - holdingCosts - closingBuy - closingSell - flipperMargin;

  if (flipperMaxBuy <= 0) {
    return failFlip("flipper max buy is negative — deal not viable");
  }

  // Our MAO = flipper max buy - our fee - buffer
  const assignmentFee = MIN_ASSIGNMENT_FEE;
  const mao = flipperMaxBuy - assignmentFee - TRANSACTION_BUFFER;

  if (mao <= 0) {
    return failFlip("MAO after fee and buffer is negative");
  }

  const projectedSpread = flipperMaxBuy - mao;
  const flipProfit = arv - rehab - holdingCosts - closingBuy - closingSell - flipperMaxBuy;
  const flipROI = flipProfit / (flipperMaxBuy + rehab + closingBuy);

  return {
    strategy: "FLIP",
    arvUsed: arv,
    rehabUsed: rehab,
    holdingCosts,
    closingCostsBuy: closingBuy,
    closingCostsSell: closingSell,
    flipperMargin,
    flipperMaxBuy,
    assignmentFee,
    mao,
    projectedSpread,
    flipProfit,
    flipROI,
    meetsMinimumFee: assignmentFee >= MIN_ASSIGNMENT_FEE,
    feeSurplus: assignmentFee - MIN_ASSIGNMENT_FEE,
    passesUnderwriting: mao > 0 && assignmentFee >= MIN_ASSIGNMENT_FEE,
    rejectReason: null,
    calcBreakdown: [
      `ARV:                   $${arv.toLocaleString()}`,
      `- Rehab:               $${rehab.toLocaleString()}`,
      `- Holding Costs (4%):  $${holdingCosts.toLocaleString()}`,
      `- Closing Buy (1%):    $${closingBuy.toLocaleString()}`,
      `- Closing Sell (8%):   $${closingSell.toLocaleString()}`,
      `- Flipper Margin (15%):$${flipperMargin.toLocaleString()}`,
      `= Flipper Max Buy:     $${flipperMaxBuy.toLocaleString()}`,
      `- Our Fee:             $${assignmentFee.toLocaleString()}`,
      `- Buffer:              $${TRANSACTION_BUFFER.toLocaleString()}`,
      `= MAO to Seller:       $${mao.toLocaleString()}`,
      `Flipper Net Profit:    $${flipProfit.toLocaleString()} (${Math.round(flipROI * 100)}% ROI)`,
    ].join("\n"),
  };
}

function failFlip(reason: string): FlipOutput {
  return {
    strategy: "FLIP",
    arvUsed: 0,
    rehabUsed: 0,
    holdingCosts: 0,
    closingCostsBuy: 0,
    closingCostsSell: 0,
    flipperMargin: 0,
    flipperMaxBuy: 0,
    assignmentFee: 0,
    mao: 0,
    projectedSpread: 0,
    flipProfit: 0,
    flipROI: 0,
    meetsMinimumFee: false,
    feeSurplus: 0,
    passesUnderwriting: false,
    rejectReason: reason,
    calcBreakdown: `FAIL: ${reason}`,
  };
}
