import fs from 'fs';
import path from 'path';
import { evaluateChains } from './performance-evaluator';
import { rewriteChain } from './chain-rewriter';
import { testAndDeploy } from './improvement-tester';
import { gainIQ } from '@/lib/iq/iq-engine';
import { writeMemory } from '@/lib/memory/memory-writer';

export interface ImprovementCycleResult {
  date: string;
  chainsEvaluated: number;
  chainsRewritten: number;
  chainsDeployed: number;
  chainsDiscarded: number;
  iqGained: number;
  consecutiveFailures: number;
  report: string;
}

// Track consecutive failures across calls
let consecutiveFailures = 0;
const MAX_CONSECUTIVE_FAILURES = 3;

export async function runSelfImprovementCycle(): Promise<ImprovementCycleResult> {
  const date = new Date().toISOString().slice(0, 10);
  let totalIqGained = 0;
  let chainsRewritten = 0;
  let chainsDeployed = 0;
  let chainsDiscarded = 0;

  // Safety: only run between midnight and 5am
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 23) {
    const msg = `Self-improvement skipped — only runs midnight–5am (current hour: ${hour})`;
    return { date, chainsEvaluated: 0, chainsRewritten: 0, chainsDeployed: 0, chainsDiscarded: 0, iqGained: 0, consecutiveFailures, report: msg };
  }

  if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
    const msg = `Self-improvement PAUSED — ${consecutiveFailures} consecutive failures. Scott should review.`;
    fs.appendFileSync(path.resolve(process.cwd(), 'reports/SELF_IMPROVEMENT_LOG.md'), `\n## ${date}\n${msg}\n`, 'utf-8');
    return { date, chainsEvaluated: 0, chainsRewritten: 0, chainsDeployed: 0, chainsDiscarded: 0, iqGained: 0, consecutiveFailures, report: msg };
  }

  const scores = evaluateChains();
  const underperforming = scores.filter((s) => s.belowThreshold && s.traceCount > 0);

  const deployResults = [];

  for (const chain of underperforming) {
    // +1 IQ per attempt
    totalIqGained += 1;
    await gainIQ(1, `Chain rewrite attempted: ${chain.chainName}`).catch(() => {});

    const rewrite = await rewriteChain(chain, '').catch((err) => ({
      chainName: chain.chainName, attempted: false, candidatePath: null, reason: String(err),
    }));

    if (!rewrite.attempted) {
      chainsDiscarded++;
      consecutiveFailures++;
      continue;
    }

    chainsRewritten++;

    const testResult = await testAndDeploy(rewrite, chain).catch((err) => ({
      chainName: chain.chainName, deployed: false, oldScore: chain.composite, newScore: chain.composite, delta: 0, backupPath: null, reason: String(err),
    }));

    deployResults.push(testResult);

    if (testResult.deployed) {
      chainsDeployed++;
      consecutiveFailures = 0;
      const iqForDeploy = 5;
      totalIqGained += iqForDeploy;
      await gainIQ(iqForDeploy, `Chain rewrite deployed: ${chain.chainName} +${testResult.delta}`).catch(() => {});
    } else {
      chainsDiscarded++;
      consecutiveFailures++;
    }
  }

  // Bonus: 5 consecutive successful deployments
  if (chainsDeployed >= 5) {
    totalIqGained += 15;
    await gainIQ(15, '5 consecutive successful chain improvements').catch(() => {});
  }

  // Full cycle complete
  totalIqGained += 3;
  await gainIQ(3, 'Nightly self-improvement cycle completed').catch(() => {});

  const report = buildReport(date, scores, deployResults, totalIqGained);
  writeReports(report, date);

  await writeMemory({
    content: `Self-improvement cycle ${date}: ${chainsDeployed} chains improved, IQ +${totalIqGained}`,
    category: 'agent_run',
    metadata: { date, chainsDeployed, iqGained: totalIqGained },
  }).catch(() => {});

  return { date, chainsEvaluated: scores.length, chainsRewritten, chainsDeployed, chainsDiscarded, iqGained: totalIqGained, consecutiveFailures, report };
}

function buildReport(date: string, scores: ReturnType<typeof evaluateChains>, deployResults: unknown[], iqGained: number): string {
  return `# SELF-IMPROVEMENT CYCLE — ${date}

## Chain Evaluation
| Chain | Composite Score | Status |
|-------|----------------|--------|
${scores.map((s) => `| ${s.chainName} | ${s.composite} | ${s.belowThreshold ? '⚠️ BELOW THRESHOLD' : '✓ OK'} |`).join('\n')}

## Rewrite Results
${deployResults.length ? (deployResults as Array<{ chainName: string; deployed: boolean; oldScore: number; newScore: number; delta: number; reason: string }>).map((r) => `- **${r.chainName}**: ${r.deployed ? '✓ DEPLOYED' : '✗ DISCARDED'} | ${r.oldScore} → ${r.newScore} (+${r.delta}) | ${r.reason}`).join('\n') : '_No rewrites this cycle_'}

## IQ Gained This Cycle: +${iqGained}
`;
}

function writeReports(report: string, date: string): void {
  const logPath = path.resolve(process.cwd(), 'reports/SELF_IMPROVEMENT_LOG.md');
  const notePath = path.resolve(process.cwd(), `notes/improvements/${date}.md`);
  const datePath = path.resolve(process.cwd(), `reports/SELF_IMPROVEMENT_${date}.md`);

  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.mkdirSync(path.dirname(notePath), { recursive: true });
  fs.writeFileSync(datePath, report, 'utf-8');
  fs.appendFileSync(logPath, `\n${report}`, 'utf-8');
  fs.writeFileSync(notePath, `---\ntags: [improvement, amara, self-learning]\ndate: ${date}\n---\n\n${report}\n[[AMARA]]`, 'utf-8');
}
