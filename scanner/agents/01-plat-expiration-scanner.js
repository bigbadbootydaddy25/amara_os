'use strict';

/**
 * Agent 01 — Plat Expiration Scanner
 * ---------------------------------------------------------------------------
 * Scans Polk County, FL public GIS and property-appraiser data to identify:
 *
 *  A) PRELIMINARY PLATS nearing or past expiration
 *     Polk County LDC §310 allows 24 months from preliminary approval to
 *     final plat recording. Unrecorded approved plats are prime targets.
 *
 *  B) DORMANT RECORDED PLATS
 *     Recorded subdivisions with no permits, no sales, and no improvement
 *     value for >= DORMANCY_THRESHOLD years signal abandoned development.
 *
 *  C) VACATION CANDIDATES
 *     Platted lots where 100% of parcels are owned by a single entity and
 *     no development has occurred — common precursor to plat vacation.
 *
 * When the GIS endpoint is offline the agent falls back to a rich offline
 * mock dataset so the pipeline can be exercised end-to-end at any time.
 * ---------------------------------------------------------------------------
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-01');
const { fetchSubdivisions, fetchParcelsForSubdivision } = require('../lib/polk-county-client');
const config = require('../config/polk-county.json');

const AGENT_ID      = '01-plat-expiration-scanner';
const AGENT_VERSION = '1.0.0';

const {
  preliminaryPlatMaxAgeMonths,
  warningWindowMonths,
  dormancyThresholdYears,
  lookbackYears,
} = config.platExpiration;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function monthsAgo(months) {
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d;
}

function yearsAgo(years) {
  const d = new Date();
  d.setFullYear(d.getFullYear() - years);
  return d;
}

/** Parse various date formats returned by GIS (epoch ms, ISO string, or null). */
function parseRecordDate(raw) {
  if (!raw) return null;
  if (typeof raw === 'number') return new Date(raw);
  const d = new Date(raw);
  return isNaN(d.getTime()) ? null : d;
}

function monthsBetween(a, b) {
  return (b - a) / (1000 * 60 * 60 * 24 * 30.44);
}

/**
 * Classify a subdivision record into one of four expiration risk categories.
 *
 *  EXPIRED       — preliminary plat past the max age with no final recording
 *  WARNING       — preliminary plat within the warning window
 *  DORMANT       — recorded plat, no development activity in N years
 *  VACATION_CAND — recorded plat, single-owner, zero improvements
 *  ACTIVE        — normal, developing subdivision
 */
function classifySubdivision(sub, parcels) {
  const recorded = parseRecordDate(sub.RECORD_DATE);
  const now = new Date();

  const ageMonths = recorded ? monthsBetween(recorded, now) : null;

  // Parcel-level signals
  const totalParcels = parcels.length;
  const builtParcels = parcels.filter(
    (p) => p.BUILD_VALUE > 0 || (p.YEAR_BUILT && p.YEAR_BUILT > 1900),
  ).length;
  const developmentRatio = totalParcels > 0 ? builtParcels / totalParcels : 0;

  const latestSale = parcels.reduce((best, p) => {
    const d = parseRecordDate(p.SALE_DATE);
    return d && (!best || d > best) ? d : best;
  }, null);

  const uniqueOwners = new Set(
    parcels.map((p) => (p.OWNER ?? '').trim().toUpperCase()).filter(Boolean),
  );

  // --- Classification logic ---

  // Preliminary plat flag: STATUS field = 'PRELIMINARY' or 'APPROVED'
  const isPreliminary =
    sub.STATUS &&
    /prelim|approved|pending/i.test(sub.STATUS);

  if (isPreliminary && ageMonths !== null) {
    if (ageMonths > preliminaryPlatMaxAgeMonths) {
      return { category: 'EXPIRED', ageMonths, developmentRatio, uniqueOwners: uniqueOwners.size };
    }
    if (ageMonths > preliminaryPlatMaxAgeMonths - warningWindowMonths) {
      return { category: 'WARNING', ageMonths, developmentRatio, uniqueOwners: uniqueOwners.size };
    }
  }

  // Vacation candidate: single owner, zero builds
  if (totalParcels >= 2 && uniqueOwners.size === 1 && developmentRatio === 0) {
    return { category: 'VACATION_CAND', ageMonths, developmentRatio, uniqueOwners: 1 };
  }

  // Dormant: recorded >= threshold years ago, < 10% built, no recent sales
  const dormancyCutoff = yearsAgo(dormancyThresholdYears);
  const noRecentSales = !latestSale || latestSale < dormancyCutoff;
  if (
    recorded &&
    recorded < dormancyCutoff &&
    developmentRatio < 0.10 &&
    noRecentSales
  ) {
    return { category: 'DORMANT', ageMonths, developmentRatio, uniqueOwners: uniqueOwners.size };
  }

  return { category: 'ACTIVE', ageMonths, developmentRatio, uniqueOwners: uniqueOwners.size };
}

// ---------------------------------------------------------------------------
// Offline mock data  (used when GIS is unreachable)
// ---------------------------------------------------------------------------

function buildMockSubdivisions() {
  const now = Date.now();
  const mo = (n) => now - n * 30 * 24 * 60 * 60 * 1000;

  return [
    {
      OBJECTID: 1001, SUBDIV_NAME: 'LAKE WALES HIGHLANDS UNIT 3',
      PLAT_BOOK: '142', PLAT_PAGE: '17', RECORD_DATE: mo(27),
      TOTAL_ACRES: 38.4, TOTAL_LOTS: 72, DEVELOPER: 'HIGHLAND LAND LLC',
      STATUS: 'PRELIMINARY', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2022-0341',
    },
    {
      OBJECTID: 1002, SUBDIV_NAME: 'WINTER HAVEN GROVE ESTATES',
      PLAT_BOOK: '138', PLAT_PAGE: '5',  RECORD_DATE: mo(22),
      TOTAL_ACRES: 14.1, TOTAL_LOTS: 28, DEVELOPER: 'GROVE PARTNERS INC',
      STATUS: 'APPROVED', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2022-0187',
    },
    {
      OBJECTID: 1003, SUBDIV_NAME: 'BARTOW OAKS SUBDIVISION',
      PLAT_BOOK: '91',  PLAT_PAGE: '44', RECORD_DATE: mo(84),
      TOTAL_ACRES: 22.7, TOTAL_LOTS: 44, DEVELOPER: 'BARTOW OAKS CORP',
      STATUS: 'RECORDED', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2017-0099',
    },
    {
      OBJECTID: 1004, SUBDIV_NAME: 'FROSTPROOF PALMS PH 2',
      PLAT_BOOK: '155', PLAT_PAGE: '8',  RECORD_DATE: mo(18),
      TOTAL_ACRES: 9.5,  TOTAL_LOTS: 19, DEVELOPER: 'FROSTPROOF DEV GROUP',
      STATUS: 'APPROVED', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2023-0512',
    },
    {
      OBJECTID: 1005, SUBDIV_NAME: 'HAINES CITY RESERVE NORTH',
      PLAT_BOOK: '107', PLAT_PAGE: '22', RECORD_DATE: mo(72),
      TOTAL_ACRES: 51.0, TOTAL_LOTS: 98, DEVELOPER: 'HC RESERVE HOLDINGS LLC',
      STATUS: 'RECORDED', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2018-0222',
    },
    {
      OBJECTID: 1006, SUBDIV_NAME: 'DUNDEE RIDGE PLAT A',
      PLAT_BOOK: '129', PLAT_PAGE: '61', RECORD_DATE: mo(36),
      TOTAL_ACRES: 17.8, TOTAL_LOTS: 34, DEVELOPER: 'RIDGE CAPITAL FL LLC',
      STATUS: 'RECORDED', COUNTY_ID: '12105', SUBDIV_ID: 'PLK-2021-0405',
    },
  ];
}

function buildMockParcels(subdivName) {
  const mockMap = {
    'LAKE WALES HIGHLANDS UNIT 3': [
      { PARCEL_ID: 'LW-001', SUBDIV_NAME: subdivName, OWNER: 'HIGHLAND LAND LLC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
      { PARCEL_ID: 'LW-002', SUBDIV_NAME: subdivName, OWNER: 'HIGHLAND LAND LLC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
      { PARCEL_ID: 'LW-003', SUBDIV_NAME: subdivName, OWNER: 'HIGHLAND LAND LLC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
    ],
    'BARTOW OAKS SUBDIVISION': [
      { PARCEL_ID: 'BO-001', SUBDIV_NAME: subdivName, OWNER: 'BARTOW OAKS CORP', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: '2017-04-10' },
      { PARCEL_ID: 'BO-002', SUBDIV_NAME: subdivName, OWNER: 'BARTOW OAKS CORP', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
      { PARCEL_ID: 'BO-003', SUBDIV_NAME: subdivName, OWNER: 'BARTOW OAKS CORP', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
      { PARCEL_ID: 'BO-004', SUBDIV_NAME: subdivName, OWNER: 'BARTOW OAKS CORP', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
    ],
    'HAINES CITY RESERVE NORTH': [
      { PARCEL_ID: 'HC-001', SUBDIV_NAME: subdivName, OWNER: 'HC RESERVE HOLDINGS LLC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: '2019-11-02' },
      { PARCEL_ID: 'HC-002', SUBDIV_NAME: subdivName, OWNER: 'HC RESERVE HOLDINGS LLC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
      { PARCEL_ID: 'HC-003', SUBDIV_NAME: subdivName, OWNER: 'INDIVIDUAL BUYER A',       LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: '2020-03-15' },
    ],
    'WINTER HAVEN GROVE ESTATES': [
      { PARCEL_ID: 'WH-001', SUBDIV_NAME: subdivName, OWNER: 'GROVE PARTNERS INC', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
    ],
    'FROSTPROOF PALMS PH 2': [
      { PARCEL_ID: 'FP-001', SUBDIV_NAME: subdivName, OWNER: 'FROSTPROOF DEV GROUP', LAND_USE: 'VAC RESID', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
    ],
    'DUNDEE RIDGE PLAT A': [
      { PARCEL_ID: 'DR-001', SUBDIV_NAME: subdivName, OWNER: 'RIDGE CAPITAL FL LLC', LAND_USE: 'SFR', BUILD_VALUE: 185000, YEAR_BUILT: 2022, SALE_DATE: '2023-01-20' },
      { PARCEL_ID: 'DR-002', SUBDIV_NAME: subdivName, OWNER: 'RESIDENT A',           LAND_USE: 'SFR', BUILD_VALUE: 192000, YEAR_BUILT: 2022, SALE_DATE: '2023-04-07' },
    ],
  };

  return mockMap[subdivName] ?? [
    { PARCEL_ID: 'MOCK-001', SUBDIV_NAME: subdivName, OWNER: 'UNKNOWN OWNER', LAND_USE: 'VAC', BUILD_VALUE: 0, YEAR_BUILT: null, SALE_DATE: null },
  ];
}

// ---------------------------------------------------------------------------
// Core scan logic
// ---------------------------------------------------------------------------

async function fetchSubdivisionsWithFallback(gisOnline) {
  if (!gisOnline) {
    log.warn('GIS offline — using mock dataset');
    return buildMockSubdivisions();
  }

  try {
    // Only scan subdivisions recorded within the lookback window
    const cutoff = yearsAgo(lookbackYears);
    const epochMs = cutoff.getTime();

    return await fetchSubdivisions({
      where: `RECORD_DATE >= DATE '${cutoff.toISOString().slice(0, 10)}'`,
      extra: { time: `${epochMs},` },  // ArcGIS time extent (optional)
    });
  } catch (err) {
    log.warn(`GIS query failed (${err.message}) — falling back to mock data`);
    return buildMockSubdivisions();
  }
}

async function fetchParcelsWithFallback(gisOnline, subdivName) {
  if (!gisOnline) return buildMockParcels(subdivName);

  try {
    return await fetchParcelsForSubdivision(subdivName);
  } catch (err) {
    log.warn(`Parcel fetch failed for "${subdivName}" (${err.message}) — using mock`);
    return buildMockParcels(subdivName);
  }
}

// ---------------------------------------------------------------------------
// Agent entry point
// ---------------------------------------------------------------------------

/**
 * @param {object} ctx  RunContext from cold-start
 * @returns {object}    Agent result payload
 */
async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Target: ${ctx.county} County, ${ctx.state}  ·  FIPS ${ctx.fips}`);
  log.info(`Lookback window: ${lookbackYears} years`);
  log.info(`Preliminary plat max age: ${preliminaryPlatMaxAgeMonths} months`);
  log.info(`Dormancy threshold: ${dormancyThresholdYears} years`);

  const startedAt = Date.now();

  // 1. Fetch subdivision/plat records
  log.info('Fetching subdivision records…');
  const subdivisions = await fetchSubdivisionsWithFallback(ctx.gisOnline);
  log.info(`Retrieved ${subdivisions.length} subdivision records`);

  // 2. Classify each subdivision
  const findings = [];

  for (const sub of subdivisions) {
    const name = sub.SUBDIV_NAME ?? `OBJECTID:${sub.OBJECTID}`;
    log.debug(`Processing: ${name}`);

    const parcels = await fetchParcelsWithFallback(ctx.gisOnline, name);
    const classification = classifySubdivision(sub, parcels);

    if (classification.category === 'ACTIVE') {
      log.debug(`  → ACTIVE (skip)`);
      continue;
    }

    const finding = {
      subdivId:       sub.SUBDIV_ID ?? null,
      subdivName:     name,
      platBook:       sub.PLAT_BOOK ?? null,
      platPage:       sub.PLAT_PAGE ?? null,
      recordDate:     sub.RECORD_DATE
                        ? parseRecordDate(sub.RECORD_DATE)?.toISOString().slice(0, 10)
                        : null,
      status:         sub.STATUS ?? null,
      developer:      sub.DEVELOPER ?? null,
      totalAcres:     sub.TOTAL_ACRES ?? null,
      totalLots:      sub.TOTAL_LOTS ?? null,
      parcelCount:    parcels.length,
      ...classification,
    };

    findings.push(finding);

    log.info(
      `  ► ${finding.category.padEnd(14)} ${name}` +
      `  (${finding.totalAcres ?? '?'} ac, ${finding.ageMonths !== null ? Math.round(finding.ageMonths) + ' mo old' : 'age unknown'})`,
    );
  }

  // 3. Sort by risk priority: EXPIRED > WARNING > VACATION_CAND > DORMANT
  const PRIORITY = { EXPIRED: 0, WARNING: 1, VACATION_CAND: 2, DORMANT: 3 };
  findings.sort((a, b) => (PRIORITY[a.category] ?? 9) - (PRIORITY[b.category] ?? 9));

  // 4. Summary stats
  const byCategory = {};
  for (const f of findings) {
    byCategory[f.category] = (byCategory[f.category] ?? 0) + 1;
  }

  const summary = {
    totalScanned:    subdivisions.length,
    totalFlagged:    findings.length,
    byCategory,
    durationMs:      Date.now() - startedAt,
    dataSource:      ctx.gisOnline ? 'live-gis' : 'offline-mock',
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Scanned:  ${summary.totalScanned}`);
  log.info(`   Flagged:  ${summary.totalFlagged}`);
  for (const [cat, count] of Object.entries(byCategory)) {
    log.info(`   ${cat.padEnd(16)} ${count}`);
  }
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info(`   Source:   ${summary.dataSource}`);
  log.info('────────────────────────────────────────────────────');

  // 5. Persist output
  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, summary, findings };
}

module.exports = { run };
