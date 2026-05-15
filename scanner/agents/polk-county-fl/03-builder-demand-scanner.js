'use strict';

/**
 * Agent 03 — Builder Demand Scanner  (Polk County FL)
 * ─────────────────────────────────────────────────────
 * Reads: data/polk-county-fl/raw/permits.csv
 * Depends on: Agent 01 output (agentResults['01'].findings)
 *
 * Rules:
 *  • No demand score without real permit data.
 *  • Proximity defined as: active single-family permits within 1.0 mile of plat centroid.
 *  • If permits.csv is missing or empty: log REAL_DATA_REQUIRED and exit cleanly.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-03');
const { parseCSV, parseGovDate } = require('../../lib/csv-parser');
const { distanceMiles, parseCoord } = require('../../lib/geo-utils');

const AGENT_ID      = '03-builder-demand-scanner';
const AGENT_VERSION = '2.0.0';

const RAW_DIR     = path.resolve(__dirname, '../../data/polk-county-fl/raw');
const PERMITS_CSV = path.join(RAW_DIR, 'permits.csv');

const PROXIMITY_MILES   = 1.0;
const LOOKBACK_MONTHS   = 24;
const HIGH_DEMAND_COUNT = 10;   // ≥10 permits within radius = HIGH demand

// ── Column aliases ─────────────────────────────────────────────────────────────

const ALIASES = {
  PERMIT_NO:    ['PERMIT_NUMBER', 'APPLICATION_NO', 'APP_NO', 'PERMIT_ID', 'BLDG_PERMIT_NO'],
  PERMIT_TYPE:  ['TYPE', 'PERMIT_TYPE_DESC', 'WORK_TYPE', 'APPLICATION_TYPE', 'BLDG_TYPE'],
  STATUS:       ['PERMIT_STATUS', 'APPLICATION_STATUS', 'STATUS_DESC'],
  ISSUE_DATE:   ['DATE_ISSUED', 'ISSUE_DATE', 'APPROVAL_DATE', 'PERMIT_DATE', 'ISSUED_DATE'],
  ADDRESS:      ['PERMIT_ADDRESS', 'SITE_ADDRESS', 'PROPERTY_ADDRESS', 'LOCATION'],
  LATITUDE:     ['LAT', 'Y', 'LATITUDE_Y', 'COORD_LAT'],
  LONGITUDE:    ['LON', 'LNG', 'X', 'LONGITUDE_X', 'COORD_LON'],
  BUILDER:      ['CONTRACTOR', 'CONTRACTOR_NAME', 'APPLICANT', 'BUILDER_NAME'],
  VALUE:        ['PERMIT_VALUE', 'CONSTRUCTION_VALUE', 'VALUATION', 'JOB_VALUE'],
  PARCEL_ID:    ['PARCEL_NUMBER', 'APN', 'FOLIO'],
};

// Single-family residential permit type keywords
const SF_KEYWORDS = /\b(SINGLE.?FAM|SFR|SFD|RESID|HOUSE|DWELLING|NEW.?CONST|NEW.?HOME|ONE.?FAM)\b/i;

function monthsAgo(n) { const d = new Date(); d.setMonth(d.getMonth() - n); return d; }

// ── Classify demand from permit clusters ───────────────────────────────────────

function classifyDemand(count) {
  if (count >= HIGH_DEMAND_COUNT) return 'HIGH';
  if (count >= 5)                 return 'MEDIUM';
  if (count >= 1)                 return 'LOW';
  return 'NONE';
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Source: ${PERMITS_CSV}`);

  const startedAt = Date.now();

  // ── Load permits CSV ──
  let permitRows;
  try {
    permitRows = await parseCSV(PERMITS_CSV, { aliases: ALIASES });
    log.info(`Loaded ${permitRows.length.toLocaleString()} permit rows`);
  } catch (err) {
    if (err.code === 'CSV_MISSING' || err.code === 'CSV_EMPTY') {
      log.error(`REAL_DATA_REQUIRED — ${path.basename(PERMITS_CSV)} ${err.code === 'CSV_MISSING' ? 'not found' : 'is empty'}. Place file from Polk County Building Dept at: ${PERMITS_CSV}`);
      const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, totalFlagged: 0 }, findings: [] };
      fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
      return result;
    }
    throw err;
  }

  // ── Filter: active SF permits within lookback window with coordinates ──
  const cutoff = monthsAgo(LOOKBACK_MONTHS);

  const activePermits = permitRows.filter((row) => {
    if (!SF_KEYWORDS.test(row.PERMIT_TYPE ?? '')) return false;

    const issued = parseGovDate(row.ISSUE_DATE);
    if (!issued || issued < cutoff) return false;

    const status = (row.STATUS ?? '').toUpperCase();
    // Include active, issued, approved, under construction, finaled
    if (/cancel|void|withdraw|expire/i.test(status)) return false;

    const lat = parseCoord(row.LATITUDE);
    const lon = parseCoord(row.LONGITUDE);
    if (!lat || !lon) return false;

    return true;
  }).map((row) => ({
    permitNo:    row.PERMIT_NO   || null,
    issueDate:   row.ISSUE_DATE  || null,
    builder:     row.BUILDER     || null,
    lat:         parseCoord(row.LATITUDE),
    lon:         parseCoord(row.LONGITUDE),
    address:     row.ADDRESS     || null,
    value:       row.VALUE       || null,
  }));

  log.info(`Active SF permits (geolocated, ${LOOKBACK_MONTHS}mo): ${activePermits.length.toLocaleString()}`);

  if (!activePermits.length) {
    log.warn('No active geolocated SF permits found. Demand scores will be NONE for all plats.');
  }

  // ── Get Agent 01 findings ──
  const agent01 = ctx.agentResults?.['01'];
  const platFindings = agent01?.findings ?? [];
  log.info(`Upstream plat findings: ${platFindings.length}`);

  if (!platFindings.length) {
    log.warn('No plat findings from Agent 01 to score demand for.');
  }

  // ── Score demand per plat ──
  const findings = [];

  for (const plat of platFindings) {
    if (!plat.lat || !plat.lon) {
      // Can't do proximity without coordinates
      findings.push({
        ...platBase(plat),
        demandLevel:    'UNKNOWN',
        nearbyPermits:  [],
        nearbyCount:    0,
        topBuilders:    [],
        note:           'No coordinates available for proximity analysis',
        _sourceFile:    'permits.csv',
        _sourceRows:    0,
      });
      continue;
    }

    const nearby = activePermits.filter((p) =>
      distanceMiles(plat.lat, plat.lon, p.lat, p.lon) <= PROXIMITY_MILES,
    );

    // Builder frequency
    const builderCounts = new Map();
    for (const p of nearby) {
      if (p.builder) {
        const b = p.builder.trim().toUpperCase();
        builderCounts.set(b, (builderCounts.get(b) ?? 0) + 1);
      }
    }
    const topBuilders = [...builderCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }));

    findings.push({
      ...platBase(plat),
      demandLevel:   classifyDemand(nearby.length),
      nearbyPermits: nearby.map((p) => ({
        permitNo:  p.permitNo,
        issueDate: p.issueDate,
        builder:   p.builder,
        address:   p.address,
      })),
      nearbyCount:  nearby.length,
      topBuilders,
      _sourceFile:  'permits.csv',
      _sourceRows:  nearby.length,
    });
  }

  // Sort: highest nearby count first
  findings.sort((a, b) => b.nearbyCount - a.nearbyCount);

  const byDemand = {};
  for (const f of findings) byDemand[f.demandLevel] = (byDemand[f.demandLevel] ?? 0) + 1;

  const summary = {
    totalScanned:    platFindings.length,
    totalWithDemand: findings.filter((f) => f.nearbyCount > 0).length,
    byDemandLevel:   byDemand,
    activePermitsLoaded: activePermits.length,
    durationMs:      Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Plats scored:   ${summary.totalScanned}`);
  log.info(`   With demand:    ${summary.totalWithDemand}`);
  for (const [level, n] of Object.entries(byDemand)) log.info(`   ${level.padEnd(8)} ${n}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings };
}

function platBase(plat) {
  return {
    subdivName:             plat.subdivName,
    platBook:               plat.platBook,
    platPage:               plat.platPage,
    category:               plat.category,
    parcelCount:            plat.parcelCount,
    totalAcres:             plat.totalAcres,
    representativeParcelId: plat.representativeParcelId,
    representativeOwner:    plat.representativeOwner,
    lat:                    plat.lat,
    lon:                    plat.lon,
  };
}

module.exports = { run };
