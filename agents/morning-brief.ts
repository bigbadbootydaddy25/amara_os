import fs from 'node:fs';
import path from 'node:path';
import { DEFAULT_FEE_LOT, DEFAULT_FEE_SFR, PATHS, RULESET_VERSION } from './config';
import { withRun, type DB, type RunStats } from './lib/db';
import { lotGate, type GateResult } from './lib/lot-gate';
import { isAutoAllowed, loadSources, type SourcesFile } from './lib/sources';
import { today } from './lib/dates';

export interface BriefResult extends RunStats { sfrLeads: number; lotLeads: number; file: string | null; emailSent: false; emailNote: string }

interface Row { lead_id: number; apn: string | null; asset_type: 'sfr' | 'infill_lot'; distress_type: string; distress_date: string | null; tag: string; address: string | null; zip: string | null;
  evidence_url: string | null; county: string }
interface MatchRow { buyer_group_id: string; score: number; reasons: string; confidence_tag: string; rank: number }

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const usd = (n: number | null | undefined) => (n == null ? 'n/a' : `$${Math.round(n).toLocaleString('en-US')}`);

/**
 * Morning Brief (spec §5.5). Builds and STORES the brief (DB + out/briefs/). Email delivery is OFF:
 * nothing is sent unless sources.yaml `morning_brief_email` is approved/auto AND a sender is built (not in Phase 1).
 * SFR and Infill Lot leads are separate sections. Offer math: Buyer Max − Repairs − Fee = Net to Seller.
 */
export function runMorningBrief(db: DB, opts: { asOf?: string; outDir?: string; src?: SourcesFile } = {}): BriefResult {
  const asOf = opts.asOf ?? today();
  const src = opts.src ?? loadSources();
  return withRun(db, 'morning-brief', () => {
    const emailNote = isAutoAllowed(src, 'morning_brief_email')
      ? 'email approved in sources.yaml but no sender is implemented in Phase 1 — brief stored only'
      : 'email delivery OFF (sources.yaml: morning_brief_email) — brief stored only';
    const res: BriefResult = { recordsIn: 0, recordsOut: 0, errors: [], sfrLeads: 0, lotLeads: 0, file: null, emailSent: false, emailNote };

    const leads = db.prepare(`SELECT l.id AS lead_id, l.apn, l.asset_type, l.distress_type, l.distress_date, l.tag, COALESCE(l.address, p.address) AS address,
      COALESCE(l.zip, p.zip) AS zip, l.evidence_url, l.county FROM leads l LEFT JOIN properties p ON p.apn = l.apn AND p.county = l.county
      WHERE EXISTS (SELECT 1 FROM matches m WHERE m.lead_id = l.id) ORDER BY l.asset_type DESC, (SELECT MAX(score) FROM matches m WHERE m.lead_id = l.id) DESC`).all() as unknown as Row[];
    res.recordsIn = leads.length;

    const md: string[] = [`# AMARA Morning Brief — ${asOf}`, `_${RULESET_VERSION}_`, `_${emailNote}_`, ''];
    const html: string[] = [`<h1>AMARA Morning Brief — ${esc(asOf)}</h1><p><em>${esc(RULESET_VERSION)}</em></p><p><em>${esc(emailNote)}</em></p>`];

    for (const asset of ['sfr', 'infill_lot'] as const) {
      const section = leads.filter((l) => l.asset_type === asset);
      const title = asset === 'sfr' ? 'SFR Leads' : 'Infill Lot Leads';
      md.push(`## ${title} (${section.length})`, '');
      html.push(`<h2>${title} (${section.length})</h2>`);
      if (!section.length) { md.push('_No scored matches today._', ''); html.push('<p><em>No scored matches today.</em></p>'); }
      const fee = asset === 'sfr' ? DEFAULT_FEE_SFR : DEFAULT_FEE_LOT;
      for (const l of section) {
        if (asset === 'sfr') res.sfrLeads++; else res.lotLeads++;
        res.recordsOut++;
        const prop = l.apn ? db.prepare('SELECT * FROM properties WHERE apn = ? AND county = ?').get(l.apn, l.county) as Record<string, unknown> | undefined : undefined;
        const gate: GateResult | null = asset === 'infill_lot' ? lotGate(db, l.apn, l.county) : null;
        const ms = db.prepare('SELECT buyer_group_id, score, reasons, confidence_tag, rank FROM matches WHERE lead_id = ? ORDER BY rank').all(l.lead_id) as unknown as MatchRow[];
        const lines: string[] = [];
        lines.push(`### ${l.address ?? l.apn ?? 'unknown address'} ${l.zip ?? ''}`.trim());
        lines.push(`- Distress: ${l.distress_type} ${l.distress_date ?? ''} ${l.tag}${l.evidence_url ? ` — ${l.evidence_url}` : ''}`);
        if (prop) lines.push(`- CAD: ${[`APN ${prop.apn}`, prop.beds != null && `${prop.beds} bd`, prop.sqft != null && `${prop.sqft} sf`, prop.year_built && `built ${prop.year_built}`,
          prop.cad_value != null && `value ${usd(prop.cad_value as number)}`, prop.owner && `owner ${prop.owner}`].filter(Boolean).join(' · ')} ${prop.tag ?? ''}`);
        else lines.push('- CAD: no property record on file');
        if (gate) lines.push(`- Lot Gate: ${gate.checks.map((c) => `${c.name}=${c.state.toUpperCase()}${c.state !== 'pass' ? ` (${c.note})` : ''}`).join('; ')}`);
        lines.push('- Top buyers:');
        for (const m of ms) {
          const box = db.prepare('SELECT * FROM buy_boxes WHERE buyer_group_id = ? AND asset_type = ?').get(m.buyer_group_id, asset) as Record<string, unknown>;
          const name = (db.prepare('SELECT display_name, normalized_name FROM buyers WHERE buyer_group_id = ? ORDER BY id LIMIT 1').get(m.buyer_group_id) as
            { display_name: string | null; normalized_name: string } | undefined);
          const comps = db.prepare(`SELECT p.address, bp.date, bp.price FROM buyer_purchases bp JOIN buyers b ON b.id = bp.buyer_id
            LEFT JOIN deeds d ON d.id = bp.deed_id LEFT JOIN properties p ON p.apn = bp.apn AND p.county = d.county
            WHERE b.buyer_group_id = ? AND bp.cash_buy = 1 AND bp.asset_type = ? ORDER BY bp.date DESC LIMIT 3`).all(m.buyer_group_id, asset) as unknown as Array<{ address: string | null; date: string; price: number | null }>;
          const max = box.price_max as number | null;
          const repairs = 0;
          lines.push(`  ${m.rank}. ${name?.display_name ?? name?.normalized_name ?? m.buyer_group_id} — score ${m.score}, confidence ${m.confidence_tag}, box confidence ${box.confidence} (${box.buys_12m} cash buys/12mo, last ${box.last_buy_date})`);
          lines.push(`     comps: ${comps.map((c) => `${c.address ?? 'n/a'} ${c.date} ${usd(c.price)}`).join(' | ') || 'none'}`);
          lines.push(`     ${asset === 'sfr' ? 'Buyer Max' : 'Builder Max Lot Price'} (est., top of their price range) ${usd(max)} − ${asset === 'sfr' ? 'Repairs' : 'Lot prep/closing'} ${usd(repairs)} (PLACEHOLDER — TBD) − Fee ${usd(fee)} = Net to Seller ${max == null ? 'n/a' : usd(max - repairs - fee)}`);
          if (max == null) lines.push('     ⚠ no disclosed price history — max offer unknown, offer math incomplete');
        }
        md.push(...lines, '');
        html.push(`<pre>${esc(lines.join('\n'))}</pre>`);
      }
    }
    const body_md = md.join('\n');
    const body_html = `<!doctype html><meta charset="utf-8"><title>AMARA Morning Brief ${esc(asOf)}</title><body>${html.join('\n')}</body>`;
    db.prepare(`INSERT INTO briefs (brief_date, body_md, body_html, ruleset_version, created_at, delivered) VALUES (?,?,?,?,?,0)
      ON CONFLICT(brief_date) DO UPDATE SET body_md=excluded.body_md, body_html=excluded.body_html, ruleset_version=excluded.ruleset_version, created_at=excluded.created_at`)
      .run(asOf, body_md, body_html, RULESET_VERSION, new Date().toISOString());
    const dir = opts.outDir ?? PATHS.briefs;
    fs.mkdirSync(dir, { recursive: true });
    res.file = path.join(dir, `${asOf}.md`);
    fs.writeFileSync(res.file, body_md);
    fs.writeFileSync(path.join(dir, `${asOf}.html`), body_html);
    return res;
  });
}
