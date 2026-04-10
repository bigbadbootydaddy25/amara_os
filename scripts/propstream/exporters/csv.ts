// ─────────────────────────────────────────────────────────────────────────────
// CSV Exporter — writes sfr_targets_by_zip.csv and land_targets_by_zip.csv
// ─────────────────────────────────────────────────────────────────────────────

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import type { SFRTarget, LandTarget } from "../types/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, "../data");
const OUTPUT_DIR = path.resolve(__dirname, "../../..");  // project root

// Final output goes to the project root for easy access
export const SFR_CSV_PATH  = path.join(OUTPUT_DIR, "sfr_targets_by_zip.csv");
export const LAND_CSV_PATH = path.join(OUTPUT_DIR, "land_targets_by_zip.csv");

function escapeCell(value: unknown): string {
  const str = value === null || value === undefined ? "" : String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildRow(values: unknown[]): string {
  return values.map(escapeCell).join(",");
}

// ─── SFR CSV ──────────────────────────────────────────────────────────────────

const SFR_HEADERS = [
  "zip", "market", "tier", "address", "city", "state",
  "property_type", "year_built", "price", "assessed_value",
  "list_type", "recording_date", "distress_indicators",
  "owner_name", "incomplete",
];

export function writeSFRCSV(targets: SFRTarget[]): void {
  // Sort by ZIP then by distress count descending
  const sorted = [...targets].sort((a, b) => {
    if (a.zip !== b.zip) return a.zip.localeCompare(b.zip);
    return b.distressIndicators.length - a.distressIndicators.length;
  });

  const lines = [
    SFR_HEADERS.join(","),
    ...sorted.map((t) =>
      buildRow([
        t.zip,
        t.market,
        t.tier,
        t.address,
        t.city,
        t.state,
        t.propertyType,
        t.yearBuilt,
        t.price,
        t.assessedValue,
        t.listType,
        t.recordingDate,
        t.distressIndicators.join("|"),
        t.ownerName,
        t.incomplete,
      ])
    ),
  ];

  fs.writeFileSync(SFR_CSV_PATH, lines.join("\n"), "utf-8");
  console.log(`[csv] wrote ${sorted.length} SFR targets → ${SFR_CSV_PATH}`);
}

// ─── Land CSV ─────────────────────────────────────────────────────────────────

const LAND_HEADERS = [
  "zip", "market", "tier", "address", "apn", "city", "state", "county",
  "lot_size", "acreage", "lot_count", "zoning",
  "classification", "distress_type", "distress_signals",
  "owner_entity", "price", "assessed_value",
  "approval_date", "permit_activity", "list_type", "incomplete",
];

export function writeLandCSV(targets: LandTarget[]): void {
  const sorted = [...targets].sort((a, b) => {
    if (a.zip !== b.zip) return a.zip.localeCompare(b.zip);
    return b.distressSignals.length - a.distressSignals.length;
  });

  const lines = [
    LAND_HEADERS.join(","),
    ...sorted.map((t) =>
      buildRow([
        t.zip,
        t.market,
        t.tier,
        t.address,
        t.apn,
        t.city,
        t.state,
        t.county,
        t.lotSizeRaw,
        t.acreage,
        t.lotCount,
        t.zoning,
        t.classification,
        t.distressType,
        t.distressSignals.join("|"),
        t.ownerEntityName,
        t.price,
        t.assessedValue,
        t.approvalDate,
        t.permitActivity,
        t.listType,
        t.incomplete,
      ])
    ),
  ];

  fs.writeFileSync(LAND_CSV_PATH, lines.join("\n"), "utf-8");
  console.log(`[csv] wrote ${sorted.length} land targets → ${LAND_CSV_PATH}`);
}
