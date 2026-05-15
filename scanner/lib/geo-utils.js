'use strict';

const EARTH_MILES = 3958.8;

function toRad(deg) { return (deg * Math.PI) / 180; }

/** Haversine distance in miles between two decimal-degree points. */
function distanceMiles(lat1, lon1, lat2, lon2) {
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return EARTH_MILES * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Parse a coordinate value that may be a decimal string or DMS string.
 * Returns a number or null if unparseable.
 */
function parseCoord(raw) {
  if (!raw || raw.trim() === '') return null;
  const f = parseFloat(raw.replace(/[°'"NnSsEeWw\s]/g, ''));
  return isNaN(f) ? null : f;
}

module.exports = { distanceMiles, parseCoord };
