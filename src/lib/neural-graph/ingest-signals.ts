import { runQuery } from './neo4j-client';

export interface SignalResult {
  tagged: number;
  errors: string[];
}

const DISTRESS_KEYWORDS = ['as-is', 'as is', 'investor', 'motivated', 'cash only', 'fixer', 'needs work', 'handyman'];

function descriptionHasSignal(description: string | null): string[] {
  if (!description) return [];
  const lower = description.toLowerCase();
  return DISTRESS_KEYWORDS.filter((kw) => lower.includes(kw));
}

export async function ingestSignals(): Promise<SignalResult> {
  const result: SignalResult = { tagged: 0, errors: [] };

  // 1. DOM > 90 → distress signal
  try {
    await runQuery(
      `MATCH (d:Deal) WHERE d.dom > 90
       MERGE (s:Signal {type: 'DISTRESS', reason: 'DOM_OVER_90'})
       MERGE (d)-[:HAS_SIGNAL]->(s)`,
    );
    result.tagged++;
  } catch (err) {
    result.errors.push(`DOM signal error: ${err}`);
  }

  // 2. Keyword signals from description
  for (const keyword of DISTRESS_KEYWORDS) {
    try {
      await runQuery(
        `MATCH (d:Deal)
         WHERE d.description IS NOT NULL
           AND toLower(d.description) CONTAINS $kw
         MERGE (s:Signal {type: 'DISTRESS', reason: $reason})
         MERGE (d)-[:HAS_SIGNAL]->(s)`,
        { kw: keyword, reason: `KEYWORD_${keyword.toUpperCase().replace(/[^A-Z0-9]/g, '_')}` },
      );
      result.tagged++;
    } catch (err) {
      result.errors.push(`Keyword signal "${keyword}" error: ${err}`);
    }
  }

  return result;
}

export { descriptionHasSignal };

if (process.argv[1] && process.argv[1].includes('ingest-signals')) {
  ingestSignals()
    .then((r) => {
      console.log(`Signals applied — operations: ${r.tagged}`);
      if (r.errors.length) console.error('Errors:', r.errors);
      process.exit(r.errors.length ? 1 : 0);
    })
    .catch((e) => { console.error(e); process.exit(1); });
}
