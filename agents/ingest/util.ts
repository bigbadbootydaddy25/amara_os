import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'csv-parse/sync';

export function readCsv(file: string): Array<Record<string, string>> {
  const rows = parse(fs.readFileSync(file, 'utf8'), {
    columns: (h: string[]) => h.map((x) => x.trim().toLowerCase().replace(/^﻿/, '')),
    skip_empty_lines: true, relax_column_count: true, trim: true, bom: true,
  }) as Array<Record<string, string>>;
  return rows;
}

/** CSV text is DATA. Strip control chars and cap length; never interpreted as instructions. */
export function clean(v: string | undefined, max = 500): string | null {
  if (v == null) return null;
  const s = v.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
  return s || null;
}

export function num(v: string | undefined): number | null {
  if (v == null) return null;
  const s = v.replace(/[$,\s]/g, '');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export function isHttpUrl(v: string | null): boolean {
  if (!v) return false;
  try {
    const u = new URL(v);
    return (u.protocol === 'http:' || u.protocol === 'https:') && !!u.hostname.includes('.');
  } catch {
    return false;
  }
}

export function csvFiles(dir: string, prefix = ''): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.toLowerCase().endsWith('.csv') && f.toLowerCase().startsWith(prefix))
    .sort()
    .map((f) => path.join(dir, f));
}

/** Move a processed file out of the inbox so it is never ingested twice. */
export function archive(file: string): void {
  const dir = path.join(path.dirname(file), 'processed');
  fs.mkdirSync(dir, { recursive: true });
  fs.renameSync(file, path.join(dir, path.basename(file)));
}
