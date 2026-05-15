'use strict';

/**
 * Timestamped raw-data cache.
 *
 * Files are written to data/{county}/raw/ using two paths:
 *   {source}-{YYYY-MM-DD}.csv  — date-stamped archive
 *   {source}.csv               — "latest" copy, read by analysis agents
 *
 * Freshness: same calendar day (UTC) = fresh; older = stale.
 */

const fs   = require('node:fs');
const path = require('node:path');

const RAW_BASE = path.resolve(__dirname, '../../data');

function rawDir(countySlug) {
  return path.join(RAW_BASE, countySlug, 'raw');
}

function todayTag() {
  return new Date().toISOString().slice(0, 10);   // YYYY-MM-DD
}

/**
 * Check whether a cached copy is fresh (pulled today).
 * Returns the path to the latest file if fresh, null otherwise.
 */
function isFresh(countySlug, sourceName) {
  const dated = path.join(rawDir(countySlug), `${sourceName}-${todayTag()}.csv`);
  const latest = path.join(rawDir(countySlug), `${sourceName}.csv`);

  if (fs.existsSync(dated) && fs.statSync(dated).size > 0) return latest;
  return null;
}

/**
 * Write CSV content to both the dated archive and the latest symlink.
 * Returns the path to the latest file.
 */
function writeCache(countySlug, sourceName, csvContent) {
  const dir     = rawDir(countySlug);
  const dated   = path.join(dir, `${sourceName}-${todayTag()}.csv`);
  const latest  = path.join(dir, `${sourceName}.csv`);

  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(dated,  csvContent, 'utf8');
  fs.writeFileSync(latest, csvContent, 'utf8');

  return latest;
}

/**
 * Read the latest cached file for a source. Returns null if not present.
 */
function readCache(countySlug, sourceName) {
  const latest = path.join(rawDir(countySlug), `${sourceName}.csv`);
  if (!fs.existsSync(latest)) return null;
  const content = fs.readFileSync(latest, 'utf8');
  return content.trim() ? content : null;
}

/**
 * List all dated archives for a source (for cleanup / audit).
 */
function listArchives(countySlug, sourceName) {
  const dir = rawDir(countySlug);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.startsWith(`${sourceName}-`) && f.endsWith('.csv'))
    .sort();
}

module.exports = { rawDir, isFresh, writeCache, readCache, listArchives };
