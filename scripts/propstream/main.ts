#!/usr/bin/env tsx
// ─────────────────────────────────────────────────────────────────────────────
// PropStream Data Extraction & Deal-Matching System — Main Orchestrator
//
// Usage:
//   npm run propstream                # full run (scrape + process + match)
//   npm run propstream:inspect        # DOM inspection only (safe first step)
//   npm run propstream:scrape         # scrape only (skips already-done lists)
//   npm run propstream:process        # process + export from existing raw data
//   npm run propstream:airtable       # push existing results to Airtable
//
// Environment variables (set in scripts/propstream/.env.propstream):
//   PROPSTREAM_EMAIL
//   PROPSTREAM_PASSWORD
//   AIRTABLE_API_KEY        (only required for --airtable-only)
// ─────────────────────────────────────────────────────────────────────────────

import * as fs from "fs";
import * as path from "path";
import * as readline from "readline";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Load .env.propstream before any other imports
loadEnv();

import { PropStreamBrowser } from "./lib/browser.js";
import { login } from "./lib/auth.js";
import { inspectDOM, loadCachedSelectors } from "./lib/dom-inspector.js";
import { RateLimiter } from "./lib/rate-limiter.js";
import { LeadListScraper } from "./scrapers/list-scraper.js";
import { normalise } from "./processors/normaliser.js";
import { processSFRTrack } from "./processors/sfr.js";
import { processLandTrack } from "./processors/land.js";
import { buildSFRBuyerProfiles, buildLandBuyerProfiles } from "./processors/buyers.js";
import { buildSFRMatchBoard, buildBuilderMatchBoard } from "./matchers/match-board.js";
import { writeSFRCSV, writeLandCSV } from "./exporters/csv.js";
import {
  writeSFRBuyers, writeLandBuyers, writeSFRMatchBoard,
  writeBuilderMatchBoard, writeDeadPaperTargets,
  writeGhostSubdivisionTargets, writeSummaryManifest,
} from "./exporters/json.js";
import { pushToAirtable } from "./exporters/airtable.js";
import {
  loadRawList, ensureDataDir, DATA_DIR, writeJson,
} from "./lib/storage.js";
import { ALL_LEAD_LISTS, BUYER_LISTS } from "./config/lists.js";
import type { NormalisedRecord, LeadListName } from "./types/index.js";

// ─── CLI flags ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const INSPECT_ONLY  = args.includes("--inspect-only");
const SCRAPE_ONLY   = args.includes("--scrape-only");
const PROCESS_ONLY  = args.includes("--process-only");
const AIRTABLE_ONLY = args.includes("--airtable-only");
const SKIP_SCRAPE   = PROCESS_ONLY || AIRTABLE_ONLY;
const SKIP_PROCESS  = AIRTABLE_ONLY;

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log(" PropStream Data Extraction & Deal-Matching System");
  console.log("═══════════════════════════════════════════════════════\n");

  ensureDataDir();

  const creds = getCredentials();

  // ── Phase 1: Scrape ────────────────────────────────────────────────────────
  if (!SKIP_SCRAPE) {
    await runScrapePhase(creds);
    if (SCRAPE_ONLY || INSPECT_ONLY) {
      console.log("\n[main] scrape/inspect phase complete. Exiting.");
      return;
    }
  }

  // ── Phase 2: Process + Export ──────────────────────────────────────────────
  if (!SKIP_PROCESS) {
    await runProcessPhase();
    if (SCRAPE_ONLY) return;
  }

  // ── Phase 3: Airtable push (optional) ─────────────────────────────────────
  const airtableKey = process.env.AIRTABLE_API_KEY;
  if (airtableKey) {
    await runAirtablePhase(airtableKey);
  } else if (AIRTABLE_ONLY) {
    const key = await promptForInput("Enter Airtable API key: ");
    if (!key) {
      console.error("[main] No Airtable API key provided. Skipping push.");
      return;
    }
    await runAirtablePhase(key);
  } else {
    console.log(
      "\n[main] Airtable push skipped (set AIRTABLE_API_KEY env var or use --airtable-only to push)."
    );
  }

  console.log("\n═══════════════════════════════════════════════════════");
  console.log(" All done! Check project root for output files.");
  console.log("═══════════════════════════════════════════════════════");
}

// ─── Phase implementations ────────────────────────────────────────────────────

async function runScrapePhase(creds: { email: string; password: string }) {
  console.log("\n[phase 1] SCRAPING — 19 lead lists\n");

  const browser = new PropStreamBrowser({ headless: true, screenshotsEnabled: true });
  const page = await browser.launch();

  try {
    // Login
    await login(page, browser, creds);

    // DOM inspection (always runs on first scrape or when --inspect-only)
    let selectors = loadCachedSelectors();
    if (!selectors || INSPECT_ONLY) {
      console.log("\n[phase 1] running DOM inspection...");
      const report = await inspectDOM(page, browser);
      selectors = report.selectors;
      console.log("[phase 1] DOM inspection complete");
      if (INSPECT_ONLY) return;
    }

    // Scrape all 19 lists
    const rateLimiter = new RateLimiter();
    const scraper = new LeadListScraper(page, browser, selectors, rateLimiter);
    await scraper.scrapeAll(ALL_LEAD_LISTS, /* skipCompleted */ true);

  } finally {
    await browser.close();
  }
}

async function runProcessPhase() {
  console.log("\n[phase 2] PROCESSING — normalise, filter, classify, match\n");

  const startedAt = new Date().toISOString();
  let totalRawRecords = 0;

  // Load and normalise all raw records
  console.log("[process] loading and normalising raw records...");
  const allNormalised: NormalisedRecord[] = [];

  for (const listName of ALL_LEAD_LISTS) {
    const raw = loadRawList(listName);
    totalRawRecords += raw.length;
    const normalised = raw.map(normalise);
    allNormalised.push(...normalised);
    if (raw.length > 0) {
      console.log(`  ✓ ${listName}: ${raw.length} records`);
    } else {
      console.warn(`  ⚠ ${listName}: no records found (list may not have been scraped)`);
    }
  }

  console.log(`\n[process] total normalised records: ${allNormalised.length}`);

  // ── SFR Track ──────────────────────────────────────────────────────────────
  console.log("\n[process] SFR track...");
  const sfrTargets = processSFRTrack(allNormalised);
  console.log(`  SFR targets in scope: ${sfrTargets.length}`);
  writeSFRCSV(sfrTargets);

  // ── Land Track ─────────────────────────────────────────────────────────────
  console.log("\n[process] Land track...");
  const { allLandTargets, deadPaperTargets, ghostSubdivisionTargets } =
    processLandTrack(allNormalised);
  console.log(`  Land targets: ${allLandTargets.length}`);
  console.log(`  Dead paper:   ${deadPaperTargets.length}`);
  console.log(`  Ghost subdivisions: ${ghostSubdivisionTargets.length}`);
  writeLandCSV(allLandTargets);
  writeDeadPaperTargets(deadPaperTargets);
  writeGhostSubdivisionTargets(ghostSubdivisionTargets);

  // ── Buyer Profiles ─────────────────────────────────────────────────────────
  console.log("\n[process] buyer profiles...");
  const buyerRecords = BUYER_LISTS.flatMap((l) => loadRawList(l).map(normalise));
  const cashBuyers  = buyerRecords.filter((r) => r.listType === "Cash Buyers");
  const flippers    = buyerRecords.filter((r) => r.listType === "Flippers");

  const sfrBuyers  = buildSFRBuyerProfiles(cashBuyers, flippers);
  const landBuyers = buildLandBuyerProfiles(cashBuyers, flippers);
  console.log(`  SFR buyers:  ${sfrBuyers.length}`);
  console.log(`  Land buyers: ${landBuyers.length}`);
  writeSFRBuyers(sfrBuyers);
  writeLandBuyers(landBuyers);

  // ── Match Board ────────────────────────────────────────────────────────────
  console.log("\n[process] match board...");
  const sfrMatches = buildSFRMatchBoard(sfrTargets, sfrBuyers);
  const builderMatches = buildBuilderMatchBoard(allLandTargets, landBuyers, deadPaperTargets);
  const immediateFlags = builderMatches.filter((m) => m.flagForImmediateAction).length;

  console.log(`  SFR matches:       ${sfrMatches.length}`);
  console.log(`  Builder matches:   ${builderMatches.length}`);
  console.log(`  Immediate action:  ${immediateFlags} (score ≥ 75)`);
  writeSFRMatchBoard(sfrMatches);
  writeBuilderMatchBoard(builderMatches);

  // ── Summary manifest ───────────────────────────────────────────────────────
  writeSummaryManifest({
    scrapeCompletedAt:    startedAt,
    listsScraped:         ALL_LEAD_LISTS.length,
    totalRawRecords,
    sfrTargets:           sfrTargets.length,
    landTargets:          allLandTargets.length,
    deadPaperTargets:     deadPaperTargets.length,
    ghostSubdivisions:    ghostSubdivisionTargets.length,
    sfrBuyers:            sfrBuyers.length,
    landBuyers:           landBuyers.length,
    sfrMatches:           sfrMatches.length,
    builderMatches:       builderMatches.length,
    immediateActionFlags: immediateFlags,
  });

  // Persist processed data for Airtable phase
  writeJson("processed_sfr_targets.json", sfrTargets);
  writeJson("processed_land_targets.json", allLandTargets);
  writeJson("processed_sfr_buyers.json", sfrBuyers);
  writeJson("processed_land_buyers.json", landBuyers);
  writeJson("processed_sfr_matches.json", sfrMatches);
  writeJson("processed_builder_matches.json", builderMatches);
  writeJson("processed_dead_paper.json", deadPaperTargets);

  console.log("\n[process] ✓ processing complete");
}

async function runAirtablePhase(apiKey: string) {
  console.log("\n[phase 3] AIRTABLE — pushing to base app0jn857ZwVzQs8i\n");

  // Load processed data (may be from a previous process run)
  const load = <T>(file: string): T[] => {
    const p = path.join(DATA_DIR, file);
    if (!fs.existsSync(p)) {
      console.warn(`  [airtable] missing ${file} — run --process first`);
      return [];
    }
    return JSON.parse(fs.readFileSync(p, "utf-8")) as T[];
  };

  await pushToAirtable({
    apiKey,
    sfrTargets:       load("processed_sfr_targets.json"),
    landTargets:      load("processed_land_targets.json"),
    deadPaperTargets: load("processed_dead_paper.json"),
    sfrBuyers:        load("processed_sfr_buyers.json"),
    landBuyers:       load("processed_land_buyers.json"),
    sfrMatches:       load("processed_sfr_matches.json"),
    builderMatches:   load("processed_builder_matches.json"),
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getCredentials(): { email: string; password: string } {
  const email    = process.env.PROPSTREAM_EMAIL;
  const password = process.env.PROPSTREAM_PASSWORD;

  if (!email || !password) {
    console.error(
      "\n[main] ERROR: PropStream credentials not found.\n" +
      "Create scripts/propstream/.env.propstream with:\n" +
      "  PROPSTREAM_EMAIL=your@email.com\n" +
      "  PROPSTREAM_PASSWORD=yourpassword\n"
    );
    process.exit(1);
  }

  return { email, password };
}

function promptForInput(question: string): Promise<string> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

function loadEnv() {
  const envPath = path.join(__dirname, ".env.propstream");
  if (!fs.existsSync(envPath)) return;
  const lines = fs.readFileSync(envPath, "utf-8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx < 0) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, "");
    process.env[key] = val;
  }
}

// ─── Run ──────────────────────────────────────────────────────────────────────

main().catch((err) => {
  console.error("\n[main] FATAL ERROR:", err);
  process.exit(1);
});
