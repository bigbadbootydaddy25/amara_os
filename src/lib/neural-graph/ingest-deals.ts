import fs from 'fs';
import path from 'path';
import { runQuery } from './neo4j-client';

export interface DealRecord {
  address: string;
  city?: string;
  state?: string;
  zip?: string;
  market?: string;
  price?: number;
  arv?: number;
  beds?: number;
  baths?: number;
  sqft?: number;
  dom?: number;
  description?: string;
  propertyType?: string;
  lane?: string; // SFR_INFILL | WHALE_SUBDIVISION
  source?: string;
}

function normaliseDeal(raw: Record<string, unknown>, lane: string): DealRecord {
  const zip = raw.zip || raw.zipCode || raw.postalCode;
  return {
    address: String(raw.address || raw.propertyAddress || '').trim(),
    city: raw.city ? String(raw.city).trim() : undefined,
    state: raw.state ? String(raw.state).toUpperCase().trim() : undefined,
    zip: zip ? String(zip).padStart(5, '0') : undefined,
    market: raw.market ? String(raw.market).toUpperCase().trim() : undefined,
    price: raw.price != null ? Number(raw.price) : raw.listPrice != null ? Number(raw.listPrice) : undefined,
    arv: raw.arv != null ? Number(raw.arv) : undefined,
    beds: raw.beds != null ? Number(raw.beds) : undefined,
    baths: raw.baths != null ? Number(raw.baths) : undefined,
    sqft: raw.sqft != null ? Number(raw.sqft) : raw.squareFeet != null ? Number(raw.squareFeet) : undefined,
    dom: raw.dom != null ? Number(raw.dom) : raw.daysOnMarket != null ? Number(raw.daysOnMarket) : undefined,
    description: raw.description ? String(raw.description) : undefined,
    propertyType: raw.propertyType ? String(raw.propertyType) : lane === 'WHALE_SUBDIVISION' ? 'LAND' : 'SFR',
    lane,
    source: raw.source ? String(raw.source) : undefined,
  };
}

export interface IngestResult {
  created: number;
  skipped: number;
  errors: string[];
}

async function ingestLane(dir: string, lane: string, result: IngestResult): Promise<void> {
  if (!fs.existsSync(dir)) return;

  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  for (const file of files) {
    const filePath = path.join(dir, file);
    let records: unknown[];

    try {
      const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as unknown;
      records = Array.isArray(raw) ? raw : [raw];
    } catch (err) {
      result.errors.push(`Failed to parse ${file}: ${err}`);
      continue;
    }

    for (const record of records) {
      if (typeof record !== 'object' || !record) { result.skipped++; continue; }

      const deal = normaliseDeal(record as Record<string, unknown>, lane);
      if (!deal.address) { result.skipped++; continue; }

      try {
        await runQuery(
          `MERGE (d:Deal {address: $address})
           SET d.city        = $city,
               d.state       = $state,
               d.zip         = $zip,
               d.price       = $price,
               d.arv         = $arv,
               d.beds        = $beds,
               d.baths       = $baths,
               d.sqft        = $sqft,
               d.dom         = $dom,
               d.description = $description,
               d.propertyType= $propertyType,
               d.lane        = $lane,
               d.source      = $source,
               d.updatedAt   = datetime()
           WITH d
           WHERE $market IS NOT NULL
             MERGE (m:Market {name: $market})
             MERGE (d)-[:LOCATED_IN]->(m)
           RETURN d`,
          {
            address: deal.address,
            city: deal.city ?? null,
            state: deal.state ?? null,
            zip: deal.zip ?? null,
            market: deal.market ?? null,
            price: deal.price ?? null,
            arv: deal.arv ?? null,
            beds: deal.beds ?? null,
            baths: deal.baths ?? null,
            sqft: deal.sqft ?? null,
            dom: deal.dom ?? null,
            description: deal.description ?? null,
            propertyType: deal.propertyType ?? null,
            lane: deal.lane,
            source: deal.source ?? null,
          },
        );
        result.created++;
      } catch (err) {
        result.errors.push(`Failed to ingest deal "${deal.address}": ${err}`);
      }
    }
  }
}

export async function ingestDeals(dealsDir: string): Promise<IngestResult> {
  const result: IngestResult = { created: 0, skipped: 0, errors: [] };
  await ingestLane(path.join(dealsDir, 'SFR_INFILL'), 'SFR_INFILL', result);
  await ingestLane(path.join(dealsDir, 'WHALE_SUBDIVISIONS'), 'WHALE_SUBDIVISION', result);
  return result;
}

if (process.argv[1] && process.argv[1].includes('ingest-deals')) {
  const dealsDir = process.env.DEALS_DIR || path.resolve(process.cwd(), 'data/DEALS');
  ingestDeals(dealsDir)
    .then((r) => {
      console.log(`Deals ingested — created: ${r.created}, skipped: ${r.skipped}`);
      if (r.errors.length) console.error('Errors:', r.errors);
      process.exit(r.errors.length ? 1 : 0);
    })
    .catch((e) => { console.error(e); process.exit(1); });
}
