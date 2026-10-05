import path from 'node:path';
import { PATHS } from '../config';
import { parseDate, today } from '../lib/dates';
import { withRun, type DB, type RunStats } from '../lib/db';
import { normalizeName } from '../lib/names';
import { loadSources, type SourcesFile } from '../lib/sources';
import { tag } from '../lib/tags';
import { archive, clean, csvFiles, num, readCsv } from './util';

/**
 * ASSISTED MODE: a human (or an allowed browser session) pulls an export from a records source and
 * drops the CSV in /inbox/records/. File name prefix picks the table:
 *   deeds_*  dot_*  properties_*  lots_*  permits_*  distress_*  enrichment_*
 * Every row names a `source` that must exist in sources.yaml; its evidence_tier ([GR] for
 * government records) is stamped with the import date. Rows outside active_counties are rejected.
 * No network access happens here, so the approval gate is not bypassed.
 */
export interface RecordsResult extends RunStats {
  byTable: Record<string, number>;
  rejected: number;
  files: string[];
}

type Handler = (r: Record<string, string>, ctx: Ctx) => boolean;
interface Ctx { db: DB; src: SourcesFile; asOf: string; tierTag: (source: string | null) => string | null }

const ISO = (s: string | undefined) => (parseDate(s) ? s!.slice(0, 10) : null);

const handlers: Record<string, Handler> = {
  deeds: (r, { db, tierTag }) => {
    const tg = tierTag(r.source); const date = ISO(r.record_date);
    if (!tg || !date || !r.instrument_no || !r.county) return false;
    return !!db.prepare(`INSERT OR IGNORE INTO deeds (county, instrument_no, type, record_date, grantor, grantee, consideration, legal, apn, source, tag)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)`).run(r.county, r.instrument_no, clean(r.type, 60), date, clean(r.grantor), clean(r.grantee),
      num(r.consideration), clean(r.legal), clean(r.apn, 40), r.source, tg).changes || true;
  },
  dot: (r, { db, tierTag }) => {
    const tg = tierTag(r.source); const date = ISO(r.record_date);
    if (!tg || !date || !r.instrument_no || !r.county) return false;
    db.prepare(`INSERT OR IGNORE INTO deeds_of_trust (county, instrument_no, record_date, grantor, lender, amount, apn, source, tag)
      VALUES (?,?,?,?,?,?,?,?,?)`).run(r.county, r.instrument_no, date, clean(r.grantor), clean(r.lender), num(r.amount), clean(r.apn, 40), r.source, tg);
    return true;
  },
  properties: (r, { db, tierTag }) => {
    const tg = tierTag(r.source);
    if (!tg || !r.apn || !r.county) return false;
    db.prepare(`INSERT OR REPLACE INTO properties (apn, county, address, zip, land_use, beds, baths, sqft, year_built, cad_value, owner,
      owner_mailing, land_use_prior, improvement_value, improvement_value_prior, last_sale_date, source, tag)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(clean(r.apn, 40), r.county, clean(r.address), clean(r.zip, 10), clean(r.land_use, 20),
      num(r.beds), num(r.baths), num(r.sqft), num(r.year_built), num(r.cad_value), clean(r.owner), clean(r.owner_mailing),
      clean(r.land_use_prior, 20), num(r.improvement_value), num(r.improvement_value_prior), ISO(r.last_sale_date), r.source, tg);
    return true;
  },
  lots: (r, { db, tierTag }) => {
    const tg = tierTag(r.source);
    if (!tg || !r.apn) return false;
    db.prepare(`INSERT OR REPLACE INTO lot_details (apn, county, lot_sqft, frontage_ft, zoning, flood_zone, water_sewer, tag, floodway)
      VALUES (?,?,?,?,?,?,?,?,?)`).run(clean(r.apn, 40), r.county || 'Dallas', num(r.lot_sqft), num(r.frontage_ft), clean(r.zoning, 30),
      clean(r.flood_zone, 20), clean(r.water_sewer, 60), tg, /^(1|y|yes|true)$/i.test(r.floodway ?? '') ? 1 : 0);
    return true;
  },
  permits: (r, { db, tierTag }) => {
    if (!tierTag(r.source) || !r.permit_no) return false;
    db.prepare(`INSERT OR IGNORE INTO permits (permit_no, city, apn, type, issue_date, applicant, valuation) VALUES (?,?,?,?,?,?,?)`)
      .run(clean(r.permit_no, 40), clean(r.city, 60) ?? 'Dallas', clean(r.apn, 40), clean(r.type, 100), ISO(r.issue_date), clean(r.applicant), num(r.valuation));
    return true;
  },
  distress: (r, { db, tierTag, src }) => {
    const tg = tierTag(r.source); const asset = (r.asset_type ?? '').toLowerCase();
    if (!tg || !['sfr', 'infill_lot'].includes(asset) || !r.distress_type || !(r.apn || r.address)) return false;
    const county = r.county || 'Dallas';
    if (!src.active_counties.includes(county)) return false;
    const key = `rec|${county}|${r.apn || r.address}|${asset}|${r.distress_type}|${r.distress_date ?? ''}`.toUpperCase();
    db.prepare(`INSERT OR IGNORE INTO leads (apn, asset_type, distress_type, distress_date, source, tag, status, county, address, zip, evidence_url, dedupe_key)
      VALUES (?,?,?,?,?,?, 'new', ?,?,?,?,?)`).run(clean(r.apn, 40), asset, clean(r.distress_type, 60), ISO(r.distress_date), r.source, tg,
      county, clean(r.address), clean(r.zip, 10), clean(r.evidence_url, 1000), key);
    return true;
  },
  enrichment: (r, { db }) => {
    const n = normalizeName(r.name ?? '');
    if (!n) return false;
    db.prepare(`INSERT INTO buyers (normalized_name, display_name, registered_agent, mailing, phone, email, contact_tag)
      VALUES (?,?,?,?,?,?,?)
      ON CONFLICT(normalized_name) DO UPDATE SET registered_agent=COALESCE(excluded.registered_agent, registered_agent),
        mailing=COALESCE(excluded.mailing, mailing), phone=COALESCE(excluded.phone, phone),
        email=COALESCE(excluded.email, email), contact_tag=excluded.contact_tag`)
      .run(n, clean(r.name), clean(r.registered_agent), clean(r.mailing), clean(r.phone, 40), clean(r.email, 120), tag('SR', today()));
    return true;
  },
};

export function ingestRecords(db: DB, opts: { dir?: string; asOf?: string; archiveFiles?: boolean; src?: SourcesFile } = {}): RecordsResult {
  const dir = opts.dir ?? PATHS.recordsInbox;
  const asOf = opts.asOf ?? today();
  const src = opts.src ?? loadSources();
  const tierTag = (s: string | null) => {
    const found = src.sources.find((x) => x.name === (s ?? ''));
    return found ? tag(found.evidence_tier, asOf) : null; // unknown source => row rejected
  };
  return withRun(db, 'ingest-records', () => {
    const res: RecordsResult = { recordsIn: 0, recordsOut: 0, errors: [], byTable: {}, rejected: 0, files: [] };
    for (const file of csvFiles(dir)) {
      const base = path.basename(file).toLowerCase();
      const prefix = Object.keys(handlers).find((p) => base.startsWith(`${p}_`));
      if (!prefix) { res.errors.push(`${base}: unknown file prefix, skipped`); continue; }
      res.files.push(base);
      let rows: Array<Record<string, string>>;
      try { rows = readCsv(file); } catch (e) { res.errors.push(`${base}: ${(e as Error).message}`); continue; }
      db.exec('BEGIN');
      for (const r of rows) {
        res.recordsIn++;
        if (r.county && !src.active_counties.includes(r.county)) { res.rejected++; continue; } // Phase 1: Dallas only
        if (handlers[prefix](r, { db, src, asOf, tierTag })) { res.recordsOut++; res.byTable[prefix] = (res.byTable[prefix] ?? 0) + 1; }
        else res.rejected++;
      }
      db.exec('COMMIT');
      if (opts.archiveFiles !== false) archive(file);
    }
    return res;
  });
}
