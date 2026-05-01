import fs from 'fs';
import path from 'path';
import { BuyerAgent } from './buyer-agent';
import { SfrDomAgent } from './sfr-dom-agent';
import { LandSubdivisionAgent } from './land-subdivision-agent';
import { OsintAgent } from './osint-agent';
import type { AgentConfig, AgentRunResult } from './agent-base';

export interface MarketConfig {
  name: string;
  strategies?: string[];
}

export interface OrchestratorResult {
  date: string;
  marketsRun: number;
  marketsSucceeded: number;
  marketsFailed: number;
  sourceNotAccessible: number;
  results: AgentRunResult[];
  errors: string[];
}

function loadMarkets(marketsDir: string): MarketConfig[] {
  if (!fs.existsSync(marketsDir)) return [];

  const markets: MarketConfig[] = [];
  const files = fs.readdirSync(marketsDir).filter((f) => f.endsWith('.json'));

  for (const file of files) {
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(marketsDir, file), 'utf-8')) as unknown;
      if (Array.isArray(raw)) {
        markets.push(...(raw as MarketConfig[]));
      } else if (typeof raw === 'object' && raw !== null) {
        markets.push(raw as MarketConfig);
      }
    } catch {
      // skip malformed market files
    }
  }

  return markets;
}

async function runMarketAgents(market: string): Promise<AgentRunResult[]> {
  const configs: AgentConfig[] = [
    { market, strategy: 'BUYER_RECON', dataTarget: 'buyers' },
    { market, strategy: 'SFR_90_DOM', dataTarget: 'sfr_dom' },
    { market, strategy: 'LAND_SUBDIVISION', dataTarget: 'land' },
    { market, strategy: 'OSINT', dataTarget: '' },
  ];

  const agents = [
    new BuyerAgent(configs[0]),
    new SfrDomAgent(configs[1]),
    new LandSubdivisionAgent(configs[2]),
    new OsintAgent(configs[3]),
  ];

  // Run all four agents for this market in parallel
  return Promise.all(agents.map((a) => a.run().catch((err): AgentRunResult => ({
    market,
    strategy: 'UNKNOWN',
    status: 'FAILED',
    findings: [],
    errors: [String(err)],
  }))));
}

function writeReport(content: string, filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf-8');
}

export async function runHermes(marketsDir?: string): Promise<OrchestratorResult> {
  const date = new Date().toISOString().slice(0, 10);
  const dir = marketsDir ?? path.resolve(process.cwd(), 'data/MARKETS');
  const markets = loadMarkets(dir);

  const orchestratorResult: OrchestratorResult = {
    date,
    marketsRun: markets.length,
    marketsSucceeded: 0,
    marketsFailed: 0,
    sourceNotAccessible: 0,
    results: [],
    errors: [],
  };

  if (markets.length === 0) {
    orchestratorResult.errors.push(`No market JSON files found in ${dir}`);
    return orchestratorResult;
  }

  // Run all markets in parallel (Promise.all per spec)
  const allResults = await Promise.all(
    markets.map((m) =>
      runMarketAgents(m.name).catch((err): AgentRunResult[] => [
        {
          market: m.name,
          strategy: 'ORCHESTRATOR',
          status: 'FAILED',
          findings: [],
          errors: [String(err)],
        },
      ]),
    ),
  );

  for (const marketResults of allResults) {
    orchestratorResult.results.push(...marketResults);

    for (const r of marketResults) {
      if (r.status === 'FAILED') orchestratorResult.marketsFailed++;
      else orchestratorResult.marketsSucceeded++;

      const notAccessible = r.findings.some((f) => f.type === 'SOURCE_NOT_ACCESSIBLE');
      if (notAccessible) orchestratorResult.sourceNotAccessible++;

      // Per-market report
      const marketReport = `# HERMES — ${r.market} — ${date}\n\nStrategy: ${r.strategy}\nStatus: ${r.status}\n\n## Findings\n${r.findings.map((f) => `### ${f.type}\n${f.summary}`).join('\n\n')}\n\n## Errors\n${r.errors.length ? r.errors.join('\n') : '_None_'}\n`;
      writeReport(marketReport, path.resolve(process.cwd(), `reports/HERMES_${r.market}_${date}.md`));

      // Obsidian note
      const note = `---\ntags: [hermes, market, ${r.market.toLowerCase()}]\ndate: ${date}\n---\n\n${marketReport}\n[[AMARA]] [[Hermes Agents]]`;
      writeReport(note, path.resolve(process.cwd(), `notes/hermes/${r.market}_${date}.md`));
    }
  }

  // Master report
  const successRate = orchestratorResult.marketsRun > 0
    ? Math.round((orchestratorResult.marketsSucceeded / orchestratorResult.marketsRun) * 100)
    : 0;

  const masterReport = `# HERMES MASTER REPORT — ${date}

## Summary
| Metric | Value |
|--------|-------|
| Markets run | ${orchestratorResult.marketsRun} |
| Succeeded | ${orchestratorResult.marketsSucceeded} |
| Failed | ${orchestratorResult.marketsFailed} |
| Source not accessible | ${orchestratorResult.sourceNotAccessible} |
| Success rate | ${successRate}% |

## Markets — SOURCE_NOT_ACCESSIBLE
${orchestratorResult.results
  .filter((r) => r.findings.some((f) => f.type === 'SOURCE_NOT_ACCESSIBLE'))
  .map((r) => `- ${r.market}`)
  .join('\n') || '_None_'}

## Top Findings
${orchestratorResult.results
  .flatMap((r) => r.findings)
  .filter((f) => f.type !== 'SOURCE_NOT_ACCESSIBLE' && f.type !== 'NO_BUYERS' && f.type !== 'NO_SFR_DOM' && f.type !== 'NO_LAND_DEALS')
  .slice(0, 20)
  .map((f) => `- **${f.type}**: ${f.summary.slice(0, 200)}`)
  .join('\n') || '_No substantive findings yet — load deal and buyer data_'}
`;

  writeReport(masterReport, path.resolve(process.cwd(), `reports/HERMES_MASTER_${date}.md`));

  return orchestratorResult;
}
