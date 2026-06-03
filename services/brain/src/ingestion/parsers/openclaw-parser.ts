/**
 * OpenClaw field parser
 *
 * Normalises property data captured via the OpenClaw browser extraction
 * workflow.  Accepts two shapes:
 *   1. Structured JSON  — key/value pairs scraped from county assessor portals
 *   2. Raw HTML snippet — a flat <table> or <dl> extracted from the page DOM
 *
 * Returns a Record<string,unknown> that feeds directly into normalizeProperty().
 */

// ─── Field alias map ──────────────────────────────────────────────────────────

const FIELD_ALIASES: Record<string, string> = {
  // Address
  'site address':          'address',
  'situs address':         'address',
  'property address':      'address',
  'location':              'address',
  'street address':        'address',

  // City / state / zip
  'city':                  'city',
  'municipality':          'city',
  'state':                 'state',
  'zip code':              'zip',
  'zip':                   'zip',
  'postal code':           'zip',

  // County / APN
  'county':                'county',
  'parcel number':         'apn',
  'parcel id':             'apn',
  'account number':        'apn',
  'apn':                   'apn',
  'pin':                   'apn',
  'tax id':                'apn',

  // Beds / baths / sqft
  'bedrooms':              'beds',
  'beds':                  'beds',
  'bed':                   'beds',
  'bathrooms':             'baths',
  'baths':                 'baths',
  'bath':                  'baths',
  'living area':           'sqft',
  'living area (sq ft)':   'sqft',
  'building sq ft':        'sqft',
  'heated area':           'sqft',
  'sq ft':                 'sqft',
  'sqft':                  'sqft',
  'gross area':            'sqft',
  'lot size':              'lot_sqft',
  'lot sq ft':             'lot_sqft',
  'lot area':              'lot_sqft',

  // Year built
  'year built':            'year_built',
  'yr built':              'year_built',
  'effective year':        'year_built',

  // Valuation
  'appraised value':       'arv_estimate',
  'total appraised':       'arv_estimate',
  'market value':          'arv_estimate',
  'total market value':    'arv_estimate',
  'assessed value':        'arv_estimate',
  'land + improvement':    'arv_estimate',
  'asking price':          'list_price',
  'list price':            'list_price',
  'sales price':           'list_price',
  'last sale price':       'list_price',

  // Condition / property type
  'condition':             'condition',
  'building condition':    'condition',
  'property type':         'property_type',
  'land use':              'property_type',
  'use code':              'property_type',
  'zoning':                'zoning',
  'zoning code':           'zoning',

  // Distress signals
  'tax delinquent':        'tax_delinquent',
  'delinquent taxes':      'tax_delinquent',
  'past due':              'tax_delinquent',
  'foreclosure':           'pre_foreclosure',
  'lis pendens':           'pre_foreclosure',
  'vacancy':               'vacant',
  'vacant':                'vacant',
  'owner occupied':        'vacant',  // inverted below
};

// ─── HTML → key/value extractor ───────────────────────────────────────────────

function extractFromHtml(html: string): Record<string, string> {
  const result: Record<string, string> = {};

  // <tr><td>Label</td><td>Value</td></tr>
  const trPattern = /<tr[^>]*>[\s\S]*?<\/tr>/gi;
  const tdPattern = /<td[^>]*>([\s\S]*?)<\/td>/gi;

  for (const trMatch of html.matchAll(trPattern)) {
    const cells: string[] = [];
    for (const tdMatch of trMatch[0].matchAll(tdPattern)) {
      cells.push(stripHtml(tdMatch[1]).trim());
    }
    if (cells.length >= 2 && cells[0] && cells[1]) {
      result[cells[0].toLowerCase()] = cells[1];
    }
  }

  // <dt>Label</dt><dd>Value</dd>
  const dlPattern = /<dt[^>]*>([\s\S]*?)<\/dt>\s*<dd[^>]*>([\s\S]*?)<\/dd>/gi;
  for (const m of html.matchAll(dlPattern)) {
    const key = stripHtml(m[1]).trim().toLowerCase();
    const val = stripHtml(m[2]).trim();
    if (key && val) result[key] = val;
  }

  // <span class="label">...</span><span class="value">...</span>
  const spanPattern = /<span[^>]*class="[^"]*label[^"]*"[^>]*>([\s\S]*?)<\/span>\s*<span[^>]*class="[^"]*value[^"]*"[^>]*>([\s\S]*?)<\/span>/gi;
  for (const m of html.matchAll(spanPattern)) {
    const key = stripHtml(m[1]).trim().toLowerCase();
    const val = stripHtml(m[2]).trim();
    if (key && val) result[key] = val;
  }

  return result;
}

function stripHtml(s: string): string {
  return s.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
}

// ─── Alias resolution ─────────────────────────────────────────────────────────

function applyAliases(raw: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  for (const [rawKey, rawVal] of Object.entries(raw)) {
    const canonical = FIELD_ALIASES[rawKey.toLowerCase().trim()] ?? rawKey.toLowerCase().replace(/\s+/g, '_');
    let val: unknown = rawVal;

    // Boolean coercion for distress flags
    if (['tax_delinquent', 'pre_foreclosure', 'vacant'].includes(canonical)) {
      const lower = rawVal.toLowerCase();
      if (canonical === 'vacant' && rawKey.toLowerCase().includes('owner occupied')) {
        val = lower.includes('no') || lower.includes('false');
      } else {
        val = lower.includes('yes') || lower.includes('true') || lower.includes('delinquent') || lower.includes('pending');
      }
    }

    out[canonical] = val;
  }

  return out;
}

// ─── Public API ───────────────────────────────────────────────────────────────

export interface OpenClawParseResult {
  fields:   Record<string, unknown>;
  warnings: string[];
}

/**
 * Parse an OpenClaw capture payload.
 * Accepts either:
 *   { format: 'json',  data: Record<string,unknown> }
 *   { format: 'html',  data: string }
 */
export function parseOpenClawPayload(payload: {
  format: 'json' | 'html';
  data:   Record<string, unknown> | string;
  source?: string;  // e.g. "payne_county_assessor"
}): OpenClawParseResult {
  const warnings: string[] = [];
  let rawKV: Record<string, string> = {};

  if (payload.format === 'html') {
    if (typeof payload.data !== 'string') {
      return { fields: {}, warnings: ['HTML payload must be a string'] };
    }
    rawKV = extractFromHtml(payload.data);
    if (Object.keys(rawKV).length === 0) {
      warnings.push('No fields extracted from HTML — check table/dl structure');
    }
  } else {
    if (typeof payload.data !== 'object' || payload.data === null || Array.isArray(payload.data)) {
      return { fields: {}, warnings: ['JSON payload must be an object'] };
    }
    // Stringify all values so applyAliases works uniformly
    for (const [k, v] of Object.entries(payload.data as Record<string, unknown>)) {
      rawKV[k] = String(v ?? '');
    }
  }

  const fields = applyAliases(rawKV);

  // Warn on critical missing fields
  for (const required of ['address', 'zip', 'arv_estimate']) {
    if (!fields[required]) {
      warnings.push(`Missing required field: ${required}`);
    }
  }

  // Always tag source
  fields['source'] = 'openclaw_scrape';
  if (payload.source) fields['openclaw_source'] = payload.source;

  return { fields, warnings };
}
