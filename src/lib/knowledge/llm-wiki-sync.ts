import fs from 'fs';
import path from 'path';
import Anthropic from '@anthropic-ai/sdk';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { gainIQ } from '@/lib/iq/iq-engine';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const WIKI_DIR = path.resolve(process.cwd(), 'data/imports/llm_wiki');
const PROCESSED_DIR = path.join(WIKI_DIR, 'processed');

export interface WikiSyncResult {
  patternsExtracted: number;
  iqGained: number;
  errors: string[];
}

async function extractReasoningPatterns(content: string, filename: string): Promise<string> {
  if (!process.env.ANTHROPIC_API_KEY?.trim()) return '';

  let patterns = '';
  const stream = anthropic.messages.stream({
    model: 'claude-sonnet-4-6',
    max_tokens: 2048,
    system: 'You are extracting reasoning patterns from AI/LLM research for AMARA\'s self-improvement engine. Extract: decision-making heuristics, chain-of-thought patterns, self-evaluation techniques, and any patterns applicable to real estate deal analysis and buyer psychology.',
    messages: [{ role: 'user', content: `Source: ${filename}\n\n${content.slice(0, 10000)}` }],
  });

  for await (const event of stream) {
    if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
      patterns += event.delta.text;
    }
  }
  return patterns;
}

export async function syncLlmWiki(): Promise<WikiSyncResult> {
  const result: WikiSyncResult = { patternsExtracted: 0, iqGained: 0, errors: [] };

  if (!fs.existsSync(WIKI_DIR)) {
    fs.mkdirSync(WIKI_DIR, { recursive: true });
    return result;
  }

  const files = fs.readdirSync(WIKI_DIR).filter((f) => f.endsWith('.txt') || f.endsWith('.md') || f.endsWith('.json'));
  fs.mkdirSync(PROCESSED_DIR, { recursive: true });

  for (const file of files) {
    const filePath = path.join(WIKI_DIR, file);
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const patterns = await extractReasoningPatterns(content, file);

      if (patterns) {
        // Store as ReasoningPattern in Neo4j
        await runQuery(
          `MERGE (rp:ReasoningPattern {filename: $filename})
           SET rp.patterns = $patterns, rp.syncedAt = datetime(), rp.source = 'llm_wiki'`,
          { filename: file, patterns },
        ).catch(() => {});

        result.patternsExtracted++;

        // IQ gain: 4–8 per wiki file
        const iqGain = Math.min(8, Math.max(4, Math.ceil(patterns.length / 300)));
        await gainIQ(iqGain, `Karpathy LLM Wiki sync: ${file}`).catch(() => {});
        result.iqGained += iqGain;
      }

      fs.renameSync(filePath, path.join(PROCESSED_DIR, file));
    } catch (err) {
      result.errors.push(`${file}: ${err}`);
    }
  }

  return result;
}

// Inject wiki patterns into chain rewriter context
export async function getReasoningPatternContext(): Promise<string> {
  try {
    const rows = await runQuery<{ patterns: string }>(
      `MATCH (rp:ReasoningPattern) RETURN rp.patterns AS patterns ORDER BY rp.syncedAt DESC LIMIT 3`,
    );
    return rows.map((r) => r.patterns).join('\n---\n').slice(0, 3000);
  } catch {
    return '';
  }
}
