/**
 * AMARA OS — Deal Gate
 * The final qualification filter before a deal surfaces on Mission Control.
 * If it fails any gate, it is silently discarded. AMARA watches so you don't.
 *
 * Gates (in order):
 * 1. Buyer Gate    — no exit path = no deal
 * 2. Distress Gate — no distress = no deal
 * 3. Spread Gate   — no viable MAO = no deal
 * 4. Action Gate   — no clear next action = no deal
 */

import { CanonicalDeal } from "@/core/schema/canonical";
import { passesDistressGate } from "../engines/distress/scorer";
import { passesBuyerGate, BuyerMatchResult } from "../engines/buyer/buyerMatcher";
import { passesSpreadGate, MAOOutput } from "../engines/mao/maoEngine";

export interface DealGateResult {
  qualifies: boolean;
  failedGates: string[];
  passedGates: string[];
  closeConfidenceScore: number;
  urgencyFlag: CanonicalDeal["urgencyFlag"];
  dealLabel: string;
}

export function runDealGate(deal: {
  distress: CanonicalDeal["distress"];
  buyerMatchResult: BuyerMatchResult;
  maoOutput: MAOOutput;
  propertyType: string;
  market: string;
  zip: string;
  listPrice: number | null;
  remarks: string | null;
}): DealGateResult {
  const failedGates: string[] = [];
  const passedGates: string[] = [];

  // ── Gate 1: Buyer ──────────────────────────────────────────────────────────
  const buyerCheck = passesBuyerGate(deal.buyerMatchResult);
  if (!buyerCheck.passes) {
    failedGates.push(`BUYER_GATE: ${buyerCheck.reason}`);
  } else {
    passedGates.push("BUYER_GATE");
  }

  // ── Gate 2: Distress ───────────────────────────────────────────────────────
  const { scanKeywords } = require("../engines/distress/keywords");
  const kwResult = scanKeywords(deal.remarks ?? "");
  const distressCheck = passesDistressGate(deal.distress, kwResult.hasRetailSignals);
  if (!distressCheck.passes) {
    failedGates.push(`DISTRESS_GATE: ${distressCheck.reason}`);
  } else {
    passedGates.push("DISTRESS_GATE");
  }

  // ── Gate 3: Spread / MAO ───────────────────────────────────────────────────
  const spreadCheck = passesSpreadGate(deal.maoOutput, deal.listPrice);
  if (!spreadCheck.passes) {
    failedGates.push(`SPREAD_GATE: ${spreadCheck.reason}`);
  } else {
    passedGates.push("SPREAD_GATE");
  }

  // ── Gate 4: Action Gate ────────────────────────────────────────────────────
  // Must have at least a buyer lane and MAO to have an actionable next step
  const hasAction =
    deal.buyerMatchResult.matched &&
    deal.maoOutput.mao !== null &&
    deal.maoOutput.mao > 0;
  if (!hasAction) {
    failedGates.push("ACTION_GATE: no clear next action — missing buyer or MAO");
  } else {
    passedGates.push("ACTION_GATE");
  }

  const qualifies = failedGates.length === 0;

  // ── Confidence Score ───────────────────────────────────────────────────────
  let score = 0;
  if (qualifies) {
    score += deal.distress.totalDistressScore * 0.25;         // 25% distress
    score += deal.buyerMatchResult.exitConfidenceScore * 0.40; // 40% exit certainty
    // Spread quality
    const spread = deal.maoOutput.projectedSpread ?? 0;
    const spreadScore = Math.min(35, (spread / 1000) * 1.2);
    score += spreadScore * 0.35;
  }

  // ── Urgency Flag ───────────────────────────────────────────────────────────
  let urgencyFlag: CanonicalDeal["urgencyFlag"] = null;
  if (qualifies) {
    if (deal.distress.domBucket === "FRESH" && deal.distress.totalDistressScore >= 50) {
      urgencyFlag = "HOT";
    } else if (deal.distress.totalDistressScore >= 35) {
      urgencyFlag = "WARM";
    }
  }

  // ── Deal Label ────────────────────────────────────────────────────────────
  let dealLabel = "";
  if (qualifies) {
    const type = deal.maoOutput.dealType.replace("_", " ");
    const spread = deal.maoOutput.projectedSpread
      ? `$${Math.round(deal.maoOutput.projectedSpread / 1000)}K SPREAD`
      : "";
    dealLabel = `${type} — ${deal.market} — ${spread}`.toUpperCase();
  }

  return {
    qualifies,
    failedGates,
    passedGates,
    closeConfidenceScore: Math.min(100, Math.round(score)),
    urgencyFlag,
    dealLabel,
  };
}
