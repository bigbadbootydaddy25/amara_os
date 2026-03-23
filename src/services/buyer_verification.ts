/**
 * BuyerVerificationService
 *
 * Computes verification tier and flags for a buyer entity using ONLY
 * recorded transaction data. No assumptions are made. A buyer is never
 * labeled verified without satisfying explicit, quantitative rules.
 *
 * Rules:
 *   verified_active   — (≥2 tx in last 12mo) OR (≥4 tx in last 24mo)
 *                       AND last transaction within 180 days
 *   verified_inactive — previously met thresholds but last tx > 180 days ago
 *   unverified        — has transactions but does not meet any threshold
 *   insufficient_data — fewer than 2 recorded transactions total
 */

import { query, queryOne } from '../db/client';
import type { BuyerEntity, BuyerTier, EntityType, VerificationFlags } from '../models/buyer';
import { BUILDER_DEVELOPER_KEYWORDS, INSTITUTIONAL_KEYWORDS } from '../models/buyer';

// ─── Verification thresholds (single source of truth) ────────────────────────

const THRESHOLD = {
  MIN_TX_12MO: 2,          // verified: 2+ transactions in last 12 months
  MIN_TX_24MO: 4,          // verified: 4+ transactions in last 24 months
  ACTIVE_DAYS: 180,        // last transaction must be within this many days to be "active"
  MIN_TOTAL_TX: 2,         // minimum transactions to attempt any verification
} as const;

// ─── Entity type detection ────────────────────────────────────────────────────

export function detectEntityType(name: string): EntityType {
  const lower = name.toLowerCase();

  if (containsAny(lower, INSTITUTIONAL_KEYWORDS)) return 'institution';
  if (containsAny(lower, BUILDER_DEVELOPER_KEYWORDS)) return 'builder_developer';

  // Legal entity suffix detection
  if (/\bllc\b/.test(lower)) return 'llc';
  if (/\b(inc|incorporated|corp|corporation)\b/.test(lower)) return 'corporation';
  if (/\btrust\b/.test(lower)) return 'trust';
  if (/\b(lp|llp|partnership|partners)\b/.test(lower)) return 'partnership';

  return 'unknown';
}

function containsAny(haystack: string, needles: readonly string[]): boolean {
  return needles.some((kw) => haystack.includes(kw));
}

// ─── Consistency score ────────────────────────────────────────────────────────
/**
 * Measures how evenly distributed transactions are across time.
 * Score = 1.0 means perfectly uniform cadence; 0 means all clustered.
 *
 * Method: coefficient of variation of monthly transaction counts,
 * normalized so lower CV → higher consistency score.
 */
function computeConsistencyScore(recordedDates: Date[]): number | null {
  if (recordedDates.length < 2) return null;

  // Bucket by year-month
  const buckets = new Map<string, number>();
  for (const d of recordedDates) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }

  const counts = Array.from(buckets.values());
  const mean = counts.reduce((a, b) => a + b, 0) / counts.length;
  if (mean === 0) return 0;

  const variance = counts.reduce((sum, c) => sum + (c - mean) ** 2, 0) / counts.length;
  const cv = Math.sqrt(variance) / mean;

  // Map CV to 0–1: CV=0 → score=1, CV≥2 → score=0
  return Math.max(0, 1 - cv / 2);
}

// ─── Core verification logic ──────────────────────────────────────────────────

interface RawSummaryRow {
  buyer_entity_id: string;
  total_transactions: string;
  transactions_last_12mo: string;
  transactions_last_24mo: string;
  first_transaction_date: Date | null;
  last_transaction_date: Date | null;
  days_since_last_transaction: string | null;
  avg_days_between_transactions: string | null;
}

interface TransactionDateRow {
  recorded_date: Date;
}

export function computeVerificationFlags(
  summary: RawSummaryRow,
  recordedDates: Date[],
  entityName: string
): VerificationFlags {
  const total = parseInt(summary.total_transactions, 10);
  const tx12 = parseInt(summary.transactions_last_12mo, 10);
  const tx24 = parseInt(summary.transactions_last_24mo, 10);
  const daysSinceLast = summary.days_since_last_transaction
    ? parseInt(summary.days_since_last_transaction, 10)
    : null;

  const nameLower = entityName.toLowerCase();
  const isBuilder = containsAny(nameLower, BUILDER_DEVELOPER_KEYWORDS);
  const isInstitutional = containsAny(nameLower, INSTITUTIONAL_KEYWORDS);

  // Acquisition pace: annualised from span
  let pacePerYear: number | null = null;
  if (
    total >= 2 &&
    summary.first_transaction_date &&
    summary.last_transaction_date
  ) {
    const spanDays =
      (summary.last_transaction_date.getTime() -
        summary.first_transaction_date.getTime()) /
      86_400_000;
    pacePerYear = spanDays > 0 ? (total / spanDays) * 365 : null;
  }

  return {
    meets_12mo_threshold: tx12 >= THRESHOLD.MIN_TX_12MO,
    meets_24mo_threshold: tx24 >= THRESHOLD.MIN_TX_24MO,
    last_transaction_days_ago: daysSinceLast,
    is_recently_active: daysSinceLast !== null && daysSinceLast <= THRESHOLD.ACTIVE_DAYS,
    is_builder_developer: isBuilder,
    is_institutional: isInstitutional,
    total_transaction_count: total,
    transaction_pace_per_year: pacePerYear !== null ? Math.round(pacePerYear * 100) / 100 : null,
    consistency_score: computeConsistencyScore(recordedDates),
  };
}

export function computeTier(flags: VerificationFlags): BuyerTier {
  if (flags.total_transaction_count < THRESHOLD.MIN_TOTAL_TX) {
    return 'insufficient_data';
  }

  const meetsQuantThreshold =
    flags.meets_12mo_threshold || flags.meets_24mo_threshold;

  if (!meetsQuantThreshold) {
    return 'unverified';
  }

  return flags.is_recently_active ? 'verified_active' : 'verified_inactive';
}

// ─── Service class ────────────────────────────────────────────────────────────

export class BuyerVerificationService {
  /**
   * Recompute and persist verification tier + flags for a single buyer.
   * Always reads from transaction records — never uses cached/stale state.
   */
  async verifyBuyer(buyerEntityId: string): Promise<BuyerEntity> {
    // 1. Fetch buyer
    const buyer = await queryOne<BuyerEntity>(
      `SELECT * FROM buyer_entities WHERE id = $1`,
      [buyerEntityId]
    );
    if (!buyer) throw new Error(`BuyerEntity not found: ${buyerEntityId}`);

    // 2. Fetch transaction summary from materialized view
    const summary = await queryOne<RawSummaryRow>(
      `SELECT * FROM transaction_summary WHERE buyer_entity_id = $1`,
      [buyerEntityId]
    );

    if (!summary) {
      // No transactions at all
      const flags: VerificationFlags = {
        meets_12mo_threshold: false,
        meets_24mo_threshold: false,
        last_transaction_days_ago: null,
        is_recently_active: false,
        is_builder_developer: false,
        is_institutional: false,
        total_transaction_count: 0,
        transaction_pace_per_year: null,
        consistency_score: null,
      };
      return this.persistVerification(buyer, flags, 'insufficient_data');
    }

    // 3. Fetch individual recorded dates for consistency scoring
    const dateRows = await query<TransactionDateRow>(
      `SELECT recorded_date FROM transactions WHERE buyer_entity_id = $1 ORDER BY recorded_date`,
      [buyerEntityId]
    );
    const recordedDates = dateRows.map((r) => new Date(r.recorded_date));

    // 4. Compute flags and tier
    const flags = computeVerificationFlags(summary, recordedDates, buyer.name);
    const tier = computeTier(flags);

    // 5. Update entity type if currently unknown
    let entityType = buyer.entity_type as EntityType;
    if (entityType === 'unknown') {
      entityType = detectEntityType(buyer.name);
    }

    return this.persistVerification(buyer, flags, tier, entityType);
  }

  /**
   * Batch-verify all buyers whose verification is stale (> 24 hours old
   * or never computed), in pages.
   */
  async verifyStale(pageSize = 100): Promise<{ processed: number; errors: number }> {
    const staleIds = await query<{ id: string }>(
      `SELECT id FROM buyer_entities
       WHERE tier_computed_at IS NULL
          OR tier_computed_at < NOW() - INTERVAL '24 hours'
       ORDER BY tier_computed_at ASC NULLS FIRST
       LIMIT $1`,
      [pageSize]
    );

    let errors = 0;
    for (const { id } of staleIds) {
      try {
        await this.verifyBuyer(id);
      } catch (e) {
        errors++;
        console.error(`[verification] failed for buyer ${id}:`, e);
      }
    }

    return { processed: staleIds.length, errors };
  }

  private async persistVerification(
    buyer: BuyerEntity,
    flags: VerificationFlags,
    tier: BuyerTier,
    entityType?: EntityType
  ): Promise<BuyerEntity> {
    const rows = await query<BuyerEntity>(
      `UPDATE buyer_entities
       SET tier = $1,
           verification_flags = $2,
           tier_computed_at = NOW(),
           entity_type = COALESCE($3, entity_type)
       WHERE id = $4
       RETURNING *`,
      [tier, JSON.stringify(flags), entityType ?? null, buyer.id]
    );
    return rows[0]!;
  }

  /**
   * Return all verified_active buyers, sorted by tier and acquisition pace.
   * Only surfaces buyers suitable for the primary disposition layer.
   */
  async getVerifiedActiveBuyers(filters?: {
    zip?: string;
    minPacePerYear?: number;
    strategy?: string;
  }): Promise<BuyerEntity[]> {
    const conditions: string[] = [`be.tier = 'verified_active'`];
    const params: unknown[] = [];
    let i = 1;

    if (filters?.minPacePerYear !== undefined) {
      conditions.push(
        `(be.verification_flags->>'transaction_pace_per_year')::numeric >= $${i++}`
      );
      params.push(filters.minPacePerYear);
    }

    if (filters?.zip) {
      // Join through buy_boxes preferred_zips
      conditions.push(
        `EXISTS (
           SELECT 1 FROM buy_boxes bb
           WHERE bb.buyer_entity_id = be.id
             AND bb.preferred_zips @> $${i++}::jsonb
         )`
      );
      params.push(JSON.stringify([{ zip: filters.zip }]));
    }

    const sql = `
      SELECT be.*
      FROM buyer_entities be
      WHERE ${conditions.join(' AND ')}
      ORDER BY
        (be.verification_flags->>'transaction_pace_per_year')::numeric DESC NULLS LAST,
        be.tier_computed_at DESC
    `;

    return query<BuyerEntity>(sql, params);
  }
}

export const buyerVerificationService = new BuyerVerificationService();
