import { ACTIVE_DAYS_LOT, ACTIVE_DAYS_SFR } from './config';
import { addMonths, parseDate, toISO, today } from './lib/dates';
import { classifyLandUse } from './lib/cashbuy';
import { withRun, type DB, type RunStats } from './lib/db';
import { loadSources, type SourcesFile } from './lib/sources';

export interface ScoutResult extends RunStats {
  fromResearch: number;
  derivedSfr: number;
  derivedLots: number;
  kept: { sfr: number; infill_lot: number };
  filtered: number;
}

const LONG_OWNERSHIP_YEARS = 10;

/**
 * Distress Scout (daily): collect new distress items, then keep ONLY properties in a ZIP where an
 * ACTIVE buyer buys (SFR: repeat cash buyer, last 90 days; lots: confirmed builder, last 180 days).
 * Official distress records (foreclosure, probate, tax, code, liens) arrive via assisted-mode
 * distress_*.csv imports; no source is queried automatically unless sources.yaml approves it.
 */
export function runDistressScout(db: DB, opts: { asOf?: string; src?: SourcesFile } = {}): ScoutResult {
  const asOf = opts.asOf ?? today();
  const src = opts.src ?? loadSources();
  return withRun(db, 'distress-scout', () => {
    const res: ScoutResult = {
      recordsIn: 0, recordsOut: 0, errors: [], fromResearch: 0, derivedSfr: 0, derivedLots: 0,
      kept: { sfr: 0, infill_lot: 0 }, filtered: 0,
    };
    const counties = src.active_counties;
    const asOfD = parseDate(asOf)!;
    const insLead = db.prepare(`INSERT OR IGNORE INTO leads (apn, asset_type, distress_type, distress_date, source, tag, status, county, address, zip, asking_price, evidence_url, dedupe_key)
      VALUES (?,?,?,?,?,?, 'new', ?,?,?,?,?,?)`);

    db.exec('BEGIN');
    // 1. research deals ([SR] queue) -> leads, still tagged [SR] (weakest link carries through to matches)
    for (const d of db.prepare('SELECT * FROM research_deals').all() as Array<Record<string, string | number | null>>) {
      res.recordsIn++;
      if (!counties.includes(String(d.county ?? ''))) continue;
      const key = `res|${d.id}`;
      if (insLead.run(null, d.asset_type as string, d.distress_type as string, d.distress_date as string | null, 'research_inbox', d.tag as string,
        d.county as string, d.address as string, d.zip as string | null, d.asking_price as number | null, d.evidence_url as string, key).changes) res.fromResearch++;
    }

    // 2. derived from CAD data: absentee + long ownership (SFR secondary), out-of-area long-held lots, demolished lots
    const cutoff = toISO(addMonths(asOfD, -12 * LONG_OWNERSHIP_YEARS));
    const ph = counties.map(() => '?').join(',');
    for (const p of db.prepare(`SELECT * FROM properties WHERE county IN (${ph})`).all(...counties) as Array<Record<string, string | number | null>>) {
      res.recordsIn++;
      const asset = classifyLandUse(p.land_use as string);
      if (!asset) continue;
      const norm = (s: unknown) => String(s ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
      const longHeld = !!p.last_sale_date && String(p.last_sale_date) <= cutoff;
      const mailing = String(p.owner_mailing ?? '');
      const absentee = !!mailing && norm(mailing) !== norm(p.address) && !norm(mailing).includes(norm(p.address));
      const base = [p.apn as string, asset];
      const add = (type: string) => {
        const k = `cad|${p.county}|${p.apn}|${type}`;
        const info = insLead.run(p.apn as string, base[1], type, asOf, p.source as string, p.tag as string, p.county as string,
          p.address as string, p.zip as string, null, null, k);
        if (info.changes) { if (asset === 'sfr') res.derivedSfr++; else res.derivedLots++; }
      };
      if (asset === 'sfr' && absentee && longHeld) add('absentee_long_owner');
      if (asset === 'infill_lot') {
        if (absentee && longHeld && !/\bTX\b|TEXAS/i.test(mailing)) add('out_of_state_long_owner');
        if ((Number(p.improvement_value) || 0) === 0 && (Number(p.improvement_value_prior) || 0) > 0) add('demolished');
      }
    }

    // 3. keep only leads in a ZIP where an active buyer buys
    const activeZips = (asset: 'sfr' | 'infill_lot', days: number): Set<string> => {
      const from = toISO(new Date(asOfD.getTime() - days * 86_400_000));
      const flag = asset === 'sfr' ? 'b.verified_repeat_buyer' : 'b.verified_repeat_lot_buyer AND b.confirmed_builder';
      const rows = db.prepare(`SELECT DISTINCT p.zip FROM buyer_purchases bp JOIN buyers b ON b.id = bp.buyer_id
        JOIN deeds d ON d.id = bp.deed_id JOIN properties p ON p.apn = bp.apn AND p.county = d.county
        WHERE bp.cash_buy = 1 AND bp.asset_type = ? AND ${flag} AND bp.date >= ? AND bp.date <= ? AND p.zip IS NOT NULL`)
        .all(asset, from, asOf) as Array<{ zip: string }>;
      return new Set(rows.map((r) => r.zip));
    };
    const zips = { sfr: activeZips('sfr', ACTIVE_DAYS_SFR), infill_lot: activeZips('infill_lot', ACTIVE_DAYS_LOT) };
    const upd = db.prepare('UPDATE leads SET status = ? WHERE id = ?');
    const leads = db.prepare(`SELECT l.id, l.asset_type, COALESCE(l.zip, p.zip) AS zip FROM leads l
      LEFT JOIN properties p ON p.apn = l.apn AND p.county = l.county
      WHERE l.status IN ('new','kept','filtered_no_zip','filtered_no_buyer')`).all() as Array<{ id: number; asset_type: 'sfr' | 'infill_lot'; zip: string | null }>;
    for (const l of leads) {
      if (!l.zip) { upd.run('filtered_no_zip', l.id); res.filtered++; continue; }
      if (zips[l.asset_type].has(l.zip.slice(0, 5))) { upd.run('kept', l.id); res.kept[l.asset_type]++; res.recordsOut++; }
      else { upd.run('filtered_no_buyer', l.id); res.filtered++; }
    }
    db.exec('COMMIT');
    return res;
  });
}
