/**
 * BuyBoxInferenceService
 *
 * Derives a buyer's buy box from their actual recorded acquisitions.
 * A buy box is NEVER authored by hand or seeded with default values.
 *
 * A buy box is only materialized when:
 *   - The buyer has ≥ MIN_TX_FOR_INFERENCE recorded transactions
 *
 * Fields that cannot be derived are stored as null.
 * The `derived_from_transaction_count` field on every BuyBox
 * makes the evidential basis explicit and auditable.
 */

import { query, queryOne } from '../db/client';
import type { BuyBox, ZipPreference, PropertyTypePreference } from '../models/buybox';
import type { PropertyType } from '../models/transaction';

const MIN_TX_FOR_INFERENCE = 2;

// ─── Percentile helper ────────────────────────────────────────────────────────

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo]!;
  return sorted[lo]! + (sorted[hi]! - sorted[lo]!) * (idx - lo);
}

function median(sorted: number[]): number {
  return percentile(sorted, 50);
}

// ─── Database row types ────────────────────────────────────────────────────────

interface TransactionRow {
  id: string;
  recorded_date: Date;
  close_date: Date | null;
  purchase_price: string;
  zip: string;
  state: string;
  city: string;
  property_type: PropertyType;
  sqft: number | null;
  lot_size_sqft: number | null;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export class BuyBoxInferenceService {
  /**
   * Infer and persist the buy box for a buyer from their full transaction history.
   * Returns null if the buyer has fewer than MIN_TX_FOR_INFERENCE transactions.
   */
  async inferBuyBox(buyerEntityId: string): Promise<BuyBox | null> {
    const txRows = await query<TransactionRow>(
      `SELECT id, recorded_date, close_date, purchase_price, zip, state, city,
              property_type, sqft, lot_size_sqft
       FROM transactions
       WHERE buyer_entity_id = $1
       ORDER BY recorded_date ASC`,
      [buyerEntityId]
    );

    if (txRows.length < MIN_TX_FOR_INFERENCE) {
      return null; // Not enough data — do not fabricate
    }

    // ── Price analysis ──────────────────────────────────────────────────────
    const prices = txRows
      .map((r) => parseFloat(r.purchase_price))
      .filter((p) => p > 0)
      .sort((a, b) => a - b);

    const priceRange = prices.length > 0
      ? {
          min: prices[0]!,
          max: prices[prices.length - 1]!,
          avg: Math.round(prices.reduce((s, p) => s + p, 0) / prices.length),
          median: Math.round(median(prices)),
          p25: Math.round(percentile(prices, 25)),
          p75: Math.round(percentile(prices, 75)),
          sample_count: prices.length,
        }
      : null;

    // ── Geographic preferences ───────────────────────────────────────────────
    const zipCounts = new Map<string, number>();
    const stateCounts = new Map<string, number>();
    const cityCounts = new Map<string, number>();

    for (const tx of txRows) {
      zipCounts.set(tx.zip, (zipCounts.get(tx.zip) ?? 0) + 1);
      stateCounts.set(tx.state, (stateCounts.get(tx.state) ?? 0) + 1);
      if (tx.city) cityCounts.set(tx.city, (cityCounts.get(tx.city) ?? 0) + 1);
    }

    const preferredZips: ZipPreference[] = Array.from(zipCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([zip, count]) => ({
        zip,
        transaction_count: count,
        pct_of_total: Math.round((count / txRows.length) * 10000) / 100,
      }));

    const preferredStates = Array.from(stateCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([s]) => s);

    const preferredCities = Array.from(cityCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([c]) => c);

    // ── Property type preferences ────────────────────────────────────────────
    const typeCounts = new Map<PropertyType, { count: number; prices: number[] }>();
    for (const tx of txRows) {
      const entry = typeCounts.get(tx.property_type) ?? { count: 0, prices: [] };
      entry.count++;
      const price = parseFloat(tx.purchase_price);
      if (price > 0) entry.prices.push(price);
      typeCounts.set(tx.property_type, entry);
    }

    const propertyTypes: PropertyTypePreference[] = Array.from(typeCounts.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .map(([type, data]) => ({
        property_type: type,
        transaction_count: data.count,
        pct_of_total: Math.round((data.count / txRows.length) * 10000) / 100,
        avg_price:
          data.prices.length > 0
            ? Math.round(data.prices.reduce((s, p) => s + p, 0) / data.prices.length)
            : null,
      }));

    // ── Physical characteristics ─────────────────────────────────────────────
    const sqftValues = txRows.map((r) => r.sqft).filter((v): v is number => v !== null);
    const lotValues = txRows.map((r) => r.lot_size_sqft).filter((v): v is number => v !== null);

    const avgSqft =
      sqftValues.length > 0
        ? Math.round(sqftValues.reduce((s, v) => s + v, 0) / sqftValues.length)
        : null;

    const sqftRange =
      sqftValues.length > 0
        ? { min: Math.min(...sqftValues), max: Math.max(...sqftValues) }
        : null;

    const avgLotSize =
      lotValues.length > 0
        ? Math.round(lotValues.reduce((s, v) => s + v, 0) / lotValues.length)
        : null;

    // ── Acquisition speed ────────────────────────────────────────────────────
    const closeSpeeds: number[] = [];
    for (const tx of txRows) {
      if (tx.close_date && tx.recorded_date) {
        const days =
          (new Date(tx.recorded_date).getTime() - new Date(tx.close_date).getTime()) /
          86_400_000;
        if (days >= 0 && days < 365) closeSpeeds.push(days);
      }
    }
    const avgDaysToClose =
      closeSpeeds.length > 0
        ? Math.round(closeSpeeds.reduce((s, d) => s + d, 0) / closeSpeeds.length * 10) / 10
        : null;

    // ── Acquisition frequency ────────────────────────────────────────────────
    let acquisitionsPerYear: number | null = null;
    if (txRows.length >= 2) {
      const first = new Date(txRows[0]!.recorded_date).getTime();
      const last = new Date(txRows[txRows.length - 1]!.recorded_date).getTime();
      const spanYears = (last - first) / (86_400_000 * 365.25);
      acquisitionsPerYear =
        spanYears > 0
          ? Math.round((txRows.length / spanYears) * 100) / 100
          : null;
    }

    // ── Persist / upsert ─────────────────────────────────────────────────────
    const isStale = (() => {
      const lastTx = txRows[txRows.length - 1];
      if (!lastTx) return true;
      const daysSince =
        (Date.now() - new Date(lastTx.recorded_date).getTime()) / 86_400_000;
      return daysSince > 180;
    })();

    const rows = await query<BuyBox>(
      `INSERT INTO buy_boxes (
         buyer_entity_id,
         price_min, price_max, price_avg, price_median, price_p25, price_p75, price_sample_count,
         preferred_zips, preferred_states, preferred_cities,
         property_types,
         avg_sqft, sqft_min, sqft_max,
         avg_lot_size_sqft,
         avg_days_to_close,
         acquisitions_per_year,
         derived_from_transaction_count,
         last_derived_at,
         is_stale
       ) VALUES (
         $1,
         $2, $3, $4, $5, $6, $7, $8,
         $9, $10, $11,
         $12,
         $13, $14, $15,
         $16,
         $17,
         $18,
         $19,
         NOW(),
         $20
       )
       ON CONFLICT (buyer_entity_id) DO UPDATE SET
         price_min                        = EXCLUDED.price_min,
         price_max                        = EXCLUDED.price_max,
         price_avg                        = EXCLUDED.price_avg,
         price_median                     = EXCLUDED.price_median,
         price_p25                        = EXCLUDED.price_p25,
         price_p75                        = EXCLUDED.price_p75,
         price_sample_count               = EXCLUDED.price_sample_count,
         preferred_zips                   = EXCLUDED.preferred_zips,
         preferred_states                 = EXCLUDED.preferred_states,
         preferred_cities                 = EXCLUDED.preferred_cities,
         property_types                   = EXCLUDED.property_types,
         avg_sqft                         = EXCLUDED.avg_sqft,
         sqft_min                         = EXCLUDED.sqft_min,
         sqft_max                         = EXCLUDED.sqft_max,
         avg_lot_size_sqft                = EXCLUDED.avg_lot_size_sqft,
         avg_days_to_close                = EXCLUDED.avg_days_to_close,
         acquisitions_per_year            = EXCLUDED.acquisitions_per_year,
         derived_from_transaction_count   = EXCLUDED.derived_from_transaction_count,
         last_derived_at                  = NOW(),
         is_stale                         = EXCLUDED.is_stale
       RETURNING *`,
      [
        buyerEntityId,
        priceRange?.min ?? null,
        priceRange?.max ?? null,
        priceRange?.avg ?? null,
        priceRange?.median ?? null,
        priceRange?.p25 ?? null,
        priceRange?.p75 ?? null,
        priceRange?.sample_count ?? 0,
        JSON.stringify(preferredZips),
        preferredStates,
        preferredCities,
        JSON.stringify(propertyTypes),
        avgSqft,
        sqftRange?.min ?? null,
        sqftRange?.max ?? null,
        avgLotSize,
        avgDaysToClose,
        acquisitionsPerYear,
        txRows.length,
        isStale,
      ]
    );

    return rows[0] ?? null;
  }

  /**
   * Refresh all buy boxes where the last derivation is stale
   * (no derivation in the last 24 hours, or new transactions arrived).
   */
  async refreshStaleBuyBoxes(pageSize = 100): Promise<{ processed: number; errors: number }> {
    const staleRows = await query<{ buyer_entity_id: string }>(
      `SELECT DISTINCT t.buyer_entity_id
       FROM transactions t
       LEFT JOIN buy_boxes bb ON bb.buyer_entity_id = t.buyer_entity_id
       WHERE bb.buyer_entity_id IS NULL
          OR bb.last_derived_at < t.updated_at
          OR bb.last_derived_at < NOW() - INTERVAL '24 hours'
       LIMIT $1`,
      [pageSize]
    );

    let errors = 0;
    for (const { buyer_entity_id } of staleRows) {
      try {
        await this.inferBuyBox(buyer_entity_id);
      } catch (e) {
        errors++;
        console.error(`[buybox_inference] failed for buyer ${buyer_entity_id}:`, e);
      }
    }

    return { processed: staleRows.length, errors };
  }

  /**
   * Fetch buy box for display — returns null if none exists (honest absence).
   */
  async getBuyBox(buyerEntityId: string): Promise<BuyBox | null> {
    return queryOne<BuyBox>(
      `SELECT * FROM buy_boxes WHERE buyer_entity_id = $1`,
      [buyerEntityId]
    );
  }
}

export const buyBoxInferenceService = new BuyBoxInferenceService();
