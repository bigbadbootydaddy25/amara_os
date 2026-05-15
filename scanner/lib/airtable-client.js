'use strict';

const log = require('./logger').agent('airtable');

const BASE_ID    = process.env.AIRTABLE_BASE_ID  || 'app0jn857ZwVzQs8i';
const TABLE_NAME = process.env.AIRTABLE_TABLE     || 'Land Pipeline';
const API_KEY    = process.env.AIRTABLE_API_KEY   || '';

const BASE_URL = `https://api.airtable.com/v0/${BASE_ID}/${encodeURIComponent(TABLE_NAME)}`;

/**
 * Push a single record to Airtable.
 * Returns { ok, id } on success; { ok: false, reason, error } on failure.
 * Never throws — callers log and continue.
 */
async function pushRecord(fields) {
  if (!API_KEY) {
    log.warn('AIRTABLE_API_KEY not set — skipping push');
    return { ok: false, reason: 'no-api-key' };
  }

  try {
    const res = await fetch(BASE_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ fields }),
      signal: AbortSignal.timeout(15_000),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => res.statusText);
      throw new Error(`HTTP ${res.status}: ${body}`);
    }

    const data = await res.json();
    log.info(`Record created: ${data.id}`);
    return { ok: true, id: data.id };
  } catch (err) {
    log.warn(`Push failed: ${err.message}`);
    return { ok: false, reason: 'api-error', error: err.message };
  }
}

module.exports = { pushRecord };
