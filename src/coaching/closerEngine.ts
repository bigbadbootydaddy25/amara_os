/**
 * AMARA OS — Closer Engine
 * Coaches you like an elite acquisitions manager.
 * Reads the seller, builds the angle, frames the deal.
 * Harvey Specter plays the man, not the hand. AMARA does the same.
 */

import { DistressSignals, CloseStrategy } from "@/core/schema/canonical";

export interface CloserInput {
  distress: DistressSignals;
  listPrice: number | null;
  mao: number | null;
  assignmentFee: number | null;
  dom: number | null;
  ownershipYears: number | null;
  occupancyStatus: string;
  market: string;
  propertyType: string;
  rehabGrade: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// PAIN PROFILE MAPPING
// ─────────────────────────────────────────────────────────────────────────────
function detectPainProfile(distress: DistressSignals): {
  profile: string;
  likelyMotivation: string;
  urgencyLevel: "HIGH" | "MEDIUM" | "LOW";
} {
  if (distress.probate || distress.estate || distress.inherited) {
    return {
      profile: "ESTATE / INHERITED",
      likelyMotivation: "Heirs want to liquidate without managing a property. Decision-making may involve multiple parties. Emotional attachment to family home. Relief value is high.",
      urgencyLevel: "MEDIUM",
    };
  }
  if (distress.foreclosure || distress.lis_pendens || distress.preforeclosure) {
    return {
      profile: "FINANCIAL DISTRESS / FORECLOSURE",
      likelyMotivation: "Seller is facing credit damage and timeline pressure. They need out fast. Any deal that stops the bleeding wins.",
      urgencyLevel: "HIGH",
    };
  }
  if (distress.taxDelinquent) {
    return {
      profile: "TAX DELINQUENT / FINANCIAL OVERLOAD",
      likelyMotivation: "Carrying a debt they cannot resolve. Anxiety around accumulating penalties. Looking for clean exit with zero hassle.",
      urgencyLevel: "HIGH",
    };
  }
  if (distress.landlordFatigue || distress.tenantOccupied) {
    return {
      profile: "LANDLORD FATIGUE",
      likelyMotivation: "Tired of managing the property, tenant headaches, or vacancy. Absentee owner who checked out mentally long before listing.",
      urgencyLevel: "MEDIUM",
    };
  }
  if (distress.vacancy) {
    return {
      profile: "VACANT / BLEEDING CARRYING COSTS",
      likelyMotivation: "Empty property is eating money every month. Seller wants to stop the drain. Cash certainty > price.",
      urgencyLevel: "HIGH",
    };
  }
  if (distress.priceReduced && distress.domDays >= 60) {
    return {
      profile: "PRICE-CHASING / MARKET FATIGUE",
      likelyMotivation: "Already shown willingness to reduce. Market validated their price is too high. Ready for a real conversation.",
      urgencyLevel: "MEDIUM",
    };
  }
  return {
    profile: "MOTIVATED SELLER — GENERAL",
    likelyMotivation: "Distress signals present. Seller is motivated but exact pain point unclear. Lead with empathy and uncover the real reason.",
    urgencyLevel: "LOW",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// NEGOTIATION ANGLE BUILDER
// ─────────────────────────────────────────────────────────────────────────────
function buildNegotiationAngle(
  profile: string,
  mao: number | null,
  listPrice: number | null,
  dom: number | null
): string {
  const gap = listPrice && mao ? listPrice - mao : null;
  const gapPct = gap && listPrice ? Math.round((gap / listPrice) * 100) : null;

  if (profile.includes("ESTATE")) {
    return `Lead with empathy. Acknowledge the loss. Position yourself as the easiest exit — no showings, no repairs, no waiting. The value you offer isn't the price, it's the peace.`;
  }
  if (profile.includes("FORECLOSURE")) {
    return `Time is your leverage — but never say it cruelly. Say: "I can close in 10 days and stop the process. What matters most to you right now — the number or the speed?" Let them choose.`;
  }
  if (profile.includes("LANDLORD")) {
    return `You are buying their headache. Don't frame it as a low offer — frame it as: "You keep the tenant, the repairs, and the liability — OR you walk away with cash tomorrow." Make the problem vivid, not the price.`;
  }
  if (profile.includes("VACANT")) {
    return `Ask them how much the vacant property has cost them so far. Let the number sit. Then say: "I can end that today."`;
  }
  if (profile.includes("PRICE-CHASING") && dom && dom >= 60) {
    return `The market already told them something. You're confirming it, not insulting them. Say: "You've been incredibly patient. What the market is saying is that cash buyers at this price don't exist right now — but I'm here, and I can close."`;
  }
  return `Lead with certainty. You're not negotiating price — you're offering a different kind of value: certainty, speed, no-contingency cash close. Price is just one axis. When they push back on price, reframe to: "What does closing fast mean for you?"`;
}

// ─────────────────────────────────────────────────────────────────────────────
// OPENING APPROACH
// ─────────────────────────────────────────────────────────────────────────────
function buildOpeningApproach(distress: DistressSignals, mao: number | null): string {
  if (distress.foreclosure || distress.lis_pendens) {
    return `Open with a brief, calm acknowledgment of their situation. No pity. No pressure. Say: "I saw the property. I do cash deals. If you want to talk through your options, I'm available today." Less is more.`;
  }
  if (distress.estate || distress.probate) {
    return `Open by acknowledging the process is difficult. Say: "I understand there may be multiple people involved. My offer is simple — as-is, cash, you pick the close date. I make it easy."`;
  }
  return `Don't open with price. Open with certainty: "I'm a cash buyer. I close fast, no contingencies, no repairs required. I've seen the property — can we talk today?"`;
}

// ─────────────────────────────────────────────────────────────────────────────
// OBJECTION RESPONSE
// ─────────────────────────────────────────────────────────────────────────────
function buildObjectionResponse(
  profile: string,
  listPrice: number | null,
  mao: number | null
): string {
  const gapStr = listPrice && mao ? `$${Math.round((listPrice - mao) / 1000)}K` : "the gap";
  return `When they say "that's too low": Don't apologize. Don't justify. Ask: "What would it take for you to feel good about this?" Let them anchor down. Most sellers come down significantly when given the chance to talk. If they stay firm above your MAO, simply say: "I understand. My number works for me. If you ever want to revisit, I'll be here." Walk with frame. Never beg.`;
}

// ─────────────────────────────────────────────────────────────────────────────
// FOLLOW-UP SCHEDULE
// ─────────────────────────────────────────────────────────────────────────────
function buildFollowUpSchedule(urgencyLevel: "HIGH" | "MEDIUM" | "LOW"): string {
  if (urgencyLevel === "HIGH") {
    return "Day 0: First contact. Day 2: Follow-up call. Day 5: Written offer. Day 7: Final check-in before walking. Move fast — this has a timeline.";
  }
  if (urgencyLevel === "MEDIUM") {
    return "Day 0: First contact. Day 3: Follow-up. Day 7: Second follow-up. Day 14: Written offer. Day 21: Final check. Mark calendar. Don't let this go cold.";
  }
  return "Week 1: First contact. Week 2: Follow-up. Week 4: Check-in. Month 2: Re-engage. These sellers often move slowly — stay in the rotation without chasing.";
}

// ─────────────────────────────────────────────────────────────────────────────
// WALK-AWAY TRIGGER
// ─────────────────────────────────────────────────────────────────────────────
function buildWalkAwayTrigger(mao: number | null, listPrice: number | null): string {
  if (!mao) return "No MAO calculated. Do not make an offer without underwriting.";
  if (listPrice && listPrice <= mao) {
    return `Seller is already priced at or below your MAO ($${mao.toLocaleString()}). Buy it now. Don't renegotiate down — you're already at or under the number.`;
  }
  return `Walk if they won't move to within 10% of your MAO ($${mao.toLocaleString()}) after two conversations. You have 37 markets. Your energy is an asset — protect it.`;
}

// ─────────────────────────────────────────────────────────────────────────────
// COACHING NOTE
// ─────────────────────────────────────────────────────────────────────────────
function buildCoachingNote(distress: DistressSignals, urgencyLevel: string): string {
  if (distress.totalDistressScore >= 60) {
    return "HIGH DISTRESS DEAL — Move on this TODAY. Distress this deep means a motivated seller. Don't let analysis paralysis cost you a closing. Pick up the phone.";
  }
  if (distress.totalDistressScore >= 40) {
    return "SOLID DEAL — Make contact within 24 hours. Get the seller talking. Your job is to uncover what they REALLY need.";
  }
  return "DECENT LEAD — Qualify the motivation fast. Don't invest more than one call until you confirm they're ready to sell at the right number.";
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN CLOSER ENGINE
// ─────────────────────────────────────────────────────────────────────────────
export function buildCloseStrategy(input: CloserInput): CloseStrategy {
  const { profile, likelyMotivation, urgencyLevel } = detectPainProfile(input.distress);

  return {
    sellerPainProfile: profile,
    likelyMotivation,
    negotiationAngle: buildNegotiationAngle(profile, input.mao, input.listPrice, input.dom),
    openingApproach: buildOpeningApproach(input.distress, input.mao),
    anchorPriceLogic: input.mao
      ? `Your anchor is $${input.mao.toLocaleString()}. Never open above this. If forced to counter up, move in $2,000–$5,000 increments only. Each concession must extract a reciprocal commitment from the seller.`
      : "No MAO set — do not make an offer until underwriting is complete.",
    objectionResponse: buildObjectionResponse(profile, input.listPrice, input.mao),
    followUpSchedule: buildFollowUpSchedule(urgencyLevel),
    walkAwayTrigger: buildWalkAwayTrigger(input.mao, input.listPrice),
    coachingNote: buildCoachingNote(input.distress, urgencyLevel),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// NEXT ACTION BUILDER
// ─────────────────────────────────────────────────────────────────────────────
export function buildNextAction(
  listPrice: number | null,
  mao: number | null,
  distressScore: number,
  buyerConfidence: number,
  dom: number | null
): { action: string; dueDate: string } {
  const now = new Date();

  if (listPrice && mao && listPrice <= mao * 1.05) {
    const due = new Date(now.getTime() + 4 * 3600000); // 4 hours
    return {
      action: "URGENT: List price is at or below MAO. Call seller NOW and lock up contract.",
      dueDate: due.toISOString(),
    };
  }

  if (distressScore >= 50 || dom && dom >= 90) {
    const due = new Date(now.getTime() + 24 * 3600000); // 24 hours
    return {
      action: "HIGH PRIORITY: Call seller within 24 hours. Distress and DOM indicate high motivation. Get on the phone.",
      dueDate: due.toISOString(),
    };
  }

  const due = new Date(now.getTime() + 48 * 3600000); // 48 hours
  return {
    action: "Make first contact within 48 hours. Run comps, confirm buyer lane, then present verbal offer.",
    dueDate: due.toISOString(),
  };
}
