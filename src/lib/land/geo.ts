/** Small geo helpers shared by the land-intelligence module. No I/O. */

export interface LonLat {
  lon: number;
  lat: number;
}

export interface BBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

const EARTH_RADIUS_M = 6_371_000;

/**
 * Bounding box of radiusM meters around a point, in WGS84 degrees.
 * Longitude delta widens near the poles via cos(lat); clamped so a
 * high-latitude query never wraps past +/-180.
 */
export function bboxAroundPoint({ lon, lat }: LonLat, radiusM: number): BBox {
  const latDelta = (radiusM / EARTH_RADIUS_M) * (180 / Math.PI);
  const lonScale = Math.max(Math.cos((lat * Math.PI) / 180), 0.01);
  const lonDelta = (radiusM / (EARTH_RADIUS_M * lonScale)) * (180 / Math.PI);
  return {
    minLon: Math.max(lon - lonDelta, -180),
    maxLon: Math.min(lon + lonDelta, 180),
    minLat: Math.max(lat - latDelta, -90),
    maxLat: Math.min(lat + latDelta, 90),
  };
}

export function isFiniteCoordinate(lon: unknown, lat: unknown): lon is number {
  return (
    typeof lon === 'number' &&
    typeof lat === 'number' &&
    Number.isFinite(lon) &&
    Number.isFinite(lat) &&
    lon >= -180 &&
    lon <= 180 &&
    lat >= -90 &&
    lat <= 90
  );
}

/** Haversine great-circle distance in meters. */
export function distanceMeters(a: LonLat, b: LonLat): number {
  const toRad = (v: number) => (v * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h =
    sinLat * sinLat +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * sinLon * sinLon;
  return EARTH_RADIUS_M * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}
