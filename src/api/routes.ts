/**
 * Buyer Intelligence Engine — API Routes
 *
 * All endpoints return truth-preserving data: no buyer is labeled verified
 * without passing transaction-based rules, no buy box is fabricated, and
 * exit confidence always traces to recorded transaction history.
 */

import { Router, Request, Response, NextFunction } from 'express';
import { buyerVerificationService } from '../services/buyer_verification';
import { buyBoxInferenceService } from '../services/buybox_inference';
import { zipLiquidityEngine } from '../services/zip_liquidity';
import { dealEngine, DealInput } from '../engine/deal_engine';
import { classifyStrategy, applyStrategyToBuyBox } from '../services/strategy_classifier';
import { query, queryOne } from '../db/client';
import type { BuyerEntity } from '../models/buyer';
import type { BuyBox, PropertyTypePreference, ZipPreference } from '../models/buybox';
import type { Transaction } from '../models/transaction';

export const router = Router();

// ─── Error wrapper ────────────────────────────────────────────────────────────

function asyncHandler(fn: (req: Request, res: Response, next: NextFunction) => Promise<void>) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}

// ─── BUYERS ──────────────────────────────────────────────────────────────────

/**
 * GET /buyers
 * List buyers. Default: only verified_active (primary disposition layer).
 * Pass ?tier=all to include all tiers.
 */
router.get(
  '/buyers',
  asyncHandler(async (req, res) => {
    const tier = req.query['tier'] as string | undefined;
    const limit = Math.min(parseInt((req.query['limit'] as string) || '50', 10), 200);
    const offset = parseInt((req.query['offset'] as string) || '0', 10);

    let sql: string;
    let params: unknown[];

    if (!tier || tier === 'verified_active') {
      sql = `SELECT * FROM buyer_entities WHERE tier = 'verified_active'
             ORDER BY (verification_flags->>'transaction_pace_per_year')::numeric DESC NULLS LAST
             LIMIT $1 OFFSET $2`;
      params = [limit, offset];
    } else if (tier === 'all') {
      sql = `SELECT * FROM buyer_entities
             ORDER BY tier, updated_at DESC
             LIMIT $1 OFFSET $2`;
      params = [limit, offset];
    } else {
      sql = `SELECT * FROM buyer_entities WHERE tier = $1
             ORDER BY updated_at DESC LIMIT $2 OFFSET $3`;
      params = [tier, limit, offset];
    }

    const buyers = await query<BuyerEntity>(sql, params);
    res.json({ buyers, count: buyers.length });
  })
);

/**
 * GET /buyers/:id
 * Full buyer profile including verification flags.
 */
router.get(
  '/buyers/:id',
  asyncHandler(async (req, res) => {
    const buyer = await queryOne<BuyerEntity>(
      `SELECT * FROM buyer_entities WHERE id = $1`,
      [req.params['id']]
    );
    if (!buyer) return void res.status(404).json({ error: 'Buyer not found' });
    res.json(buyer);
  })
);

/**
 * POST /buyers
 * Register a new buyer entity. Tier starts as insufficient_data until
 * transactions are recorded and verification is run.
 */
router.post(
  '/buyers',
  asyncHandler(async (req, res) => {
    const { name, email, phone, website } = req.body as {
      name?: string; email?: string; phone?: string; website?: string;
    };

    if (!name || typeof name !== 'string' || name.trim().length === 0) {
      return void res.status(400).json({ error: 'name is required' });
    }

    const rows = await query<BuyerEntity>(
      `INSERT INTO buyer_entities (name, email, phone, website, raw_name_variants)
       VALUES ($1, $2, $3, $4, ARRAY[$1])
       RETURNING *`,
      [name.trim(), email ?? null, phone ?? null, website ?? null]
    );

    res.status(201).json(rows[0]);
  })
);

/**
 * POST /buyers/:id/verify
 * Trigger (re)verification of a buyer from their transaction record.
 */
router.post(
  '/buyers/:id/verify',
  asyncHandler(async (req, res) => {
    const buyer = await buyerVerificationService.verifyBuyer(req.params['id']!);
    res.json(buyer);
  })
);

// ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

/**
 * GET /buyers/:id/transactions
 * All recorded transactions for a buyer.
 */
router.get(
  '/buyers/:id/transactions',
  asyncHandler(async (req, res) => {
    const txs = await query<Transaction>(
      `SELECT * FROM transactions WHERE buyer_entity_id = $1 ORDER BY recorded_date DESC`,
      [req.params['id']]
    );
    res.json({ transactions: txs, count: txs.length });
  })
);

/**
 * POST /buyers/:id/transactions
 * Record a new transaction for a buyer. Triggers async re-verification
 * and buy box re-inference.
 */
router.post(
  '/buyers/:id/transactions',
  asyncHandler(async (req, res) => {
    const {
      recorded_date, close_date, purchase_price,
      address, city, state, zip,
      property_type, sqft, lot_size_sqft, bedrooms, bathrooms, year_built,
      source, source_id,
    } = req.body as Partial<Transaction>;

    if (!recorded_date || !purchase_price || !address || !city || !state || !zip || !source) {
      return void res.status(400).json({
        error: 'required: recorded_date, purchase_price, address, city, state, zip, source',
      });
    }

    const rows = await query<Transaction>(
      `INSERT INTO transactions (
         buyer_entity_id, recorded_date, close_date, purchase_price,
         address, city, state, zip,
         property_type, sqft, lot_size_sqft, bedrooms, bathrooms, year_built,
         source, source_id
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
       RETURNING *`,
      [
        req.params['id'], recorded_date, close_date ?? null, purchase_price,
        address, city, state, zip,
        property_type ?? 'unknown', sqft ?? null, lot_size_sqft ?? null,
        bedrooms ?? null, bathrooms ?? null, year_built ?? null,
        source, source_id ?? null,
      ]
    );

    const tx = rows[0]!;

    // Fire-and-forget: re-verify buyer, re-infer buy box, update ZIP liquidity
    setImmediate(async () => {
      try {
        await buyerVerificationService.verifyBuyer(req.params['id']!);
        const buyBox = await buyBoxInferenceService.inferBuyBox(req.params['id']!);
        if (buyBox) {
          // Re-classify strategy after new buy box data
          const priceSpreadRatio =
            buyBox.price_range && buyBox.price_range.median > 0
              ? (buyBox.price_range.p75 - buyBox.price_range.p25) / buyBox.price_range.median
              : null;

          const buyer = await queryOne<BuyerEntity>(
            `SELECT * FROM buyer_entities WHERE id = $1`,
            [req.params['id']]
          );
          if (buyer) {
            const classResult = classifyStrategy({
              propertyTypes: (buyBox.property_types ?? []) as PropertyTypePreference[],
              priceAvg: buyBox.price_range?.avg ?? null,
              priceSpreadRatio,
              acquisitionsPerYear: buyBox.acquisitions_per_year,
              uniqueZipCount: ((buyBox.preferred_zips ?? []) as ZipPreference[]).length,
              totalTransactions: buyBox.derived_from_transaction_count,
              entityFlags: buyer.verification_flags,
            });
            await applyStrategyToBuyBox(buyer.id, classResult);
          }
        }
        await zipLiquidityEngine.computeForZip(zip as string);
      } catch (e) {
        console.error('[post-transaction update] error:', e);
      }
    });

    res.status(201).json(tx);
  })
);

// ─── BUY BOXES ───────────────────────────────────────────────────────────────

/**
 * GET /buyers/:id/buybox
 * Return the inferred buy box for a buyer.
 * Returns 404 with clear message if insufficient transaction data.
 */
router.get(
  '/buyers/:id/buybox',
  asyncHandler(async (req, res) => {
    const buyBox = await buyBoxInferenceService.getBuyBox(req.params['id']!);
    if (!buyBox) {
      return void res.status(404).json({
        error: 'No buy box available — insufficient transaction history',
        minimum_transactions_required: 2,
      });
    }
    res.json(buyBox);
  })
);

/**
 * POST /buyers/:id/buybox/infer
 * Explicitly trigger buy box re-inference from current transaction history.
 */
router.post(
  '/buyers/:id/buybox/infer',
  asyncHandler(async (req, res) => {
    const buyBox = await buyBoxInferenceService.inferBuyBox(req.params['id']!);
    if (!buyBox) {
      return void res.status(422).json({
        error: 'Cannot infer buy box — buyer has fewer than 2 recorded transactions',
      });
    }
    res.json(buyBox);
  })
);

// ─── ZIP LIQUIDITY ────────────────────────────────────────────────────────────

/**
 * GET /liquidity/:zip
 * Liquidity snapshot for a specific ZIP.
 */
router.get(
  '/liquidity/:zip',
  asyncHandler(async (req, res) => {
    const liquidity = await zipLiquidityEngine.getLiquidity(req.params['zip']!);
    if (!liquidity) {
      return void res.status(404).json({
        error: `No transaction data for ZIP ${req.params['zip']}`,
        exit_certainty: 0,
        liquidity_class: 'none',
      });
    }
    res.json(liquidity);
  })
);

/**
 * GET /liquidity/heatmap/:state
 * Full heat map for a state (all ZIPs with recorded transaction history).
 */
router.get(
  '/liquidity/heatmap/:state',
  asyncHandler(async (req, res) => {
    const heatMap = await zipLiquidityEngine.getHeatMap(
      req.params['state']!.toUpperCase()
    );
    res.json({ state: req.params['state']!.toUpperCase(), zips: heatMap });
  })
);

/**
 * GET /liquidity/top/:state
 * Top ZIPs by exit certainty for a state.
 */
router.get(
  '/liquidity/top/:state',
  asyncHandler(async (req, res) => {
    const limit = Math.min(parseInt((req.query['limit'] as string) || '25', 10), 100);
    const top = await zipLiquidityEngine.getTopZipsByExitCertainty(
      req.params['state']!.toUpperCase(),
      limit
    );
    res.json({ state: req.params['state']!.toUpperCase(), zips: top });
  })
);

// ─── DEAL ENGINE ─────────────────────────────────────────────────────────────

/**
 * POST /deals/score
 * Score a deal against verified buyers and ZIP liquidity.
 * Body: DealInput
 */
router.post(
  '/deals/score',
  asyncHandler(async (req, res) => {
    const { zip, state, asking_price, property_type, sqft, arv, condition } =
      req.body as Partial<DealInput>;

    if (!zip || !asking_price || !property_type) {
      return void res.status(400).json({
        error: 'required: zip, asking_price, property_type',
      });
    }

    const dealScore = await dealEngine.scoreDeal({
      zip,
      state: state ?? '',
      asking_price,
      property_type,
      sqft,
      arv,
      condition,
    });

    res.json(dealScore);
  })
);

/**
 * GET /deals/buyers/:zip
 * Quick lookup: verified buyers active in a ZIP.
 * ?price=&property_type= optional filters.
 */
router.get(
  '/deals/buyers/:zip',
  asyncHandler(async (req, res) => {
    const zip = req.params['zip']!;
    const price = req.query['price'] ? parseFloat(req.query['price'] as string) : 0;
    const propertyType = (req.query['property_type'] as string) || 'sfr';

    const matches = await dealEngine.findBuyersForZip(
      zip,
      price,
      propertyType as DealInput['property_type']
    );

    res.json({ zip, matches, count: matches.length });
  })
);

// ─── ADMIN / BATCH ────────────────────────────────────────────────────────────

/**
 * POST /admin/verify-stale
 * Batch re-verify buyers whose verification is older than 24 hours.
 */
router.post(
  '/admin/verify-stale',
  asyncHandler(async (req, res) => {
    const pageSize = parseInt((req.body as { page_size?: string }).page_size ?? '100', 10);
    const result = await buyerVerificationService.verifyStale(pageSize);
    res.json(result);
  })
);

/**
 * POST /admin/refresh-buyboxes
 * Batch re-infer buy boxes for buyers with new transaction data.
 */
router.post(
  '/admin/refresh-buyboxes',
  asyncHandler(async (req, res) => {
    const pageSize = parseInt((req.body as { page_size?: string }).page_size ?? '100', 10);
    const result = await buyBoxInferenceService.refreshStaleBuyBoxes(pageSize);
    res.json(result);
  })
);

/**
 * POST /admin/compute-liquidity
 * Recompute ZIP liquidity heat map for all ZIPs with recent activity.
 */
router.post(
  '/admin/compute-liquidity',
  asyncHandler(async (_req, res) => {
    const result = await zipLiquidityEngine.computeAll();
    res.json(result);
  })
);
