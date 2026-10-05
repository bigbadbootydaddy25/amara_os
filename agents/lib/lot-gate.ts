import fs from 'node:fs';
import YAML from 'yaml';
import { PATHS } from '../config';
import type { DB } from './db';

export type GateState = 'pass' | 'fail' | 'unknown';
export interface GateCheck { name: string; state: GateState; note: string; tier: 'GR' | 'SR' | 'manual' }
export interface GateResult { checks: GateCheck[]; blocked: boolean }

interface Zoning { verified: boolean; districts: Record<string, number> }
let zoning: Zoning | null = null;
const loadZoning = (): Zoning => (zoning ??= YAML.parse(fs.readFileSync(PATHS.zoning, 'utf8')) as Zoning);

/**
 * Lot Gate (spec §5.6). A FAIL blocks the lot from the brief; UNKNOWN is shown flagged.
 * Zoning rules come from config/dallas-zoning.yaml, which is `verified: false` until Scott
 * confirms them, so a zoning "pass" is reported as unknown rather than silently trusted.
 */
export function lotGate(db: DB, apn: string | null, county: string | null): GateResult {
  const d = apn ? (db.prepare('SELECT * FROM lot_details WHERE apn = ? AND county = ?').get(apn, county ?? 'Dallas') as
    { lot_sqft: number | null; frontage_ft: number | null; zoning: string | null; flood_zone: string | null; water_sewer: string | null; floodway: number } | undefined) : undefined;
  const z = loadZoning();
  const checks: GateCheck[] = [];

  if (!d?.zoning) checks.push({ name: 'zoning_sfr_by_right', state: 'unknown', note: 'no zoning on file', tier: 'GR' });
  else if (!(d.zoning in z.districts)) checks.push({ name: 'zoning_sfr_by_right', state: 'fail', note: `${d.zoning} not a single-family-by-right district`, tier: 'GR' });
  else checks.push({ name: 'zoning_sfr_by_right', state: z.verified ? 'pass' : 'unknown', note: z.verified ? d.zoning : `${d.zoning} (zoning table unverified)`, tier: 'GR' });

  const minSqft = d?.zoning ? z.districts[d.zoning] : undefined;
  if (d?.lot_sqft == null || minSqft == null) checks.push({ name: 'min_lot_size', state: 'unknown', note: 'lot size or district minimum unavailable', tier: 'GR' });
  else if (d.lot_sqft < minSqft) checks.push({ name: 'min_lot_size', state: 'fail', note: `${d.lot_sqft} sf < ${minSqft} sf minimum`, tier: 'GR' });
  else checks.push({ name: 'min_lot_size', state: z.verified ? 'pass' : 'unknown', note: `${d.lot_sqft} sf >= ${minSqft} sf`, tier: 'GR' });

  if (!d) checks.push({ name: 'floodway', state: 'unknown', note: 'no flood data', tier: 'GR' });
  else if (d.floodway) checks.push({ name: 'floodway', state: 'fail', note: 'in floodway', tier: 'GR' });
  else checks.push({ name: 'floodway', state: d.flood_zone ? 'pass' : 'unknown', note: `flood zone: ${d.flood_zone ?? 'not noted'}`, tier: 'GR' });

  checks.push({ name: 'water_sewer', state: 'unknown', note: d?.water_sewer ? `${d.water_sewer} — [SR] until confirmed with city` : 'not confirmed — [SR] until confirmed with city', tier: 'SR' });
  checks.push({ name: 'title_defects', state: 'unknown', note: 'HOA/deed restrictions/open liens — Scott title review', tier: 'manual' });
  return { checks, blocked: checks.some((c) => c.state === 'fail') };
}
