#!/usr/bin/env node
/**
 * AMARA OS — CLI: processSFRDeals
 *
 * Usage:
 *   node backend/src/cli/processSFRDeals.js \
 *     --properties <path/to/properties.json> \
 *     --buyers     <path/to/buyers.json> \
 *     [--out-dir   <output_dir>]          (default: ./output)
 *
 * Output files:
 *   <out-dir>/approvedDeals.json
 *   <out-dir>/rejectedDeals.json
 *
 * Reads:
 *   properties.json — array of normalized property objects
 *   buyers.json     — array of vetted buyer objects
 *
 * Prints:
 *   Summary counts on completion
 */

'use strict';

const fs   = require('fs');
const path = require('path');
const { processSFRDeals } = require('../deals/processSFRDeals');

// ── Argument parsing ─────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    propertiesPath: null,
    buyersPath:     null,
    outDir:         path.resolve(process.cwd(), 'output'),
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--properties' && args[i + 1]) {
      parsed.propertiesPath = path.resolve(args[++i]);
    } else if (args[i] === '--buyers' && args[i + 1]) {
      parsed.buyersPath = path.resolve(args[++i]);
    } else if (args[i] === '--out-dir' && args[i + 1]) {
      parsed.outDir = path.resolve(args[++i]);
    }
  }

  return parsed;
}

// ── Load sample data if no paths provided ────────────────────────────────────

function loadSampleProperties() {
  // Prices reflect realistic distressed/wholesale asking prices — below MAO ceiling
  return [
    {
      address:      '4812 Crane St, Houston TX',
      zip:          '77008',
      price:        88_000,    // MAO ~$93k at hot ZIP 80% — deal pencils
      sqft:         1_400,
      daysOnMarket: 92,
      description:  'Estate sale, as-is, needs work, priced to sell',
    },
    {
      address:      '2241 Westmoreland Rd, Dallas TX',
      zip:          '75211',
      price:        95_000,    // MAO ~$112k at normal ZIP 75%
      sqft:         1_600,
      daysOnMarket: 75,
      description:  'Investor special — TLC needed, fixer upper, cash buyers welcome',
    },
    {
      address:      '8904 Fuqua St, Houston TX',
      zip:          '77033',
      price:        62_000,    // MAO ~$63k — tight but qualifies
      sqft:         1_100,
      daysOnMarket: 110,
      description:  'Probate sale, estate, bring all offers, priced below market',
    },
    {
      address:      '500 Clean Lane, Dallas TX',
      zip:          '75201',
      price:        350_000,
      sqft:         2_500,
      daysOnMarket: 12,        // rejected at filter — too new, no distress
      description:  'Beautiful updated home, move-in ready, granite counters, new HVAC',
    },
    {
      address:      '3318 W McDowell, Phoenix AZ',
      zip:          '85009',
      price:        118_000,   // MAO ~$124k at hot ZIP 80%
      sqft:         1_300,
      daysOnMarket: 88,
      description:  'Tenant occupied, as-is sale, repairs needed, investor opportunity',
    },
  ];
}

function loadSampleBuyers() {
  return [
    {
      buyerId:      'BUY-0001',
      name:         'Marcus Webb',
      entityName:   'Webb Acquisitions LLC',
      zipCodes:     ['77008', '77009', '77018', '77022', '77026', '77093'],
      propertyTypes:['SFR'],
      minPrice:     80_000,
      maxPrice:     180_000,
      totalDeals:   14,
      monthsInactive: 1,
    },
    {
      buyerId:      'BUY-0002',
      name:         'Diana Reyes',
      entityName:   'Reyes Capital Group LLC',
      zipCodes:     ['75211', '75212', '75220', '75229', '75247'],
      propertyTypes:['SFR'],
      minPrice:     100_000,
      maxPrice:     220_000,
      totalDeals:   9,
      monthsInactive: 2,
    },
    {
      buyerId:      'BUY-0003',
      name:         'Jordan Tate',
      entityName:   'Tate Holdings LLC',
      zipCodes:     ['77033', '77034', '77051', '77085', '77489'],
      propertyTypes:['SFR'],
      minPrice:     70_000,
      maxPrice:     140_000,
      totalDeals:   6,
      monthsInactive: 4,
    },
    {
      buyerId:      'BUY-0005',
      name:         'Carlos Mendez',
      entityName:   'Mendez Realty Investments LLC',
      zipCodes:     ['85009', '85031', '85033', '85035', '85043', '85303'],
      propertyTypes:['SFR'],
      minPrice:     80_000,     // lowered floor to catch the $118k deal
      maxPrice:     320_000,
      totalDeals:   17,
      monthsInactive: 0,
    },
  ];
}

// ── Main ─────────────────────────────────────────────────────────────────────

function main() {
  const { propertiesPath, buyersPath, outDir } = parseArgs();

  // Load data
  let properties, buyers;

  if (propertiesPath) {
    if (!fs.existsSync(propertiesPath)) {
      console.error(`Error: properties file not found: ${propertiesPath}`);
      process.exit(1);
    }
    properties = JSON.parse(fs.readFileSync(propertiesPath, 'utf8'));
    console.log(`Loaded ${properties.length} properties from ${propertiesPath}`);
  } else {
    properties = loadSampleProperties();
    console.log(`Using ${properties.length} sample properties (no --properties provided)`);
  }

  if (buyersPath) {
    if (!fs.existsSync(buyersPath)) {
      console.error(`Error: buyers file not found: ${buyersPath}`);
      process.exit(1);
    }
    buyers = JSON.parse(fs.readFileSync(buyersPath, 'utf8'));
    console.log(`Loaded ${buyers.length} buyers from ${buyersPath}`);
  } else {
    buyers = loadSampleBuyers();
    console.log(`Using ${buyers.length} sample buyers (no --buyers provided)`);
  }

  // Run pipeline
  console.log('\nRunning SFR deal execution pipeline...\n');
  const { approvedDeals, rejectedDeals, summary } = processSFRDeals(properties, buyers);

  // Write output
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const approvedPath = path.join(outDir, 'approvedDeals.json');
  const rejectedPath = path.join(outDir, 'rejectedDeals.json');

  fs.writeFileSync(approvedPath, JSON.stringify(approvedDeals, null, 2), 'utf8');
  fs.writeFileSync(rejectedPath, JSON.stringify(rejectedDeals, null, 2), 'utf8');

  // Print summary
  console.log('━'.repeat(50));
  console.log('DEAL EXECUTION SUMMARY');
  console.log('━'.repeat(50));
  console.log(`  Total input:          ${summary.totalInput}`);
  console.log(`  Passed filter:        ${summary.passedFilter}  (rejected: ${summary.failedFilter})`);
  console.log(`  Passed underwriting:  ${summary.passedUnderwriting}  (rejected: ${summary.failedUnderwriting})`);
  console.log(`  Matched with buyer:   ${summary.matchedWithBuyer}  (no match: ${summary.noMatchFound})`);
  console.log('─'.repeat(50));
  console.log(`  APPROVED DEALS:       ${summary.approvedDeals}`);
  console.log(`  REJECTED DEALS:       ${summary.rejectedDeals}`);
  console.log('━'.repeat(50));

  if (approvedDeals.length > 0) {
    console.log('\nAPPROVED:');
    for (const deal of approvedDeals) {
      console.log(
        `  [${deal.buyer.tier}] ${deal.address} — MAO $${deal.mao.toLocaleString()} | ` +
        `Fee $${deal.assignment.toLocaleString()} | Buyer: ${deal.buyer.name}`
      );
    }
  }

  console.log(`\nOutput:`);
  console.log(`  ${approvedPath}`);
  console.log(`  ${rejectedPath}`);
}

main();
