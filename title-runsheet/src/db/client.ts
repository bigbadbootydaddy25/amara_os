import { Pool, types, type QueryResultRow } from 'pg';
import { env } from '../config/env.js';

// node-postgres returns `numeric`/`decimal` columns as strings by default
// (to avoid silent precision loss on huge values) — our numeric columns
// (confidence, net_mineral_acres) are small and meant to be used as JS
// numbers everywhere, so parse them eagerly instead of making every caller
// remember to Number() them.
const PG_NUMERIC_OID = 1700;
types.setTypeParser(PG_NUMERIC_OID, (value: string) => (value === null ? null : parseFloat(value)));

// node-postgres parses `date` columns into a JS Date at local midnight,
// which both shifts the calendar day under most timezones and silently
// stringifies to an epoch-ms number in CSV export. Our `date` columns
// (execution_date, recording_date) are always used as plain "YYYY-MM-DD"
// strings (Project/InstrumentRow types agree), so keep Postgres's own
// text representation instead of letting it become a Date.
const PG_DATE_OID = 1082;
types.setTypeParser(PG_DATE_OID, (value: string) => value);

let pool: Pool | undefined;

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({ connectionString: env.databaseUrl() });
  }
  return pool;
}

export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const result = await getPool().query<T>(text, params);
  return result.rows;
}

export async function queryOne<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params: unknown[] = [],
): Promise<T | undefined> {
  const rows = await query<T>(text, params);
  return rows[0];
}

export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = undefined;
  }
}
