/**
 * ZipLiquidity — a heat map scoring the exit certainty for a given ZIP code.
 *
 * Built entirely from transaction records. A ZIP with no recorded transactions
 * receives a score of 0 and class 'none'. No market assumptions are made.
 */

export type LiquidityClass =
  | 'A'    // High liquidity — deep buyer pool, fast velocity
  | 'B'    // Moderate liquidity — reliable buyer activity
  | 'C'    // Low liquidity — thin buyer pool, slow velocity
  | 'D'    // Very low liquidity — sparse activity
  | 'none'; // No recorded transaction history for this ZIP

/**
 * Exit certainty: probability that a deal in this ZIP will find a qualified
 * buyer within 90 days, scored 0–100 from recorded market data.
 */
export type ExitCertaintyScore = number; // 0–100

export interface ZipLiquidity {
  id: string;
  zip: string;
  state: string;
  city: string | null;

  // ── Core Transaction Metrics ─────────────────────────────────────────────
  total_transactions: number;
  unique_buyer_count: number;
  repeat_buyer_count: number;       // Buyers with 2+ transactions in this ZIP
  repeat_buyer_ratio: number;       // repeat_buyer_count / unique_buyer_count

  // ── Velocity Metrics ─────────────────────────────────────────────────────
  transactions_last_90d: number;
  transactions_last_180d: number;
  transactions_last_12mo: number;
  transactions_last_24mo: number;
  avg_transactions_per_month: number | null;  // Over the active window

  // ── Derived Scores ───────────────────────────────────────────────────────
  velocity_score: number;           // 0–100: rate of recent activity
  depth_score: number;              // 0–100: breadth of unique buyers
  consistency_score: number;        // 0–100: how steady activity is over time
  liquidity_score: number;          // 0–100: composite
  liquidity_class: LiquidityClass;
  exit_certainty: ExitCertaintyScore;

  // ── Computation Window ───────────────────────────────────────────────────
  analysis_window_start: Date;
  analysis_window_end: Date;
  computed_at: Date;

  created_at: Date;
  updated_at: Date;
}

/**
 * Thresholds that define liquidity classification.
 * Tunable without touching scoring logic.
 */
export const LIQUIDITY_THRESHOLDS = {
  CLASS_A: { min_score: 75, min_unique_buyers: 10, min_velocity_90d: 5 },
  CLASS_B: { min_score: 50, min_unique_buyers: 5,  min_velocity_90d: 2 },
  CLASS_C: { min_score: 25, min_unique_buyers: 2,  min_velocity_90d: 1 },
  CLASS_D: { min_score: 1,  min_unique_buyers: 1,  min_velocity_90d: 0 },
} as const;
