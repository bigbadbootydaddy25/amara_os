import { WINDOW_MONTHS } from './config';
import { addMonths, parseDate, toISO, today } from './lib/dates';
import {
  classifyLandUse, countCashBuys, evaluateCashBuy, type AssetType, type DotRow, type PurchaseFact,
} from './lib/cashbuy';
import { withRun, type DB, type RunStats } from './lib/db';
import { classifyExcluded, groupBuyers, normalizeName } from './lib/names';
import { loadSources, type SourcesFile } from './lib/sources';

export interface FinderResult extends RunStats {
  grantees: number;
  cashBuys: number;
  hardMoneyBuys: number;
  repeatBuyers: number;
  repeatLotBuyers: number;
  confirmedBuilders: number;
  excluded: number;
  skipped: Record<string, number>;
}

interface DeedDb {
  id: number; county: string; instrument_no: string; type: string | null; record_date: string;
  grantor: string | null; grantee: string | null; consideration: number | null; apn: string | null;
}

const NEW_RES_PERMIT = /(new.*(residential|single|sfr|dwelling|home|house))|((residential|single|sfr|dwelling|home|house).*new)/i;

export interface BuilderEvidence {
  confirmed: boolean;
  evidence: Array<{ apn: string; kind: 'permit' | 'cad_improvement'; ref: string; monthsToPermit: number | null }>;
}

/**
 * Lot Buyer Finder step 3 (spec §5.6): a residential building permit for the lot within 12 months of
 * purchase, or new improvement value on the CAD roll for that lot -> confirmed_builder [GR].
 * CAD improvement is only accepted when the roll shows the lot was vacant before (land_use_prior
 * is a lot code) and improvement_value is now > 0.
 */
export function confirmBuilder(db: DB, lotPurchases: Array<{ apn: string | null; date: string }>): BuilderEvidence {
  const out: BuilderEvidence = { confirmed: false, evidence: [] };
  for (const p of lotPurchases) {
    if (!p.apn) continue;
    const bought = parseDate(p.date);
    if (!bought) continue;
    const limit = addMonths(bought, WINDOW_MONTHS);
    const permits = db.prepare('SELECT permit_no, type, issue_date FROM permits WHERE apn = ?').all(p.apn) as
      Array<{ permit_no: string; type: string | null; issue_date: string | null }>;
    let hit = false;
    for (const pm of permits) {
      const d = parseDate(pm.issue_date);
      if (!d || d < bought || d > limit || !NEW_RES_PERMIT.test(pm.type ?? '')) continue;
      const months = (d.getUTCFullYear() - bought.getUTCFullYear()) * 12 + (d.getUTCMonth() - bought.getUTCMonth());
      out.evidence.push({ apn: p.apn, kind: 'permit', ref: pm.permit_no, monthsToPermit: months });
      hit = true;
    }
    if (hit) continue;
    const prop = db.prepare('SELECT land_use_prior, improvement_value FROM properties WHERE apn = ?').get(p.apn) as
      { land_use_prior: string | null; improvement_value: number | null } | undefined;
    if (prop && (prop.improvement_value ?? 0) > 0 && classifyLandUse(prop.land_use_prior) === 'infill_lot') {
      out.evidence.push({ apn: p.apn, kind: 'cad_improvement', ref: `improvement_value=${prop.improvement_value}`, monthsToPermit: null });
    }
  }
  out.confirmed = out.evidence.length > 0;
  return out;
}

/** Buyer Finder (SFR) + Lot Buyer Finder, weekly. Idempotent: purchases/flags are recomputed from the deed index. */
export function runBuyerFinder(db: DB, opts: { asOf?: string; src?: SourcesFile } = {}): FinderResult {
  const asOf = opts.asOf ?? today();
  const src = opts.src ?? loadSources();
  return withRun(db, 'buyer-finder', () => {
    const res: FinderResult = {
      recordsIn: 0, recordsOut: 0, errors: [], grantees: 0, cashBuys: 0, hardMoneyBuys: 0, repeatBuyers: 0,
      repeatLotBuyers: 0, confirmedBuilders: 0, excluded: 0, skipped: {},
    };
    const start = toISO(addMonths(parseDate(asOf)!, -WINDOW_MONTHS));
    const counties = src.active_counties;
    const ph = counties.map(() => '?').join(',');
    const deeds = db.prepare(
      `SELECT id, county, instrument_no, type, record_date, grantor, grantee, consideration, apn FROM deeds
       WHERE county IN (${ph}) AND record_date > ? AND record_date <= ? ORDER BY record_date, id`,
    ).all(...counties, start, asOf) as unknown as DeedDb[];
    res.recordsIn = deeds.length;

    const props = new Map<string, { land_use: string | null; land_use_prior: string | null }>();
    for (const p of db.prepare('SELECT county, apn, land_use, land_use_prior FROM properties').all() as Array<{
      county: string; apn: string; land_use: string | null; land_use_prior: string | null }>) props.set(`${p.county}|${p.apn}`, p);
    const dotsByBorrower = new Map<string, DotRow[]>();
    for (const d of db.prepare('SELECT county, record_date, grantor, lender, apn FROM deeds_of_trust').all() as unknown as Array<DotRow & { county: string }>) {
      if (!d.grantor) continue;
      const k = `${d.county}|${normalizeName(d.grantor)}`;
      (dotsByBorrower.get(k) ?? dotsByBorrower.set(k, []).get(k)!).push(d);
    }

    // Buyer groups: existing enrichment (registered agent + mailing) merges entities into one group.
    const enrich = db.prepare('SELECT normalized_name, registered_agent, mailing FROM buyers').all() as Array<{
      normalized_name: string; registered_agent: string | null; mailing: string | null }>;
    const names = new Map<string, { normalized: string; registeredAgent?: string | null; mailing?: string | null }>();
    for (const e of enrich) names.set(e.normalized_name, { normalized: e.normalized_name, registeredAgent: e.registered_agent, mailing: e.mailing });
    for (const d of deeds) {
      const n = d.grantee ? normalizeName(d.grantee) : '';
      if (n && !names.has(n)) names.set(n, { normalized: n });
    }
    const groups = groupBuyers([...names.values()]);
    const groupOf = (n: string) => groups.get(n);

    db.exec('BEGIN');
    db.exec('DELETE FROM buyer_purchases; DELETE FROM excluded_buyers;');
    db.exec('UPDATE buyers SET verified_repeat_buyer=0, verified_repeat_lot_buyer=0, confirmed_builder=0, repeat_basis=NULL');
    const upBuyer = db.prepare(`INSERT INTO buyers (normalized_name, display_name, buyer_group_id, type) VALUES (?,?,?,?)
      ON CONFLICT(normalized_name) DO UPDATE SET buyer_group_id=excluded.buyer_group_id,
        display_name=COALESCE(display_name, excluded.display_name), type=excluded.type`);
    const buyerId = db.prepare('SELECT id FROM buyers WHERE normalized_name = ?');
    const insPurchase = db.prepare(`INSERT OR IGNORE INTO buyer_purchases (buyer_id, apn, deed_id, date, price, cash_buy, hard_money, asset_type)
      VALUES (?,?,?,?,?,?,?,?)`);
    const insExcluded = db.prepare('INSERT OR IGNORE INTO excluded_buyers (normalized_name, category, example_deed_id) VALUES (?,?,?)');

    const facts = new Map<string, PurchaseFact[]>(); // normalized grantee -> purchases
    const skip = (k: string) => { res.skipped[k] = (res.skipped[k] ?? 0) + 1; };
    for (const d of deeds) {
      const norm = d.grantee ? normalizeName(d.grantee) : '';
      if (norm) {
        const cat = classifyExcluded(norm);
        if (cat) { insExcluded.run(norm, cat, d.id); res.excluded++; continue; }
      }
      const prop = d.apn ? props.get(`${d.county}|${d.apn}`) : undefined;
      // Land use AT PURCHASE: the prior-roll code when present (a lot later built on is still a lot buy).
      const landUse = prop?.land_use_prior ?? prop?.land_use ?? null;
      const dots = dotsByBorrower.get(`${d.county}|${norm}`) ?? [];
      const ev = evaluateCashBuy(d, landUse, dots, groupOf);
      if (!ev.counted) { skip(ev.reason ?? 'other'); continue; }
      const type = 'investor';
      upBuyer.run(norm, d.grantee, groupOf(norm) ?? `G:${norm}`, type);
      const id = (buyerId.get(norm) as { id: number }).id;
      insPurchase.run(id, d.apn, d.id, d.record_date, d.consideration, ev.cashBuy ? 1 : 0, ev.financedHardMoney ? 1 : 0, ev.assetType);
      (facts.get(norm) ?? facts.set(norm, []).get(norm)!).push({
        deedId: d.id, instrumentNo: d.instrument_no, apn: d.apn, date: d.record_date,
        cashBuy: ev.cashBuy, hardMoney: ev.financedHardMoney, assetType: ev.assetType!,
      });
      if (ev.cashBuy) res.cashBuys++;
      if (ev.financedHardMoney) res.hardMoneyBuys++;
    }
    res.grantees = facts.size;

    // Repeat tests: per grantee, then per buyer_group (entities sharing agent + mailing act as one buyer).
    const byGroup = new Map<string, string[]>();
    for (const n of facts.keys()) (byGroup.get(groups.get(n)!) ?? byGroup.set(groups.get(n)!, []).get(groups.get(n)!)!).push(n);
    const setFlags = db.prepare(`UPDATE buyers SET verified_repeat_buyer=MAX(verified_repeat_buyer, ?), verified_repeat_lot_buyer=MAX(verified_repeat_lot_buyer, ?),
      confirmed_builder=MAX(confirmed_builder, ?), repeat_basis=COALESCE(repeat_basis, ?) WHERE normalized_name = ?`);
    for (const [, members] of byGroup) {
      for (const asset of ['sfr', 'infill_lot'] as AssetType[]) {
        const all = members.flatMap((m) => facts.get(m)!);
        const groupRepeat = countCashBuys(all, asOf, asset) >= 2;
        let lotConfirm = false;
        if (asset === 'infill_lot' && groupRepeat) {
          const lots = all.filter((p) => p.assetType === 'infill_lot' && p.cashBuy);
          lotConfirm = confirmBuilder(db, lots).confirmed;
        }
        for (const m of members) {
          const own = countCashBuys(facts.get(m)!, asOf, asset) >= 2;
          if (!own && !groupRepeat) continue;
          const basis = own ? 'grantee' : 'group';
          setFlags.run(asset === 'sfr' ? 1 : 0, asset === 'infill_lot' ? 1 : 0, lotConfirm ? 1 : 0, basis, m);
        }
        if (groupRepeat) { if (asset === 'sfr') res.repeatBuyers++; else { res.repeatLotBuyers++; if (lotConfirm) res.confirmedBuilders++; } }
      }
    }

    // [SR] research buyers become verified once a [GR] deed-derived buyer with the same normalized name exists.
    db.exec(`UPDATE research_buyers SET verification_status='verified_gr',
      matched_buyer_id=(SELECT b.id FROM buyers b WHERE b.normalized_name = research_buyers.normalized_name)
      WHERE EXISTS (SELECT 1 FROM buyer_purchases bp JOIN buyers b ON b.id = bp.buyer_id
                    WHERE b.normalized_name = research_buyers.normalized_name AND bp.cash_buy = 1)`);
    db.exec('COMMIT');

    res.recordsOut = res.cashBuys;
    const noLand = res.skipped.land_use_unknown ?? 0;
    if (noLand) res.errors.push(`${noLand} deed(s) not evaluated: no CAD land-use record (import properties_*.csv)`);
    return res;
  });
}
