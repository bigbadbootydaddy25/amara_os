import { describe, it, expect } from 'vitest';
import { normalizeProperty } from '../ingestion/normalizers/property-normalizer.js';
import { parseCsv } from '../ingestion/parsers/csv-parser.js';
import { ingestDeal, ingestCsvBatch, ingestJsonBatch } from '../ingestion/ingestion-pipeline.js';

describe('Property Normalizer', () => {
  it('normalizes a clean manual input', () => {
    const { property, warnings } = normalizeProperty(
      {
        address: '5000 Oak Lane',
        city: 'Dallas',
        state: 'TX',
        zip: '75201',
        askingPrice: '185000',
        arvEstimate: '260000',
        rehabEstimate: '20000',
        bedrooms: '3',
        taxDelinquent: 'yes',
      },
      'manual',
    );

    expect(property.address).toBe('5000 Oak Lane');
    expect(property.city).toBe('Dallas');
    expect(property.zip).toBe('75201');
    expect(property.askingPrice).toBe(185_000);
    expect(property.arvEstimate).toBe(260_000);
    expect(property.taxDelinquent).toBe(true);
    expect(warnings.length).toBe(0);
  });

  it('strips dollar signs and commas from price fields', () => {
    const { property } = normalizeProperty(
      {
        address: '100 Test St',
        zip: '77001',
        askingPrice: '$145,000',
        arvEstimate: '$210,000',
      },
      'csv_upload',
    );
    expect(property.askingPrice).toBe(145_000);
    expect(property.arvEstimate).toBe(210_000);
  });

  it('swaps inverted ARV low/high and warns', () => {
    const { property, warnings } = normalizeProperty(
      {
        address: '200 Flip St',
        zip: '77002',
        arvLow: '250000',
        arvHigh: '200000',
      },
      'manual',
    );
    expect(property.arvLow).toBe(200_000);
    expect(property.arvHigh).toBe(250_000);
    expect(warnings.some((w) => w.includes('swapping'))).toBe(true);
  });

  it('warns when no ARV provided', () => {
    const { warnings } = normalizeProperty(
      { address: '300 No ARV Ln', zip: '77003', askingPrice: '100000' },
      'manual',
    );
    expect(warnings.some((w) => w.includes('No ARV'))).toBe(true);
  });

  it('estimates rehab from condition grade when not provided', () => {
    const { property } = normalizeProperty(
      {
        address: '400 Rough House Rd',
        zip: '77004',
        arvEstimate: '200000',
        conditionGrade: '2',
      },
      'manual',
    );
    // Grade 2 = heavy rehab = 25% of ARV
    expect(property.rehabEstimate).toBeCloseTo(50_000, -2);
  });

  it('throws on invalid zip', () => {
    expect(() =>
      normalizeProperty({ address: '500 Bad Zip', zip: 'ABCDE' }, 'manual'),
    ).toThrow();
  });

  it('throws on too-short address', () => {
    expect(() =>
      normalizeProperty({ address: 'X', zip: '77001' }, 'manual'),
    ).toThrow();
  });
});

describe('CSV Parser', () => {
  it('parses a valid CSV with header aliases', () => {
    const csv = `address,zip,asking_price,arv,beds,tax_delinquent
100 Main St,77001,150000,220000,3,yes
200 Oak Ave,77002,120000,185000,2,no`;

    const { rows, errors } = parseCsv(csv);
    expect(errors).toHaveLength(0);
    expect(rows).toHaveLength(2);
    expect(rows[0].address).toBe('100 Main St');
    expect(rows[0].askingPrice).toBe('150000');
    expect(rows[0].arvEstimate).toBe('220000');
    expect(rows[0].taxDelinquent).toBe('yes');
  });

  it('handles quoted fields with commas', () => {
    const csv = `address,zip,asking_price
"1234 Oak, Suite 2",77001,150000`;

    const { rows, errors } = parseCsv(csv);
    expect(errors).toHaveLength(0);
    expect(rows[0].address).toBe('1234 Oak, Suite 2');
  });

  it('reports row errors for wrong column count', () => {
    const csv = `address,zip,asking_price
100 Main St,77001`;

    const { errors } = parseCsv(csv);
    expect(errors.length).toBeGreaterThan(0);
  });

  it('returns error for CSV with less than 2 lines', () => {
    const { errors } = parseCsv('just a header');
    expect(errors.length).toBeGreaterThan(0);
  });
});

describe('Ingestion Pipeline', () => {
  it('ingests a single deal and returns simulation', async () => {
    const result = await ingestDeal(
      {
        address: '999 Pipeline Ave',
        city: 'Austin',
        state: 'TX',
        zip: '78701',
        askingPrice: 160_000,
        arvEstimate: 240_000,
        rehabEstimate: 18_000,
      },
      { source: 'manual' },
    );

    expect(result.success).toBe(true);
    expect(result.propertyId).toBeTruthy();
    expect(result.simulationId).toBeTruthy();
    expect(result.processingMs).toBeGreaterThanOrEqual(0);
  });

  it('returns failure on invalid input', async () => {
    const result = await ingestDeal({ address: 'X', zip: 'BAD' }, { source: 'manual' });
    expect(result.success).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('ingests CSV batch', async () => {
    const csv = `address,zip,asking_price,arv
100 Batch St,77001,140000,210000
200 Batch Ave,77002,130000,195000`;

    const result = await ingestCsvBatch(csv, { source: 'csv_upload' });
    expect(result.total).toBe(2);
    expect(result.succeeded).toBe(2);
    expect(result.failed).toBe(0);
  });

  it('ingests JSON batch', async () => {
    const json = JSON.stringify([
      { address: '10 JSON Ln', zip: '77001', askingPrice: 145000, arvEstimate: 215000 },
      { address: '20 JSON Blvd', zip: '77002', askingPrice: 125000, arvEstimate: 190000 },
    ]);

    const result = await ingestJsonBatch(json, { source: 'json_upload' });
    expect(result.total).toBe(2);
    expect(result.succeeded).toBe(2);
  });

  it('handles partial batch failure gracefully', async () => {
    const json = JSON.stringify([
      { address: '10 Good St', zip: '77001', askingPrice: 145000 },
      { address: 'X', zip: 'BAD' }, // invalid
    ]);

    const result = await ingestJsonBatch(json, { source: 'json_upload' });
    expect(result.total).toBe(2);
    expect(result.succeeded).toBe(1);
    expect(result.failed).toBe(1);
  });
});
