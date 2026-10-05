import { MIN_MATCH_SCORE, TOP_N_BUYERS, ACTIVE_DAYS_LOT } from './config';
import { daysBetween, parseDate, today } from './lib/dates';
import { withRun, type DB, type RunStats } from './lib/db';
import { lotGate } from './lib/lot-gate';
import { tag, weakest } from './lib/tags';
import { loadSources, type SourcesFile } from './lib/sources';

export interface MatchResult extends RunStats { leads: number; matches: number }

interface Lead { id: number; apn: string | null; asset_type: 'sfr' | 'infill_lot'; distress_type: string; tag: string; county: string; zip: string | null; asking_price: number | null }
interface Prop { beds: number | null; sqft: number | null; year_built: number | null; cad_value: number | null; zip: string | null }
interface Box {
  buyer_group_id: string; asset_type: string; zips: string; price_min: number | null; price_max: number | null; beds_min: number | null; beds_max: number | null;
  sqft_min: number | null; sqft_max: number | null; year_min: number | null; year_max: number | null; condition_proxy: string; last_buy_date: string; details: string;
}

/** 1 inside [lo, hi]; falls linearly to 0 at `tol` (fraction of the range edge) outside; null when the box has no data. */
export function rangeFit(v: number | null, lo: number | null, hi: number | null, tol = 0.25): number | null {
  if (lo == null || hi == null) return null;
  if (v == null) return 0.5; // unknown lead attribute: neutral, never a full match
  if (v >= lo && v <= hi) return 1;
  const edge = v < lo ? lo : hi;
  const off = Math.abs(v - edge) / Math.max(Math.abs(edge), 1);
  return Math.max(0, 1 - off / tol);
}

const pts = (frac: number | null, max: number) => Math.round((frac == null ? 0.5 : frac) * max * 10) / 10;

export function recencyPoints(lastBuy: string, asOf: string, asset: 'sfr' | 'infill_lot'): number {
  const days = daysBetween(parseDate(lastBuy)!, parseDate(asOf)!);
  if (asset === 'sfr') return days <= 30 ? 15 : days <= 60 ? 10 : days <= 90 ? 5 : 0;
  return days <= 60 ? 15 : days <= 120 ? 10 : days <= ACTIVE_DAYS_LOT ? 5 : 0;
}

/**
 * Matcher (daily, after Scout). SFR: ZIP 30 · price 25 · beds/sqft/year 20 · recency 15 · strategy 10.
 * Lot:  ZIP 30 · lot size/frontage 20 · price 20 · builder recency 15 · zoning 15.
 * Top 5 buyers per lead with score >= 60. Unknown inputs earn neutral (half) credit and are
 * listed in `reasons`, so thin data cannot silently look like a strong match.
 * Confidence follows the weakest-link rule (spec §4).
 */
export function runMatcher(db: DB, opts: { asOf?: string; src?: SourcesFile } = {}): MatchResult {
  const asOf = opts.asOf ?? today();
  const src = opts.src ?? loadSources();
  return withRun(db, 'matcher', () => {
    const res: MatchResult = { recordsIn: 0, recordsOut: 0, errors: [], leads: 0, matches: 0 };
    const leads = db.prepare(`SELECT id, apn, asset_type, distress_type, tag, county, COALESCE(zip, (SELECT zip FROM properties p WHERE p.apn=leads.apn AND p.county=leads.county)) AS zip, asking_price
      FROM leads WHERE status = 'kept'`).all() as unknown as Lead[];
    res.recordsIn = leads.length;
    const boxes = db.prepare(`SELECT bb.*, 1 AS ok FROM buy_boxes bb JOIN buyers b ON b.buyer_group_id = bb.buyer_group_id
      WHERE (bb.asset_type='sfr') OR (bb.asset_type='infill_lot' AND b.confirmed_builder=1) GROUP BY bb.buyer_group_id, bb.asset_type`).all() as unknown as Box[];
    const insert = db.prepare('INSERT INTO matches (lead_id, buyer_group_id, score, reasons, created_at, asset_type, confidence_tag, rank) VALUES (?,?,?,?,?,?,?,?)');
    const lotSizes = db.prepare('SELECT lot_sqft, frontage_ft, zoning FROM lot_details WHERE apn = ? AND county = ?');
    const propQ = db.prepare('SELECT beds, sqft, year_built, cad_value, zip FROM properties WHERE apn = ? AND county = ?');

    db.exec('BEGIN');
    for (const lead of leads) {
      if (!src.active_counties.includes(lead.county)) continue;
      db.prepare('DELETE FROM matches WHERE lead_id = ?').run(lead.id);
      const prop = (lead.apn ? propQ.get(lead.apn, lead.county) : undefined) as Prop | undefined;
      const lot = (lead.apn ? lotSizes.get(lead.apn, lead.county) : undefined) as { lot_sqft: number | null; frontage_ft: number | null; zoning: string | null } | undefined;
      if (lead.asset_type === 'infill_lot' && lead.apn && lotGate(db, lead.apn, lead.county).blocked) continue; // failed Lot Gate
      const price = lead.asking_price ?? prop?.cad_value ?? null; // CAD value is a proxy; noted in reasons
      const priceNote = lead.asking_price != null ? 'asking price' : prop?.cad_value != null ? 'CAD value (proxy)' : 'none';

      const scored: Array<{ grp: string; score: number; reasons: string[]; tags: string[] }> = [];
      for (const b of boxes.filter((x) => x.asset_type === lead.asset_type)) {
        const reasons: string[] = [];
        const zips = JSON.parse(b.zips) as Record<string, number>;
        const zipHit = !!lead.zip && lead.zip.slice(0, 5) in zips;
        const zipPts = zipHit ? 30 : 0;
        reasons.push(`ZIP ${zipHit ? `match (${zips[lead.zip!.slice(0, 5)]} buys)` : 'no match'} ${zipPts}/30`);
        let total = zipPts;
        const price25 = pts(rangeFit(price, b.price_min, b.price_max), lead.asset_type === 'sfr' ? 25 : 20);
        reasons.push(`price fit (${priceNote}) ${price25}/${lead.asset_type === 'sfr' ? 25 : 20}`);
        total += price25;
        const rec = recencyPoints(b.last_buy_date, asOf, lead.asset_type);
        reasons.push(`recency (last buy ${b.last_buy_date}) ${rec}/15`);
        total += rec;
        if (lead.asset_type === 'sfr') {
          const beds = pts(rangeFit(prop?.beds ?? null, b.beds_min, b.beds_max, 0.34), 6);
          const sqft = pts(rangeFit(prop?.sqft ?? null, b.sqft_min, b.sqft_max), 7);
          const year = pts(rangeFit(prop?.year_built ?? null, b.year_min, b.year_max, 0.02), 7);
          reasons.push(`beds ${beds}/6 · sqft ${sqft}/7 · year ${year}/7`);
          total += beds + sqft + year;
          const strat = b.condition_proxy === 'rehab' ? 10 : b.condition_proxy === 'unknown' ? 5 : 2;
          reasons.push(`strategy (${b.condition_proxy} buyer vs ${lead.distress_type}) ${strat}/10`);
          total += strat;
        } else {
          const d = JSON.parse(b.details) as { lot_sqft_min: number | null; lot_sqft_max: number | null; frontage_min: number | null; frontage_max: number | null; zoning: string[] };
          const size = rangeFit(lot?.lot_sqft ?? null, d.lot_sqft_min, d.lot_sqft_max);
          const front = rangeFit(lot?.frontage_ft ?? null, d.frontage_min, d.frontage_max);
          const sf = pts(size == null && front == null ? null : ((size ?? 0.5) + (front ?? 0.5)) / 2, 20);
          reasons.push(`lot size/frontage ${sf}/20`);
          total += sf;
          const zn = !d.zoning.length ? 7.5 : lot?.zoning ? (d.zoning.includes(lot.zoning) ? 15 : 0) : 7.5;
          reasons.push(`zoning (${lot?.zoning ?? 'unknown'} vs ${d.zoning.join('/') || 'n/a'}) ${zn}/15`);
          total += zn;
        }
        const score = Math.round(total);
        if (score >= MIN_MATCH_SCORE) scored.push({ grp: b.buyer_group_id, score, reasons, tags: [] });
      }
      scored.sort((a, c) => c.score - a.score || a.grp.localeCompare(c.grp));
      scored.slice(0, TOP_N_BUYERS).forEach((m, i) => {
        // weakest link: the lead's own tag and the buyer evidence (deed-derived purchases are [GR])
        const buyerTags = db.prepare(`SELECT d.tag FROM buyer_purchases bp JOIN buyers b ON b.id=bp.buyer_id JOIN deeds d ON d.id=bp.deed_id
          WHERE b.buyer_group_id = ? AND bp.cash_buy = 1`).all(m.grp) as Array<{ tag: string | null }>;
        const tier = weakest([lead.tag, ...buyerTags.map((t) => t.tag)]);
        insert.run(lead.id, m.grp, m.score, JSON.stringify(m.reasons), new Date().toISOString(), lead.asset_type, tag(tier, asOf), i + 1);
        res.matches++; res.recordsOut++;
      });
      res.leads++;
    }
    db.exec('COMMIT');
    return res;
  });
}
