import fs from 'fs';
import path from 'path';
import Anthropic from '@anthropic-ai/sdk';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { gainIQ } from '@/lib/iq/iq-engine';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const KNOWLEDGE_DIR = path.resolve(process.cwd(), 'data/imports/knowledge');
const PROCESSED_DIR = path.join(KNOWLEDGE_DIR, 'processed');

export interface KnowledgeIngestResult {
  filesProcessed: number;
  iqGained: number;
  errors: string[];
}

async function extractInsights(content: string, filename: string): Promise<string> {
  if (!process.env.ANTHROPIC_API_KEY?.trim()) return content.slice(0, 500);

  let insights = '';
  const stream = anthropic.messages.stream({
    model: 'claude-sonnet-4-6',
    max_tokens: 2048,
    system: 'You are AMARA\'s knowledge extraction engine. Extract the most actionable real estate investment insights from this document. Focus on: market signals, deal strategies, buyer behavior, pricing patterns. Be concise — bullet points, no fluff.',
    messages: [{ role: 'user', content: `File: ${filename}\n\n${content.slice(0, 12000)}` }],
  });

  for await (const event of stream) {
    if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
      insights += event.delta.text;
    }
  }
  return insights;
}

export async function watchAndIngest(): Promise<KnowledgeIngestResult> {
  const result: KnowledgeIngestResult = { filesProcessed: 0, iqGained: 0, errors: [] };

  if (!fs.existsSync(KNOWLEDGE_DIR)) {
    fs.mkdirSync(KNOWLEDGE_DIR, { recursive: true });
    return result;
  }

  const files = fs.readdirSync(KNOWLEDGE_DIR).filter((f) =>
    f.endsWith('.txt') || f.endsWith('.md') || f.endsWith('.pdf') || f.endsWith('.json'),
  );

  fs.mkdirSync(PROCESSED_DIR, { recursive: true });

  for (const file of files) {
    const filePath = path.join(KNOWLEDGE_DIR, file);
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const insights = await extractInsights(content, file);

      // Write to Neo4j as KnowledgeNode
      await runQuery(
        `MERGE (k:KnowledgeNode {filename: $filename})
         SET k.insights = $insights, k.ingestedAt = datetime(), k.source = 'notebooklm'`,
        { filename: file, insights },
      ).catch(() => {});

      // Write Obsidian note
      const notePath = path.resolve(process.cwd(), `notes/knowledge/${file.replace(/\.[^.]+$/, '.md')}`);
      fs.mkdirSync(path.dirname(notePath), { recursive: true });
      fs.writeFileSync(notePath, `---\ntags: [knowledge, notebooklm]\nsource: ${file}\n---\n\n${insights}\n\n[[AMARA]]`, 'utf-8');

      // IQ gain: 2–5 based on content depth
      const iqGain = Math.min(5, Math.max(2, Math.ceil(insights.length / 500)));
      await gainIQ(iqGain, `NotebookLM knowledge ingested: ${file}`).catch(() => {});
      result.iqGained += iqGain;
      result.filesProcessed++;

      // Archive
      fs.renameSync(filePath, path.join(PROCESSED_DIR, file));
    } catch (err) {
      result.errors.push(`${file}: ${err}`);
    }
  }

  return result;
}
