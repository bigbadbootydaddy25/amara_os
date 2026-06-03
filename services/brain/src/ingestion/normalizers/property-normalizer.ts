import { z } from 'zod';
import type { Property, IngestionSource } from '../../types.js';

// ─────────────────────────────────────────────
// SCHEMA
// ─────────────────────────────────────────────

const coercedNumber = z.union([
  z.number(),
  z.string().transform((v) => parseFloat(v.replace(/[$,]/g, ''))),
]).pipe(z.number().nonnegative());

const coercedBool = z.union([
  z.boolean(),
  z.string().transform((v) => ['true', 'yes', '1', 'y'].includes(v.toLowerCase())),
]).pipe(z.boolean());

export const RawDealSchema = z.object({
  address: z.string().min(5, 'Address too short'),
  city: z.string().optional().default(''),
  state: z.string().length(2, 'State must be 2-letter code').optional().default('TX'),
  zip: z.string().regex(/^\d{5}(-\d{4})?$/, 'Invalid ZIP format'),

  askingPrice:    coercedNumber.optional(),
  arvEstimate:    coercedNumber.optional(),
  arvLow:         coercedNumber.optional(),
  arvHigh:        coercedNumber.optional(),
  rehabEstimate:  coercedNumber.optional(),

  bedrooms:       coercedNumber.optional(),
  bathrooms:      coercedNumber.optional(),
  sqft:           coercedNumber.optional(),
  yearBuilt:      coercedNumber.optional(),
  conditionGrade: coercedNumber.pipe(z.number().min(1).max(10)).optional(),

  taxDelinquent:  coercedBool.optional().default(false),
  bankruptcy:     coercedBool.optional().default(false),
  liens:          coercedBool.optional().default(false),
  vacant:         coercedBool.optional().default(false),
  preForeclosure: coercedBool.optional().default(false),

  notes: z.string().optional(),
}).passthrough();

export type ValidatedRaw = z.infer<typeof RawDealSchema>;

// ─────────────────────────────────────────────
// NORMALIZER
// ─────────────────────────────────────────────

export interface NormalizeResult {
  property: Property;
  warnings: string[];
}

export function normalizeProperty(
  raw: Record<string, unknown>,
  source: IngestionSource,
): NormalizeResult {
  const parsed = RawDealSchema.parse(raw);
  const warnings: string[] = [];

  // ARV validation
  if (parsed.arvLow && parsed.arvHigh && parsed.arvLow > parsed.arvHigh) {
    warnings.push(`arvLow (${parsed.arvLow}) > arvHigh (${parsed.arvHigh}) — swapping values`);
    [parsed.arvLow, parsed.arvHigh] = [parsed.arvHigh, parsed.arvLow];
  }

  if (!parsed.arvEstimate && !parsed.arvLow && !parsed.arvHigh) {
    warnings.push('No ARV provided — simulation confidence will be low');
  }

  if (parsed.conditionGrade !== undefined) {
    if (parsed.conditionGrade <= 3 && !parsed.rehabEstimate) {
      warnings.push('Poor condition grade (≤3) with no rehab estimate — defaulting to 20% ARV');
    }
  }

  const property: Property = {
    address:       parsed.address.trim(),
    city:          parsed.city?.trim() ?? '',
    state:         parsed.state?.toUpperCase() ?? 'TX',
    zip:           parsed.zip.slice(0, 5),
    ingestionSource: source,

    bedrooms:      parsed.bedrooms,
    bathrooms:     parsed.bathrooms,
    sqft:          parsed.sqft,
    yearBuilt:     parsed.yearBuilt,
    conditionGrade: parsed.conditionGrade,

    askingPrice:   parsed.askingPrice,
    arvEstimate:   parsed.arvEstimate,
    arvLow:        parsed.arvLow,
    arvHigh:       parsed.arvHigh,
    rehabEstimate: resolveRehab(parsed),

    taxDelinquent:  parsed.taxDelinquent,
    bankruptcy:     parsed.bankruptcy,
    liens:          parsed.liens,
    vacant:         parsed.vacant,
    preForeclosure: parsed.preForeclosure,

    notes:          parsed.notes,
    rawInput:       raw as Record<string, unknown>,
  };

  return { property, warnings };
}

function resolveRehab(parsed: ValidatedRaw): number {
  if (parsed.rehabEstimate !== undefined) return parsed.rehabEstimate;

  // Estimate from condition grade if no rehab given
  const arv = parsed.arvEstimate ?? parsed.arvHigh ?? parsed.arvLow;
  if (!arv || !parsed.conditionGrade) return 0;

  const grade = parsed.conditionGrade;
  if (grade >= 8) return arv * 0.03;       // light cosmetic
  if (grade >= 6) return arv * 0.08;       // moderate
  if (grade >= 4) return arv * 0.15;       // full cosmetic
  if (grade >= 2) return arv * 0.25;       // heavy rehab
  return arv * 0.40;                        // gut rehab
}
