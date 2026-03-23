/**
 * AMARA OS — MAO Engine (Maximum Allowable Offer)
 * Orchestrates the correct underwriting strategy and outputs final MAO.
 * Applies business rules — never recommend offers below minimum fee.
 */

import { CanonicalDeal, UnderwritingResult, DealType, ExitStrategy } from "@/core/schema/canonical";
import { underwriteWholesale } from "../underwriting/wholesale";
import { underwriteFlip } from "../underwriting/flip";
import { underwriteLand, LandInput } from "../underwriting/land";
import { estimateInvestorResaleFromARV } from "../comps/investorComps";

const MIN_FEE_SFR = 10_000;
const REHAB_GRADES = ["LIPSTICK", "COSMETIC", "MODERATE", "FULL_GUT"] as const;

export interface MAOInput {
  propertyType: string;
  isLand: boolean;
  arvEstimate: number | null;
  avm: number | null;
  listPrice: number | null;
  investorResaleEstimate: number | null;
  rehabEstimate: number | null;
  rehabGrade: string;
  lotSizeSqft: number | null;
  lotSizeAcres: number | null;
  zoning: string | null;
  subdivisionPotentialLots: number | null;
  finishedLotValueEach: number | null;
  market: string;
  // Buyer lane context
  buyerClass: string;
}

export interface MAOOutput {
  dealType: DealType;
  exitStrategy: ExitStrategy;
  mao: number | null;
  assignmentFee: number | null;
  buyerResaleMax: number | null;
  projectedSpread: number | null;
  projectedProfit: number | null;
  flipProfit: number | null;
  flipROI: number | null;
  holdingCosts: number | null;
  closingCostsBuy: number | null;
  closingCostsSell: number | null;
  flipperMarginTarget: number | null;
  meetsMinimumFee: boolean;
  feeSurplus: number | null;
  passesUnderwriting: boolean;
  rejectReason: string | null;
  calcBreakdown: string;
}

export function calculateMAO(input: MAOInput): MAOOutput {
  // ─── LAND PATH ───────────────────────────────────────────────────────────
  if (input.isLand || input.propertyType === "LAND" || input.propertyType === "LOT") {
    const landInput: LandInput = {
      lotSizeSqft: input.lotSizeSqft,
      lotSizeAcres: input.lotSizeAcres,
      zoning: input.zoning,
      frontageLinearFt: null,
      hasUtilities: null,
      floodZone: null,
      entitlementStage: null,
      subdivisionPotentialLots: input.subdivisionPotentialLots,
      finishedLotValueEach: input.finishedLotValueEach,
      listPrice: input.listPrice,
      arvIfSFR: input.arvEstimate,
      marketName: input.market,
    };
    const result = underwriteLand(landInput);
    return {
      dealType: "LAND_SUBDIVISION",
      exitStrategy: "ASSIGN_TO_DEVELOPER",
      mao: result.mao,
      assignmentFee: result.ourTargetFee,
      buyerResaleMax: result.developerMaxPay,
      projectedSpread: result.projectedSpread,
      projectedProfit: result.ourTargetFee,
      flipProfit: null,
      flipROI: null,
      holdingCosts: result.entitlementCarryCost,
      closingCostsBuy: null,
      closingCostsSell: null,
      flipperMarginTarget: null,
      meetsMinimumFee: result.passesUnderwriting,
      feeSurplus: result.ourTargetFee > 50_000 ? result.ourTargetFee - 50_000 : 0,
      passesUnderwriting: result.passesUnderwriting,
      rejectReason: result.rejectReason,
      calcBreakdown: result.calcBreakdown,
    };
  }

  // ─── SFR/MFR PATH — Choose best strategy ──────────────────────────────────
  // First, determine investor resale estimate if not provided
  let investorResale = input.investorResaleEstimate;
  if (!investorResale && input.arvEstimate) {
    const estimate = estimateInvestorResaleFromARV(input.arvEstimate, input.rehabGrade);
    investorResale = estimate.estimate;
  }

  // Try wholesale path first (fastest, preferred for weekly closings)
  if (investorResale && investorResale > 0) {
    const wsResult = underwriteWholesale({
      investorResaleEstimate: investorResale,
      arvEstimate: input.arvEstimate,
      listPrice: input.listPrice,
      isLand: false,
    });

    if (wsResult.passesUnderwriting) {
      return {
        dealType: "WHOLESALE_ASSIGNMENT",
        exitStrategy: input.buyerClass === "LANDLORD" ? "ASSIGN_TO_LANDLORD" : "ASSIGN_TO_FLIPPER",
        mao: wsResult.mao,
        assignmentFee: wsResult.assignmentFee,
        buyerResaleMax: wsResult.investorResaleUsed,
        projectedSpread: wsResult.projectedSpread,
        projectedProfit: wsResult.assignmentFee,
        flipProfit: null,
        flipROI: null,
        holdingCosts: null,
        closingCostsBuy: null,
        closingCostsSell: null,
        flipperMarginTarget: null,
        meetsMinimumFee: wsResult.meetsMinimumFee,
        feeSurplus: wsResult.feeSurplus,
        passesUnderwriting: true,
        rejectReason: null,
        calcBreakdown: wsResult.calcBreakdown,
      };
    }
  }

  // Try flip path if ARV and rehab are available
  if (input.arvEstimate && input.rehabEstimate) {
    const flipResult = underwriteFlip({
      arvEstimate: input.arvEstimate,
      rehabEstimate: input.rehabEstimate,
      listPrice: input.listPrice,
    });

    if (flipResult.passesUnderwriting) {
      return {
        dealType: "FLIP",
        exitStrategy: "ASSIGN_TO_FLIPPER",
        mao: flipResult.mao,
        assignmentFee: flipResult.assignmentFee,
        buyerResaleMax: flipResult.flipperMaxBuy,
        projectedSpread: flipResult.projectedSpread,
        projectedProfit: flipResult.assignmentFee,
        flipProfit: flipResult.flipProfit,
        flipROI: flipResult.flipROI,
        holdingCosts: flipResult.holdingCosts,
        closingCostsBuy: flipResult.closingCostsBuy,
        closingCostsSell: flipResult.closingCostsSell,
        flipperMarginTarget: flipResult.flipperMargin,
        meetsMinimumFee: flipResult.meetsMinimumFee,
        feeSurplus: flipResult.feeSurplus,
        passesUnderwriting: true,
        rejectReason: null,
        calcBreakdown: flipResult.calcBreakdown,
      };
    }
  }

  // No viable path
  return {
    dealType: "UNKNOWN",
    exitStrategy: "UNKNOWN",
    mao: null,
    assignmentFee: null,
    buyerResaleMax: null,
    projectedSpread: null,
    projectedProfit: null,
    flipProfit: null,
    flipROI: null,
    holdingCosts: null,
    closingCostsBuy: null,
    closingCostsSell: null,
    flipperMarginTarget: null,
    meetsMinimumFee: false,
    feeSurplus: null,
    passesUnderwriting: false,
    rejectReason: "insufficient valuation data to calculate MAO — need ARV or investor resale",
    calcBreakdown: "FAIL: no underwriting path available",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SPREAD GATE
// ─────────────────────────────────────────────────────────────────────────────
export function passesSpreadGate(
  maoResult: MAOOutput,
  listPrice: number | null
): { passes: boolean; reason: string } {
  if (!maoResult.passesUnderwriting) {
    return { passes: false, reason: maoResult.rejectReason ?? "underwriting failed" };
  }
  if (!maoResult.mao) {
    return { passes: false, reason: "no MAO calculated" };
  }
  if (!maoResult.meetsMinimumFee) {
    return { passes: false, reason: `below minimum fee floor — need $${MIN_FEE_SFR.toLocaleString()}+` };
  }
  // If list price known and above MAO — still surface it, but note the gap
  return { passes: true, reason: "" };
}
