// Lightweight CSV parser — no external deps, handles quoted fields and header aliasing

export interface CsvParseResult {
  rows: Record<string, string>[];
  errors: string[];
}

// Column aliases: canonical name → accepted header variants
const HEADER_ALIASES: Record<string, string[]> = {
  address:        ['address', 'property_address', 'addr', 'street'],
  city:           ['city', 'property_city'],
  state:          ['state', 'st', 'property_state'],
  zip:            ['zip', 'zip_code', 'postal', 'zipcode'],
  askingPrice:    ['asking_price', 'asking', 'list_price', 'price'],
  arvEstimate:    ['arv', 'arv_estimate', 'after_repair_value', 'arv_est'],
  arvLow:         ['arv_low', 'arv_min', 'arv_conservative'],
  arvHigh:        ['arv_high', 'arv_max', 'arv_aggressive'],
  rehabEstimate:  ['rehab', 'rehab_estimate', 'repair_cost', 'repairs'],
  bedrooms:       ['beds', 'bedrooms', 'bd', 'br'],
  bathrooms:      ['baths', 'bathrooms', 'ba'],
  sqft:           ['sqft', 'sq_ft', 'square_feet', 'living_area'],
  yearBuilt:      ['year_built', 'yr_built', 'built'],
  conditionGrade: ['condition', 'condition_grade', 'grade'],
  taxDelinquent:  ['tax_delinquent', 'tax_delinq', 'delinquent'],
  bankruptcy:     ['bankruptcy', 'bk'],
  liens:          ['liens', 'lien'],
  vacant:         ['vacant', 'vacancy'],
  preForeclosure: ['pre_foreclosure', 'preforeclosure', 'nod'],
  notes:          ['notes', 'comments', 'remarks'],
};

// Build reverse lookup: normalized_lower_header → canonical key
const REVERSE_MAP: Map<string, string> = new Map();
for (const [canonical, variants] of Object.entries(HEADER_ALIASES)) {
  for (const variant of variants) {
    REVERSE_MAP.set(variant.toLowerCase(), canonical);
  }
}

export function parseCsv(csvText: string): CsvParseResult {
  const lines = csvText.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) {
    return { rows: [], errors: ['CSV must have a header row and at least one data row'] };
  }

  const errors: string[] = [];
  const rawHeaders = parseCsvLine(lines[0]);
  const headers = rawHeaders.map((h) => REVERSE_MAP.get(h.trim().toLowerCase()) ?? h.trim().toLowerCase());

  const rows: Record<string, string>[] = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const values = parseCsvLine(line);
    if (values.length !== rawHeaders.length) {
      errors.push(`Row ${i + 1}: expected ${rawHeaders.length} columns, got ${values.length} — skipping`);
      continue;
    }

    const row: Record<string, string> = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = values[j].trim();
    }
    rows.push(row);
  }

  return { rows, errors };
}

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      fields.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  fields.push(current);
  return fields;
}
