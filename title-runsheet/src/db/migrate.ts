import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { Pool } from 'pg';
import { env } from '../config/env.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const schemaPath = path.resolve(__dirname, '../../db/schema.sql');
  const sql = readFileSync(schemaPath, 'utf8');

  const pool = new Pool({ connectionString: env.databaseUrl() });
  try {
    console.log(`Applying schema from ${schemaPath} ...`);
    await pool.query(sql);
    console.log('Schema applied successfully.');
  } finally {
    await pool.end();
  }
}

main().catch((err) => {
  console.error('Migration failed:', err);
  process.exitCode = 1;
});
