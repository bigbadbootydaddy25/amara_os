import path from 'node:path';
import { PATHS } from '../config';
import { parseDate, today } from '../lib/dates';
import { withRun, type DB, type RunStats } from '../lib/db';
import { normalizeName } from '../lib/names';
import { tag } from '../lib/tags';
import { archive, clean, csvFiles, isHttpUrl, num, readCsv } from './util';

export interface ResearchResult extends RunStats {
  buyers: number;
  deals: number;
  discarded: number;
  duplicates: number;
  files: string[];
}

const ASSET = new Set(['sfr', 'infill_lot']);

/**
 * Spec §7: research tools never write to the DB directly. This ingest tags EVERY row [SR]
 * (whatever the file says) and queues it for [GR] verification. Rows with no linkable
 * evidence_url are discarded.
 */
export function ingestResearch(
  db: DB, opts: { dir?: string; asOf?: string; archiveFiles?: boolean } = {},
): ResearchResult {
  const dir = opts.dir ?? PATHS.researchInbox;
  const asOf = opts.asOf ?? today();
  return withRun(db, 'ingest-research', () => {
    const res: ResearchResult = { recordsIn: 0, recordsOut: 0, errors: [], buyers: 0, deals: 0, discarded: 0, duplicates: 0, files: [] };
    const insBuyer = db.prepare(`INSERT OR IGNORE INTO research_buyers
      (normalized_name, name, entity_type, asset_type, county, zip_list, evidence_url, evidence_summary, date_found, tool, tag, file, dedupe_key)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`);
    const insDeal = db.prepare(`INSERT OR IGNORE INTO research_deals
      (address, county, zip, asset_type, distress_type, distress_date, evidence_url, asking_price, date_found, tool, tag, file, dedupe_key)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`);

    for (const file of csvFiles(dir)) {
      const base = path.basename(file);
      let rows: Array<Record<string, string>>;
      try {
        rows = readCsv(file);
      } catch (e) {
        res.errors.push(`${base}: unreadable CSV (${(e as Error).message})`);
        continue;
      }
      res.files.push(base);
      const fileAsset = /infill|lot/i.test(base) ? 'infill_lot' : 'sfr'; // default when the column is absent
      for (const r of rows) {
        res.recordsIn++;
        const url = clean(r.evidence_url, 1000);
        if (!isHttpUrl(url)) { res.discarded++; continue; } // "A source with no link is discarded."
        const found = parseDate(r.date_found);
        const rowTag = tag('SR', found ? r.date_found.slice(0, 10) : asOf); // ALWAYS SR
        const asset = ASSET.has((r.asset_type ?? '').toLowerCase()) ? r.asset_type.toLowerCase() : fileAsset;
        const isDeal = 'address' in r && !('name' in r);
        if (isDeal) {
          const addr = clean(r.address);
          if (!addr) { res.discarded++; continue; }
          const key = `deal|${addr.toUpperCase()}|${url}`;
          const info = insDeal.run(addr, clean(r.county, 60), clean(r.zip, 10), asset, clean(r.distress_type, 60),
            parseDate(r.distress_date) ? r.distress_date.slice(0, 10) : null, url, num(r.asking_price_if_any),
            found ? r.date_found.slice(0, 10) : asOf, clean(r.tool, 40), rowTag, base, key);
          if (info.changes) { res.deals++; res.recordsOut++; } else res.duplicates++;
        } else {
          const name = clean(r.name);
          const norm = name ? normalizeName(name) : '';
          if (!norm) { res.discarded++; continue; }
          const key = `buyer|${norm}|${asset}|${url}`;
          const info = insBuyer.run(norm, name, clean(r.entity_type, 40), asset, clean(r.county, 60), clean(r.zip_list, 200),
            url, clean(r.evidence_summary, 1000), found ? r.date_found.slice(0, 10) : asOf, clean(r.tool, 40), rowTag, base, key);
          if (info.changes) { res.buyers++; res.recordsOut++; } else res.duplicates++;
        }
      }
      if (opts.archiveFiles !== false) archive(file);
    }
    return res;
  });
}
