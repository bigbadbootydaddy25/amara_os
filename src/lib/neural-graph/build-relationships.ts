import { runQuery } from './neo4j-client';

export interface MatchResult {
  buyerName: string;
  dealAddress: string;
  score: number;
}

export interface RelationshipResult {
  matchesBuilt: number;
  topMatches: MatchResult[];
  errors: string[];
}

/**
 * Score a Buyer↔Deal pair (0–100).
 * Criteria: price range match, zip match, property type match, repeat buyer bonus.
 */
async function scoreAllPairs(): Promise<void> {
  // Clear stale scores
  await runQuery(`MATCH ()-[r:LIKELY_TO_BUY]->() DELETE r`);

  // Build scores in Cypher — fast graph-native calculation
  await runQuery(
    `MATCH (b:Buyer), (d:Deal)
     WITH b, d,
       // price range match (40 pts)
       CASE
         WHEN b.priceMin IS NOT NULL AND b.priceMax IS NOT NULL
              AND d.price >= b.priceMin AND d.price <= b.priceMax THEN 40
         WHEN b.priceMax IS NOT NULL AND d.price <= b.priceMax THEN 20
         ELSE 0
       END AS priceScore,
       // zip match (30 pts)
       CASE
         WHEN b.zipCodes IS NOT NULL AND d.zip IS NOT NULL
              AND d.zip IN b.zipCodes THEN 30
         ELSE 0
       END AS zipScore,
       // repeat buyer bonus (20 pts)
       CASE WHEN b.isRepeat = true THEN 20 ELSE 0 END AS repeatScore,
       // whale × land match (10 pts)
       CASE
         WHEN b.isWhale = true AND d.propertyType = 'LAND' THEN 10
         ELSE 0
       END AS whaleScore
     WITH b, d, (priceScore + zipScore + repeatScore + whaleScore) AS score
     WHERE score > 0
     MERGE (b)-[r:LIKELY_TO_BUY]->(d)
     SET r.score = score`,
  );
}

export async function buildRelationships(): Promise<RelationshipResult> {
  const result: RelationshipResult = { matchesBuilt: 0, topMatches: [], errors: [] };

  try {
    await scoreAllPairs();
  } catch (err) {
    result.errors.push(`Score calculation failed: ${err}`);
    return result;
  }

  // Count matches built
  try {
    const counts = await runQuery<{ total: { low: number } }>(
      `MATCH ()-[r:LIKELY_TO_BUY]->() RETURN count(r) AS total`,
    );
    result.matchesBuilt = counts[0]?.total?.low ?? 0;
  } catch (err) {
    result.errors.push(`Count query failed: ${err}`);
  }

  // Top 10 matches
  try {
    const rows = await runQuery<{ buyer: string; deal: string; score: { low: number } }>(
      `MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d:Deal)
       RETURN b.name AS buyer, d.address AS deal, r.score AS score
       ORDER BY r.score DESC
       LIMIT 10`,
    );
    result.topMatches = rows.map((row) => ({
      buyerName: row.buyer,
      dealAddress: row.deal,
      score: row.score?.low ?? 0,
    }));
  } catch (err) {
    result.errors.push(`Top matches query failed: ${err}`);
  }

  return result;
}

if (process.argv[1] && process.argv[1].includes('build-relationships')) {
  buildRelationships()
    .then((r) => {
      console.log(`Relationships built — matches: ${r.matchesBuilt}`);
      console.log('Top matches:', r.topMatches);
      if (r.errors.length) console.error('Errors:', r.errors);
      process.exit(r.errors.length ? 1 : 0);
    })
    .catch((e) => { console.error(e); process.exit(1); });
}
