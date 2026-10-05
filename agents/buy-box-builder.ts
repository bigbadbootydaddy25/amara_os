import { MIN_REAL_CONSIDERATION, REHAB_RATIO, WINDOW_MONTHS } from './config';
import { confirmBuilder } from './buyer-finder';
import { addMonths, daysBetween, parseDate, toISO, today } from './lib/dates';
import { inWindow, type AssetType } from './lib/cashbuy';
import { withRun, type DB, type RunStats } from './lib/db';
import { normalizeName } from './lib/names';

export interface BoxResult extends RunStats { sfrBoxes: number; lotBoxes: number }

const median = (xs: number[]): number | null => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const min = (xs: number[]) => (xs.length ? Math.min(...xs) : null);
const max = (xs: number[]) => (xs.length ? Math.max(...xs) : null);
const tally = (xs: Array<string | null>) => {
  const o: Record<string, number> = {};
  for (const x of xs) if (x) o[x] = (o[x] ?? 0) + 1;
  return o;
};

export function confidence(n: number): 'high' | 'medium' | 'low' {
  return n >= 5 ? 'high' : n >= 3 ? 'medium' : 'low';
}

interface Purchase {
  grp: string; apn: string | null; date: string; price: number | null; asset: AssetType; deedId: number;
  zip: string | null; beds: number | null; baths: number | null; sqft: number | null; year: number | null;
  cad_value: number | null; improvement_value: number | null; owner: string | null; owner_mailing: string | null; address: string | null;
  lot_sqft: number | null; frontage_ft: number | null; zoning: string | null;
}

/** Buy-Box Builder (spec §5.2 + §5.6 lot buy box) — runs after Buyer Finder. One box per buyer_group per asset type. */
export function runBuyBoxBuilder(db: DB, opts: { asOf?: string } = {}): BoxResult {
  const asOf = opts.asOf ?? today();
  return withRun(db, 'buy-box-builder', () => {
    const res: BoxResult = { recordsIn: 0, recordsOut: 0, errors: [], sfrBoxes: 0, lotBoxes: 0 };
    const rows = db.prepare(`
      SELECT b.buyer_group_id AS grp, bp.apn, bp.date, bp.price, bp.asset_type AS asset, bp.deed_id AS deedId,
             p.zip, p.beds, p.baths, p.sqft, p.year_built AS year, p.cad_value, p.improvement_value, p.owner, p.owner_mailing, p.address,
             l.lot_sqft, l.frontage_ft, l.zoning, b.verified_repeat_buyer AS rb, b.verified_repeat_lot_buyer AS rl
      FROM buyer_purchases bp JOIN buyers b ON b.id = bp.buyer_id
      LEFT JOIN deeds d ON d.id = bp.deed_id
      LEFT JOIN properties p ON p.apn = bp.apn AND p.county = d.county
      LEFT JOIN lot_details l ON l.apn = bp.apn AND l.county = d.county
      WHERE bp.cash_buy = 1 AND ((bp.asset_type='sfr' AND b.verified_repeat_buyer=1) OR (bp.asset_type='infill_lot' AND b.verified_repeat_lot_buyer=1))
    `).all() as unknown as Array<Purchase & { rb: number; rl: number }>;
    res.recordsIn = rows.length;

    // Area $/sqft by zip, from every counted SFR deed with a disclosed price (not only investors).
    const area = new Map<string, number[]>();
    const all: number[] = [];
    for (const r of db.prepare(`SELECT p.zip, d.consideration c, p.sqft s FROM deeds d JOIN properties p ON p.apn=d.apn AND p.county=d.county
        WHERE d.consideration >= ? AND p.sqft > 0 AND d.record_date > ? AND d.record_date <= ?`)
      .all(MIN_REAL_CONSIDERATION, toISO(addMonths(parseDate(asOf)!, -WINDOW_MONTHS)), asOf) as Array<{ zip: string | null; c: number; s: number }>) {
      const v = r.c / r.s;
      all.push(v);
      if (r.zip) (area.get(r.zip) ?? area.set(r.zip, []).get(r.zip)!).push(v);
    }
    const areaMedian = (zips: string[]): number | null => {
      const z = zips.flatMap((k) => area.get(k) ?? []);
      return median(z.length >= 3 ? z : all.length >= 3 ? all : []);
    };

    const byKey = new Map<string, Purchase[]>();
    for (const r of rows) {
      const k = `${r.grp}|${r.asset}`;
      (byKey.get(k) ?? byKey.set(k, []).get(k)!).push(r);
    }
    db.exec('BEGIN');
    db.exec('DELETE FROM buy_boxes');
    const ins = db.prepare(`INSERT INTO buy_boxes (buyer_group_id, asset_type, zips, price_min, price_max, beds_min, beds_max, sqft_min, sqft_max,
      year_min, year_max, strategy, confidence, last_buy_date, buys_12m, buys_90d, price_median, condition_proxy, details)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`);

    for (const [key, all12] of byKey) {
      const [grp, asset] = key.split('|') as [string, AssetType];
      // distinct cash buys inside the 12-month window
      const seen = new Set<string>();
      const ps = all12.filter((p) => inWindow(p.date, asOf)).filter((p) => {
        const k = p.apn ? `${p.apn}|${p.date}` : `deed${p.deedId}`;
        if (seen.has(k)) return false; seen.add(k); return true;
      });
      if (ps.length < 2) continue;
      const prices = ps.map((p) => p.price).filter((x): x is number => x != null && x >= MIN_REAL_CONSIDERATION);
      const zips = tally(ps.map((p) => p.zip));
      const dates = ps.map((p) => p.date).sort();
      const last = dates[dates.length - 1];
      const buys90 = ps.filter((p) => daysBetween(parseDate(p.date)!, parseDate(asOf)!) <= 90).length;
      const nums = (f: (p: Purchase) => number | null) => ps.map(f).filter((x): x is number => x != null);

      if (asset === 'sfr') {
        // Condition proxy: bought below area median $/sqft => likely rehab buyer.
        const ppsf = ps.filter((p) => p.price != null && p.price >= MIN_REAL_CONSIDERATION && (p.sqft ?? 0) > 0).map((p) => p.price! / p.sqft!);
        const am = areaMedian(Object.keys(zips));
        const bm = median(ppsf);
        const proxy = bm == null || am == null ? 'unknown' : bm < am * REHAB_RATIO ? 'rehab' : 'market';
        // Strategy: flip (resold within 12 months) vs hold (still owned, mailing differs from the property).
        const members = new Set((db.prepare('SELECT normalized_name n FROM buyers WHERE buyer_group_id = ?').all(grp) as Array<{ n: string }>).map((m) => m.n));
        const norm = (n: string | null) => (n ? normalizeName(n) : '');
        let flips = 0, holds = 0;
        for (const p of ps) {
          if (!p.apn) continue;
          const resold = db.prepare('SELECT grantor FROM deeds WHERE apn = ? AND record_date > ? AND record_date <= ?')
            .all(p.apn, p.date, toISO(addMonths(parseDate(p.date)!, 12))) as Array<{ grantor: string | null }>;
          if (resold.some((s) => members.has(norm(s.grantor)))) flips++;
          else if (members.has(norm(p.owner)) && p.owner_mailing && p.address &&
                   normalizeName(p.owner_mailing) !== normalizeName(p.address)) holds++;
        }
        const strategy = flips > 0 && flips >= holds ? 'flip' : holds > flips ? 'hold' : 'unknown';
        ins.run(grp, asset, JSON.stringify(zips), min(prices), max(prices), min(nums((p) => p.beds)), max(nums((p) => p.beds)),
          min(nums((p) => p.sqft)), max(nums((p) => p.sqft)), min(nums((p) => p.year)), max(nums((p) => p.year)),
          strategy, confidence(ps.length), last, ps.length, buys90, median(prices), proxy,
          JSON.stringify({ baths_min: min(nums((p) => p.baths)), baths_max: max(nums((p) => p.baths)),
            ppsf_median: median(ppsf), area_ppsf_median: am, flips, holds, comp_deed_ids: ps.map((p) => p.deedId) }));
        res.sfrBoxes++;
      } else {
        const ev = confirmBuilder(db, ps);
        const months = ev.evidence.map((e) => e.monthsToPermit).filter((x): x is number => x != null);
        const built = ps.filter((p) => (p.improvement_value ?? 0) > 0 && p.cad_value != null).map((p) => p.cad_value!);
        ins.run(grp, asset, JSON.stringify(zips), min(prices), max(prices), null, null, null, null, null, null,
          'build', confidence(ps.length), last, ps.length, buys90, median(prices), 'n/a',
          JSON.stringify({
            lot_sqft_min: min(nums((p) => p.lot_sqft)), lot_sqft_max: max(nums((p) => p.lot_sqft)),
            frontage_min: min(nums((p) => p.frontage_ft)), frontage_max: max(nums((p) => p.frontage_ft)),
            zoning: Object.keys(tally(ps.map((p) => p.zoning))), built_value_min: min(built), built_value_max: max(built),
            built_value_median: median(built), months_to_permit_median: median(months),
            confirmed_builder: ev.confirmed, builder_evidence: ev.evidence, comp_deed_ids: ps.map((p) => p.deedId),
          }));
        res.lotBoxes++;
      }
      res.recordsOut++;
    }
    db.exec('COMMIT');
    return res;
  });
}
