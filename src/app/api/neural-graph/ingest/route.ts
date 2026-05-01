import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { ingestBuyers } from '@/lib/neural-graph/ingest-buyers';
import { ingestDeals } from '@/lib/neural-graph/ingest-deals';
import { ingestSignals } from '@/lib/neural-graph/ingest-signals';
import { buildRelationships } from '@/lib/neural-graph/build-relationships';
import { verifyConnectivity } from '@/lib/neural-graph/neo4j-client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function writeReport(content: string, filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf-8');
}

export async function POST(_request: NextRequest) {
  try {
    await verifyConnectivity();
  } catch {
    return NextResponse.json({ error: 'Neo4j unreachable — check NEO4J_URI and credentials' }, { status: 503 });
  }

  const dataRoot = path.resolve(process.cwd(), 'data');
  const date = new Date().toISOString().slice(0, 10);

  const [buyerResult, dealResult, signalResult] = await Promise.all([
    ingestBuyers(path.join(dataRoot, 'imports/buyers')),
    ingestDeals(path.join(dataRoot, 'DEALS')),
    ingestSignals(),
  ]);

  const relResult = await buildRelationships();

  const allErrors = [
    ...buyerResult.errors,
    ...dealResult.errors,
    ...signalResult.errors,
    ...relResult.errors,
  ];

  const topMatchLines = relResult.topMatches.length
    ? relResult.topMatches
        .map((m, i) => `${i + 1}. **${m.buyerName}** → ${m.dealAddress} (score: ${m.score})`)
        .join('\n')
    : '_No matches found yet — add buyer and deal JSON files to data/_';

  const report = `# NEURAL GRAPH INGEST — ${date}

## Summary
| Item | Count |
|------|-------|
| Buyers created/updated | ${buyerResult.created} |
| Buyers skipped | ${buyerResult.skipped} |
| Deals created/updated | ${dealResult.created} |
| Deals skipped | ${dealResult.skipped} |
| Signal operations | ${signalResult.tagged} |
| Buyer↔Deal matches | ${relResult.matchesBuilt} |

## Top 10 Buyer–Deal Matches
${topMatchLines}

## Errors (${allErrors.length})
${allErrors.length ? allErrors.map((e) => `- ${e}`).join('\n') : '_None_'}
`;

  const obsidianNote = `---
tags: [neo4j, graph, buyers, deals]
date: ${date}
---

${report}

[[AMARA]] [[Buyer Engine]] [[Neural Graph]]
`;

  writeReport(report, path.resolve(process.cwd(), `reports/NEURAL_GRAPH_${date}.md`));
  writeReport(obsidianNote, path.resolve(process.cwd(), `notes/NEURAL_GRAPH_${date}.md`));

  return NextResponse.json({
    date,
    buyers: { created: buyerResult.created, skipped: buyerResult.skipped },
    deals: { created: dealResult.created, skipped: dealResult.skipped },
    signals: { tagged: signalResult.tagged },
    matches: relResult.matchesBuilt,
    topMatches: relResult.topMatches,
    errors: allErrors,
  });
}
