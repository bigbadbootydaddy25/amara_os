/**
 * ZipLiquidityEngine
 *
 * Builds a transaction-based liquidity heat map for each ZIP code.
 * All scores are derived from recorded acquisition counts — no market
 * assumption or external data source is used.
 *
 * Score components (each 0–100):
 *
 *   velocity_score    — rate of recent transactions (90-day and 12-month windows)
 *   depth_score       — breadth of unique buyers (thin vs. deep buyer pool)
 *   consistency_score — steadiness of activity over the analysis window
 *
 *   liquidity_score   = weighted composite of the three
 *   exit_certainty    = 0–100 probability analog for finding a buyer within 90 days
 *
 * Liquidity classes:
 *   A  ≥75  deep pool, fast velocity
 *   B  ≥50  reliable activity
 *   C  ≥25  thin pool, slow velocity
 *   D  ≥1   sparse
 *   none 0  no data
 */

import { query } from '../db/client';
import type { ZipLiquidity, LiquidityClass } from '../models/zip_liquidity';
import { LIQUIDITY_THRESHOLDS } from '../models/zip_liquidity';

const ANALYSIS_WINDOW_MONTHS = 24;
const WEIGHTS = { velocity: 0.45, depth: 0.35, consistency: 0.20 } as const;

// ─── Scoring helpers ──────────────────────────────────────────────────────────

/**
 * Velocity score — anchors:
 *   90-day count ≥ 10  → 100
 *   90-day count = 5   → 75
 *   90-day count = 2   → 40
 *   90-day count = 0   → 0 (boosted by 12mo if recent)
 */
function scoreVelocity(tx90d: number, tx12mo: number): number {
  const v90 = Math.min(tx90d / 10, 1) * 80;
  const v12 = Math.min(tx12mo / 30, 1) * 20;
  return Math.round(v90 + v12);
}

/**
 * Depth score — anchors:
 *   unique_buyers ≥ 20 → 100
 *   unique_buyers = 10 → 70
 *   unique_buyers = 5  → 40
 *   unique_buyers = 1  → 5
 */
function scoreDepth(uniqueBuyers: number, repeatBuyers: number): number {
  const base = Math.min(uniqueBuyers / 20, 1) * 75;
  const repeatBonus = Math.min(repeatBuyers / Math.max(uniqueBuyers, 1), 1) * 25;
  return Math.round(base + repeatBonus);
}

/**
 * Consistency score — months with activity / total months in window.
 * A ZIP with steady monthly activity scores higher than one with a single burst.
 */
function scoreConsistency(monthsWithActivity: number, windowMonths: number): number {
  return Math.round(Math.min(monthsWithActivity / windowMonths, 1) * 100);
}

function computeLiquidityClass(score: number, uniqueBuyers: number, tx90d: number): LiquidityClass {
  if (score <= 0) return 'none';
  if (
    score >= LIQUIDITY_THRESHOLDS.CLASS_A.min_score &&
    uniqueBuyers >= LIQUIDITY_THRESHOLDS.CLASS_A.min_unique_buyers &&
    tx90d >= LIQUIDITY_THRESHOLDS.CLASS_A.min_velocity_90d
  ) return 'A';
  if (
    score >= LIQUIDITY_THRESHOLDS.CLASS_B.min_score &&
    uniqueBuyers >= LIQUIDITY_THRESHOLDS.CLASS_B.min_unique_buyers &&
    tx90d >= LIQUIDITY_THRESHOLDS.CLASS_B.min_velocity_90d
  ) return 'B';
  if (
    score >= LIQUIDITY_THRESHOLDS.CLASS_C.min_score &&
    uniqueBuyers >= LIQUIDITY_THRESHOLDS.CLASS_C.min_unique_buyers
  ) return 'C';
  if (score >= LIQUIDITY_THRESHOLDS.CLASS_D.min_score) return 'D';
  return 'none';
}

/**
 * Exit certainty: calibrated from liquidity class + recency.
 * Does NOT extrapolate — strictly based on historical transaction density.
 */
function computeExitCertainty(
  liquidityScore: number,
  liquidityClass: LiquidityClass,
  tx90d: number
): number {
  if (liquidityClass === 'none') return 0;

  // Base from score
  let base = liquidityScore * 0.7;

  // Bonus for very recent activity (last 90 days)
  if (tx90d >= 5) base += 15;
  else if (tx90d >= 2) base += 8;
  else if (tx90d >= 1) base += 3;

  // Class floor / ceiling
  const floors: Record<LiquidityClass, number> = { A: 60, B: 40, C: 20, D: 5, none: 0 };
  const ceilings: Record<LiquidityClass, number> = { A: 95, B: 75, C: 55, D: 35, none: 0 };

  return Math.round(Math.max(floors[liquidityClass], Math.min(base, ceilings[liquidityClass])));
}

// ─── DB row types ─────────────────────────────────────────────────────────────

interface ZipAggRow {
  zip: string;
  state: string;
  city: string | null;
  total_transactions: string;
  unique_buyer_count: string;
  repeat_buyer_count: string;
  tx_last_90d: string;
  tx_last_180d: string;
  tx_last_12mo: string;
  tx_last_24mo: string;
  months_with_activity: string;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export class ZipLiquidityEngine {
  /**
   * Recompute liquidity scores for all ZIPs with transaction history
   * in the last ANALYSIS_WINDOW_MONTHS months.
   */
  async computeAll(): Promise<{ processed: number; errors: number }> {
    const windowStart = new Date();
    windowStart.setMonth(windowStart.getMonth() - ANALYSIS_WINDOW_MONTHS);

    const zipRows = await query<ZipAggRow>(
      `SELECT
         t.zip,
         t.state,
         MAX(t.city) AS city,
         COUNT(*)                                                       AS total_transactions,
         COUNT(DISTINCT t.buyer_entity_id)                             AS unique_buyer_count,
         COUNT(DISTINCT CASE
           WHEN sub.cnt >= 2 THEN t.buyer_entity_id END)               AS repeat_buyer_count,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '90 days')
                                                                        AS tx_last_90d,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '180 days')
                                                                        AS tx_last_180d,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '12 months')
                                                                        AS tx_last_12mo,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '24 months')
                                                                        AS tx_last_24mo,
         COUNT(DISTINCT TO_CHAR(t.recorded_date, 'YYYY-MM'))           AS months_with_activity
       FROM transactions t
       JOIN (
         SELECT zip, buyer_entity_id, COUNT(*) AS cnt
         FROM transactions
         GROUP BY zip, buyer_entity_id
       ) sub ON sub.zip = t.zip AND sub.buyer_entity_id = t.buyer_entity_id
       WHERE t.recorded_date >= $1
       GROUP BY t.zip, t.state`,
      [windowStart.toISOString()]
    );

    const windowEnd = new Date();
    let errors = 0;

    for (const row of zipRows) {
      try {
        await this.upsertZipLiquidity(row, windowStart, windowEnd);
      } catch (e) {
        errors++;
        console.error(`[zip_liquidity] failed for ZIP ${row.zip}:`, e);
      }
    }

    return { processed: zipRows.length, errors };
  }

  /**
   * Recompute liquidity for a single ZIP — called after new transactions
   * are recorded in that ZIP.
   */
  async computeForZip(zip: string): Promise<ZipLiquidity | null> {
    const windowStart = new Date();
    windowStart.setMonth(windowStart.getMonth() - ANALYSIS_WINDOW_MONTHS);

    const rows = await query<ZipAggRow>(
      `SELECT
         t.zip,
         t.state,
         MAX(t.city) AS city,
         COUNT(*)                                                       AS total_transactions,
         COUNT(DISTINCT t.buyer_entity_id)                             AS unique_buyer_count,
         COUNT(DISTINCT CASE WHEN sub.cnt >= 2 THEN t.buyer_entity_id END)
                                                                        AS repeat_buyer_count,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '90 days')  AS tx_last_90d,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '180 days') AS tx_last_180d,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '12 months') AS tx_last_12mo,
         COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '24 months') AS tx_last_24mo,
         COUNT(DISTINCT TO_CHAR(t.recorded_date, 'YYYY-MM'))           AS months_with_activity
       FROM transactions t
       JOIN (
         SELECT zip, buyer_entity_id, COUNT(*) AS cnt
         FROM transactions
         WHERE zip = $1
         GROUP BY zip, buyer_entity_id
       ) sub ON sub.zip = t.zip AND sub.buyer_entity_id = t.buyer_entity_id
       WHERE t.zip = $1
         AND t.recorded_date >= $2
       GROUP BY t.zip, t.state`,
      [zip, windowStart.toISOString()]
    );

    if (rows.length === 0) return null;
    return this.upsertZipLiquidity(rows[0]!, windowStart, new Date());
  }

  private async upsertZipLiquidity(
    row: ZipAggRow,
    windowStart: Date,
    windowEnd: Date
  ): Promise<ZipLiquidity> {
    const totalTx       = parseInt(row.total_transactions, 10);
    const uniqueBuyers  = parseInt(row.unique_buyer_count, 10);
    const repeatBuyers  = parseInt(row.repeat_buyer_count, 10);
    const tx90d         = parseInt(row.tx_last_90d, 10);
    const tx180d        = parseInt(row.tx_last_180d, 10);
    const tx12mo        = parseInt(row.tx_last_12mo, 10);
    const tx24mo        = parseInt(row.tx_last_24mo, 10);
    const monthsActive  = parseInt(row.months_with_activity, 10);

    const repeatRatio = uniqueBuyers > 0 ? Math.round((repeatBuyers / uniqueBuyers) * 10000) / 10000 : 0;

    const windowMonths = ANALYSIS_WINDOW_MONTHS;
    const avgPerMonth = totalTx > 0 ? Math.round((totalTx / windowMonths) * 100) / 100 : null;

    const velocityScore    = scoreVelocity(tx90d, tx12mo);
    const depthScore       = scoreDepth(uniqueBuyers, repeatBuyers);
    const consistencyScore = scoreConsistency(monthsActive, windowMonths);

    const liquidityScore = Math.round(
      velocityScore * WEIGHTS.velocity +
      depthScore    * WEIGHTS.depth +
      consistencyScore * WEIGHTS.consistency
    );

    const liquidityClass = computeLiquidityClass(liquidityScore, uniqueBuyers, tx90d);
    const exitCertainty  = computeExitCertainty(liquidityScore, liquidityClass, tx90d);

    const upserted = await query<ZipLiquidity>(
      `INSERT INTO zip_liquidity (
         zip, state, city,
         total_transactions, unique_buyer_count, repeat_buyer_count, repeat_buyer_ratio,
         transactions_last_90d, transactions_last_180d, transactions_last_12mo, transactions_last_24mo,
         avg_transactions_per_month,
         velocity_score, depth_score, consistency_score, liquidity_score,
         liquidity_class, exit_certainty,
         analysis_window_start, analysis_window_end,
         computed_at
       ) VALUES (
         $1, $2, $3,
         $4, $5, $6, $7,
         $8, $9, $10, $11,
         $12,
         $13, $14, $15, $16,
         $17, $18,
         $19, $20,
         NOW()
       )
       ON CONFLICT (zip, analysis_window_end) DO UPDATE SET
         state                       = EXCLUDED.state,
         city                        = EXCLUDED.city,
         total_transactions          = EXCLUDED.total_transactions,
         unique_buyer_count          = EXCLUDED.unique_buyer_count,
         repeat_buyer_count          = EXCLUDED.repeat_buyer_count,
         repeat_buyer_ratio          = EXCLUDED.repeat_buyer_ratio,
         transactions_last_90d       = EXCLUDED.transactions_last_90d,
         transactions_last_180d      = EXCLUDED.transactions_last_180d,
         transactions_last_12mo      = EXCLUDED.transactions_last_12mo,
         transactions_last_24mo      = EXCLUDED.transactions_last_24mo,
         avg_transactions_per_month  = EXCLUDED.avg_transactions_per_month,
         velocity_score              = EXCLUDED.velocity_score,
         depth_score                 = EXCLUDED.depth_score,
         consistency_score           = EXCLUDED.consistency_score,
         liquidity_score             = EXCLUDED.liquidity_score,
         liquidity_class             = EXCLUDED.liquidity_class,
         exit_certainty              = EXCLUDED.exit_certainty,
         computed_at                 = NOW()
       RETURNING *`,
      [
        row.zip, row.state, row.city,
        totalTx, uniqueBuyers, repeatBuyers, repeatRatio,
        tx90d, tx180d, tx12mo, tx24mo,
        avgPerMonth,
        velocityScore, depthScore, consistencyScore, liquidityScore,
        liquidityClass, exitCertainty,
        windowStart.toISOString(), windowEnd.toISOString(),
      ]
    );

    return upserted[0]!;
  }

  /**
   * Fetch the most recent liquidity snapshot for a ZIP.
   * Returns null if no data exists (honest absence — never fabricate a score).
   */
  async getLiquidity(zip: string): Promise<ZipLiquidity | null> {
    const rows = await query<ZipLiquidity>(
      `SELECT * FROM zip_liquidity
       WHERE zip = $1
       ORDER BY computed_at DESC
       LIMIT 1`,
      [zip]
    );
    return rows[0] ?? null;
  }

  /**
   * Fetch top-N ZIPs by exit certainty for a given state.
   */
  async getTopZipsByExitCertainty(
    state: string,
    limit = 25
  ): Promise<ZipLiquidity[]> {
    return query<ZipLiquidity>(
      `SELECT DISTINCT ON (zip) *
       FROM zip_liquidity
       WHERE state = $1
       ORDER BY zip, computed_at DESC, exit_certainty DESC
       LIMIT $2`,
      [state, limit]
    );
  }

  /**
   * Heat map: all ZIPs with their latest liquidity scores for a state.
   */
  async getHeatMap(state: string): Promise<ZipLiquidity[]> {
    return query<ZipLiquidity>(
      `SELECT DISTINCT ON (zip) *
       FROM zip_liquidity
       WHERE state = $1
       ORDER BY zip, computed_at DESC`,
      [state]
    );
  }
}

export const zipLiquidityEngine = new ZipLiquidityEngine();
