import fs from 'node:fs';
import YAML from 'yaml';
import { PATHS } from '../config';
import type { DB } from './db';

export type AccessStatus = 'pending' | 'approved' | 'assisted_only' | 'denied' | 'not_checked';

export interface Source {
  name: string;
  description?: string;
  county: string | null;
  use?: string;
  access_status: AccessStatus;
  terms_checked_date: string | null;
  mode: 'auto' | 'assisted';
  evidence_tier: 'SR' | 'GR' | 'PC';
  paid: boolean;
}

export interface SourcesFile {
  ruleset_version: string;
  active_counties: string[];
  sources: Source[];
}

const STATUSES: AccessStatus[] = ['pending', 'approved', 'assisted_only', 'denied', 'not_checked'];

export function loadSources(file: string = PATHS.sources): SourcesFile {
  const raw = YAML.parse(fs.readFileSync(file, 'utf8'), { schema: 'core' }) as SourcesFile;
  const names = new Set<string>();
  for (const s of raw.sources) {
    if (!STATUSES.includes(s.access_status)) throw new Error(`sources.yaml: bad access_status for ${s.name}`);
    if (names.has(s.name)) throw new Error(`sources.yaml: duplicate source ${s.name}`);
    names.add(s.name);
    s.terms_checked_date = s.terms_checked_date ? String(s.terms_checked_date).slice(0, 10) : null;
  }
  return raw;
}

/**
 * THE GATE. Automatic access is allowed only when access_status is exactly
 * `approved` AND mode is `auto`. Unknown source names are denied.
 */
export function isAutoAllowed(src: SourcesFile, name: string): boolean {
  const s = src.sources.find((x) => x.name === name);
  return !!s && s.access_status === 'approved' && s.mode === 'auto';
}

export function requireAutoAccess(src: SourcesFile, name: string): void {
  if (!isAutoAllowed(src, name)) {
    throw new Error(`source "${name}" is not approved for automatic access (assisted mode only)`);
  }
}

export function activeCounties(src: SourcesFile): string[] {
  return src.active_counties;
}

/** Mirror sources.yaml into the `sources` table (yaml is the single source of truth). */
export function syncSources(db: DB, src: SourcesFile): number {
  db.exec('DELETE FROM sources');
  const ins = db.prepare(
    'INSERT INTO sources (name, county, access_status, terms_checked_date, mode, evidence_tier, paid) VALUES (?,?,?,?,?,?,?)',
  );
  for (const s of src.sources) {
    ins.run(s.name, s.county, s.access_status, s.terms_checked_date, s.mode, s.evidence_tier, s.paid ? 1 : 0);
  }
  return src.sources.length;
}
