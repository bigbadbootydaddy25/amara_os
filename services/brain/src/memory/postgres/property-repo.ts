import type pg from 'pg';
import type { Property } from '../../types.js';
import { getPool } from './pool.js';

export interface PropertyRow {
  id: string;
  created_at: Date;
  updated_at: Date;
  address: string;
  city: string;
  state: string;
  zip: string;
  county: string | null;
  apn: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  lot_sqft: number | null;
  year_built: number | null;
  property_type: string | null;
  condition_grade: number | null;
  rehab_estimate: string | null;
  asking_price: string | null;
  arv_estimate: string | null;
  arv_low: string | null;
  arv_high: string | null;
  tax_delinquent: boolean;
  bankruptcy: boolean;
  liens: boolean;
  vacant: boolean;
  pre_foreclosure: boolean;
  ingestion_source: string;
  raw_input: unknown;
  notes: string | null;
}

function rowToProperty(row: PropertyRow): Property {
  return {
    id:              row.id,
    address:         row.address,
    city:            row.city,
    state:           row.state,
    zip:             row.zip,
    county:          row.county ?? undefined,
    apn:             row.apn ?? undefined,
    bedrooms:        row.bedrooms ?? undefined,
    bathrooms:       row.bathrooms ?? undefined,
    sqft:            row.sqft ?? undefined,
    yearBuilt:       row.year_built ?? undefined,
    conditionGrade:  row.condition_grade ?? undefined,
    rehabEstimate:   row.rehab_estimate ? parseFloat(row.rehab_estimate) : undefined,
    askingPrice:     row.asking_price ? parseFloat(row.asking_price) : undefined,
    arvEstimate:     row.arv_estimate ? parseFloat(row.arv_estimate) : undefined,
    arvLow:          row.arv_low ? parseFloat(row.arv_low) : undefined,
    arvHigh:         row.arv_high ? parseFloat(row.arv_high) : undefined,
    taxDelinquent:   row.tax_delinquent,
    bankruptcy:      row.bankruptcy,
    liens:           row.liens,
    vacant:          row.vacant,
    preForeclosure:  row.pre_foreclosure,
    ingestionSource: row.ingestion_source as Property['ingestionSource'],
    notes:           row.notes ?? undefined,
  };
}

export const PropertyRepo = {
  async create(property: Property, client?: pg.PoolClient): Promise<string> {
    const db = client ?? getPool();
    const result = await db.query<{ id: string }>(
      `INSERT INTO properties (
        id, address, city, state, zip, county, apn,
        bedrooms, bathrooms, sqft, year_built, condition_grade,
        rehab_estimate, asking_price, arv_estimate, arv_low, arv_high,
        tax_delinquent, bankruptcy, liens, vacant, pre_foreclosure,
        ingestion_source, raw_input, notes
      ) VALUES (
        $1,$2,$3,$4,$5,$6,$7,
        $8,$9,$10,$11,$12,
        $13,$14,$15,$16,$17,
        $18,$19,$20,$21,$22,
        $23,$24,$25
      )
      ON CONFLICT (id) DO UPDATE SET
        updated_at = NOW(),
        asking_price = EXCLUDED.asking_price,
        arv_estimate = EXCLUDED.arv_estimate,
        notes = EXCLUDED.notes
      RETURNING id`,
      [
        property.id,
        property.address,
        property.city,
        property.state,
        property.zip,
        property.county ?? null,
        property.apn ?? null,
        property.bedrooms ?? null,
        property.bathrooms ?? null,
        property.sqft ?? null,
        property.yearBuilt ?? null,
        property.conditionGrade ?? null,
        property.rehabEstimate ?? null,
        property.askingPrice ?? null,
        property.arvEstimate ?? null,
        property.arvLow ?? null,
        property.arvHigh ?? null,
        property.taxDelinquent ?? false,
        property.bankruptcy ?? false,
        property.liens ?? false,
        property.vacant ?? false,
        property.preForeclosure ?? false,
        property.ingestionSource,
        property.rawInput ? JSON.stringify(property.rawInput) : null,
        property.notes ?? null,
      ],
    );
    return result.rows[0].id;
  },

  async findById(id: string): Promise<Property | null> {
    const result = await getPool().query<PropertyRow>(
      'SELECT * FROM properties WHERE id = $1',
      [id],
    );
    return result.rows[0] ? rowToProperty(result.rows[0]) : null;
  },

  async findByZip(zip: string, limit = 50): Promise<Property[]> {
    const result = await getPool().query<PropertyRow>(
      'SELECT * FROM properties WHERE zip = $1 ORDER BY created_at DESC LIMIT $2',
      [zip, limit],
    );
    return result.rows.map(rowToProperty);
  },

  async search(params: {
    zip?: string;
    state?: string;
    minArv?: number;
    maxArv?: number;
    limit?: number;
  }): Promise<Property[]> {
    const conditions: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (params.zip) { conditions.push(`zip = $${idx++}`); values.push(params.zip); }
    if (params.state) { conditions.push(`state = $${idx++}`); values.push(params.state); }
    if (params.minArv) { conditions.push(`arv_estimate >= $${idx++}`); values.push(params.minArv); }
    if (params.maxArv) { conditions.push(`arv_estimate <= $${idx++}`); values.push(params.maxArv); }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
    const limit = params.limit ?? 50;
    const result = await getPool().query<PropertyRow>(
      `SELECT * FROM properties ${where} ORDER BY created_at DESC LIMIT $${idx}`,
      [...values, limit],
    );
    return result.rows.map(rowToProperty);
  },
};
