/**
 * AMARA OS — Distress Analysis Tool (Claude API Tool)
 */

import { scoreDistress } from "@/core/engines/distress/scorer";

export const distressToolDefinition = {
  name: "analyze_distress",
  description: "Scores a property for distress signals. Returns composite score 0-100 and breakdown. Score >= 25 passes the distress gate.",
  input_schema: {
    type: "object" as const,
    properties: {
      remarks: { type: "string", description: "Listing remarks / description text" },
      dom: { type: "number", description: "Days on market", nullable: true },
      cdom: { type: "number", description: "Cumulative days on market", nullable: true },
      priceReductionCount: { type: "number", description: "Number of price reductions" },
      priceReductionTotalPct: { type: "number", description: "Total price reduction as decimal (e.g. 0.15 = 15%)" },
      yearBuilt: { type: "number", description: "Year property was built", nullable: true },
      absenteeOwner: { type: "boolean" },
      outOfStateOwner: { type: "boolean" },
      taxDelinquent: { type: "boolean" },
      preforeclosure: { type: "boolean" },
      foreclosure: { type: "boolean" },
      probate: { type: "boolean" },
      estate: { type: "boolean" },
      vacancy: { type: "boolean" },
    },
    required: ["remarks"],
  },
};

export async function runDistressTool(input: {
  remarks: string;
  dom?: number | null;
  cdom?: number | null;
  priceReductionCount?: number;
  priceReductionTotalPct?: number;
  yearBuilt?: number | null;
  absenteeOwner?: boolean;
  outOfStateOwner?: boolean;
  taxDelinquent?: boolean;
  preforeclosure?: boolean;
  foreclosure?: boolean;
  probate?: boolean;
  estate?: boolean;
  vacancy?: boolean;
}) {
  const result = scoreDistress({
    remarks: input.remarks,
    dom: input.dom ?? null,
    cdom: input.cdom ?? null,
    priceReductionCount: input.priceReductionCount ?? 0,
    priceReductionTotalPct: input.priceReductionTotalPct ?? 0,
    yearBuilt: input.yearBuilt ?? null,
    absenteeOwner: input.absenteeOwner,
    outOfStateOwner: input.outOfStateOwner,
    taxDelinquent: input.taxDelinquent,
    preforeclosure: input.preforeclosure,
    foreclosure: input.foreclosure,
    probate: input.probate,
    estate: input.estate,
    vacancy: input.vacancy,
  });

  return JSON.stringify({
    totalDistressScore: result.totalDistressScore,
    passesGate: result.totalDistressScore >= 25,
    keywordsFound: result.distressKeywordsFound.slice(0, 10),
    keywordScore: result.keywordDistressScore,
    domBucket: result.domBucket,
    domDays: result.domDays,
    priceReduced: result.priceReduced,
    priceReductionCount: result.priceReductionCount,
    landlordFatigue: result.landlordFatigue,
    foreclosure: result.foreclosure,
    preforeclosure: result.preforeclosure,
    probate: result.probate,
    estate: result.estate,
    vacancy: result.vacancy,
  });
}
