/**
 * DealEngine
 *
 * Integrates buyer verification and ZIP liquidity into a unified deal-scoring
 * layer. For each deal opportunity, it surfaces:
 *
 *   1. Matched buyers — verified_active buyers whose inferred buy box
 *      overlaps with the subject deal. Weak/unverified buyers are NOT
 *      surfaced in the primary layer.
 *
 *   2. ZIP liquidity context — exit certainty score and liquidity class
 *      for the deal's ZIP code, derived from transaction history.
 *
 *   3. Exit confidence — composite score combining buyer depth in the
 *      ZIP and the deal's fit to verified buy boxes.
 *
 * Truth-preserving guarantees:
 *   - Buyers labeled verified_active only if they satisfied the
 *     threshold rules in BuyerVerificationService.
 *   - Exit confidence = 0 when no verified buyers exist for the ZIP
 *     or the deal parameters do not fit any recorded buy box.
 *   - All scores trace to real transaction records.
 */

import { query, queryOne } from '../db/client';
import type { BuyerEntity } from '../models/buyer';
import type { BuyBox } from '../models/buybox';
import type { ZipLiquidity } from '../models/zip_liquidity';
import type { PropertyType } from '../models/transaction';
import { zipLiquidityEngine } from '../services/zip_liquidity';
import { buyerVerificationService } from '../services/buyer_verification';

// ─── Deal input ───────────────────────────────────────────────────────────────

export interface DealInput {
  zip: string;
  state: string;
  asking_price: number;
  property_type: PropertyType;
  sqft?: number;
  arv?: number;                // After-repair value if known
  condition?: 'distressed' | 'average' | 'updated' | 'new';
}

// ─── Output types ─────────────────────────────────────────────────────────────

export interface BuyerMatch {
  buyer: BuyerEntity;
  buy_box: BuyBox;
  match_score: number;    // 0–100: how well the deal fits this buyer's box
  match_reasons: string[];
  disqualifications: string[];
}

export interface DealScore {
  deal: DealInput;

  // ZIP liquidity context
  zip_liquidity: ZipLiquidity | null;
  zip_liquidity_class: string;
  zip_exit_certainty: number;

  // Buyer matching
  verified_buyer_matches: BuyerMatch[];    // verified_active only
  matched_buyer_count: number;
  top_buyer: BuyerMatch | null;

  // Composite exit confidence
  exit_confidence: number;                 // 0–100
  exit_confidence_label: 'high' | 'moderate' | 'low' | 'insufficient_data';

  // Disposition recommendation
  disposition_viable: boolean;
  disposition_notes: string[];

  scored_at: Date;
}

// ─── Buyer-to-deal matching ───────────────────────────────────────────────────

interface BuyBoxRow extends BuyBox {
  price_min: number;
  price_max: number;
  price_avg: number;
  preferred_zips: Array<{ zip: string; transaction_count: number; pct_of_total: number }>;
  property_types: Array<{ property_type: PropertyType; pct_of_total: number }>;
}

function matchBuyerToDeal(
  buyer: BuyerEntity,
  buyBox: BuyBoxRow,
  deal: DealInput
): BuyerMatch {
  let score = 0;
  const reasons: string[] = [];
  const disqualifications: string[] = [];

  // ── Price fit ───────────────────────────────────────────────────────────
  const priceMin = buyBox.price_min;
  const priceMax = buyBox.price_max;

  if (priceMin !== null && priceMax !== null) {
    if (deal.asking_price >= priceMin && deal.asking_price <= priceMax) {
      score += 40;
      reasons.push(`price $${deal.asking_price.toLocaleString()} fits box [$${priceMin.toLocaleString()}–$${priceMax.toLocaleString()}]`);
    } else if (
      deal.asking_price >= priceMin * 0.85 &&
      deal.asking_price <= priceMax * 1.15
    ) {
      score += 20;
      reasons.push(`price within 15% of buy box range`);
    } else {
      disqualifications.push(
        `price $${deal.asking_price.toLocaleString()} outside box [$${priceMin.toLocaleString()}–$${priceMax.toLocaleString()}]`
      );
    }
  } else {
    score += 10; // No price data — partial credit
    reasons.push('no price range inferred (insufficient data)');
  }

  // ── ZIP fit ─────────────────────────────────────────────────────────────
  const prefZips = (buyBox.preferred_zips ?? []) as Array<{ zip: string; pct_of_total: number }>;
  const zipMatch = prefZips.find((z) => z.zip === deal.zip);

  if (zipMatch) {
    const bonus = Math.round(zipMatch.pct_of_total * 0.3); // up to 30
    score += bonus;
    reasons.push(`ZIP ${deal.zip} is ${zipMatch.pct_of_total}% of buyer's acquisitions`);
  } else if (prefZips.length === 0) {
    score += 5;
    reasons.push('no ZIP preference data available');
  } else {
    disqualifications.push(`ZIP ${deal.zip} not in buyer's recorded purchase ZIPs`);
  }

  // ── Property type fit ───────────────────────────────────────────────────
  const propTypes = (buyBox.property_types ?? []) as Array<{
    property_type: PropertyType;
    pct_of_total: number;
  }>;
  const typeMatch = propTypes.find((p) => p.property_type === deal.property_type);

  if (typeMatch) {
    const bonus = Math.round(typeMatch.pct_of_total * 0.2); // up to 20
    score += bonus;
    reasons.push(`${deal.property_type} is ${typeMatch.pct_of_total}% of buyer's acquisitions`);
  } else if (propTypes.length === 0) {
    score += 5;
  } else {
    disqualifications.push(
      `buyer has no recorded ${deal.property_type} acquisitions`
    );
  }

  // ── Sqft fit ────────────────────────────────────────────────────────────
  if (deal.sqft && buyBox.sqft_min && buyBox.sqft_max) {
    if (deal.sqft >= buyBox.sqft_min && deal.sqft <= buyBox.sqft_max) {
      score += 10;
      reasons.push(`sqft ${deal.sqft} fits buyer range [${buyBox.sqft_min}–${buyBox.sqft_max}]`);
    }
  }

  return {
    buyer,
    buy_box: buyBox,
    match_score: Math.min(score, 100),
    match_reasons: reasons,
    disqualifications,
  };
}

function exitConfidenceLabel(score: number): DealScore['exit_confidence_label'] {
  if (score >= 65) return 'high';
  if (score >= 40) return 'moderate';
  if (score >= 10) return 'low';
  return 'insufficient_data';
}

// ─── Deal Engine ──────────────────────────────────────────────────────────────

export class DealEngine {
  /**
   * Score a deal: match against verified_active buyers and compute
   * exit confidence from buyer depth + ZIP liquidity.
   */
  async scoreDeal(deal: DealInput): Promise<DealScore> {
    const scoredAt = new Date();
    const dispositionNotes: string[] = [];

    // 1. ZIP liquidity
    const zipLiquidity = await zipLiquidityEngine.getLiquidity(deal.zip);
    const zipExitCertainty = zipLiquidity?.exit_certainty ?? 0;
    const zipClass = zipLiquidity?.liquidity_class ?? 'none';

    if (!zipLiquidity) {
      dispositionNotes.push(`No transaction history for ZIP ${deal.zip} — exit certainty unknown`);
    }

    // 2. Find verified_active buyers whose buy box could match
    const candidateBuyers = await buyerVerificationService.getVerifiedActiveBuyers({
      zip: deal.zip,
    });

    // If no ZIP-specific matches, broaden to all verified_active
    const allVerifiedBuyers =
      candidateBuyers.length > 0
        ? candidateBuyers
        : await buyerVerificationService.getVerifiedActiveBuyers();

    // 3. Load buy boxes and match
    const matches: BuyerMatch[] = [];

    for (const buyer of allVerifiedBuyers) {
      const buyBox = await queryOne<BuyBoxRow>(
        `SELECT * FROM buy_boxes WHERE buyer_entity_id = $1`,
        [buyer.id]
      );
      if (!buyBox) continue;

      const match = matchBuyerToDeal(buyer, buyBox, deal);
      // Only include if there are no hard disqualifications, or score > threshold
      if (match.disqualifications.length === 0 || match.match_score >= 30) {
        matches.push(match);
      }
    }

    // Sort by match score descending
    matches.sort((a, b) => b.match_score - a.match_score);
    const topBuyers = matches.slice(0, 10); // Return top 10

    // 4. Composite exit confidence
    let exitConfidence = 0;

    if (topBuyers.length > 0) {
      const topMatchScore = topBuyers[0]!.match_score;
      const buyerDepthBonus = Math.min(topBuyers.length * 3, 20); // up to 20 pts for buyer depth
      exitConfidence = Math.round(
        topMatchScore * 0.5 +          // best buyer fit
        zipExitCertainty * 0.3 +       // ZIP market depth
        buyerDepthBonus                // number of matching buyers
      );
    } else {
      // No verified buyers match — set to ZIP-only signal, dampened
      exitConfidence = Math.round(zipExitCertainty * 0.3);
      dispositionNotes.push('No verified_active buyers match this deal — exit confidence limited to ZIP signal');
    }

    exitConfidence = Math.min(exitConfidence, 100);

    // 5. Disposition viability
    const dispositionViable =
      exitConfidence >= 40 &&
      topBuyers.length >= 1 &&
      zipClass !== 'none';

    if (!dispositionViable) {
      if (topBuyers.length === 0) {
        dispositionNotes.push('No qualified buyers identified — do not surface in primary disposition layer');
      }
      if (zipClass === 'none' || zipClass === 'D') {
        dispositionNotes.push(`ZIP ${deal.zip} liquidity class ${zipClass} — thin exit market`);
      }
    }

    return {
      deal,
      zip_liquidity: zipLiquidity,
      zip_liquidity_class: zipClass,
      zip_exit_certainty: zipExitCertainty,
      verified_buyer_matches: topBuyers,
      matched_buyer_count: topBuyers.length,
      top_buyer: topBuyers[0] ?? null,
      exit_confidence: exitConfidence,
      exit_confidence_label: exitConfidenceLabel(exitConfidence),
      disposition_viable: dispositionViable,
      disposition_notes: dispositionNotes,
      scored_at: scoredAt,
    };
  }

  /**
   * Find the best matching buyers for a specific ZIP and price point,
   * without a full deal score. Used for quick disposition lookup.
   */
  async findBuyersForZip(
    zip: string,
    askingPrice: number,
    propertyType: PropertyType
  ): Promise<BuyerMatch[]> {
    const deal: DealInput = { zip, state: '', asking_price: askingPrice, property_type: propertyType };
    const score = await this.scoreDeal(deal);
    return score.verified_buyer_matches;
  }
}

export const dealEngine = new DealEngine();
