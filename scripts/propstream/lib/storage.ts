// ─────────────────────────────────────────────────────────────────────────────
// Storage — read/write raw JSON files and maintain a progress checkpoint
// ─────────────────────────────────────────────────────────────────────────────

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import type { LeadListName, RawRecord } from "../types/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.resolve(__dirname, "../data");
const CHECKPOINT_PATH = path.join(DATA_DIR, "checkpoint.json");

export function ensureDataDir(): void {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// ─── Raw list files ───────────────────────────────────────────────────────────

export function rawListPath(listName: LeadListName): string {
  const safe = listName.toLowerCase().replace(/[^a-z0-9]+/g, "_");
  return path.join(DATA_DIR, `raw_${safe}.json`);
}

export function saveRawList(listName: LeadListName, records: RawRecord[]): void {
  ensureDataDir();
  fs.writeFileSync(rawListPath(listName), JSON.stringify(records, null, 2));
  console.log(`  [storage] saved ${records.length} records → ${path.basename(rawListPath(listName))}`);
}

export function loadRawList(listName: LeadListName): RawRecord[] {
  const p = rawListPath(listName);
  if (!fs.existsSync(p)) return [];
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

export function rawListExists(listName: LeadListName): boolean {
  return fs.existsSync(rawListPath(listName));
}

// Append a page of records without holding all in memory
export function appendRawPage(listName: LeadListName, newRecords: RawRecord[]): void {
  ensureDataDir();
  const p = rawListPath(listName);
  let existing: RawRecord[] = [];
  if (fs.existsSync(p)) {
    try { existing = JSON.parse(fs.readFileSync(p, "utf-8")); } catch { /* fresh */ }
  }
  existing.push(...newRecords);
  fs.writeFileSync(p, JSON.stringify(existing, null, 2));
}

// ─── Checkpoint (resume interrupted runs) ─────────────────────────────────────

export interface Checkpoint {
  startedAt: string;
  completedLists: LeadListName[];
  inProgressList: LeadListName | null;
  inProgressPage: number;
  errors: Array<{ list: LeadListName; message: string }>;
}

export function loadCheckpoint(): Checkpoint {
  if (!fs.existsSync(CHECKPOINT_PATH)) {
    return {
      startedAt: new Date().toISOString(),
      completedLists: [],
      inProgressList: null,
      inProgressPage: 0,
      errors: [],
    };
  }
  return JSON.parse(fs.readFileSync(CHECKPOINT_PATH, "utf-8"));
}

export function saveCheckpoint(cp: Checkpoint): void {
  ensureDataDir();
  fs.writeFileSync(CHECKPOINT_PATH, JSON.stringify(cp, null, 2));
}

export function markListComplete(listName: LeadListName): void {
  const cp = loadCheckpoint();
  if (!cp.completedLists.includes(listName)) {
    cp.completedLists.push(listName);
  }
  cp.inProgressList = null;
  cp.inProgressPage = 0;
  saveCheckpoint(cp);
}

export function markListInProgress(listName: LeadListName, page: number): void {
  const cp = loadCheckpoint();
  cp.inProgressList = listName;
  cp.inProgressPage = page;
  saveCheckpoint(cp);
}

export function recordError(listName: LeadListName, message: string): void {
  const cp = loadCheckpoint();
  cp.errors.push({ list: listName, message });
  saveCheckpoint(cp);
}

// ─── Generic JSON file helpers ────────────────────────────────────────────────

export function writeJson(filename: string, data: unknown): void {
  ensureDataDir();
  const p = path.join(DATA_DIR, filename);
  fs.writeFileSync(p, JSON.stringify(data, null, 2));
  console.log(`  [storage] wrote ${p}`);
}

export function readJson<T>(filename: string): T | null {
  const p = path.join(DATA_DIR, filename);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf-8")) as T;
}
