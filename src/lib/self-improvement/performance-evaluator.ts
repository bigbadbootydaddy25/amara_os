import fs from 'fs';
import path from 'path';

export interface ChainScore {
  chainName: string;
  conversionRate: number;   // 0–1
  matchAccuracy: number;    // 0–1
  signalAccuracy: number;   // 0–1
  speedScore: number;       // 0–1 (1 = fast)
  composite: number;        // weighted aggregate
  belowThreshold: boolean;  // composite < 0.6
  traceCount: number;
}

interface LocalTrace {
  agentName: string;
  success: boolean;
  durationMs: number;
  timestamp: string;
}

function loadTraces(days = 7): LocalTrace[] {
  const dir = path.resolve(process.cwd(), 'logs/langfuse_local');
  if (!fs.existsSync(dir)) return [];

  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const traces: LocalTrace[] = [];

  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    try {
      const t = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf-8')) as LocalTrace;
      if (new Date(t.timestamp).getTime() > cutoff) traces.push(t);
    } catch { /* skip */ }
  }
  return traces;
}

const CHAIN_NAMES = ['DealDiscovery', 'BuyerMatch', 'DailyPipeline', 'BuyerAgent', 'SfrDomAgent', 'LandSubdivisionAgent'];

export function evaluateChains(): ChainScore[] {
  const traces = loadTraces(7);
  const results: ChainScore[] = [];

  for (const chainName of CHAIN_NAMES) {
    const chainTraces = traces.filter((t) => t.agentName?.includes(chainName));
    if (chainTraces.length === 0) {
      results.push({ chainName, conversionRate: 0.5, matchAccuracy: 0.5, signalAccuracy: 0.5, speedScore: 0.5, composite: 0.5, belowThreshold: false, traceCount: 0 });
      continue;
    }

    const successRate = chainTraces.filter((t) => t.success).length / chainTraces.length;
    const avgDuration = chainTraces.reduce((s, t) => s + t.durationMs, 0) / chainTraces.length;
    // Speed score: 0 = >60s, 1 = <5s
    const speedScore = Math.max(0, 1 - avgDuration / 60_000);

    // Without deal outcome data, use success rate as proxy for all quality metrics
    const composite = successRate * 0.5 + successRate * 0.3 + successRate * 0.15 + speedScore * 0.05;

    results.push({
      chainName,
      conversionRate: successRate,
      matchAccuracy: successRate,
      signalAccuracy: successRate,
      speedScore,
      composite: +composite.toFixed(3),
      belowThreshold: composite < 0.6,
      traceCount: chainTraces.length,
    });
  }

  return results;
}
