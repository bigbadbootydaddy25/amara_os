'use strict';

/**
 * Static-page HTTP client using axios + cheerio.
 * Used for government portals that render HTML without JS hydration.
 */

const axios   = require('axios');
const cheerio = require('cheerio');

const USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const DEFAULT_TIMEOUT = 30_000;
const DEFAULT_RETRIES = 3;
const RETRY_DELAY_MS  = 4_000;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

/**
 * GET a URL and return { status, data, headers, $ } where $ is a cheerio instance.
 */
async function get(url, opts = {}) {
  const retries = opts.retries ?? DEFAULT_RETRIES;

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const resp = await axios.get(url, {
        timeout: opts.timeout ?? DEFAULT_TIMEOUT,
        responseType: opts.binary ? 'arraybuffer' : 'text',
        headers: {
          'User-Agent': USER_AGENT,
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9',
          'Accept-Encoding': 'gzip, deflate, br',
          ...(opts.headers ?? {}),
        },
        maxRedirects: 10,
        validateStatus: (s) => s < 500,
      });

      if (resp.status === 429 || resp.status === 503) {
        const wait = attempt * RETRY_DELAY_MS * 2;
        if (attempt < retries) { await sleep(wait); continue; }
      }

      const html = typeof resp.data === 'string' ? resp.data : resp.data?.toString?.('utf8') ?? '';
      const $    = cheerio.load(html);

      return { status: resp.status, data: resp.data, html, $, headers: resp.headers };
    } catch (err) {
      if (attempt < retries) {
        await sleep(attempt * RETRY_DELAY_MS);
        continue;
      }
      throw err;
    }
  }
}

/**
 * POST to a URL (form submit style) and return { status, data, html, $ }.
 */
async function post(url, body, opts = {}) {
  const resp = await axios.post(url, body, {
    timeout: opts.timeout ?? DEFAULT_TIMEOUT,
    headers: {
      'User-Agent': USER_AGENT,
      'Content-Type': opts.contentType ?? 'application/x-www-form-urlencoded',
      'Accept': 'text/html,application/xhtml+xml,*/*',
      ...(opts.headers ?? {}),
    },
    maxRedirects: 10,
    validateStatus: (s) => s < 500,
  });

  const html = typeof resp.data === 'string' ? resp.data : '';
  const $    = cheerio.load(html);
  return { status: resp.status, data: resp.data, html, $, headers: resp.headers };
}

/**
 * Download a binary file (CSV, XLS, XLSX) and return the buffer.
 */
async function download(url, opts = {}) {
  const resp = await axios.get(url, {
    timeout: opts.timeout ?? 60_000,
    responseType: 'arraybuffer',
    headers: {
      'User-Agent': USER_AGENT,
      ...(opts.headers ?? {}),
    },
    maxRedirects: 10,
  });
  return resp.data;
}

/**
 * Extract all rows from the first matching HTML table.
 * Returns { headers: string[], rows: string[][] }
 */
function parseTable($, tableSelector = 'table') {
  const table = $(tableSelector).first();
  if (!table.length) return { headers: [], rows: [] };

  const headers = [];
  table.find('thead tr th, thead tr td').each((_, el) => {
    headers.push($(el).text().trim().replace(/\s+/g, ' '));
  });

  // Some gov sites put headers in the first tbody tr
  const bodyRows = [];
  table.find('tbody tr').each((_, tr) => {
    const cells = [];
    $(tr).find('td, th').each((_, td) => cells.push($(td).text().trim().replace(/\s+/g, ' ')));
    if (cells.some((c) => c)) bodyRows.push(cells);
  });

  // If no thead, use first row as headers
  if (!headers.length && bodyRows.length) {
    headers.push(...bodyRows.shift());
  }

  return { headers, rows: bodyRows };
}

/**
 * Parse ALL matching tables on the page.
 */
function parseTables($, tableSelector = 'table') {
  const results = [];
  $(tableSelector).each((_, table) => {
    results.push(parseTable(cheerio.load($.html(table))));
  });
  return results;
}

/**
 * Serialise { headers, rows } to a CSV string.
 */
function toCsv({ headers, rows }) {
  function escape(v) {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  }

  const lines = [headers.map(escape).join(',')];
  for (const row of rows) {
    lines.push(headers.map((_, i) => escape(row[i] ?? '')).join(','));
  }
  return lines.join('\n');
}

/**
 * Parse a JSON API response into CSV format given a field map.
 * fieldMap: { CSV_COLUMN: 'jsonKey' | (item => value) }
 */
function jsonToCsv(items, fieldMap) {
  const headers = Object.keys(fieldMap);
  const rows = items.map((item) =>
    headers.map((h) => {
      const spec = fieldMap[h];
      return typeof spec === 'function' ? spec(item) : (item[spec] ?? '');
    }),
  );
  return toCsv({ headers, rows });
}

module.exports = { get, post, download, parseTable, parseTables, toCsv, jsonToCsv };
