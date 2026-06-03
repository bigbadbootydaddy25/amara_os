import { describe, it, expect } from 'vitest';
import { parseOpenClawPayload } from '../ingestion/parsers/openclaw-parser.js';

// ─── JSON format ──────────────────────────────────────────────────────────────

describe('OpenClaw Parser — JSON format', () => {
  it('parses a standard assessor JSON payload', () => {
    const { fields, warnings } = parseOpenClawPayload({
      format: 'json',
      data: {
        'Property Address': '789 Oak St',
        'City':             'Edmond',
        'State':            'OK',
        'Zip Code':         '73034',
        'Parcel Number':    '12345-678',
        'Living Area':      '1800',
        'Year Built':       '1995',
        'Total Market Value': '250000',
        'Bedrooms':         '4',
        'Bathrooms':        '2',
      },
      source: 'oklahoma_county_assessor',
    });

    expect(fields.address).toBe('789 Oak St');
    expect(fields.city).toBe('Edmond');
    expect(fields.zip).toBe('73034');
    expect(fields.apn).toBe('12345-678');
    expect(fields.sqft).toBe('1800');
    expect(fields.year_built).toBe('1995');
    expect(fields.arv_estimate).toBe('250000');
    expect(fields.beds).toBe('4');
    expect(fields.source).toBe('openclaw_scrape');
    expect(fields.openclaw_source).toBe('oklahoma_county_assessor');
    expect(warnings).toHaveLength(0);
  });

  it('warns on missing required fields', () => {
    const { warnings } = parseOpenClawPayload({
      format: 'json',
      data: { City: 'Tulsa', State: 'OK' },
    });
    expect(warnings.some((w) => w.includes('address'))).toBe(true);
    expect(warnings.some((w) => w.includes('zip'))).toBe(true);
    expect(warnings.some((w) => w.includes('arv_estimate'))).toBe(true);
  });

  it('coerces boolean distress fields from yes/no', () => {
    const { fields } = parseOpenClawPayload({
      format: 'json',
      data: {
        'Property Address': '1 Test',
        'Zip Code': '73000',
        'Total Market Value': '100000',
        'Tax Delinquent': 'Yes',
        'Vacant': 'No',
        'Foreclosure': 'Pending',
      },
    });
    expect(fields.tax_delinquent).toBe(true);
    expect(fields.pre_foreclosure).toBe(true);
  });

  it('handles non-object JSON data gracefully', () => {
    const { fields, warnings } = parseOpenClawPayload({
      format: 'json',
      data: 'not an object' as unknown as Record<string, unknown>,
    });
    expect(Object.keys(fields)).toHaveLength(0);
    expect(warnings.length).toBeGreaterThan(0);
  });
});

// ─── HTML format ──────────────────────────────────────────────────────────────

describe('OpenClaw Parser — HTML format', () => {
  it('extracts fields from a <table> structure', () => {
    const html = `
      <table>
        <tr><td>Property Address</td><td>321 Elm Ave</td></tr>
        <tr><td>Zip Code</td><td>73101</td></tr>
        <tr><td>Total Market Value</td><td>$185,000</td></tr>
        <tr><td>Year Built</td><td>1978</td></tr>
        <tr><td>Living Area</td><td>1,350</td></tr>
      </table>`;

    const { fields, warnings } = parseOpenClawPayload({ format: 'html', data: html });
    expect(fields.address).toBe('321 Elm Ave');
    expect(fields.zip).toBe('73101');
    expect(fields.arv_estimate).toBe('$185,000');
    expect(fields.year_built).toBe('1978');
  });

  it('extracts fields from a <dl> structure', () => {
    const html = `
      <dl>
        <dt>Site Address</dt><dd>99 Maple Rd</dd>
        <dt>Zip Code</dt><dd>74103</dd>
        <dt>Market Value</dt><dd>195000</dd>
      </dl>`;
    const { fields } = parseOpenClawPayload({ format: 'html', data: html });
    expect(fields.address).toBe('99 Maple Rd');
    expect(fields.zip).toBe('74103');
  });

  it('warns when no fields extracted from HTML', () => {
    const { warnings } = parseOpenClawPayload({ format: 'html', data: '<p>Nothing useful here</p>' });
    expect(warnings.some((w) => w.includes('No fields extracted'))).toBe(true);
  });

  it('strips HTML tags from extracted values', () => {
    const html = `<table><tr><td>Property Address</td><td><b>456 Bold St</b></td></tr>
    <tr><td>Zip Code</td><td>73000</td></tr>
    <tr><td>Total Market Value</td><td>150000</td></tr>
    </table>`;
    const { fields } = parseOpenClawPayload({ format: 'html', data: html });
    expect(fields.address).toBe('456 Bold St');
  });

  it('rejects non-string HTML data', () => {
    const { warnings } = parseOpenClawPayload({
      format: 'html',
      data: { not: 'a string' } as unknown as string,
    });
    expect(warnings.some((w) => w.includes('string'))).toBe(true);
  });
});

// ─── Field alias coverage ─────────────────────────────────────────────────────

describe('OpenClaw Parser — field alias coverage', () => {
  // Each alias case uses only the single field under test plus non-conflicting required fields
  const ALIAS_CASES: Array<[string, string, string, Record<string, string>]> = [
    ['Situs Address',   '1 Main',  'address',       { 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Parcel ID',       'ABC-123', 'apn',            { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Building Sq Ft',  '1200',    'sqft',           { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Heated Area',     '1100',    'sqft',           { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Appraised Value', '200000',  'arv_estimate',   { 'Property Address': '1 T', 'Zip Code': '73000' }],
    ['Assessed Value',  '180000',  'arv_estimate',   { 'Property Address': '1 T', 'Zip Code': '73000' }],
    ['Last Sale Price', '155000',  'list_price',     { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Land Use',        'RES',     'property_type',  { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
    ['Zoning Code',     'R-1',     'zoning',         { 'Property Address': '1 T', 'Zip Code': '73000', 'Total Market Value': '100000' }],
  ];

  for (const [rawKey, rawVal, canonical, base] of ALIAS_CASES) {
    it(`maps "${rawKey}" → ${canonical}`, () => {
      const { fields } = parseOpenClawPayload({
        format: 'json',
        data: { [rawKey]: rawVal, ...base },
      });
      expect(fields[canonical]).toBe(rawVal);
    });
  }
});
