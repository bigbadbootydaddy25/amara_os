/**
 * Writes AMARA cash buyer registry files to /output/.
 *
 * Outputs:
 *   cash_buyers_raw.json       — all grouped entities with full transaction arrays
 *   cash_buyers_registry.json  — AMARA-format registry (no raw transactions)
 *   scrape_log.json            — run metadata: timestamps, records, errors
 */

import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = join(__dirname, '..', 'output');

function ensureOutputDir() {
  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }
}

function writeJson(filename, data) {
  const filepath = join(OUTPUT_DIR, filename);
  writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf8');
  console.log(`[exporter] Wrote ${filepath}`);
  return filepath;
}

// ─── Registry shape ───────────────────────────────────────────────────────────

function toRegistryEntry(entity) {
  return {
    name: entity.name,
    type: entity.type,
    purchase_count: entity.purchase_count,
    cash_count: entity.cash_purchases,
    zips: entity.zips,
    markets: entity.markets,
    min_price: entity.min_price,
    max_price: entity.max_price,
    last_purchase: entity.last_purchase_date,
    signal_strength: entity.signal_strength,
    strategy: entity.strategy,
  };
}

// ─── Main export function ─────────────────────────────────────────────────────

/**
 * @param {Array} buyers           — output of grouper.groupBuyers()
 * @param {Object} stats           — summary stats from grouper
 * @param {Array} scraperResults   — raw scraper results (for log)
 * @param {Date} runStart          — when the run began
 */
export function exportResults(buyers, stats, scraperResults, runStart) {
  ensureOutputDir();

  const runEnd = new Date();
  const durationSec = ((runEnd - runStart) / 1000).toFixed(1);

  // 1. Raw file — includes transaction arrays
  const rawData = {
    generated_at: runEnd.toISOString(),
    run_duration_sec: parseFloat(durationSec),
    total_buyers: buyers.length,
    buyers,
  };
  writeJson('cash_buyers_raw.json', rawData);

  // 2. Registry file — AMARA format, no raw transaction arrays
  const registry = buyers.map(toRegistryEntry);
  const registryData = {
    generated_at: runEnd.toISOString(),
    total_buyers: registry.length,
    buyers: registry,
  };
  writeJson('cash_buyers_registry.json', registryData);

  // 3. Scrape log
  const logEntries = (scraperResults || []).map((r) => {
    if (!r) return null;
    const cashFlagged = (r.transactions || []).filter((t) => t.cash_flag).length;
    return {
      timestamp: runEnd.toISOString(),
      county: r.county,
      records_pulled: r.transactions?.length ?? 0,
      cash_flagged: cashFlagged,
      errors: r.errors ?? [],
      status: (r.errors?.length ?? 0) > 0 ? 'partial' : 'ok',
    };
  }).filter(Boolean);

  const scrapeLog = {
    run_started: runStart.toISOString(),
    run_completed: runEnd.toISOString(),
    run_duration_sec: parseFloat(durationSec),
    summary: {
      total_records: stats.total_transactions,
      total_repeat_buyers: stats.total_buyers_found,
      signal_HIGH: stats.by_signal?.HIGH ?? 0,
      signal_MEDIUM: stats.by_signal?.MEDIUM ?? 0,
      signal_LOW: stats.by_signal?.LOW ?? 0,
    },
    counties: logEntries,
  };
  writeJson('scrape_log.json', scrapeLog);

  return { rawPath: join(OUTPUT_DIR, 'cash_buyers_raw.json'), registryPath: join(OUTPUT_DIR, 'cash_buyers_registry.json'), logPath: join(OUTPUT_DIR, 'scrape_log.json') };
}

// ─── Optional PostgreSQL writer ───────────────────────────────────────────────

/**
 * Writes buyers to PostgreSQL if PG_CONNECTION_STRING env var is set.
 * Table schema is created if not exists.
 */
export async function writeToPostgres(buyers) {
  const connStr = process.env.PG_CONNECTION_STRING;
  if (!connStr) {
    console.log('[exporter] PG_CONNECTION_STRING not set — skipping Postgres write');
    return;
  }

  let pg;
  try {
    pg = await import('pg');
  } catch {
    console.warn('[exporter] pg package not available — skipping Postgres write');
    return;
  }

  const { Client } = pg.default || pg;
  const client = new Client({ connectionString: connStr });

  try {
    await client.connect();

    // Create table if not exists
    await client.query(`
      CREATE TABLE IF NOT EXISTS cash_buyers (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        normalized_key TEXT,
        type TEXT,
        strategy TEXT,
        purchase_count INTEGER,
        cash_count INTEGER,
        zips TEXT[],
        markets TEXT[],
        min_price NUMERIC,
        max_price NUMERIC,
        last_purchase DATE,
        signal_strength TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(normalized_key)
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS cash_buyer_transactions (
        id SERIAL PRIMARY KEY,
        buyer_key TEXT,
        source_county TEXT,
        grantee TEXT,
        grantor TEXT,
        document_date DATE,
        document_type TEXT,
        document_number TEXT,
        apn TEXT,
        consideration NUMERIC,
        address TEXT,
        zip TEXT,
        cash_flag BOOLEAN,
        has_dot BOOLEAN,
        scraped_at TIMESTAMPTZ,
        UNIQUE(source_county, document_number)
      )
    `);

    let inserted = 0;
    let updated = 0;

    for (const buyer of buyers) {
      // Upsert buyer entity
      const res = await client.query(
        `INSERT INTO cash_buyers
           (name, normalized_key, type, strategy, purchase_count, cash_count,
            zips, markets, min_price, max_price, last_purchase, signal_strength, updated_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW())
         ON CONFLICT (normalized_key)
         DO UPDATE SET
           purchase_count = EXCLUDED.purchase_count,
           cash_count = EXCLUDED.cash_count,
           zips = EXCLUDED.zips,
           markets = EXCLUDED.markets,
           min_price = EXCLUDED.min_price,
           max_price = EXCLUDED.max_price,
           last_purchase = EXCLUDED.last_purchase,
           signal_strength = EXCLUDED.signal_strength,
           updated_at = NOW()
         RETURNING (xmax = 0) AS inserted`,
        [
          buyer.name,
          buyer.normalized_key,
          buyer.type,
          buyer.strategy,
          buyer.purchase_count,
          buyer.cash_purchases,
          buyer.zips,
          buyer.markets,
          buyer.min_price,
          buyer.max_price,
          buyer.last_purchase_date || null,
          buyer.signal_strength,
        ]
      );

      if (res.rows[0]?.inserted) inserted++;
      else updated++;

      // Upsert individual transactions
      for (const t of buyer.transactions || []) {
        await client.query(
          `INSERT INTO cash_buyer_transactions
             (buyer_key, source_county, grantee, grantor, document_date, document_type,
              document_number, apn, consideration, address, zip, cash_flag, has_dot, scraped_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
           ON CONFLICT (source_county, document_number) DO NOTHING`,
          [
            buyer.normalized_key,
            t.source_county,
            t.grantee,
            t.grantor,
            t.document_date || null,
            t.document_type,
            t.document_number,
            t.apn,
            t.consideration,
            t.address,
            t.zip,
            t.cash_flag,
            t.has_dot,
            t.scraped_at || null,
          ]
        ).catch(() => {}); // Non-fatal: skip duplicate transactions
      }
    }

    console.log(`[exporter] Postgres: ${inserted} new buyers, ${updated} updated`);
  } catch (err) {
    console.error(`[exporter] Postgres write failed: ${err.message}`);
  } finally {
    await client.end();
  }
}
