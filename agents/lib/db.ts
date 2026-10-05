import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { PATHS, RULESET_VERSION } from '../config';

export type DB = DatabaseSync;

// Spec §6 tables, plus the extra columns/tables the spec's own rules need
// (marked "-- ext"). Nothing from §6 is dropped.
const SCHEMA = `
CREATE TABLE IF NOT EXISTS deeds (
  id INTEGER PRIMARY KEY, county TEXT NOT NULL, instrument_no TEXT NOT NULL, type TEXT,
  record_date TEXT NOT NULL, grantor TEXT, grantee TEXT, consideration REAL, legal TEXT, apn TEXT,
  source TEXT, tag TEXT,
  UNIQUE (county, instrument_no)
);
CREATE INDEX IF NOT EXISTS deeds_apn ON deeds(apn);
CREATE TABLE IF NOT EXISTS deeds_of_trust (
  id INTEGER PRIMARY KEY, county TEXT NOT NULL, instrument_no TEXT NOT NULL, record_date TEXT NOT NULL,
  grantor TEXT, lender TEXT, amount REAL, apn TEXT,
  source TEXT, tag TEXT, -- ext
  UNIQUE (county, instrument_no)
);
CREATE TABLE IF NOT EXISTS properties (
  apn TEXT NOT NULL, county TEXT NOT NULL, address TEXT, zip TEXT, land_use TEXT,
  beds REAL, baths REAL, sqft REAL, year_built INTEGER, cad_value REAL, owner TEXT, owner_mailing TEXT,
  land_use_prior TEXT, improvement_value REAL, improvement_value_prior REAL, -- ext (lot track)
  last_sale_date TEXT, source TEXT, tag TEXT,                                  -- ext
  PRIMARY KEY (county, apn)
);
CREATE TABLE IF NOT EXISTS buyers (
  id INTEGER PRIMARY KEY, normalized_name TEXT NOT NULL UNIQUE, buyer_group_id TEXT, type TEXT,
  registered_agent TEXT, mailing TEXT, phone TEXT, email TEXT, contact_tag TEXT,
  display_name TEXT,                                -- ext
  verified_repeat_buyer INTEGER DEFAULT 0,          -- ext: >=2 SFR cash buys in 12 mo (own purchases)
  verified_repeat_lot_buyer INTEGER DEFAULT 0,      -- ext
  confirmed_builder INTEGER DEFAULT 0,              -- ext: permit / CAD improvement evidence [GR]
  repeat_basis TEXT                                 -- ext: 'grantee' | 'group'
);
CREATE TABLE IF NOT EXISTS excluded_buyers (        -- ext (spec 5.1: separate table)
  normalized_name TEXT PRIMARY KEY, category TEXT NOT NULL, example_deed_id INTEGER
);
CREATE TABLE IF NOT EXISTS buyer_purchases (
  buyer_id INTEGER NOT NULL, apn TEXT, deed_id INTEGER NOT NULL, date TEXT, price REAL,
  cash_buy INTEGER NOT NULL, hard_money INTEGER NOT NULL,
  asset_type TEXT NOT NULL,                         -- ext: sfr | infill_lot
  PRIMARY KEY (buyer_id, deed_id)
);
CREATE TABLE IF NOT EXISTS buy_boxes (
  buyer_group_id TEXT NOT NULL, asset_type TEXT NOT NULL, zips TEXT, price_min REAL, price_max REAL,
  beds_min REAL, beds_max REAL, sqft_min REAL, sqft_max REAL, year_min INTEGER, year_max INTEGER,
  strategy TEXT, confidence TEXT, last_buy_date TEXT,
  buys_12m INTEGER, buys_90d INTEGER, price_median REAL, condition_proxy TEXT, -- ext
  details TEXT,                                                                -- ext: JSON (lot fields, baths, evidence)
  PRIMARY KEY (buyer_group_id, asset_type)
);
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY, apn TEXT, asset_type TEXT NOT NULL, distress_type TEXT, distress_date TEXT,
  source TEXT, tag TEXT, status TEXT NOT NULL DEFAULT 'new',
  county TEXT, address TEXT, zip TEXT, asking_price REAL, evidence_url TEXT, -- ext
  dedupe_key TEXT UNIQUE                                                      -- ext
);
CREATE TABLE IF NOT EXISTS lot_details (
  apn TEXT NOT NULL, county TEXT NOT NULL DEFAULT 'Dallas', lot_sqft REAL, frontage_ft REAL,
  zoning TEXT, flood_zone TEXT, water_sewer TEXT, tag TEXT,
  floodway INTEGER DEFAULT 0,                                                  -- ext
  PRIMARY KEY (county, apn)
);
CREATE TABLE IF NOT EXISTS permits (
  permit_no TEXT NOT NULL, city TEXT, apn TEXT, type TEXT, issue_date TEXT, applicant TEXT, valuation REAL,
  PRIMARY KEY (city, permit_no)
);
CREATE TABLE IF NOT EXISTS matches (
  lead_id INTEGER NOT NULL, buyer_group_id TEXT NOT NULL, score INTEGER NOT NULL, reasons TEXT, created_at TEXT,
  asset_type TEXT, confidence_tag TEXT, rank INTEGER,                         -- ext
  PRIMARY KEY (lead_id, buyer_group_id)
);
CREATE TABLE IF NOT EXISTS sources (
  name TEXT PRIMARY KEY, county TEXT, access_status TEXT NOT NULL, terms_checked_date TEXT, mode TEXT,
  evidence_tier TEXT, paid INTEGER                                            -- ext
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, started TEXT NOT NULL, finished TEXT,
  records_in INTEGER, records_out INTEGER, ruleset_version TEXT NOT NULL, errors TEXT
);
-- ext: research feed queue (spec §7): everything [SR], awaiting [GR] verification
CREATE TABLE IF NOT EXISTS research_buyers (
  id INTEGER PRIMARY KEY, normalized_name TEXT, name TEXT, entity_type TEXT, asset_type TEXT, county TEXT,
  zip_list TEXT, evidence_url TEXT NOT NULL, evidence_summary TEXT, date_found TEXT, tool TEXT,
  tag TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'pending_gr', matched_buyer_id INTEGER,
  file TEXT, dedupe_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS research_deals (
  id INTEGER PRIMARY KEY, address TEXT, county TEXT, zip TEXT, asset_type TEXT, distress_type TEXT,
  distress_date TEXT, evidence_url TEXT NOT NULL, asking_price REAL, date_found TEXT, tool TEXT,
  tag TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'pending_gr', file TEXT, dedupe_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS briefs (
  id INTEGER PRIMARY KEY, brief_date TEXT NOT NULL UNIQUE, body_md TEXT, body_html TEXT,
  ruleset_version TEXT, created_at TEXT, delivered INTEGER DEFAULT 0
);
`;

export function openDb(file: string = PATHS.db): DB {
  if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;');
  db.exec(SCHEMA);
  return db;
}

export interface RunStats {
  recordsIn: number;
  recordsOut: number;
  errors: string[];
}

/** Every job logs to `runs` with the ruleset version (playbook §1). */
export function withRun<T extends RunStats>(db: DB, agent: string, fn: () => T): T {
  const started = new Date().toISOString();
  const id = Number(
    db.prepare('INSERT INTO runs (agent, started, ruleset_version) VALUES (?,?,?)').run(agent, started, RULESET_VERSION)
      .lastInsertRowid,
  );
  try {
    const r = fn();
    db.prepare('UPDATE runs SET finished=?, records_in=?, records_out=?, errors=? WHERE id=?').run(
      new Date().toISOString(), r.recordsIn, r.recordsOut, r.errors.length ? JSON.stringify(r.errors) : null, id,
    );
    return r;
  } catch (e) {
    db.prepare('UPDATE runs SET finished=?, errors=? WHERE id=?').run(
      new Date().toISOString(), JSON.stringify([String((e as Error).message ?? e)]), id,
    );
    throw e;
  }
}
