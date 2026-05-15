'use strict';

const fs       = require('node:fs');
const readline = require('node:readline');

/**
 * Parse a CSV file into an array of objects.
 *
 * opts.aliases  — { CANONICAL: ['ALT1', 'ALT2', ...] }
 *                 Resolved after upcasing the header row.
 *
 * Throws:
 *   CSV_MISSING: <path>   — file does not exist
 *   CSV_EMPTY:   <path>   — file is 0 bytes or contains only a header
 */
async function parseCSV(filePath, opts = {}) {
  if (!fs.existsSync(filePath)) {
    throw Object.assign(new Error(`CSV_MISSING: ${filePath}`), { code: 'CSV_MISSING' });
  }

  const stat = fs.statSync(filePath);
  if (stat.size === 0) {
    throw Object.assign(new Error(`CSV_EMPTY: ${filePath}`), { code: 'CSV_EMPTY' });
  }

  const rl = readline.createInterface({
    input: fs.createReadStream(filePath, { encoding: opts.encoding ?? 'utf8' }),
    crlfDelay: Infinity,
  });

  const lines = [];
  for await (const raw of rl) {
    // Strip UTF-8 BOM if present on first line
    const line = lines.length === 0 ? raw.replace(/^﻿/, '') : raw;
    if (line.trim()) lines.push(line);
  }

  if (lines.length < 2) {
    throw Object.assign(new Error(`CSV_EMPTY: ${filePath}`), { code: 'CSV_EMPTY' });
  }

  // --- Header resolution ---
  const rawHeaders = splitRow(lines[0]).map((h) => h.trim().toUpperCase().replace(/\s+/g, '_'));

  // Build alias map: 'ALT_HEADER' → 'CANONICAL'
  const aliasLookup = {};
  for (const [canonical, variants] of Object.entries(opts.aliases ?? {})) {
    for (const v of variants) aliasLookup[v.toUpperCase()] = canonical;
  }

  const headers = rawHeaders.map((h) => aliasLookup[h] ?? h);

  // --- Rows ---
  const records = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = splitRow(lines[i]);
    const rec   = {};
    headers.forEach((h, idx) => {
      rec[h] = (cells[idx] ?? '').trim();
    });
    records.push(rec);
  }

  return records;
}

/** RFC-4180-compliant field splitter. */
function splitRow(line) {
  const fields = [];
  let cur = '';
  let inQ = false;

  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
      else inQ = !inQ;
    } else if (c === ',' && !inQ) {
      fields.push(cur); cur = '';
    } else {
      cur += c;
    }
  }
  fields.push(cur);
  return fields;
}

/** Parse a government date string into a Date (or null). */
function parseGovDate(raw) {
  if (!raw || raw.trim() === '') return null;
  const s = raw.trim();

  // MM/DD/YYYY or M/D/YYYY
  const mdy = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (mdy) return new Date(`${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`);

  // YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return new Date(s.slice(0, 10));

  // MM/DD/YY
  const mdyy = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/);
  if (mdyy) {
    const yr = parseInt(mdyy[3], 10);
    const full = yr >= 50 ? 1900 + yr : 2000 + yr;
    return new Date(`${full}-${mdyy[1].padStart(2, '0')}-${mdyy[2].padStart(2, '0')}`);
  }

  // Excel serial date (numeric string)
  if (/^\d{5}$/.test(s)) {
    const serial = parseInt(s, 10);
    return new Date((serial - 25569) * 86400000); // Excel epoch 1900-01-01
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

/** Return a float from various numeric-string formats ('$1,234.56' → 1234.56). */
function parseAmount(raw) {
  if (!raw || raw.trim() === '') return 0;
  const cleaned = raw.replace(/[$,\s]/g, '');
  const n = parseFloat(cleaned);
  return isNaN(n) ? 0 : n;
}

module.exports = { parseCSV, parseGovDate, parseAmount };
