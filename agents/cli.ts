import { runBuyBoxBuilder } from './buy-box-builder';
import { runBuyerFinder } from './buyer-finder';
import { runDistressScout } from './distress-scout';
import { ingestRecords } from './ingest/records-csv';
import { ingestResearch } from './ingest/research-csv';
import { openDb } from './lib/db';
import { loadSources, syncSources } from './lib/sources';
import { runMatcher } from './matcher';
import { runMorningBrief } from './morning-brief';

// Usage: npm run amara -- <job> [--as-of YYYY-MM-DD]
const jobs = ['sync-sources', 'ingest-records', 'ingest-research', 'buyer-finder', 'buy-box', 'distress-scout', 'matcher', 'morning-brief', 'weekly', 'daily'] as const;
const job = process.argv[2];
const i = process.argv.indexOf('--as-of');
const asOf = i > 0 ? process.argv[i + 1] : undefined;

if (!jobs.includes(job as (typeof jobs)[number])) {
  console.error(`usage: npm run amara -- <${jobs.join('|')}> [--as-of YYYY-MM-DD]`);
  process.exit(2);
}
const db = openDb();
const src = loadSources();
syncSources(db, src);
const show = (n: string, r: unknown) => console.log(n, JSON.stringify(r));
const steps: Record<string, () => unknown> = {
  'sync-sources': () => ({ sources: src.sources.length }),
  'ingest-records': () => ingestRecords(db, { asOf, src }),
  'ingest-research': () => ingestResearch(db, { asOf }),
  'buyer-finder': () => runBuyerFinder(db, { asOf, src }),
  'buy-box': () => runBuyBoxBuilder(db, { asOf }),
  'distress-scout': () => runDistressScout(db, { asOf, src }),
  matcher: () => runMatcher(db, { asOf, src }),
  'morning-brief': () => runMorningBrief(db, { asOf, src }),
};
const plan: Record<string, string[]> = {
  weekly: ['ingest-records', 'buyer-finder', 'buy-box'],
  daily: ['ingest-research', 'ingest-records', 'distress-scout', 'matcher', 'morning-brief'],
};
for (const s of plan[job] ?? [job]) show(s, steps[s]());
