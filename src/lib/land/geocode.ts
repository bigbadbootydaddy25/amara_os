/**
 * Address/place search against OpenStreetMap's Nominatim, the same free,
 * keyless geocoder gods-eye-view uses for its search box. No API key
 * required; usage-policy limited (identify with a real User-Agent, keep
 * request volume low). Swap this module out if you later license a
 * commercial parcel/geocoding API.
 */

const NOMINATIM_BASE = 'https://nominatim.openstreetmap.org/search';

export interface GeocodeResult {
  displayName: string;
  lat: number;
  lon: number;
  boundingBox: [south: number, north: number, west: number, east: number] | null;
  category: string | null;
}

export function buildNominatimUrl(query: string, limit = 5): string {
  const trimmed = query.trim();
  if (!trimmed) throw new Error('Empty search query');
  const params = new URLSearchParams({
    q: trimmed,
    format: 'jsonv2',
    limit: String(Math.max(1, Math.min(limit, 10))),
    addressdetails: '0',
  });
  return `${NOMINATIM_BASE}?${params.toString()}`;
}

interface NominatimRow {
  display_name?: unknown;
  lat?: unknown;
  lon?: unknown;
  boundingbox?: unknown;
  category?: unknown;
  type?: unknown;
}

/** Parse and validate a Nominatim JSON response into normalized results. */
export function parseNominatimResults(body: string): GeocodeResult[] {
  let data: unknown;
  try {
    data = JSON.parse(body);
  } catch {
    throw new Error('Geocoder returned malformed JSON');
  }
  if (!Array.isArray(data)) return [];

  const results: GeocodeResult[] = [];
  for (const rawRow of data) {
    const row = rawRow as NominatimRow;
    const lat = Number(row.lat);
    const lon = Number(row.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) continue;

    let boundingBox: GeocodeResult['boundingBox'] = null;
    if (Array.isArray(row.boundingbox) && row.boundingbox.length === 4) {
      const nums = row.boundingbox.map(Number) as [number, number, number, number];
      if (nums.every(Number.isFinite)) boundingBox = nums;
    }

    results.push({
      displayName: typeof row.display_name === 'string' ? row.display_name : `${lat}, ${lon}`,
      lat,
      lon,
      boundingBox,
      category:
        typeof row.category === 'string'
          ? row.category
          : typeof row.type === 'string'
            ? row.type
            : null,
    });
  }
  return results;
}
