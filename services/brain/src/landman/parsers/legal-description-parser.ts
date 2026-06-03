/**
 * Legal Description Parser
 * Handles U.S. Rectangular (Section-Township-Range) and basic Metes & Bounds.
 * Always read aliquot descriptions BACKWARDS per landman convention.
 */

import type { AliquotPart, LegalDescription, STRLocation } from '../types.js';

// ─── Acreage table (standard quarter subdivisions) ────────────────────────────

const FRACTION_ACRES: Record<string, number> = {
  'section':     640,
  'e/2':         320,  'w/2':  320,  'n/2':  320,  's/2': 320,
  'ne/4':        160,  'nw/4': 160,  'se/4': 160,  'sw/4': 160,
  'ne/4 ne/4':    40,  'nw/4 ne/4':  40, 'se/4 ne/4':  40, 'sw/4 ne/4':  40,
  'ne/4 nw/4':    40,  'nw/4 nw/4':  40, 'se/4 nw/4':  40, 'sw/4 nw/4':  40,
  'ne/4 se/4':    40,  'nw/4 se/4':  40, 'se/4 se/4':  40, 'sw/4 se/4':  40,
  'ne/4 sw/4':    40,  'nw/4 sw/4':  40, 'se/4 sw/4':  40, 'sw/4 sw/4':  40,
  'e/2 ne/4':     80,  'w/2 ne/4':   80, 'n/2 ne/4':   80, 's/2 ne/4':   80,
  'e/2 nw/4':     80,  'w/2 nw/4':   80, 'n/2 nw/4':   80, 's/2 nw/4':   80,
  'e/2 se/4':     80,  'w/2 se/4':   80, 'n/2 se/4':   80, 's/2 se/4':   80,
  'e/2 sw/4':     80,  'w/2 sw/4':   80, 'n/2 sw/4':   80, 's/2 sw/4':   80,
  'e/2 ne/4 ne/4': 20, 'w/2 ne/4 ne/4': 20,
  'n/2 ne/4 ne/4': 20, 's/2 ne/4 ne/4': 20,
  'ne/4 ne/4 ne/4': 10, 'sw/4 sw/4 sw/4': 10,
};

// ─── STR extraction ───────────────────────────────────────────────────────────

const STR_PATTERN =
  /[Ss]ection\s+(\d+)[,\s]+[Tt]ownship\s+(\d+)\s*([NS])[,\s]+[Rr]ange\s+(\d+)\s*([EW])/i;

const LOT_PATTERN = /[Ll]ot[s]?\s+([\d,\s&and]+)/i;

export function parseSTR(text: string): Partial<STRLocation> | null {
  const m = STR_PATTERN.exec(text);
  if (!m) return null;
  return {
    section:     parseInt(m[1], 10),
    township:    parseInt(m[2], 10),
    townshipDir: m[3].toUpperCase() as 'N' | 'S',
    range:       parseInt(m[4], 10),
    rangeDir:    m[5].toUpperCase() as 'E' | 'W',
  };
}

// ─── Aliquot parser ───────────────────────────────────────────────────────────

export function parseAliquots(description: string): AliquotPart[] {
  // Normalise: uppercase, collapse whitespace, remove "of the"
  const norm = description
    .toUpperCase()
    .replace(/\bOF\s+THE\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  // Extract the aliquot portion (before "Section")
  const sectionIdx = norm.search(/SECTION/i);
  const aliquotText = sectionIdx > 0 ? norm.slice(0, sectionIdx).trim() : norm;

  // Split on comma for multiple tracts in one description
  const parts = aliquotText.split(',').map((p) => p.trim()).filter(Boolean);
  const result: AliquotPart[] = [];

  for (const part of parts) {
    const acres = lookupAcres(part);
    result.push({ fraction: part, acres });
  }

  return result;
}

function lookupAcres(aliquot: string): number {
  const key = aliquot.toLowerCase().trim();
  if (FRACTION_ACRES[key] !== undefined) return FRACTION_ACRES[key];

  // Try progressive partial match (longest prefix first)
  const words = key.split(/\s+/);
  for (let len = words.length; len >= 1; len--) {
    const attempt = words.slice(0, len).join(' ');
    if (FRACTION_ACRES[attempt] !== undefined) {
      // Apply subdivision factor for remaining parts
      const base = FRACTION_ACRES[attempt];
      const remaining = words.slice(len).join(' ');
      if (!remaining) return base;
      const subFactor = lookupSubdivisionFactor(remaining);
      return base * subFactor;
    }
  }
  return 0; // unknown — caller should flag
}

function lookupSubdivisionFactor(aliquot: string): number {
  const halves  = (aliquot.match(/\/2/g) ?? []).length;
  const quarters = (aliquot.match(/\/4/g) ?? []).length;
  return (1 / Math.pow(2, halves)) * (1 / Math.pow(4, quarters));
}

// ─── Full description parser ──────────────────────────────────────────────────

export function parseLegalDescription(
  raw: string,
  strLocation: STRLocation,
): LegalDescription {
  const lotMatch = LOT_PATTERN.exec(raw);
  const isLot = lotMatch !== null;

  const lotNumbers = isLot
    ? lotMatch![1].split(/[,\s&]+/).map(Number).filter((n) => !isNaN(n))
    : undefined;

  const aliquots = isLot ? [] : parseAliquots(raw);
  const totalAcres = aliquots.reduce((s, a) => s + a.acres, 0);

  return { raw, strLocation, aliquots, totalAcres, isLot, lotNumbers };
}

// ─── Acreage calculator ───────────────────────────────────────────────────────

export function calculateAcres(aliquotDescription: string): number {
  return parseAliquots(aliquotDescription).reduce((s, a) => s + a.acres, 0);
}

// ─── Metes & Bounds bearing parser ───────────────────────────────────────────

export interface Bearing {
  direction: string;  // e.g. "N 42°35' W"
  degrees:   number;
  minutes:   number;
  quadrant:  string;
}

const BEARING_PATTERN = /([NS])\s*(\d+)[°\s]+(\d+)'?\s*([EW])/gi;

export function parseMetesAndBounds(text: string): Bearing[] {
  const bearings: Bearing[] = [];
  let match: RegExpExecArray | null;

  while ((match = BEARING_PATTERN.exec(text)) !== null) {
    bearings.push({
      direction: `${match[1]} ${match[2]}°${match[3]}' ${match[4]}`,
      degrees:   parseInt(match[2], 10),
      minutes:   parseInt(match[3], 10),
      quadrant:  `${match[1]}${match[4]}`,
    });
  }

  return bearings;
}

// ─── Unit conversion helpers ──────────────────────────────────────────────────

export const CHAINS_PER_ACRE = 10;    // 10 sq chains = 1 acre
export const FEET_PER_ROD    = 16.5;
export const FEET_PER_CHAIN  = 66;
export const RODS_PER_CHAIN  = 4;

export function rodsToFeet(rods: number): number {
  return rods * FEET_PER_ROD;
}

export function chainsToFeet(chains: number): number {
  return chains * FEET_PER_CHAIN;
}
