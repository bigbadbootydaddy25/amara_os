import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { fetchMiroFishScores, mockMiroFishScore, MiroFishScore } from './mirofish-client';
import { gainIQ } from '@/lib/iq/iq-engine';

export interface ImportResult {
  scored: number;
  fromApi: number;
  fromMock: number;
  errors: string[];
}

export async function importMiroFishScores(): Promise<ImportResult> {
  const result: ImportResult = { scored: 0, fromApi: 0, fromMock: 0, errors: [] };

  // Load all deals from Neo4j
  let deals: Array<{ address: string; dom: number | null; price: number | null; arv: number | null; description: string | null }> = [];
  try {
    deals = await runQuery<{ address: string; dom: { low: number } | null; price: number | null; arv: number | null; description: string | null }>(
      `MATCH (d:Deal) RETURN d.address AS address, d.dom AS dom, d.price AS price, d.arv AS arv, d.description AS description`,
    ).then((rows) =>
      rows.map((r) => ({
        address: r.address,
        dom: r.dom?.low ?? null,
        price: r.price ?? null,
        arv: r.arv ?? null,
        description: r.description ?? null,
      })),
    );
  } catch (err) {
    result.errors.push(`Neo4j query failed: ${err}`);
    return result;
  }

  // Try live API first; fall back to mock
  const addresses = deals.map((d) => d.address);
  const apiScores = await fetchMiroFishScores(addresses);
  const scoreMap = new Map<string, MiroFishScore>();

  if (apiScores) {
    for (const s of apiScores) scoreMap.set(s.address, s);
    result.fromApi = apiScores.length;
  }

  // Mock score anything not covered by API
  for (const deal of deals) {
    if (!scoreMap.has(deal.address)) {
      scoreMap.set(deal.address, mockMiroFishScore(deal));
      result.fromMock++;
    }
  }

  // Write Signal nodes to Neo4j
  for (const [, score] of scoreMap) {
    try {
      await runQuery(
        `MATCH (d:Deal {address: $address})
         MERGE (s:Signal {type: 'mirofish_prediction', address: $address})
         SET s.weight        = $weight,
             s.distress      = $distress,
             s.equity        = $equity,
             s.motivation    = $motivation,
             s.velocity      = $velocity,
             s.source        = $source,
             s.updatedAt     = datetime()
         MERGE (d)-[:HAS_SIGNAL]->(s)`,
        {
          address: score.address,
          weight: score.weight,
          distress: score.components.distress_score,
          equity: score.components.equity_score,
          motivation: score.components.motivation_score,
          velocity: score.components.market_velocity,
          source: score.source,
        },
      );
      result.scored++;
    } catch (err) {
      result.errors.push(`Signal write failed for "${score.address}": ${err}`);
    }
  }

  // Gain IQ for model update
  if (result.scored > 0) {
    await gainIQ(Math.min(7, Math.ceil(result.scored / 2)), 'MiroFish model updated signal weights').catch(() => {});
  }

  return result;
}
