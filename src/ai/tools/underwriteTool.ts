/**
 * AMARA OS — Underwriting Tool (Claude API Tool)
 */

import { calculateMAO } from "@/core/engines/mao/maoEngine";
import type { MAOInput } from "@/core/engines/mao/maoEngine";

export const underwriteToolDefinition = {
  name: "underwrite_deal",
  description: "Calculates MAO (Maximum Allowable Offer) across wholesale, flip, and land paths. Returns the best strategy and fee. $10K minimum fee required for SFR. $50K minimum for land.",
  input_schema: {
    type: "object" as const,
    properties: {
      propertyType: { type: "string", description: "SFR, MFR, CONDO, LAND, etc." },
      isLand: { type: "boolean", description: "Is this a land/lot deal?" },
      listPrice: { type: "number", description: "Current list price", nullable: true },
      arvEstimate: { type: "number", description: "After-repair value estimate (for flip path)", nullable: true },
      avm: { type: "number", description: "AVM / Zestimate", nullable: true },
      investorResaleEstimate: { type: "number", description: "What an investor/landlord would pay as-is", nullable: true },
      rehabEstimate: { type: "number", description: "Rehab cost estimate", nullable: true },
      rehabGrade: { type: "string", description: "LIPSTICK, COSMETIC, MODERATE, FULL_GUT" },
      market: { type: "string", description: "Market ID (e.g. 'dfw')" },
      buyerClass: { type: "string", description: "LANDLORD, FLIPPER, DEVELOPER, etc." },
    },
    required: ["propertyType", "isLand", "market", "buyerClass"],
  },
};

export async function runUnderwriteTool(input: {
  propertyType: string;
  isLand: boolean;
  listPrice?: number | null;
  arvEstimate?: number | null;
  avm?: number | null;
  investorResaleEstimate?: number | null;
  rehabEstimate?: number | null;
  rehabGrade?: string;
  market: string;
  buyerClass: string;
}) {
  const maoInput: MAOInput = {
    propertyType: input.propertyType,
    isLand: input.isLand,
    listPrice: input.listPrice ?? null,
    arvEstimate: input.arvEstimate ?? null,
    avm: input.avm ?? null,
    investorResaleEstimate: input.investorResaleEstimate ?? null,
    rehabEstimate: input.rehabEstimate ?? null,
    rehabGrade: input.rehabGrade ?? "COSMETIC",
    lotSizeSqft: null,
    lotSizeAcres: null,
    zoning: null,
    subdivisionPotentialLots: null,
    finishedLotValueEach: null,
    market: input.market,
    buyerClass: input.buyerClass,
  };

  const result = calculateMAO(maoInput);

  return JSON.stringify({
    dealType: result.dealType,
    exitStrategy: result.exitStrategy,
    mao: result.mao,
    assignmentFee: result.assignmentFee,
    buyerResaleMax: result.buyerResaleMax,
    projectedSpread: result.projectedSpread,
    meetsMinimumFee: result.meetsMinimumFee,
    passesUnderwriting: result.passesUnderwriting,
    rejectReason: result.rejectReason,
    calcBreakdown: result.calcBreakdown,
  });
}
