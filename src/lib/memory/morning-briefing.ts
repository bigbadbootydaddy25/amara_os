import fs from 'fs';
import path from 'path';
import Anthropic from '@anthropic-ai/sdk';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { getSessionContext } from './memory-reader';
import { ANALYSIS_MODEL } from '@/lib/anthropic-client';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export interface BriefingResult {
  date: string;
  briefing: string;
  reportPath: string;
  notePath: string;
}

async function getTopDeals(limit = 5): Promise<string> {
  try {
    const rows = await runQuery<{ address: string; price: unknown; lane: string; matchCount: { low: number }; topScore: { low: number } }>(
      `MATCH (d:Deal)
       OPTIONAL MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d)
       RETURN d.address AS address, d.price AS price, d.lane AS lane,
              count(b) AS matchCount, max(r.score) AS topScore
       ORDER BY topScore DESC, matchCount DESC
       LIMIT $limit`,
      { limit },
    );

    if (!rows.length) return 'No deals in database yet.';

    return rows
      .map(
        (r, i) =>
          `${i + 1}. ${r.address} — $${r.price ?? '?'} [${r.lane}] — ${r.matchCount?.low ?? 0} buyers matched, top score ${r.topScore?.low ?? 0}`,
      )
      .join('\n');
  } catch {
    return 'Neo4j unavailable — deal data not loaded.';
  }
}

async function getTopBuyers(limit = 5): Promise<string> {
  try {
    const rows = await runQuery<{ name: string; matchCount: { low: number }; isWhale: boolean; priceMax: unknown }>(
      `MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d:Deal)
       RETURN b.name AS name, count(r) AS matchCount,
              b.isWhale AS isWhale, b.priceMax AS priceMax
       ORDER BY matchCount DESC
       LIMIT $limit`,
      { limit },
    );

    if (!rows.length) return 'No buyer matches yet.';

    return rows
      .map(
        (r, i) =>
          `${i + 1}. ${r.name}${r.isWhale ? ' 🐋' : ''} — ${r.matchCount?.low ?? 0} matched deals, max $${r.priceMax ?? '?'}`,
      )
      .join('\n');
  } catch {
    return 'Neo4j unavailable.';
  }
}

async function getMarketSignals(): Promise<string> {
  try {
    const rows = await runQuery<{ market: string; signalCount: { low: number } }>(
      `MATCH (d:Deal)-[:LOCATED_IN]->(m:Market)
       MATCH (d)-[:HAS_SIGNAL]->(s:Signal)
       RETURN m.name AS market, count(s) AS signalCount
       ORDER BY signalCount DESC
       LIMIT 5`,
    );

    if (!rows.length) return 'No distress signals detected yet.';

    return rows
      .map((r) => `- ${r.market}: ${r.signalCount?.low ?? 0} distress signals`)
      .join('\n');
  } catch {
    return 'Neo4j unavailable.';
  }
}

function writeFile(content: string, filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf-8');
}

export async function generateMorningBriefing(): Promise<BriefingResult> {
  const date = new Date().toISOString().slice(0, 10);

  const [topDeals, topBuyers, marketSignals, memoryContext] = await Promise.all([
    getTopDeals(),
    getTopBuyers(),
    getMarketSignals(),
    getSessionContext(),
  ]);

  const dataPayload = `
TOP DEALS BY BUYER MATCH SCORE:
${topDeals}

BUYERS MOST LIKELY TO CLOSE:
${topBuyers}

MARKETS WITH DISTRESS SIGNALS:
${marketSignals}

RECENT MEMORY / CONTEXT (last 7 days):
${memoryContext || 'No memory context available yet.'}
`.trim();

  const systemPrompt = `You are AMARA, a British female AI assistant for a real estate investor targeting $100M/year. \
Synthesize the following deal data and memories into a concise morning briefing. \
Be direct, intelligent, and actionable. Lead with the most important deal opportunity. \
Speak as if briefing your principal. Never use markdown, bullet points, or headers — flowing spoken prose only. \
Keep it under 400 words.`;

  let briefing = '';

  if (process.env.ANTHROPIC_API_KEY?.trim()) {
    const stream = anthropic.messages.stream({
      model: ANALYSIS_MODEL,
      max_tokens: 1024,
      system: systemPrompt,
      messages: [{ role: 'user', content: dataPayload }],
    });

    for await (const event of stream) {
      if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
        briefing += event.delta.text;
      }
    }
  } else {
    briefing = `Good morning. AMARA briefing for ${date}.\n\n${dataPayload}`;
  }

  const report = `# MORNING BRIEF — ${date}\n\n${briefing}\n\n---\n\n## Raw Data\n\n### Top Deals\n${topDeals}\n\n### Top Buyers\n${topBuyers}\n\n### Market Signals\n${marketSignals}\n`;
  const obsidianNote = `---\ntags: [briefing, morning, amara]\ndate: ${date}\n---\n\n${report}\n\n[[AMARA]] [[Pipeline]] [[Buyers]]`;

  const reportPath = path.resolve(process.cwd(), `reports/MORNING_BRIEF_${date}.md`);
  const notePath = path.resolve(process.cwd(), `notes/briefings/${date}.md`);

  writeFile(report, reportPath);
  writeFile(obsidianNote, notePath);

  return { date, briefing, reportPath, notePath };
}
