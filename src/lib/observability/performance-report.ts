import fs from 'fs';
import path from 'path';
import { getDailyUsageSummary } from './cost-tracker';

interface LocalTrace {
  agentName: string;
  market?: string;
  success: boolean;
  durationMs: number;
  error?: string;
  timestamp: string;
}

function loadLocalTraces(days = 7): LocalTrace[] {
  const dir = path.resolve(process.cwd(), 'logs/langfuse_local');
  if (!fs.existsSync(dir)) return [];

  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const traces: LocalTrace[] = [];

  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    try {
      const trace = JSON.parse(
        fs.readFileSync(path.join(dir, file), 'utf-8'),
      ) as LocalTrace;
      if (new Date(trace.timestamp).getTime() > cutoff) {
        traces.push(trace);
      }
    } catch {
      // skip
    }
  }
  return traces;
}

export function generatePerformanceReport(): string {
  const date = new Date().toISOString().slice(0, 10);
  const traces = loadLocalTraces(7);
  const usage = getDailyUsageSummary();

  if (traces.length === 0) {
    return `# PERFORMANCE REPORT — ${date}\n\nNo trace data yet. Run Hermes agents to populate.\n`;
  }

  // Agent speed ranking
  const agentDurations: Record<string, number[]> = {};
  const agentFailures: Record<string, number> = {};
  const marketFailures: Record<string, number> = {};

  for (const t of traces) {
    if (!agentDurations[t.agentName]) agentDurations[t.agentName] = [];
    agentDurations[t.agentName].push(t.durationMs);
    if (!t.success) {
      agentFailures[t.agentName] = (agentFailures[t.agentName] ?? 0) + 1;
      if (t.market) marketFailures[t.market] = (marketFailures[t.market] ?? 0) + 1;
    }
  }

  const avgDurations = Object.entries(agentDurations)
    .map(([name, durations]) => ({
      name,
      avg: Math.round(durations.reduce((a, b) => a + b, 0) / durations.length),
      count: durations.length,
    }))
    .sort((a, b) => b.avg - a.avg);

  const topFailMarkets = Object.entries(marketFailures)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const report = `# PERFORMANCE REPORT — ${date}

## Token / Cost (Today)
| Metric | Value |
|--------|-------|
| Total tokens | ${usage.totalTokens.toLocaleString()} |
| Estimated cost | $${usage.totalCost.toFixed(4)} |
${Object.entries(usage.byModel).map(([m, c]) => `| ${m} | $${c.toFixed(4)} |`).join('\n')}

## Agent Speed (7-day avg)
| Agent | Avg Duration | Run Count |
|-------|-------------|-----------|
${avgDurations.map((a) => `| ${a.name} | ${a.avg}ms | ${a.count} |`).join('\n')}

## Markets with Most Failures (7 days)
${topFailMarkets.length ? topFailMarkets.map(([m, n]) => `- ${m}: ${n} failures`).join('\n') : '_No failures_'}

## Agent Failure Counts (7 days)
${Object.entries(agentFailures).length
    ? Object.entries(agentFailures).map(([a, n]) => `- ${a}: ${n} failures`).join('\n')
    : '_No failures_'}

## Total Traces (7 days): ${traces.length}
`;

  const reportPath = path.resolve(process.cwd(), `reports/PERFORMANCE_${date}.md`);
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, report, 'utf-8');

  return report;
}
