/**
 * AMARA OS — Distress Keyword Engine
 * Maps keywords from listing remarks / descriptions to distress signals.
 * Each keyword has a weight. Total score 0–100.
 */

export interface KeywordRule {
  pattern: RegExp;
  label: string;
  weight: number;          // 1–20 contribution to distress score
  category: KeywordCategory;
}

export type KeywordCategory =
  | "CONDITION"
  | "MOTIVATION"
  | "LEGAL"
  | "FINANCIAL"
  | "OCCUPANCY"
  | "INVESTOR_TARGET";

export const DISTRESS_KEYWORD_RULES: KeywordRule[] = [
  // ── CONDITION ──────────────────────────────────────────────────────────────
  { pattern: /\bas[- ]is\b/i, label: "as-is", weight: 15, category: "CONDITION" },
  { pattern: /\bfixer[- ]?upper\b/i, label: "fixer-upper", weight: 14, category: "CONDITION" },
  { pattern: /\bfixer\b/i, label: "fixer", weight: 12, category: "CONDITION" },
  { pattern: /\bTLC\b/, label: "TLC", weight: 12, category: "CONDITION" },
  { pattern: /\bneeds (work|repairs?|updating|renovation|TLC)\b/i, label: "needs work", weight: 13, category: "CONDITION" },
  { pattern: /\bupdates? needed\b/i, label: "updates needed", weight: 10, category: "CONDITION" },
  { pattern: /\brepairs? needed\b/i, label: "repairs needed", weight: 12, category: "CONDITION" },
  { pattern: /\bsome (work|repairs?|updating)\b/i, label: "some repairs", weight: 8, category: "CONDITION" },
  { pattern: /\bdamage[d]?\b/i, label: "damaged", weight: 10, category: "CONDITION" },
  { pattern: /\bfire damage[d]?\b/i, label: "fire damage", weight: 18, category: "CONDITION" },
  { pattern: /\bflood damage[d]?\b/i, label: "flood damage", weight: 18, category: "CONDITION" },
  { pattern: /\bfoundation\b/i, label: "foundation", weight: 8, category: "CONDITION" },
  { pattern: /\bdeferred maintenance\b/i, label: "deferred maintenance", weight: 12, category: "CONDITION" },
  { pattern: /\bcash only\b/i, label: "cash only", weight: 10, category: "CONDITION" },
  { pattern: /\bnon[- ]warrantable\b/i, label: "non-warrantable", weight: 8, category: "CONDITION" },
  { pattern: /\bcosmetic\b/i, label: "cosmetic", weight: 6, category: "CONDITION" },
  { pattern: /\bhandyman\b/i, label: "handyman", weight: 10, category: "CONDITION" },
  { pattern: /\bproject (home|house|property)\b/i, label: "project home", weight: 12, category: "CONDITION" },
  { pattern: /\bright to (own|purchase)\b/i, label: "right to purchase", weight: 5, category: "CONDITION" },

  // ── MOTIVATION ─────────────────────────────────────────────────────────────
  { pattern: /\bmotivated seller\b/i, label: "motivated seller", weight: 15, category: "MOTIVATION" },
  { pattern: /\bmust sell\b/i, label: "must sell", weight: 16, category: "MOTIVATION" },
  { pattern: /\bprice to sell\b/i, label: "priced to sell", weight: 10, category: "MOTIVATION" },
  { pattern: /\bbring all offers?\b/i, label: "bring all offers", weight: 14, category: "MOTIVATION" },
  { pattern: /\ball offers (considered|welcome)\b/i, label: "all offers considered", weight: 12, category: "MOTIVATION" },
  { pattern: /\bseller motivated\b/i, label: "seller motivated", weight: 14, category: "MOTIVATION" },
  { pattern: /\brelocation\b/i, label: "relocation", weight: 10, category: "MOTIVATION" },
  { pattern: /\bjob (transfer|relocation)\b/i, label: "job transfer", weight: 12, category: "MOTIVATION" },
  { pattern: /\bdivorce\b/i, label: "divorce", weight: 13, category: "MOTIVATION" },
  { pattern: /\bseller financing\b/i, label: "seller financing", weight: 8, category: "MOTIVATION" },
  { pattern: /\bowner (financing|carry|carried)\b/i, label: "owner financing", weight: 8, category: "MOTIVATION" },
  { pattern: /\bprice (reduced|drop)\b/i, label: "price reduced", weight: 10, category: "MOTIVATION" },
  { pattern: /\bopportunity\b/i, label: "opportunity", weight: 5, category: "MOTIVATION" },
  { pattern: /\bpotential\b/i, label: "potential", weight: 4, category: "MOTIVATION" },

  // ── LEGAL / ESTATE ─────────────────────────────────────────────────────────
  { pattern: /\bprobate\b/i, label: "probate", weight: 18, category: "LEGAL" },
  { pattern: /\bestate (sale|property|home)\b/i, label: "estate sale", weight: 16, category: "LEGAL" },
  { pattern: /\binherited\b/i, label: "inherited", weight: 16, category: "LEGAL" },
  { pattern: /\bheirs?\b/i, label: "heir/heirs", weight: 14, category: "LEGAL" },
  { pattern: /\btrustee('s)? sale\b/i, label: "trustee sale", weight: 18, category: "LEGAL" },
  { pattern: /\bshort sale\b/i, label: "short sale", weight: 18, category: "LEGAL" },
  { pattern: /\bforeclosure\b/i, label: "foreclosure", weight: 20, category: "LEGAL" },
  { pattern: /\bpreforeclosure\b/i, label: "preforeclosure", weight: 20, category: "LEGAL" },
  { pattern: /\blis pendens\b/i, label: "lis pendens", weight: 18, category: "LEGAL" },
  { pattern: /\bREO\b/, label: "REO", weight: 16, category: "LEGAL" },
  { pattern: /\bbank[- ]?owned\b/i, label: "bank-owned", weight: 16, category: "LEGAL" },
  { pattern: /\bauction\b/i, label: "auction", weight: 16, category: "LEGAL" },
  { pattern: /\bcourt[- ]?ordered\b/i, label: "court-ordered", weight: 16, category: "LEGAL" },
  { pattern: /\bselling (as part of|pursuant to) (estate|trust)\b/i, label: "trust/estate", weight: 14, category: "LEGAL" },

  // ── FINANCIAL ──────────────────────────────────────────────────────────────
  { pattern: /\btax (delinquent|lien|sale)\b/i, label: "tax delinquent", weight: 18, category: "FINANCIAL" },
  { pattern: /\bback taxes\b/i, label: "back taxes", weight: 16, category: "FINANCIAL" },
  { pattern: /\blien\b/i, label: "lien", weight: 10, category: "FINANCIAL" },
  { pattern: /\bdefault\b/i, label: "default", weight: 14, category: "FINANCIAL" },

  // ── OCCUPANCY ──────────────────────────────────────────────────────────────
  { pattern: /\btenant[- ]?occupied\b/i, label: "tenant-occupied", weight: 12, category: "OCCUPANCY" },
  { pattern: /\bdo not disturb (tenant|occupant)\b/i, label: "do not disturb tenant", weight: 14, category: "OCCUPANCY" },
  { pattern: /\brented\b/i, label: "rented", weight: 8, category: "OCCUPANCY" },
  { pattern: /\bcurrent(ly)? rented\b/i, label: "currently rented", weight: 10, category: "OCCUPANCY" },
  { pattern: /\bmonth[- ]?to[- ]?month\b/i, label: "month-to-month", weight: 8, category: "OCCUPANCY" },
  { pattern: /\bvacant\b/i, label: "vacant", weight: 10, category: "OCCUPANCY" },
  { pattern: /\bunoccupied\b/i, label: "unoccupied", weight: 10, category: "OCCUPANCY" },
  { pattern: /\babandoned\b/i, label: "abandoned", weight: 14, category: "OCCUPANCY" },

  // ── INVESTOR TARGET ────────────────────────────────────────────────────────
  { pattern: /\binvestor (special|alert|opportunity)\b/i, label: "investor special", weight: 14, category: "INVESTOR_TARGET" },
  { pattern: /\binvestment (property|opportunity)\b/i, label: "investment property", weight: 10, category: "INVESTOR_TARGET" },
  { pattern: /\bcash (only|offer|buyer)\b/i, label: "cash buyer", weight: 8, category: "INVESTOR_TARGET" },
  { pattern: /\bgreat (investment|opportunity)\b/i, label: "great investment", weight: 6, category: "INVESTOR_TARGET" },
  { pattern: /\bbuy and hold\b/i, label: "buy and hold", weight: 6, category: "INVESTOR_TARGET" },
  { pattern: /\bARV\b/, label: "ARV", weight: 8, category: "INVESTOR_TARGET" },
  { pattern: /\bafter repair value\b/i, label: "after repair value", weight: 8, category: "INVESTOR_TARGET" },
  { pattern: /\bsweat equity\b/i, label: "sweat equity", weight: 10, category: "INVESTOR_TARGET" },
  { pattern: /\bwholesale\b/i, label: "wholesale", weight: 12, category: "INVESTOR_TARGET" },
  { pattern: /\bassignable\b/i, label: "assignable", weight: 12, category: "INVESTOR_TARGET" },
];

// ─────────────────────────────────────────────────────────────────────────────
// HARD REJECT KEYWORDS — these indicate retail/clean, not distress
// ─────────────────────────────────────────────────────────────────────────────
export const RETAIL_REJECT_KEYWORDS: RegExp[] = [
  /\bfully (renovated|updated|remodeled|upgraded)\b/i,
  /\bturn[- ]?key\b/i,
  /\bmove[- ]?in ready\b/i,
  /\blike new\b/i,
  /\bpristine\b/i,
  /\bimmaculate\b/i,
  /\bluxury\b/i,
  /\bmodel (home|perfect)\b/i,
  /\bgourmet (kitchen|chef)\b/i,
  /\bhigh[- ]?end finishes\b/i,
  /\bquartz countertop\b/i,
  /\bstainless steel appliances\b/i,
  /\bnewly (built|constructed)\b/i,
  /\bnew construction\b/i,
  /\bready to move in\b/i,
];

// ─────────────────────────────────────────────────────────────────────────────
// SCORER
// ─────────────────────────────────────────────────────────────────────────────
export interface KeywordScanResult {
  score: number;              // capped at 100
  matched: string[];          // human-readable matched labels
  hasRetailSignals: boolean;
  retailSignalsFound: string[];
}

export function scanKeywords(text: string): KeywordScanResult {
  if (!text) return { score: 0, matched: [], hasRetailSignals: false, retailSignalsFound: [] };

  const matched: string[] = [];
  let rawScore = 0;

  for (const rule of DISTRESS_KEYWORD_RULES) {
    if (rule.pattern.test(text)) {
      matched.push(rule.label);
      rawScore += rule.weight;
    }
  }

  const retailSignalsFound: string[] = [];
  for (const r of RETAIL_REJECT_KEYWORDS) {
    const m = text.match(r);
    if (m) retailSignalsFound.push(m[0]);
  }

  return {
    score: Math.min(100, rawScore),
    matched,
    hasRetailSignals: retailSignalsFound.length > 0,
    retailSignalsFound,
  };
}
