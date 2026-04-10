// ─────────────────────────────────────────────────────────────────────────────
// JSON Exporter — writes all JSON output files to project root
// ─────────────────────────────────────────────────────────────────────────────

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import type {
  SFRBuyer,
  LandBuyer,
  SFRMatch,
  BuilderMatch,
  DeadPaperTarget,
  GhostSubdivisionTarget,
} from "../types/index.js";

const __dirname  = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.resolve(__dirname, "../../..");  // project root

function write(filename: string, data: unknown, label: string): void {
  const p = path.join(OUTPUT_DIR, filename);
  fs.writeFileSync(p, JSON.stringify(data, null, 2), "utf-8");
  const count = Array.isArray(data) ? data.length : Object.keys(data as object).length;
  console.log(`[json] wrote ${count} ${label} → ${p}`);
}

export function writeSFRBuyers(buyers: SFRBuyer[]): void {
  write("sfr_buyers.json", buyers, "SFR buyers");
}

export function writeLandBuyers(buyers: LandBuyer[]): void {
  write("land_buyers.json", buyers, "land buyers");
}

export function writeSFRMatchBoard(matches: SFRMatch[]): void {
  write("sfr_match_board.json", matches, "SFR matches");
}

export function writeBuilderMatchBoard(matches: BuilderMatch[]): void {
  write("builder_match_board.json", matches, "builder matches");
}

export function writeDeadPaperTargets(targets: DeadPaperTarget[]): void {
  write("dead_paper_targets.json", targets, "dead paper targets");
}

export function writeGhostSubdivisionTargets(targets: GhostSubdivisionTarget[]): void {
  write("ghost_subdivision_targets.json", targets, "ghost subdivision targets");
}

// Summary manifest written last so the user can see what was produced
export function writeSummaryManifest(stats: {
  scrapeCompletedAt: string;
  listsScraped: number;
  totalRawRecords: number;
  sfrTargets: number;
  landTargets: number;
  deadPaperTargets: number;
  ghostSubdivisions: number;
  sfrBuyers: number;
  landBuyers: number;
  sfrMatches: number;
  builderMatches: number;
  immediateActionFlags: number;
}): void {
  write("propstream_run_summary.json", stats, "summary fields");
}
