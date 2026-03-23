/**
 * AMARA OS — Autonomous Deal Pipeline
 * Orchestrates: raw listings → normalize → distress → buyer → MAO → gate → close → store
 * AMARA runs this silently. Zero user intervention.
 */

import { CanonicalDeal, DistressSignals, BuyerLane, UnderwritingResult, CloseConfidence, emptyBuyerLane, emptyDistress, emptyCloseStrategy, emptyValuation, emptyUnderwriting } from "@/core/schema/canonical";
import { scoreDistress, passesDistressGate, DistressScoreInput } from "@/core/engines/distress/scorer";
import { matchBuyerLane, passesBuyerGate, BuyerMatchInput, BuyerMatchResult } from "@/core/engines/buyer/buyerMatcher";
import { calculateMAO, passesSpreadGate, MAOInput, MAOOutput } from "@/core/engines/mao/maoEngine";
import { runDealGate } from "@/core/deal/dealGate";
import { dealStore } from "@/lib/dealStore";
import { buildCloseStrategy } from "@/coaching/closerEngine";
import { v4 as uuid } from "uuid";

// ─────────────────────────────────────────────────────────────────────────────
// PIPELINE RESULT
// ─────────────────────────────────────────────────────────────────────────────
export interface PipelineResult {
  processed: number;
  qualified: number;
  rejected: number;
  rejectionReasons: Record<string, number>;
  deals: CanonicalDeal[];
  durationMs: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// MAP BuyerMatchResult → canonical BuyerLane
// ─────────────────────────────────────────────────────────────────────────────
function mapToBuyerLane(match: BuyerMatchResult): BuyerLane {
  const confidence: CloseConfidence =
    match.exitConfidenceScore >= 70 ? "HIGH" :
    match.exitConfidenceScore >= 40 ? "MEDIUM" : "LOW";

  return {
    buyerClass: match.buyerClass ?? "UNKNOWN",
    exitConfidence: confidence,
    exitConfidenceScore: match.exitConfidenceScore,
    matchedBuyerZIPs: match.matchedBuyerZIPs,
    matchedBuyerCount: match.matchedBuyerCount,
    topBuyerProfileIds: [],
    estimatedDaysToAssign: match.estimatedDaysToAssign,
    weeklyClosingPotential: match.weeklyClosingPotential,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// MAP MAOOutput → canonical UnderwritingResult
// ─────────────────────────────────────────────────────────────────────────────
function mapToUnderwriting(mao: MAOOutput): UnderwritingResult {
  return {
    dealType: mao.dealType,
    exitStrategy: mao.exitStrategy,
    buyerResaleMax: mao.buyerResaleMax,
    assignmentFee: mao.assignmentFee,
    mao: mao.mao,
    projectedSpread: mao.projectedSpread,
    projectedProfit: mao.projectedProfit,
    flipProfit: mao.flipProfit,
    flipROI: mao.flipROI,
    holdingCosts: mao.holdingCosts,
    closingCostsBuy: mao.closingCostsBuy,
    closingCostsSell: mao.closingCostsSell,
    flipperMarginTarget: mao.flipperMarginTarget,
    meetsMinimumFee: mao.meetsMinimumFee,
    feeSurplus: mao.feeSurplus,
    passesUnderwriting: mao.passesUnderwriting,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SINGLE DEAL PROCESSOR
// ─────────────────────────────────────────────────────────────────────────────
export async function processDeal(
  raw: Partial<CanonicalDeal>
): Promise<{ qualified: boolean; deal: CanonicalDeal; reason?: string }> {
  const now = new Date().toISOString();

  // Build base canonical deal with all required fields
  const deal: CanonicalDeal = {
    id: raw.id ?? uuid(),
    createdAt: raw.createdAt ?? now,
    updatedAt: now,
    lastScannedAt: now,
    sources: raw.sources ?? [],
    primarySource: raw.primarySource ?? "zillow",
    sourceConfidence: raw.sourceConfidence ?? "MEDIUM",
    sourceIds: raw.sourceIds ?? { zillow: null, propstream: null, propelio: null, public_records: null, xleads: null, manual: null },
    sourceUrls: raw.sourceUrls ?? {},
    address: raw.address ?? "",
    city: raw.city ?? "",
    state: raw.state ?? "",
    zip: raw.zip ?? "",
    county: raw.county ?? "",
    apn: raw.apn ?? null,
    lat: raw.lat ?? null,
    lng: raw.lng ?? null,
    market: raw.market ?? "",
    propertyType: raw.propertyType ?? "SFR",
    beds: raw.beds ?? null,
    baths: raw.baths ?? null,
    halfBaths: raw.halfBaths ?? null,
    livingAreaSqft: raw.livingAreaSqft ?? null,
    lotSizeSqft: raw.lotSizeSqft ?? null,
    lotSizeAcres: raw.lotSizeAcres ?? null,
    yearBuilt: raw.yearBuilt ?? null,
    stories: raw.stories ?? null,
    garage: raw.garage ?? null,
    pool: raw.pool ?? null,
    basement: raw.basement ?? null,
    ownerName: raw.ownerName ?? null,
    ownerMailingAddress: raw.ownerMailingAddress ?? null,
    ownerPhone: raw.ownerPhone ?? null,
    ownerEmail: raw.ownerEmail ?? null,
    ownershipYears: raw.ownershipYears ?? null,
    lastSaleDate: raw.lastSaleDate ?? null,
    lastSalePrice: raw.lastSalePrice ?? null,
    estimatedEquity: raw.estimatedEquity ?? null,
    estimatedEquityPct: raw.estimatedEquityPct ?? null,
    mortgageBalance: raw.mortgageBalance ?? null,
    occupancyStatus: raw.occupancyStatus ?? "UNKNOWN",
    listingStatus: raw.listingStatus ?? "ACTIVE",
    listPrice: raw.listPrice ?? null,
    originalListPrice: raw.originalListPrice ?? null,
    dom: raw.dom ?? null,
    cdom: raw.cdom ?? null,
    listingDate: raw.listingDate ?? null,
    listingAgent: raw.listingAgent ?? null,
    listingBrokerage: raw.listingBrokerage ?? null,
    mls: raw.mls ?? null,
    mlsId: raw.mlsId ?? null,
    remarks: raw.remarks ?? null,
    priceHistory: raw.priceHistory ?? [],
    valuation: raw.valuation ?? emptyValuation(),
    distress: raw.distress ?? emptyDistress(),
    underwriting: raw.underwriting ?? emptyUnderwriting(),
    buyerLane: raw.buyerLane ?? emptyBuyerLane(),
    closeStrategy: raw.closeStrategy ?? emptyCloseStrategy(),
    isQualifiedDeal: false,
    dealGateFailReasons: [],
    closeConfidence: "LOW",
    closeConfidenceScore: 0,
    nextAction: "",
    nextActionDueDate: null,
    accountabilityNote: null,
    dealLabel: "",
    urgencyFlag: null,
  } as CanonicalDeal;

  // ── STEP 1: DISTRESS SCORING ─────────────────────────────────────────────
  const priceReductionCount = deal.priceHistory?.filter(p => p.event === "REDUCED").length ?? 0;
  const priceReductionTotalPct =
    deal.originalListPrice && deal.listPrice && deal.originalListPrice > deal.listPrice
      ? (deal.originalListPrice - deal.listPrice) / deal.originalListPrice
      : 0;

  const distressInput: DistressScoreInput = {
    remarks: deal.remarks ?? null,
    dom: deal.dom ?? null,
    cdom: deal.cdom ?? null,
    priceReductionCount,
    priceReductionTotalPct,
    yearBuilt: deal.yearBuilt ?? null,
    absenteeOwner: deal.distress?.absenteeOwner,
    outOfStateOwner: deal.distress?.outOfStateOwner,
    corporateOwner: deal.distress?.corporateOwner,
    taxDelinquent: deal.distress?.taxDelinquent,
    preforeclosure: deal.distress?.preforeclosure,
    foreclosure: deal.distress?.foreclosure,
    auction: deal.distress?.auction,
    lis_pendens: deal.distress?.lis_pendens,
    probate: deal.distress?.probate,
    estate: deal.distress?.estate,
    inherited: deal.distress?.inherited,
    codeViolation: deal.distress?.codeViolation,
    vacancy: deal.distress?.vacancy,
    tenantOccupied: deal.distress?.tenantOccupied,
    liens: deal.distress?.liens,
  };

  const distressResult = scoreDistress(distressInput);
  deal.distress = distressResult;

  // Scan keywords for retail signal check
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { scanKeywords } = require("../engines/distress/keywords");
  const kwResult = scanKeywords(deal.remarks ?? "");

  const distressGate = passesDistressGate(distressResult, kwResult.hasRetailSignals);
  if (!distressGate.passes) {
    return { qualified: false, deal, reason: `distress gate: ${distressGate.reason}` };
  }

  // ── STEP 2: BUYER LANE MATCH ─────────────────────────────────────────────
  const isLand = deal.propertyType === "LAND";
  const rehabGrade = deal.valuation?.rehabGrade ?? "COSMETIC";

  const buyerInput: BuyerMatchInput = {
    zip: deal.zip,
    market: deal.market,
    state: deal.state,
    propertyType: deal.propertyType,
    listPrice: deal.listPrice,
    arvEstimate: deal.valuation?.arvEstimate ?? null,
    rehabGrade,
    distressScore: distressResult.totalDistressScore,
    isLand,
  };

  const buyerMatch: BuyerMatchResult = matchBuyerLane(buyerInput);
  deal.buyerLane = mapToBuyerLane(buyerMatch);

  const buyerGate = passesBuyerGate(buyerMatch);
  if (!buyerGate.passes) {
    return { qualified: false, deal, reason: `buyer gate: ${buyerGate.reason}` };
  }

  // ── STEP 3: MAO CALCULATION ──────────────────────────────────────────────
  const maoInput: MAOInput = {
    propertyType: deal.propertyType,
    isLand,
    arvEstimate: deal.valuation?.arvEstimate ?? null,
    avm: deal.valuation?.avm ?? null,
    listPrice: deal.listPrice,
    investorResaleEstimate: deal.valuation?.investorResaleEstimate ?? null,
    rehabEstimate: deal.valuation?.rehabEstimate ?? null,
    rehabGrade,
    lotSizeSqft: deal.lotSizeSqft ?? null,
    lotSizeAcres: deal.lotSizeAcres ?? null,
    zoning: null,
    subdivisionPotentialLots: null,
    finishedLotValueEach: deal.valuation?.finishedLotValue ?? null,
    market: deal.market,
    buyerClass: buyerMatch.buyerClass ?? "FLIPPER",
  };

  const maoOutput: MAOOutput = calculateMAO(maoInput);
  deal.underwriting = mapToUnderwriting(maoOutput);

  // ── STEP 4: DEAL GATE (all 4 gates) ─────────────────────────────────────
  const gateResult = runDealGate({
    distress: distressResult,
    buyerMatchResult: buyerMatch,
    maoOutput,
    propertyType: deal.propertyType,
    market: deal.market,
    zip: deal.zip,
    listPrice: deal.listPrice,
    remarks: deal.remarks,
  });

  deal.isQualifiedDeal = gateResult.qualifies;
  deal.dealGateFailReasons = gateResult.failedGates;
  deal.closeConfidenceScore = gateResult.closeConfidenceScore;
  deal.urgencyFlag = gateResult.urgencyFlag;
  deal.dealLabel = gateResult.dealLabel;

  const conf = gateResult.closeConfidenceScore;
  deal.closeConfidence = conf >= 70 ? "HIGH" : conf >= 40 ? "MEDIUM" : "LOW";

  if (!gateResult.qualifies) {
    return {
      qualified: false,
      deal,
      reason: gateResult.failedGates.join("; ") || "failed deal gate",
    };
  }

  // ── STEP 5: CLOSE STRATEGY ──────────────────────────────────────────────
  deal.closeStrategy = buildCloseStrategy({
    distress: distressResult,
    listPrice: deal.listPrice,
    mao: maoOutput.mao,
    assignmentFee: maoOutput.assignmentFee,
    dom: deal.dom ?? null,
    ownershipYears: deal.ownershipYears ?? null,
    occupancyStatus: deal.occupancyStatus,
    market: deal.market,
    propertyType: deal.propertyType,
    rehabGrade: deal.valuation?.rehabGrade ?? "COSMETIC",
  });

  // ── STEP 6: NEXT ACTION ──────────────────────────────────────────────────
  if (deal.urgencyFlag === "HOT") {
    deal.nextAction = "MAKE OFFER — HOT deal, call agent today";
    const due = new Date(Date.now() + 4 * 60 * 60 * 1000);
    deal.nextActionDueDate = due.toISOString();
  } else {
    deal.nextAction = "SUBMIT OFFER — set asking-price anchor, schedule walk";
    const due = new Date(Date.now() + 24 * 60 * 60 * 1000);
    deal.nextActionDueDate = due.toISOString();
  }

  return { qualified: true, deal };
}

// ─────────────────────────────────────────────────────────────────────────────
// BATCH PIPELINE — process multiple raw deals from any source
// ─────────────────────────────────────────────────────────────────────────────
export async function runPipeline(
  rawDeals: Partial<CanonicalDeal>[],
  options?: { market?: string; source?: string }
): Promise<PipelineResult> {
  const startTime = Date.now();
  const qualified: CanonicalDeal[] = [];
  const rejectionReasons: Record<string, number> = {};
  let rejected = 0;

  console.log(`[AMARA:Pipeline] Processing ${rawDeals.length} listings...`);

  for (const raw of rawDeals) {
    const tagged: Partial<CanonicalDeal> = {
      ...raw,
      market: raw.market || options?.market || "",
    };

    try {
      const result = await processDeal(tagged);

      if (result.qualified) {
        qualified.push(result.deal);
        dealStore.upsert(result.deal);
        console.log(
          `[AMARA:Pipeline] ✓ QUALIFIED: ${result.deal.address} | MAO: $${result.deal.underwriting?.mao?.toLocaleString() ?? 'N/A'} | Fee: $${result.deal.underwriting?.assignmentFee?.toLocaleString() ?? 'N/A'} | ${result.deal.urgencyFlag}`
        );
      } else {
        rejected++;
        const key = result.reason ?? "unknown";
        rejectionReasons[key] = (rejectionReasons[key] ?? 0) + 1;
      }
    } catch (err) {
      rejected++;
      const key = `error: ${(err as Error).message?.slice(0, 60) ?? "unknown"}`;
      rejectionReasons[key] = (rejectionReasons[key] ?? 0) + 1;
      console.error(`[AMARA:Pipeline] Error:`, err);
    }
  }

  console.log(`[AMARA:Pipeline] Complete: ${qualified.length} qualified, ${rejected} rejected in ${Date.now() - startTime}ms`);

  return {
    processed: rawDeals.length,
    qualified: qualified.length,
    rejected,
    rejectionReasons,
    deals: qualified,
    durationMs: Date.now() - startTime,
  };
}
