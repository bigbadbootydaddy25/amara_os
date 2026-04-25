/**
 * AMARA Cash Buyer Ingestion — Orchestrator
 *
 * Runs all 6 county scrapers in parallel (Promise.allSettled).
 * Individual scraper failures are caught and logged without stopping the run.
 * All results are passed to the grouper, then exported to JSON + optional Postgres.
 *
 * Usage:
 *   node main.js
 *   PG_CONNECTION_STRING=postgres://... node main.js
 */

import { scrapeDallas } from './scrapers/dallas.js';
import { scrapeHarris } from './scrapers/harris.js';
import { scrapeBexar } from './scrapers/bexar.js';
import { scrapeClark } from './scrapers/clark.js';
import { scrapeMaricopa } from './scrapers/maricopa.js';
import { scrapePolk } from './scrapers/polk.js';
import { groupBuyers } from './processor/grouper.js';
import { exportResults, writeToPostgres } from './output/exporter.js';

const SCRAPERS = [
  { name: 'DALLAS_TX',   fn: scrapeDallas },
  { name: 'HARRIS_TX',   fn: scrapeHarris },
  { name: 'BEXAR_TX',    fn: scrapeBexar },
  { name: 'CLARK_NV',    fn: scrapeClark },
  { name: 'MARICOPA_AZ', fn: scrapeMaricopa },
  { name: 'POLK_FL',     fn: scrapePolk },
];

async function run() {
  const runStart = new Date();
  console.log(`\n${'═'.repeat(60)}`);
  console.log(`  AMARA Cash Buyer Ingestion`);
  console.log(`  Started: ${runStart.toISOString()}`);
  console.log(`  Markets: ${SCRAPERS.map((s) => s.name).join(', ')}`);
  console.log(`${'═'.repeat(60)}\n`);

  // Run all scrapers in parallel — individual failures don't kill the run
  const settled = await Promise.allSettled(
    SCRAPERS.map(({ name, fn }) =>
      fn().catch((err) => {
        console.error(`[${name}] Unhandled rejection: ${err.message}`);
        return { county: name, transactions: [], errors: [err.message] };
      })
    )
  );

  // Collect results — fulfilled scrapers return county data; rejected ones get an empty stub
  const scraperResults = settled.map((result, i) => {
    if (result.status === 'fulfilled') {
      return result.value;
    }
    console.error(`[${SCRAPERS[i].name}] Promise rejected: ${result.reason}`);
    return { county: SCRAPERS[i].name, transactions: [], errors: [String(result.reason)] };
  });

  // Group and score buyers
  console.log('\n[main] Running grouper...');
  const { buyers, stats } = groupBuyers(scraperResults);

  // Export to JSON files
  console.log('[main] Exporting results...');
  const { rawPath, registryPath, logPath } = exportResults(buyers, stats, scraperResults, runStart);

  // Optional Postgres write (non-blocking)
  if (process.env.PG_CONNECTION_STRING) {
    console.log('[main] Writing to Postgres...');
    await writeToPostgres(buyers);
  }

  // Print summary
  console.log(`\n${'═'.repeat(60)}`);
  console.log('  AMARA Ingestion Complete');
  console.log(`${'═'.repeat(60)}`);

  console.log('\n  By Market:');
  for (const r of scraperResults) {
    const cashFlagged = (r.transactions || []).filter((t) => t.cash_flag).length;
    const errMsg = r.errors?.length > 0 ? ` ⚠  ${r.errors.join('; ')}` : '';
    console.log(
      `    ${r.county.padEnd(14)} ${String(r.transactions?.length ?? 0).padStart(5)} records   ` +
      `${String(cashFlagged).padStart(4)} cash flagged${errMsg}`
    );
  }

  console.log('\n  Buyer Registry:');
  console.log(`    Total transactions : ${stats.total_transactions}`);
  console.log(`    Repeat buyers found: ${stats.total_buyers_found}`);
  console.log(`    HIGH signal        : ${stats.by_signal?.HIGH ?? 0}`);
  console.log(`    MEDIUM signal      : ${stats.by_signal?.MEDIUM ?? 0}`);
  console.log(`    LOW signal         : ${stats.by_signal?.LOW ?? 0}`);
  console.log(`    Flippers           : ${stats.by_type?.flipper ?? 0}`);
  console.log(`    Landlords          : ${stats.by_type?.landlord ?? 0}`);
  console.log(`    Builders           : ${stats.by_type?.builder ?? 0}`);

  console.log('\n  Output files:');
  console.log(`    ${rawPath}`);
  console.log(`    ${registryPath}`);
  console.log(`    ${logPath}`);

  const runEnd = new Date();
  const durationMin = ((runEnd - runStart) / 60000).toFixed(1);
  console.log(`\n  Duration: ${durationMin} minutes`);
  console.log(`${'═'.repeat(60)}\n`);
}

run().catch((err) => {
  console.error('Fatal orchestrator error:', err);
  process.exit(1);
});
