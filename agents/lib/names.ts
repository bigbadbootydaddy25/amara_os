import fs from 'node:fs';
import YAML from 'yaml';
import { PATHS } from '../config';

const SUFFIXES = new Set([
  'LLC', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION', 'LP', 'LLP', 'LTD', 'CO', 'COMPANY', 'PLLC', 'PC',
]);

/**
 * Spec §5.1: strip punctuation/suffixes (LLC, L.L.C., Inc), collapse spacing.
 * Periods are removed (so "L.L.C." -> "LLC"); other punctuation becomes a space.
 */
export function normalizeName(raw: string): string {
  let s = raw.toUpperCase().replace(/\./g, '').replace(/&/g, ' AND ').replace(/[^A-Z0-9 ]/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  let parts = s.split(' ').filter(Boolean);
  // "L L C" written with spaces
  const joined = parts.join(' ');
  if (/ L L C$/.test(joined)) parts = joined.replace(/ L L C$/, '').split(' ');
  if (parts[0] === 'THE' && parts.length > 1) parts.shift();
  while (parts.length > 1 && SUFFIXES.has(parts[parts.length - 1])) parts.pop();
  return parts.join(' ');
}

export type ExcludedCategory = 'national_builder' | 'ibuyer_institutional' | 'government' | 'nonprofit';

let cached: Record<string, string[]> | null = null;
function exclusions(): Record<string, string[]> {
  if (!cached) cached = YAML.parse(fs.readFileSync(PATHS.exclusions, 'utf8')) as Record<string, string[]>;
  return cached;
}

/** Whole-word-ish substring match so "NVR" does not hit "CONVERT". */
function hasPhrase(name: string, phrase: string): boolean {
  return new RegExp(`(^| )${phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}( |$)`).test(name);
}

export function classifyExcluded(normalized: string): ExcludedCategory | null {
  for (const [cat, phrases] of Object.entries(exclusions())) {
    if (phrases.some((p) => hasPhrase(normalized, normalizeName(p) || p))) return cat as ExcludedCategory;
  }
  return null;
}

let lenders: string[] | null = null;
export function isHardMoneyLender(lender: string | null | undefined): boolean {
  if (!lender) return false;
  if (!lenders) lenders = (YAML.parse(fs.readFileSync(PATHS.hardLenders, 'utf8')) as { lenders: string[] }).lenders;
  const n = normalizeName(lender);
  return lenders.some((l) => hasPhrase(n, l));
}

/** Union-find grouping: entities sharing registered agent AND mailing address become one buyer_group. */
export function groupBuyers(
  buyers: Array<{ normalized: string; registeredAgent?: string | null; mailing?: string | null }>,
): Map<string, string> {
  const parent = new Map<string, string>();
  const find = (x: string): string => {
    let r = x;
    while (parent.get(r) !== r) r = parent.get(r)!;
    parent.set(x, r);
    return r;
  };
  for (const b of buyers) parent.set(b.normalized, b.normalized);
  const byKey = new Map<string, string>();
  for (const b of buyers) {
    const agent = b.registeredAgent ? normalizeName(b.registeredAgent) : '';
    const mail = (b.mailing ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (!agent || !mail) continue;
    const key = `${agent}|${mail}`;
    const seen = byKey.get(key);
    if (seen) {
      const a = find(seen);
      const c = find(b.normalized);
      if (a !== c) parent.set(c < a ? a : c, c < a ? c : a); // smallest name is the root => stable id
    } else byKey.set(key, b.normalized);
  }
  const out = new Map<string, string>();
  for (const b of buyers) out.set(b.normalized, `G:${find(b.normalized)}`);
  return out;
}
