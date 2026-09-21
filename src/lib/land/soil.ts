/**
 * Soil/septic-suitability screen via USDA NRCS Soil Data Access (SDA) —
 * free, keyless, official SSURGO soil survey data (the same source a
 * licensed soil scientist's percolation report is built on).
 *
 * This gives a SCREENING signal only — drainage class and hydric rating
 * for the dominant map-unit component at a point. It is NOT a
 * substitute for an actual percolation test or a permitted septic
 * design; treat "likely-suitable" as "worth investigating further," not
 * a permit.
 *
 * Confidence note: the SDA_Get_Mukey_from_intersection_with_WktWgs84
 * table-valued function and the drainagecl/hydricrating component
 * columns below match NRCS's published SDA examples, but this has not
 * been exercised against the live endpoint in this environment (outbound
 * network access here is sandboxed) — verify against a known point
 * before relying on it.
 */
import type { LonLat } from './geo';

const SDA_ENDPOINT = 'https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest';

export function buildSoilPointQuery({ lon, lat }: LonLat): string {
  // WKT point is "lon lat" (x y), not "lat lon".
  const wkt = `point(${lon} ${lat})`;
  return `
SELECT mu.mukey, mu.musym, mu.muname, c.compname, c.comppct_r,
       c.drainagecl, c.hydricrating, c.majcompflag
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('${wkt}') AS pt
INNER JOIN mapunit mu ON mu.mukey = pt.mukey
INNER JOIN component c ON c.mukey = mu.mukey
WHERE c.majcompflag = 'Yes'
ORDER BY c.comppct_r DESC`.trim();
}

export function buildSoilRequestBody(point: LonLat): string {
  return JSON.stringify({ query: buildSoilPointQuery(point), format: 'JSON' });
}

export type SepticSuitability = 'likely-suitable' | 'caution' | 'poor' | 'unknown';

export interface SoilComponent {
  mapUnitSymbol: string | null;
  mapUnitName: string | null;
  componentName: string | null;
  componentPercent: number | null;
  drainageClass: string | null;
  hydric: string | null;
}

export interface SoilSuitabilityResult {
  suitability: SepticSuitability;
  reason: string;
  dominantComponent: SoilComponent | null;
  components: SoilComponent[];
}

const POOR_DRAINAGE = new Set(['Very poorly drained', 'Poorly drained']);
const CAUTION_DRAINAGE = new Set(['Somewhat poorly drained', 'Moderately well drained']);
const GOOD_DRAINAGE = new Set([
  'Excessively drained',
  'Somewhat excessively drained',
  'Well drained',
]);

/** SDA responds { Table: [ [colName1, colName2, ...], [row1...], [row2...] ] } */
export function parseSoilResponse(body: string): SoilSuitabilityResult {
  let data: unknown;
  try {
    data = JSON.parse(body);
  } catch {
    throw new Error('Soil Data Access returned malformed JSON');
  }
  const table = (data as { Table?: unknown })?.Table;
  if (!Array.isArray(table) || table.length < 2) {
    return { suitability: 'unknown', reason: 'No soil survey data at this point.', dominantComponent: null, components: [] };
  }

  const [header, ...rows] = table as unknown[][];
  const columnIndex = (name: string) => (header as unknown[]).findIndex((c) => c === name);
  const idx = {
    musym: columnIndex('musym'),
    muname: columnIndex('muname'),
    compname: columnIndex('compname'),
    comppct: columnIndex('comppct_r'),
    drainagecl: columnIndex('drainagecl'),
    hydricrating: columnIndex('hydricrating'),
  };

  const components: SoilComponent[] = rows.map((row) => ({
    mapUnitSymbol: idx.musym >= 0 ? String(row[idx.musym] ?? '') || null : null,
    mapUnitName: idx.muname >= 0 ? String(row[idx.muname] ?? '') || null : null,
    componentName: idx.compname >= 0 ? String(row[idx.compname] ?? '') || null : null,
    componentPercent:
      idx.comppct >= 0 && Number.isFinite(Number(row[idx.comppct])) ? Number(row[idx.comppct]) : null,
    drainageClass: idx.drainagecl >= 0 ? String(row[idx.drainagecl] ?? '') || null : null,
    hydric: idx.hydricrating >= 0 ? String(row[idx.hydricrating] ?? '') || null : null,
  }));

  const dominant = components[0] ?? null;
  if (!dominant) {
    return { suitability: 'unknown', reason: 'No soil component data returned.', dominantComponent: null, components };
  }

  if (dominant.hydric === 'Yes') {
    return {
      suitability: 'poor',
      reason: `Dominant soil (${dominant.mapUnitName ?? dominant.mapUnitSymbol ?? 'unnamed unit'}) is rated hydric — typically wetland/seasonally saturated, a strong caution for conventional septic.`,
      dominantComponent: dominant,
      components,
    };
  }
  if (dominant.drainageClass && POOR_DRAINAGE.has(dominant.drainageClass)) {
    return {
      suitability: 'poor',
      reason: `Dominant soil drainage class is "${dominant.drainageClass}" — poor drainage is a common cause of septic system failure.`,
      dominantComponent: dominant,
      components,
    };
  }
  if (dominant.drainageClass && CAUTION_DRAINAGE.has(dominant.drainageClass)) {
    return {
      suitability: 'caution',
      reason: `Dominant soil drainage class is "${dominant.drainageClass}" — may need an engineered system (mound, aerobic) rather than a conventional drain field.`,
      dominantComponent: dominant,
      components,
    };
  }
  if (dominant.drainageClass && GOOD_DRAINAGE.has(dominant.drainageClass)) {
    return {
      suitability: 'likely-suitable',
      reason: `Dominant soil drainage class is "${dominant.drainageClass}" — generally favorable, still requires an on-site percolation test.`,
      dominantComponent: dominant,
      components,
    };
  }
  return {
    suitability: 'unknown',
    reason: dominant.drainageClass
      ? `Drainage class "${dominant.drainageClass}" not recognized by this screen.`
      : 'No drainage-class rating on file for this soil.',
    dominantComponent: dominant,
    components,
  };
}

export { SDA_ENDPOINT };
