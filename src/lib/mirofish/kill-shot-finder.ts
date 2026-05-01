import fs from 'fs';
import path from 'path';
import { runQuery } from '@/lib/neural-graph/neo4j-client';

export interface KillShotDeal {
  address: string;
  market: string;
  weight: number;
  distress: number;
  equity: number;
  motivation: number;
  velocity: number;
  price: number | null;
  arv: number | null;
  mao: number | null;
  topBuyer: string | null;
  buyerScore: number;
}

const KILL_SHOT_THRESHOLD = 0.8;

// KILL SHOT QUERY — deals with MiroFish weight > threshold
export async function findKillShots(threshold = KILL_SHOT_THRESHOLD): Promise<KillShotDeal[]> {
  const rows = await runQuery<{
    address: string;
    market: string;
    weight: number;
    distress: number;
    equity: number;
    motivation: number;
    velocity: number;
    price: number | null;
    arv: number | null;
    topBuyer: string | null;
    buyerScore: { low: number } | null;
  }>(
    `MATCH (d:Deal)-[:HAS_SIGNAL]->(s:Signal {type: 'mirofish_prediction'})
     WHERE s.weight >= $threshold
     OPTIONAL MATCH (d)-[:LOCATED_IN]->(m:Market)
     OPTIONAL MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d)
     WITH d, s, m, b, r
     ORDER BY r.score DESC
     WITH d, s, m, collect(b.name)[0] AS topBuyer, collect(r.score)[0] AS buyerScore
     RETURN d.address AS address,
            coalesce(m.name, 'UNKNOWN') AS market,
            s.weight AS weight,
            s.distress AS distress,
            s.equity AS equity,
            s.motivation AS motivation,
            s.velocity AS velocity,
            d.price AS price,
            d.arv AS arv,
            topBuyer,
            buyerScore
     ORDER BY s.weight DESC
     LIMIT 10`,
    { threshold },
  );

  return rows.map((r) => {
    const arv = r.arv ?? null;
    const mao = arv ? Math.round(arv * 0.7) : null; // 70% ARV rule
    return {
      address: r.address,
      market: r.market,
      weight: r.weight,
      distress: r.distress,
      equity: r.equity,
      motivation: r.motivation,
      velocity: r.velocity,
      price: r.price,
      arv,
      mao,
      topBuyer: r.topBuyer ?? null,
      buyerScore: r.buyerScore?.low ?? 0,
    };
  });
}

export function writeKillShotReport(deals: KillShotDeal[]): string {
  const date = new Date().toISOString().slice(0, 10);

  const lines = deals.length
    ? deals.map(
        (d, i) =>
          `### ${i + 1}. ${d.address}\n` +
          `- **Market:** ${d.market}\n` +
          `- **Signal weight:** ${(d.weight * 100).toFixed(1)}%\n` +
          `- **List price:** $${d.price?.toLocaleString() ?? '?'} | **ARV:** $${d.arv?.toLocaleString() ?? '?'} | **MAO (70%):** $${d.mao?.toLocaleString() ?? '?'}\n` +
          `- **Components:** distress=${(d.distress * 100).toFixed(0)}% equity=${(d.equity * 100).toFixed(0)}% motivation=${(d.motivation * 100).toFixed(0)}% velocity=${(d.velocity * 100).toFixed(0)}%\n` +
          `- **Top buyer:** ${d.topBuyer ?? 'None matched'} (score: ${d.buyerScore})`,
      ).join('\n\n')
    : '_No kill-shot deals above threshold yet. Run MiroFish score importer first._';

  const report = `# KILL SHOT DEALS — ${date}\n\nThreshold: ${KILL_SHOT_THRESHOLD * 100}% signal weight\n\n${lines}\n`;
  const obsidian = `---\ntags: [killshot, mirofish, deals]\ndate: ${date}\n---\n\n${report}\n[[AMARA]] [[MiroFish]] [[Deal Engine]]`;

  const rp = path.resolve(process.cwd(), `reports/KILL_SHOT_DEALS_${date}.md`);
  const np = path.resolve(process.cwd(), `notes/kill-shots/${date}.md`);

  fs.mkdirSync(path.dirname(rp), { recursive: true });
  fs.mkdirSync(path.dirname(np), { recursive: true });
  fs.writeFileSync(rp, report, 'utf-8');
  fs.writeFileSync(np, obsidian, 'utf-8');

  return report;
}
