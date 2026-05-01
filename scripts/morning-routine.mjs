#!/usr/bin/env node
/**
 * AMARA Morning Routine — standalone cron script
 * Cron: 0 6 * * * node /path/to/amara_os/scripts/morning-routine.mjs
 *
 * Add to crontab:
 *   crontab -e
 *   0 6 * * * cd /path/to/amara_os && node scripts/morning-routine.mjs >> logs/cron.log 2>&1
 */

import { config } from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '../.env.local') });

// Dynamic import to resolve TS paths — run with tsx or ts-node in production
// For pure JS: transpile first with `npx tsc --project tsconfig.json`
const { runMorningRoutine } = await import('../src/lib/openclaw/morning-routine.ts').catch(async () => {
  // Fallback: call the Next.js API directly if server is running
  const port = process.env.PORT || 3000;
  const res = await fetch(`http://localhost:${port}/api/openclaw/morning-routine`, { method: 'POST' });
  const data = await res.json();
  return { runMorningRoutine: () => Promise.resolve(data) };
});

console.log(`[AMARA] Morning routine starting — ${new Date().toISOString()}`);

try {
  const result = await runMorningRoutine();
  console.log(`[AMARA] Morning routine complete — ${result.steps.filter(s => s.status === 'ok').length}/${result.steps.length} steps OK`);
  console.log(`[AMARA] Kill shots: ${result.killShotCount}`);
  if (result.briefingPath) console.log(`[AMARA] Briefing: ${result.briefingPath}`);
  process.exit(0);
} catch (err) {
  console.error('[AMARA] Morning routine FAILED:', err);
  process.exit(1);
}
