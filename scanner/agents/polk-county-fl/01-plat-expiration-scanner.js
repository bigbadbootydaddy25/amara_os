'use strict';

/**
 * Agent 01 — Plat Expiration Scanner  (Polk County FL)
 * ─────────────────────────────────────────────────────
 * Reads: data/polk-county-fl/raw/parcels.csv
 * Source: Polk County Property Appraiser  (polkpa.org)
 *
 * Rules:
 *  • Every flagged record must be backed by at least one real parcel row.
 *  • No scores, no flags, no output without real data.
 *  • If the CSV is missing or empty: log REAL_DATA_REQUIRED and exit cleanly.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-01');
const { parseCSV, parseGovDate } = require('../../lib/csv-parser');

const AGENT_ID      = '01-plat-expiration-scanner';
const AGENT_VERSION = '2.0.0';

const RAW_DIR     = path.resolve(__dirname, '../../data/polk-county-fl/raw');
const PARCELS_CSV = path.join(RAW_DIR, 'parcels.csv');

// Florida DOR land-use codes that indicate vacant/undeveloped residential
const VACANT_CODES = new Set(['00', '0', '001', '002', '003', '004', '005']);

// ── Column aliases ────────────────────────────────────────────────────────────
const ALIASES = {
  PARCEL_ID:    ['PARCEL_NUMBER', 'APN', 'ACCOUNT_NO', 'ACCOUNT_NUMBER', 'STRAP', 'RE_NUMBER'],
  OWNER:        ['OWNER_NAME', 'OWNER1', 'TAXPAYER_NAME', 'OWNER_1'],
  SUBDIV_NAME:  ['SUBDIVISION', 'SUBDIV', 'PLAT_NAME', 'SUB_NAME', 'LEGAL_SUBDIV'],
  PLAT_BOOK:    ['BOOK', 'PB', 'PLAT_BK'],
  PLAT_PAGE:    ['PAGE', 'PG', 'PLAT_PG'],
  RECORD_DATE:  ['RECORDED_DATE', 'FILING_DATE', 'PLAT_DATE', 'DATE_RECORDED', 'DATE_FILED', 'PLAT_RECORDED'],
  LAND_USE:     ['USE_CODE', 'DOR_CODE', 'PROPERTY_USE', 'LND_USE_CD', 'LANDUSE', 'DOR_UC'],
  BUILD_VALUE:  ['IMPROVEMENT_VALUE', 'BLDG_VALUE', 'IMPR_VALUE', 'BUILDING_VALUE', 'JUST_VAL_IMPRV'],
  YEAR_BUILT:   ['EFFECTIVE_YEAR', 'YEAR_EFFECTIVE', 'YR_BUILT', 'ACT_YR_BLT'],
  SALE_DATE:    ['LAST_SALE_DATE', 'LAST_SALE', 'DEED_DATE', 'SALE_DATE1', 'OR_SALE_DATE'],
  TOTAL_LOTS:   ['NUM_LOTS', 'LOT_COUNT', 'LOTS'],
  ACREAGE:      ['ACRES', 'TOTAL_ACRES', 'LAND_AREA_AC', 'LAND_AREA', 'LND_SQFT'],
  OWNER_ADDR:   ['OWNER_ADDRESS', 'MAILING_ADDRESS', 'MAIL_ADDR1', 'MAILING_ADDR'],
  PROP_ADDR:    ['PROPERTY_ADDRESS', 'SITE_ADDRESS', 'PHYS_ADDR', 'SITUS_ADDR'],
  LATITUDE:     ['LAT', 'Y', 'LATITUDE_Y'],
  LONGITUDE:    ['LON', 'LNG', 'X', 'LONGITUDE_X'],
  STATUS:       ['SUBDIV_STATUS', 'PLAT_STATUS', 'PERMIT_STATUS'],
};

// ── Expiration parameters (Polk County LDC §310) ──────────────────────────────
const MAX_PRELIM_MONTHS = 24;
const WARN_WINDOW_MONTHS = 3;
const DORMANCY_YEARS = 5;

function monthsAgo(n) { const d = new Date(); d.setMonth(d.getMonth() - n); return d; }
function yearsAgo(n)  { const d = new Date(); d.setFullYear(d.getFullYear() - n); return d; }
function monthsBetween(a, b) { return (b - a) / (1000 * 60 * 60 * 24 * 30.44); }

// ── Record filtering ──────────────────────────────────────────────────────────

function isSubdivisionRecord(row) {
  // Must have a subdivision name, OR a plat book/page, OR a vacant-residential land-use code
  const hasSubdiv  = (row.SUBDIV_NAME ?? '').trim().length > 2;
  const hasPlat    = (row.PLAT_BOOK ?? '').trim() !== '' && (row.PLAT_PAGE ?? '').trim() !== '';
  const landUse    = (row.LAND_USE ?? '').trim().padStart(2, '0');
  const isVacant   = VACANT_CODES.has(landUse);
  return hasSubdiv || hasPlat || isVacant;
}

// ── Classification ────────────────────────────────────────────────────────────

function classify(group) {
  const parcels = group.parcels;
  const now     = new Date();

  const recordDate = group.recordDate;
  const ageMonths  = recordDate ? monthsBetween(recordDate, now) : null;

  const totalParcels = parcels.length;
  const builtCount   = parcels.filter((p) => p.BUILD_VALUE && parseFloat(p.BUILD_VALUE) > 0).length;
  const devRatio     = totalParcels > 0 ? builtCount / totalParcels : 0;

  const latestSale = parcels.reduce((best, p) => {
    const d = parseGovDate(p.SALE_DATE);
    return d && (!best || d > best) ? d : best;
  }, null);

  const uniqueOwners = new Set(
    parcels.map((p) => (p.OWNER ?? '').trim().toUpperCase()).filter(Boolean),
  );

  const statusRaw  = (group.status ?? '').toUpperCase();
  const isPrelim   = /prelim|approved|pending/i.test(statusRaw);

  if (isPrelim && ageMonths !== null) {
    if (ageMonths > MAX_PRELIM_MONTHS)                           return 'EXPIRED';
    if (ageMonths > MAX_PRELIM_MONTHS - WARN_WINDOW_MONTHS)     return 'WARNING';
  }

  if (totalParcels >= 2 && uniqueOwners.size === 1 && devRatio === 0)
    return 'VACATION_CAND';

  const dormCutoff    = yearsAgo(DORMANCY_YEARS);
  const noRecentSales = !latestSale || latestSale < dormCutoff;
  if (recordDate && recordDate < dormCutoff && devRatio < 0.10 && noRecentSales)
    return 'DORMANT';

  return 'ACTIVE';
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Source: ${PARCELS_CSV}`);

  const startedAt = Date.now();

  // ── Read CSV ──
  let rows;
  try {
    rows = await parseCSV(PARCELS_CSV, { aliases: ALIASES });
    log.info(`Loaded ${rows.length.toLocaleString()} parcel rows`);
  } catch (err) {
    if (err.code === 'CSV_MISSING' || err.code === 'CSV_EMPTY') {
      log.error(`REAL_DATA_REQUIRED — ${path.basename(PARCELS_CSV)} ${err.code === 'CSV_MISSING' ? 'not found' : 'is empty'}. Place the file from polkpa.org at: ${PARCELS_CSV}`);
      const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, totalFlagged: 0 }, findings: [] };
      fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
      return result;
    }
    throw err;
  }

  // ── Filter to subdivision records ──
  const subdivRows = rows.filter(isSubdivisionRecord);
  log.info(`Subdivision records: ${subdivRows.length.toLocaleString()}`);

  if (!subdivRows.length) {
    log.error('REAL_DATA_REQUIRED — No subdivision records found in parcels.csv. Verify column headers match expected format.');
    return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, totalFlagged: 0 }, findings: [] };
  }

  // ── Group by subdivision name ──
  const groups = new Map();
  for (const row of subdivRows) {
    const key = (row.SUBDIV_NAME ?? '').trim().toUpperCase() ||
                `PLAT_${(row.PLAT_BOOK ?? '').trim()}_${(row.PLAT_PAGE ?? '').trim()}`;
    if (!key || key === 'PLAT__') continue;

    if (!groups.has(key)) {
      const recordDate = parseGovDate(row.RECORD_DATE);
      groups.set(key, {
        subdivName:  (row.SUBDIV_NAME ?? key).trim(),
        platBook:    (row.PLAT_BOOK ?? '').trim() || null,
        platPage:    (row.PLAT_PAGE ?? '').trim() || null,
        recordDate,
        status:      (row.STATUS ?? '').trim(),
        parcels:     [],
        lat:         null,
        lon:         null,
      });
    }

    const g = groups.get(key);
    g.parcels.push(row);

    // Use earliest record date for the group
    const d = parseGovDate(row.RECORD_DATE);
    if (d && (!g.recordDate || d < g.recordDate)) g.recordDate = d;

    // Capture first available coordinates for the group centroid
    if (!g.lat && row.LATITUDE) {
      const lat = parseFloat(row.LATITUDE);
      const lon = parseFloat(row.LONGITUDE);
      if (!isNaN(lat) && !isNaN(lon)) { g.lat = lat; g.lon = lon; }
    }
  }

  log.info(`Unique subdivisions: ${groups.size.toLocaleString()}`);

  // ── Classify ──
  const findings = [];
  for (const [, group] of groups) {
    const category = classify(group);
    if (category === 'ACTIVE') continue;

    const now        = new Date();
    const ageMonths  = group.recordDate ? monthsBetween(group.recordDate, now) : null;
    const parcels    = group.parcels;
    const uniqueOwners = new Set(parcels.map((p) => (p.OWNER ?? '').trim().toUpperCase()).filter(Boolean));
    const builtCount = parcels.filter((p) => parseFloat(p.BUILD_VALUE ?? 0) > 0).length;

    // Compute representative parcel ID (first one alphabetically)
    const firstParcel = [...parcels].sort((a, b) => (a.PARCEL_ID ?? '').localeCompare(b.PARCEL_ID ?? ''))[0];

    // Acreage: sum across parcels, or take from first non-zero
    const totalAcres = parcels.reduce((s, p) => {
      const a = parseFloat(p.ACREAGE ?? '0');
      return s + (isNaN(a) ? 0 : a);
    }, 0);

    findings.push({
      subdivName:      group.subdivName,
      platBook:        group.platBook,
      platPage:        group.platPage,
      recordDate:      group.recordDate?.toISOString().slice(0, 10) ?? null,
      status:          group.status || null,
      category,
      ageMonths:       ageMonths !== null ? parseFloat(ageMonths.toFixed(1)) : null,
      parcelCount:     parcels.length,
      totalLots:       parcels.length,   // one row = one parcel/lot
      totalAcres:      parseFloat(totalAcres.toFixed(2)),
      developmentRatio: builtCount / parcels.length,
      uniqueOwners:    uniqueOwners.size,
      // Representative fields for downstream agents
      representativeParcelId: firstParcel?.PARCEL_ID ?? null,
      representativeOwner:    firstParcel?.OWNER ?? null,
      lat: group.lat,
      lon: group.lon,
      // Provenance
      _sourceFile:     'parcels.csv',
      _sourceRows:     parcels.length,
    });
  }

  const PRIORITY = { EXPIRED: 0, WARNING: 1, VACATION_CAND: 2, DORMANT: 3 };
  findings.sort((a, b) => (PRIORITY[a.category] ?? 9) - (PRIORITY[b.category] ?? 9));

  const byCategory = {};
  for (const f of findings) byCategory[f.category] = (byCategory[f.category] ?? 0) + 1;

  const summary = { totalScanned: groups.size, totalFlagged: findings.length, byCategory, durationMs: Date.now() - startedAt };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Subdivisions scanned: ${summary.totalScanned}`);
  log.info(`   Flagged:              ${summary.totalFlagged}`);
  for (const [cat, n] of Object.entries(byCategory)) log.info(`   ${cat.padEnd(16)} ${n}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings };
}

module.exports = { run };
