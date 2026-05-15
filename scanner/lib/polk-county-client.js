'use strict';

const { RateLimiter } = require('./rate-limiter');
const log = require('./logger');
const config = require('../config/polk-county.json');

const limiter = new RateLimiter(config.pipeline.rateLimitMs);

const UA = 'AMARA-OS/1.0 LandScanner (non-commercial OSINT; polk-county-fl)';

// ---------------------------------------------------------------------------
// Low-level helpers
// ---------------------------------------------------------------------------

async function fetchWithRetry(url, opts = {}, label = '') {
  const { maxRetries, retryBackoffMs, timeoutMs } = config.pipeline;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    await limiter.acquire();

    try {
      const res = await fetch(url, {
        ...opts,
        signal: AbortSignal.timeout(timeoutMs),
        headers: { 'User-Agent': UA, ...(opts.headers ?? {}) },
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${res.statusText}`);
      }

      return res;
    } catch (err) {
      const isLast = attempt === maxRetries;
      log.warn(
        `${label || url} — attempt ${attempt}/${maxRetries} failed: ${err.message}`,
        undefined,
        'polk-client',
      );
      if (isLast) throw err;
      await sleep(retryBackoffMs * attempt);
    }
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// ArcGIS REST helpers
// ---------------------------------------------------------------------------

/**
 * Query a single page from an ArcGIS FeatureLayer.
 * Returns { features, exceededTransferLimit }.
 */
async function queryArcGIS(layerPath, params = {}) {
  const base = `${config.gis.baseUrl}/${layerPath}/query`;
  const qs = new URLSearchParams({
    f: 'json',
    where: params.where ?? '1=1',
    outFields: params.outFields ?? '*',
    returnGeometry: String(params.returnGeometry ?? false),
    resultOffset: String(params.offset ?? 0),
    resultRecordCount: String(params.pageSize ?? config.pipeline.batchSize),
    orderByFields: params.orderBy ?? '',
    ...(params.extra ?? {}),
  });

  const url = `${base}?${qs}`;
  log.debug(`ArcGIS query → ${url}`, undefined, 'polk-client');

  const res = await fetchWithRetry(url, {}, `ArcGIS:${layerPath}`);
  const json = await res.json();

  if (json.error) {
    throw new Error(`ArcGIS error on ${layerPath}: ${json.error.message ?? JSON.stringify(json.error)}`);
  }

  return {
    features: (json.features ?? []).map((f) => f.attributes ?? f),
    exceededTransferLimit: json.exceededTransferLimit ?? false,
    fields: json.fields ?? [],
  };
}

/**
 * Paginate through all records in an ArcGIS FeatureLayer.
 * Calls onBatch(features[]) for each page.
 */
async function paginateArcGIS(layerPath, params = {}, onBatch) {
  const pageSize = params.pageSize ?? config.pipeline.batchSize;
  let offset = 0;
  let total = 0;
  let keepGoing = true;

  while (keepGoing) {
    const { features, exceededTransferLimit } = await queryArcGIS(layerPath, {
      ...params,
      offset,
      pageSize,
    });

    if (features.length) {
      await onBatch(features);
      total += features.length;
    }

    keepGoing = exceededTransferLimit && features.length === pageSize;
    offset += features.length;

    if (!features.length) break;
  }

  return total;
}

// ---------------------------------------------------------------------------
// Polk County-specific queries
// ---------------------------------------------------------------------------

/**
 * Fetch all subdivision/plat records from the county GIS.
 * Returns raw feature attribute objects.
 */
async function fetchSubdivisions(opts = {}) {
  const results = [];

  await paginateArcGIS(
    config.gis.subdivisionLayer,
    {
      where: opts.where ?? '1=1',
      outFields: opts.outFields ?? [
        'OBJECTID', 'SUBDIV_NAME', 'PLAT_BOOK', 'PLAT_PAGE',
        'RECORD_DATE', 'TOTAL_ACRES', 'TOTAL_LOTS', 'DEVELOPER',
        'STATUS', 'COUNTY_ID', 'SUBDIV_ID',
      ].join(','),
      orderBy: 'RECORD_DATE DESC',
      pageSize: 100,
    },
    async (batch) => {
      results.push(...batch);
    },
  );

  return results;
}

/**
 * Fetch parcels belonging to a given subdivision ID or plat book/page.
 */
async function fetchParcelsForSubdivision(subdivName) {
  const results = [];
  const sanitised = subdivName.replace(/'/g, "''");

  await paginateArcGIS(
    config.gis.parcelLayer,
    {
      where: `SUBDIV_NAME = '${sanitised}'`,
      outFields: 'PARCEL_ID,SUBDIV_NAME,OWNER,LAND_USE,BUILD_VALUE,YEAR_BUILT,SALE_DATE',
      pageSize: 200,
    },
    async (batch) => results.push(...batch),
  );

  return results;
}

/**
 * Lightweight connectivity check — just fetches metadata for the parcel layer.
 * Returns { ok, message }.
 */
async function ping() {
  try {
    const url = `${config.gis.baseUrl}/${config.gis.parcelLayer}?f=json`;
    const res = await fetchWithRetry(url, {}, 'ping');
    const json = await res.json();
    const name = json.name ?? json.layerName ?? 'unknown layer';
    return { ok: true, message: `Connected — layer: "${name}"` };
  } catch (err) {
    return { ok: false, message: err.message };
  }
}

module.exports = { fetchSubdivisions, fetchParcelsForSubdivision, queryArcGIS, ping };
