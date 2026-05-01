import fs from 'fs';
import path from 'path';
import { runQuery } from './neo4j-client';

export interface BuyerRecord {
  name: string;
  email?: string;
  phone?: string;
  markets?: string[];
  priceMin?: number;
  priceMax?: number;
  propertyTypes?: string[];
  zipCodes?: string[];
  pastPurchases?: number;
  isRepeat?: boolean;
  isWhale?: boolean;
}

function normaliseBuyer(raw: Record<string, unknown>): BuyerRecord {
  return {
    name: String(raw.name || raw.buyerName || raw.contact || '').trim(),
    email: raw.email ? String(raw.email).toLowerCase().trim() : undefined,
    phone: raw.phone ? String(raw.phone).replace(/\D/g, '') : undefined,
    markets: Array.isArray(raw.markets) ? (raw.markets as string[]).map((m) => String(m).toUpperCase().trim()) : [],
    priceMin: raw.priceMin != null ? Number(raw.priceMin) : raw.minPrice != null ? Number(raw.minPrice) : undefined,
    priceMax: raw.priceMax != null ? Number(raw.priceMax) : raw.maxPrice != null ? Number(raw.maxPrice) : undefined,
    propertyTypes: Array.isArray(raw.propertyTypes) ? (raw.propertyTypes as string[]) : [],
    zipCodes: Array.isArray(raw.zipCodes) ? (raw.zipCodes as string[]).map((z) => String(z).padStart(5, '0')) : [],
    pastPurchases: raw.pastPurchases != null ? Number(raw.pastPurchases) : 0,
    isRepeat: Boolean(raw.isRepeat || (raw.pastPurchases != null && Number(raw.pastPurchases) > 0)),
    isWhale: Boolean(raw.isWhale || (raw.priceMax != null && Number(raw.priceMax) >= 500000)),
  };
}

export interface IngestResult {
  created: number;
  skipped: number;
  errors: string[];
}

export async function ingestBuyers(importDir: string): Promise<IngestResult> {
  const result: IngestResult = { created: 0, skipped: 0, errors: [] };

  if (!fs.existsSync(importDir)) {
    result.errors.push(`Import directory not found: ${importDir}`);
    return result;
  }

  const files = fs.readdirSync(importDir).filter((f) => f.endsWith('.json'));

  if (files.length === 0) {
    result.errors.push(`No JSON files found in ${importDir}`);
    return result;
  }

  for (const file of files) {
    const filePath = path.join(importDir, file);
    let records: unknown[];

    try {
      const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as unknown;
      records = Array.isArray(raw) ? raw : [raw];
    } catch (err) {
      result.errors.push(`Failed to parse ${file}: ${err}`);
      continue;
    }

    for (const record of records) {
      if (typeof record !== 'object' || !record) {
        result.skipped++;
        continue;
      }

      const buyer = normaliseBuyer(record as Record<string, unknown>);

      if (!buyer.name) {
        result.skipped++;
        continue;
      }

      try {
        await runQuery(
          `MERGE (b:Buyer {name: $name})
           SET b.email       = $email,
               b.phone       = $phone,
               b.priceMin    = $priceMin,
               b.priceMax    = $priceMax,
               b.pastPurchases = $pastPurchases,
               b.isRepeat    = $isRepeat,
               b.isWhale     = $isWhale,
               b.updatedAt   = datetime()
           WITH b
           UNWIND $markets AS market
             MERGE (m:Market {name: market})
             MERGE (b)-[:ACTIVE_IN]->(m)
           WITH b
           UNWIND $zipCodes AS zip
             SET b.zipCodes = coalesce(b.zipCodes, []) + [zip]
           RETURN b`,
          {
            name: buyer.name,
            email: buyer.email ?? null,
            phone: buyer.phone ?? null,
            priceMin: buyer.priceMin ?? null,
            priceMax: buyer.priceMax ?? null,
            pastPurchases: buyer.pastPurchases ?? 0,
            isRepeat: buyer.isRepeat ?? false,
            isWhale: buyer.isWhale ?? false,
            markets: buyer.markets ?? [],
            zipCodes: buyer.zipCodes ?? [],
          },
        );
        result.created++;
      } catch (err) {
        result.errors.push(`Failed to ingest buyer "${buyer.name}": ${err}`);
      }
    }
  }

  return result;
}

// Runnable as a standalone script
if (process.argv[1] && process.argv[1].includes('ingest-buyers')) {
  const importDir = process.env.BUYERS_IMPORT_DIR || path.resolve(process.cwd(), 'data/imports/buyers');
  ingestBuyers(importDir)
    .then((r) => {
      console.log(`Buyers ingested — created: ${r.created}, skipped: ${r.skipped}`);
      if (r.errors.length) console.error('Errors:', r.errors);
      process.exit(r.errors.length ? 1 : 0);
    })
    .catch((e) => { console.error(e); process.exit(1); });
}
