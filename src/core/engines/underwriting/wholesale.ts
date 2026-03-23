/**
 * AMARA OS — Wholesale Underwriting Engine
 * Strategy A: Quick assignment to end buyer
 * Logic: buyer resale max → minus fee → minus buffer → MAO
 *
 * RULE: Minimum assignment fee = $10,000 for SFR/normal deals
 */

export interface WholesaleInput {
  investorResaleEstimate: number;   // what buyer will pay (investor resale price)
  arvEstimate: number | null;
  listPrice: number | null;
  isLand: boolean;
}

export interface WholesaleOutput {
  strategy: "WHOLESALE_ASSIGNMENT";
  investorResaleUsed: number;
  transactionBuffer: number;        // friction / slippage / error margin
  safetyMargin: number;             // seller-side safety
  assignmentFee: number;
  mao: number;
  projectedSpread: number;
  meetsMinimumFee: boolean;
  feeSurplus: number;
  passesUnderwriting: boolean;
  rejectReason: string | null;
  calcBreakdown: string;
}

const MIN_ASSIGNMENT_FEE_SFR = 10_000;
const TRANSACTION_BUFFER_PCT = 0.02;  // 2% friction / slippage
const SAFETY_MARGIN_PCT = 0.03;       // 3% seller-side safety

export function underwriteWholesale(input: WholesaleInput): WholesaleOutput {
  const resale = input.investorResaleEstimate;

  if (!resale || resale <= 0) {
    return failWholesale("no investor resale estimate — cannot underwrite");
  }

  const transactionBuffer = Math.round(resale * TRANSACTION_BUFFER_PCT);
  const safetyMargin = Math.round(resale * SAFETY_MARGIN_PCT);
  const assignmentFee = MIN_ASSIGNMENT_FEE_SFR;
  const mao = resale - assignmentFee - transactionBuffer - safetyMargin;
  const projectedSpread = resale - mao;

  if (mao <= 0) {
    return failWholesale(`MAO is negative ($${mao}) — deal not viable at minimum fee`);
  }

  const feeSurplus = assignmentFee - MIN_ASSIGNMENT_FEE_SFR;
  const meetsMinimumFee = assignmentFee >= MIN_ASSIGNMENT_FEE_SFR;

  // Sanity: MAO should not exceed 85% of resale (leave room for buyer profit)
  const maoAsPctResale = mao / resale;
  if (maoAsPctResale > 0.85) {
    return failWholesale(`MAO is ${Math.round(maoAsPctResale * 100)}% of investor resale — too tight, no room for buyer margin`);
  }

  // If list price is known, check spread is real
  if (input.listPrice && input.listPrice < mao) {
    // Listed below our MAO — this is a potential deal, great signal
    // (seller already priced at or below our MAO)
  }

  return {
    strategy: "WHOLESALE_ASSIGNMENT",
    investorResaleUsed: resale,
    transactionBuffer,
    safetyMargin,
    assignmentFee,
    mao,
    projectedSpread,
    meetsMinimumFee,
    feeSurplus,
    passesUnderwriting: meetsMinimumFee,
    rejectReason: null,
    calcBreakdown: [
      `Investor Resale:   $${resale.toLocaleString()}`,
      `- Assignment Fee:  $${assignmentFee.toLocaleString()}`,
      `- Buffer (2%):     $${transactionBuffer.toLocaleString()}`,
      `- Safety (3%):     $${safetyMargin.toLocaleString()}`,
      `= MAO to Seller:   $${mao.toLocaleString()}`,
      `Spread:            $${projectedSpread.toLocaleString()}`,
    ].join("\n"),
  };
}

function failWholesale(reason: string): WholesaleOutput {
  return {
    strategy: "WHOLESALE_ASSIGNMENT",
    investorResaleUsed: 0,
    transactionBuffer: 0,
    safetyMargin: 0,
    assignmentFee: 0,
    mao: 0,
    projectedSpread: 0,
    meetsMinimumFee: false,
    feeSurplus: 0,
    passesUnderwriting: false,
    rejectReason: reason,
    calcBreakdown: `FAIL: ${reason}`,
  };
}
