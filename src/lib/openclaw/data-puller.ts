import fs from 'fs';
import path from 'path';
import { scrapeZillowDom } from './browser-automator';
import { ingestBuyers } from '@/lib/neural-graph/ingest-buyers';
import { ingestDeals } from '@/lib/neural-graph/ingest-deals';

export interface PullResult {
  propStreamFiles: number;
  zillowDomHits: number;
  countyRecords: number;
  errors: string[];
}

// Watch imports/ for new PropStream CSV exports and move processed files
export async function pullPropStreamData(): Promise<{ filesFound: number; errors: string[] }> {
  const importDir = path.resolve(process.cwd(), 'data/imports');
  const result = { filesFound: 0, errors: [] as string[] };

  if (!fs.existsSync(importDir)) return result;

  const csvFiles = fs.readdirSync(importDir).filter((f) => f.endsWith('.csv'));

  for (const file of csvFiles) {
    const filePath = path.join(importDir, file);
    try {
      // Convert PropStream CSV → JSON in buyers/ or DEALS/ based on filename
      const raw = fs.readFileSync(filePath, 'utf-8');
      const lines = raw.split('\n').filter(Boolean);
      const headers = lines[0].split(',').map((h) => h.trim().replace(/"/g, ''));

      const records = lines.slice(1).map((line) => {
        const values = line.split(',').map((v) => v.trim().replace(/"/g, ''));
        return Object.fromEntries(headers.map((h, i) => [h, values[i] ?? '']));
      });

      const destDir = file.toLowerCase().includes('buyer')
        ? path.join(importDir, 'buyers')
        : path.join(process.cwd(), 'data/DEALS/SFR_INFILL');

      fs.mkdirSync(destDir, { recursive: true });
      const jsonPath = path.join(destDir, file.replace('.csv', '.json'));
      fs.writeFileSync(jsonPath, JSON.stringify(records, null, 2), 'utf-8');

      // Archive the original CSV
      const archiveDir = path.join(importDir, 'processed');
      fs.mkdirSync(archiveDir, { recursive: true });
      fs.renameSync(filePath, path.join(archiveDir, file));

      result.filesFound++;
    } catch (err) {
      result.errors.push(`PropStream file ${file}: ${err}`);
    }
  }

  return result;
}

export async function runFullDataPull(markets: string[]): Promise<PullResult> {
  const result: PullResult = { propStreamFiles: 0, zillowDomHits: 0, countyRecords: 0, errors: [] };

  // 1. PropStream CSVs
  const psResult = await pullPropStreamData();
  result.propStreamFiles = psResult.filesFound;
  result.errors.push(...psResult.errors);

  // If new PropStream data arrived, re-ingest
  if (psResult.filesFound > 0) {
    const buyerResult = await ingestBuyers(path.resolve(process.cwd(), 'data/imports/buyers'));
    const dealResult = await ingestDeals(path.resolve(process.cwd(), 'data/DEALS'));
    result.errors.push(...buyerResult.errors, ...dealResult.errors);
  }

  // 2. Zillow DOM scraping (stubs — wire Playwright session per market)
  for (const market of markets.slice(0, 5)) { // cap at 5 to avoid rate limits
    const hits = await scrapeZillowDom(market).catch((err) => {
      result.errors.push(`Zillow scrape ${market}: ${err}`);
      return [];
    });
    result.zillowDomHits += hits.length;
  }

  return result;
}
