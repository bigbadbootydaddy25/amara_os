/**
 * Power-line lookup via OpenStreetMap's Overpass API — free, keyless,
 * community-mapped. Pulls transmission/distribution lines, cables, and
 * substations tagged `power=*` within a bounding box.
 *
 * Coverage caveat: OSM power-infrastructure tagging is dense in some
 * regions and sparse in rural ones. Treat a clear result as "known lines
 * shown"; absence of a line here is NOT proof none exists on the parcel.
 */
import type { BBox } from './geo';

const OVERPASS_ENDPOINT = 'https://overpass-api.de/api/interpreter';

/** Overpass QL query for power lines/cables/towers/substations in a bbox. */
export function buildPowerLinesQuery(bbox: BBox, timeoutS = 20): string {
  const box = `${bbox.minLat},${bbox.minLon},${bbox.maxLat},${bbox.maxLon}`;
  return `[out:json][timeout:${timeoutS}];(
  way["power"~"^(line|minor_line|cable)$"](${box});
  node["power"~"^(tower|pole|substation)$"](${box});
  way["power"="substation"](${box});
);out geom;`;
}

export type PowerFeatureKind = 'line' | 'minor_line' | 'cable' | 'tower' | 'pole' | 'substation';

export interface PowerLineFeature {
  id: number;
  kind: PowerFeatureKind;
  voltage: number | null;
  operator: string | null;
  path: [lon: number, lat: number][];
}

export interface PowerPointFeature {
  id: number;
  kind: PowerFeatureKind;
  voltage: number | null;
  lon: number;
  lat: number;
}

export interface PowerLinesResult {
  lines: PowerLineFeature[];
  points: PowerPointFeature[];
}

interface OverpassGeometryPoint {
  lat?: unknown;
  lon?: unknown;
}

interface OverpassElement {
  type?: unknown;
  id?: unknown;
  lat?: unknown;
  lon?: unknown;
  geometry?: unknown;
  tags?: Record<string, unknown>;
}

function parseVoltage(raw: unknown): number | null {
  if (typeof raw !== 'string') return null;
  // OSM voltage tags can be semicolon-separated lists ("110000;220000");
  // take the highest, since that is what matters for a hazard/clearance read.
  const values = raw
    .split(';')
    .map((v) => Number(v.trim()))
    .filter((v) => Number.isFinite(v) && v > 0);
  return values.length ? Math.max(...values) : null;
}

function isPowerKind(value: unknown): value is PowerFeatureKind {
  return (
    value === 'line' ||
    value === 'minor_line' ||
    value === 'cable' ||
    value === 'tower' ||
    value === 'pole' ||
    value === 'substation'
  );
}

/** Parse and validate an Overpass JSON response into normalized features. */
export function parsePowerLinesResponse(body: string): PowerLinesResult {
  let data: unknown;
  try {
    data = JSON.parse(body);
  } catch {
    throw new Error('Overpass returned malformed JSON');
  }
  const elements = (data as { elements?: unknown })?.elements;
  const lines: PowerLineFeature[] = [];
  const points: PowerPointFeature[] = [];
  if (!Array.isArray(elements)) return { lines, points };

  for (const rawEl of elements) {
    const el = rawEl as OverpassElement;
    const tags = el.tags ?? {};
    const kind = isPowerKind(tags.power) ? tags.power : null;
    if (!kind) continue;
    const id = Number(el.id);
    if (!Number.isFinite(id)) continue;
    const voltage = parseVoltage(tags.voltage);
    const operator = typeof tags.operator === 'string' ? tags.operator : null;

    if (el.type === 'way' && Array.isArray(el.geometry)) {
      const path: [number, number][] = [];
      for (const rawPoint of el.geometry as OverpassGeometryPoint[]) {
        const lat = Number(rawPoint?.lat);
        const lon = Number(rawPoint?.lon);
        if (Number.isFinite(lat) && Number.isFinite(lon)) path.push([lon, lat]);
      }
      if (path.length >= 2) lines.push({ id, kind, voltage, operator, path });
    } else if (el.type === 'node') {
      const lat = Number(el.lat);
      const lon = Number(el.lon);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        points.push({ id, kind, voltage, lat, lon });
      }
    }
  }
  return { lines, points };
}

export { OVERPASS_ENDPOINT };
