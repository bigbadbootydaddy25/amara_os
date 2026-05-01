import fs from 'fs';
import path from 'path';
import { runFullDataPull } from './data-puller';
import { importMiroFishScores } from '@/lib/mirofish/score-importer';
import { runHermes } from '@/lib/hermes/hermes-orchestrator';
import { dailyPipelineChain } from '@/lib/pipeline/daily-pipeline-chain';
import { generateMorningBriefing } from '@/lib/memory/morning-briefing';
import { findKillShots, writeKillShotReport } from '@/lib/mirofish/kill-shot-finder';
import { gainIQ } from '@/lib/iq/iq-engine';
import { sendNotification } from './mac-controller';

export interface MorningRoutineResult {
  date: string;
  steps: Array<{ step: string; status: 'ok' | 'error'; detail?: string }>;
  briefingPath: string | null;
  killShotCount: number;
  errors: string[];
}

function loadMarketNames(): string[] {
  const dir = path.resolve(process.cwd(), 'data/MARKETS');
  if (!fs.existsSync(dir)) return ['DFW', 'HOUSTON', 'AUSTIN'];

  const names: string[] = [];
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf-8')) as unknown;
      const markets = Array.isArray(raw) ? raw : [raw];
      for (const m of markets) {
        if (typeof m === 'object' && m !== null && 'name' in m) {
          names.push(String((m as { name: string }).name));
        }
      }
    } catch { /* skip */ }
  }
  return names;
}

function writeLog(content: string, date: string): string {
  const logPath = path.resolve(process.cwd(), `reports/MORNING_ROUTINE_LOG_${date}.md`);
  const notePath = path.resolve(process.cwd(), `notes/routines/${date}.md`);
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.mkdirSync(path.dirname(notePath), { recursive: true });
  fs.writeFileSync(logPath, content, 'utf-8');
  fs.writeFileSync(notePath, `---\ntags: [routine, morning]\ndate: ${date}\n---\n\n${content}\n[[AMARA]]`, 'utf-8');
  return logPath;
}

export async function runMorningRoutine(): Promise<MorningRoutineResult> {
  const date = new Date().toISOString().slice(0, 10);
  const steps: MorningRoutineResult['steps'] = [];
  const errors: string[] = [];
  const markets = loadMarketNames();

  // Step 1: Pull overnight data (PropStream + Zillow)
  try {
    const pullResult = await runFullDataPull(markets);
    steps.push({ step: 'Data pull', status: 'ok', detail: `PropStream: ${pullResult.propStreamFiles} files, Zillow: ${pullResult.zillowDomHits} DOM hits` });
    errors.push(...pullResult.errors);
  } catch (err) {
    steps.push({ step: 'Data pull', status: 'error', detail: String(err) });
    errors.push(String(err));
  }

  // Step 2: Update MiroFish signal weights
  try {
    const mfResult = await importMiroFishScores();
    steps.push({ step: 'MiroFish signals', status: 'ok', detail: `Scored ${mfResult.scored} deals` });
  } catch (err) {
    steps.push({ step: 'MiroFish signals', status: 'error', detail: String(err) });
  }

  // Step 3: Hermes agent sweep
  try {
    const hermesResult = await runHermes();
    steps.push({ step: 'Hermes sweep', status: 'ok', detail: `${hermesResult.marketsSucceeded}/${hermesResult.marketsRun} markets` });
    await gainIQ(3, 'Full Hermes morning sweep completed').catch(() => {});
  } catch (err) {
    steps.push({ step: 'Hermes sweep', status: 'error', detail: String(err) });
  }

  // Step 4: Run full daily pipeline (discovery + buyer match)
  let briefingPath: string | null = null;
  try {
    const pipelineResult = await dailyPipelineChain.invoke({ markets, skipBriefing: true });
    steps.push({ step: 'Daily pipeline', status: 'ok', detail: `${pipelineResult.totalDealsFound} deals, ${pipelineResult.totalMatchesBuilt} matches` });
  } catch (err) {
    steps.push({ step: 'Daily pipeline', status: 'error', detail: String(err) });
  }

  // Step 5: Kill shot deals
  let killShotCount = 0;
  try {
    const killShots = await findKillShots(0.8);
    killShotCount = killShots.length;
    writeKillShotReport(killShots);
    steps.push({ step: 'Kill shots', status: 'ok', detail: `${killShotCount} deals above threshold` });
  } catch (err) {
    steps.push({ step: 'Kill shots', status: 'error', detail: String(err) });
  }

  // Step 6: Morning briefing
  try {
    const briefing = await generateMorningBriefing();
    briefingPath = briefing.reportPath;
    steps.push({ step: 'Morning briefing', status: 'ok', detail: briefing.reportPath });
    await gainIQ(1, 'Morning briefing generated').catch(() => {});
  } catch (err) {
    steps.push({ step: 'Morning briefing', status: 'error', detail: String(err) });
  }

  // Step 7: Mac notification
  const okCount = steps.filter((s) => s.status === 'ok').length;
  sendNotification('AMARA Morning Routine Complete', `${okCount}/${steps.length} steps succeeded. ${killShotCount} kill shots found.`);

  const log = `# MORNING ROUTINE LOG — ${date}\n\n## Steps\n${steps.map((s) => `- [${s.status === 'ok' ? '✓' : '✗'}] **${s.step}**: ${s.detail ?? ''}`).join('\n')}\n\n## Errors\n${errors.length ? errors.map((e) => `- ${e}`).join('\n') : '_None_'}\n`;
  writeLog(log, date);

  return { date, steps, briefingPath, killShotCount, errors };
}
