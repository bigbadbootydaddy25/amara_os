import fs from 'fs';
import path from 'path';
import Anthropic from '@anthropic-ai/sdk';
import { ANALYSIS_MODEL } from '@/lib/anthropic-client';
import { readProgram, programToSystemContext } from './program-reader';
import type { ChainScore } from './performance-evaluator';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// SACRED — never rewrite these files
const PROTECTED_FILES = ['prepare.ts', 'neo4j-client.ts', 'ingest-buyers.ts', 'ingest-deals.ts'];

const CHAIN_FILE_MAP: Record<string, string> = {
  DealDiscovery:       'src/lib/pipeline/deal-discovery-chain.ts',
  BuyerMatch:          'src/lib/pipeline/buyer-match-chain.ts',
  DailyPipeline:       'src/lib/pipeline/daily-pipeline-chain.ts',
  BuyerAgent:          'src/lib/hermes/buyer-agent.ts',
  SfrDomAgent:         'src/lib/hermes/sfr-dom-agent.ts',
  LandSubdivisionAgent:'src/lib/hermes/land-subdivision-agent.ts',
};

export interface RewriteResult {
  chainName: string;
  attempted: boolean;
  candidatePath: string | null;
  reason: string;
}

export async function rewriteChain(chain: ChainScore, traceContext: string): Promise<RewriteResult> {
  const relPath = CHAIN_FILE_MAP[chain.chainName];
  if (!relPath) return { chainName: chain.chainName, attempted: false, candidatePath: null, reason: 'No file mapping' };

  if (PROTECTED_FILES.some((f) => relPath.endsWith(f))) {
    return { chainName: chain.chainName, attempted: false, candidatePath: null, reason: 'Protected file — skipped' };
  }

  const filePath = path.resolve(process.cwd(), relPath);
  if (!fs.existsSync(filePath)) return { chainName: chain.chainName, attempted: false, candidatePath: null, reason: 'File not found' };

  const currentCode = fs.readFileSync(filePath, 'utf-8');
  const program = readProgram();
  const programContext = programToSystemContext(program);

  const prompt = `You are AMARA's self-improvement engine. Your task is to rewrite the following TypeScript reasoning chain to improve its deal conversion rate and buyer match accuracy.

CURRENT PERFORMANCE:
- Conversion rate: ${(chain.conversionRate * 100).toFixed(0)}%
- Match accuracy: ${(chain.matchAccuracy * 100).toFixed(0)}%
- Composite score: ${chain.composite} (threshold: 0.6)

RECENT TRACE CONTEXT:
${traceContext || 'No traces available — make conservative improvements'}

${programContext}

CURRENT CODE (${chain.chainName}):
\`\`\`typescript
${currentCode}
\`\`\`

RULES:
- Return ONLY the improved TypeScript code — no explanation, no markdown fences
- Do NOT change imports or function signatures that other modules depend on
- Do NOT touch database schema or query structure — only improve prompts and logic
- Improvements should be targeted: better prompts, smarter filtering, improved scoring weights
- Keep the file under 300 lines
- If no meaningful improvement is possible, return the original code unchanged`;

  let improvedCode = '';
  try {
    const stream = anthropic.messages.stream({
      model: ANALYSIS_MODEL,
      max_tokens: 8192,
      system: 'You are a senior TypeScript developer specializing in LangChain AI agents for real estate deal analysis. Return only valid TypeScript code.',
      messages: [{ role: 'user', content: prompt }],
    });

    for await (const event of stream) {
      if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
        improvedCode += event.delta.text;
      }
    }
  } catch (err) {
    return { chainName: chain.chainName, attempted: true, candidatePath: null, reason: `Claude API error: ${err}` };
  }

  if (!improvedCode.trim() || improvedCode.trim() === currentCode.trim()) {
    return { chainName: chain.chainName, attempted: true, candidatePath: null, reason: 'No meaningful improvement generated' };
  }

  // Write candidate — never overwrite the live file directly
  const candidatePath = filePath.replace('.ts', `_candidate_${Date.now()}.ts`);
  fs.writeFileSync(candidatePath, improvedCode, 'utf-8');

  return { chainName: chain.chainName, attempted: true, candidatePath, reason: 'Candidate generated' };
}
