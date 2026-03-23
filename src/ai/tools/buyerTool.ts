/**
 * AMARA OS — Buyer Lane Match Tool (Claude API Tool)
 */

import { matchBuyerLane, passesBuyerGate } from "@/core/engines/buyer/buyerMatcher";

export const buyerToolDefinition = {
  name: "match_buyer_lane",
  description: "Matches a property against active exit buyer lanes. Returns buyer match including exit confidence score and weekly closing potential. Score >= 20 + hasMatch = passes buyer gate.",
  input_schema: {
    type: "object" as const,
    properties: {
      zip: { type: "string", description: "Property ZIP code" },
      market: { type: "string", description: "Market ID (e.g. 'dfw', 'atlanta')" },
      state: { type: "string", description: "State abbreviation (e.g. 'TX', 'GA')" },
      propertyType: { type: "string", description: "SFR, MFR, CONDO, LAND, etc." },
      listPrice: { type: "number", description: "Current list price", nullable: true },
      arvEstimate: { type: "number", description: "After-repair value estimate", nullable: true },
      rehabGrade: { type: "string", description: "LIPSTICK, COSMETIC, MODERATE, FULL_GUT" },
      distressScore: { type: "number", description: "Distress score 0-100" },
      isLand: { type: "boolean", description: "Is this a land/lot deal?" },
    },
    required: ["zip", "market", "state", "propertyType", "distressScore", "isLand"],
  },
};

export async function runBuyerTool(input: {
  zip: string;
  market: string;
  state: string;
  propertyType: string;
  listPrice?: number | null;
  arvEstimate?: number | null;
  rehabGrade?: string;
  distressScore: number;
  isLand: boolean;
}) {
  const result = matchBuyerLane({
    zip: input.zip,
    market: input.market,
    state: input.state,
    propertyType: input.propertyType,
    listPrice: input.listPrice ?? null,
    arvEstimate: input.arvEstimate ?? null,
    rehabGrade: input.rehabGrade ?? "COSMETIC",
    distressScore: input.distressScore,
    isLand: input.isLand,
  });

  const buyerGate = passesBuyerGate(result);

  return JSON.stringify({
    matched: result.matched,
    buyerClass: result.buyerClass,
    exitConfidenceScore: result.exitConfidenceScore,
    matchedBuyerCount: result.matchedBuyerCount,
    matchedBuyerZIPs: result.matchedBuyerZIPs,
    estimatedDaysToAssign: result.estimatedDaysToAssign,
    weeklyClosingPotential: result.weeklyClosingPotential,
    reasoning: result.reasoning,
    passesBuyerGate: buyerGate.passes,
    buyerGateReason: buyerGate.reason,
  });
}
