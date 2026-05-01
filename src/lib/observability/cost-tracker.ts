import fs from 'fs';
import path from 'path';

// Claude pricing (USD per 1M tokens, as of 2025)
const COST_PER_1M: Record<string, { input: number; output: number }> = {
  'claude-sonnet-4-6':     { input: 3.0,   output: 15.0  },
  'claude-opus-4-7':       { input: 15.0,  output: 75.0  },
  'claude-haiku-4-5-20251001': { input: 0.8, output: 4.0 },
};

export interface TokenUsage {
  model: string;
  inputTokens: number;
  outputTokens: number;
  agentName?: string;
  market?: string;
  timestamp: string;
}

const usageLog: TokenUsage[] = [];

export function recordUsage(usage: TokenUsage): void {
  usageLog.push(usage);
}

export function estimateCost(model: string, inputTokens: number, outputTokens: number): number {
  const rates = COST_PER_1M[model] ?? { input: 3.0, output: 15.0 };
  return (inputTokens / 1_000_000) * rates.input + (outputTokens / 1_000_000) * rates.output;
}

export function getDailyUsageSummary(): { totalCost: number; byModel: Record<string, number>; totalTokens: number } {
  const today = new Date().toISOString().slice(0, 10);
  const todayUsage = usageLog.filter((u) => u.timestamp.startsWith(today));

  let totalCost = 0;
  let totalTokens = 0;
  const byModel: Record<string, number> = {};

  for (const u of todayUsage) {
    const cost = estimateCost(u.model, u.inputTokens, u.outputTokens);
    totalCost += cost;
    totalTokens += u.inputTokens + u.outputTokens;
    byModel[u.model] = (byModel[u.model] ?? 0) + cost;
  }

  return { totalCost, byModel, totalTokens };
}

export function writeUsageLog(): void {
  const dir = path.resolve(process.cwd(), 'logs');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(
    path.join(dir, `usage_${new Date().toISOString().slice(0, 10)}.json`),
    JSON.stringify(usageLog, null, 2),
    'utf-8',
  );
}
