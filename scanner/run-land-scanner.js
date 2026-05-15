#!/usr/bin/env node
'use strict';

/**
 * run-land-scanner.js
 * ---------------------------------------------------------------------------
 * AMARA OS — Land Intelligence Pipeline  ·  Polk County, FL
 *
 * Orchestrates the 6-agent pipeline:
 *
 *   06  builder-buybox-profiler      ← seeds/refreshes builder buy-box data (runs first)
 *   01  plat-expiration-scanner      ← scans for expired / dormant plats
 *   02  distress-scanner             ← scores financial & legal distress per plat
 *   03  builder-demand-scanner       ← permit activity + EDGAR + demand scoring
 *   04  opportunity-scorer           ← composite score, hot-match alerts, buy-box match
 *   05  quick-flip-filter            ← Kill Shot Briefs, OpenClaw, Airtable
 *
 * Usage:
 *   node run-land-scanner.js [--agents 01,02] [--log-level debug]
 *
 * Flags:
 *   --agents      Comma-separated list of agent IDs to run (default: all enabled)
 *   --log-level   debug | info | warn | error  (default: info)
 *   --dry-run     Cold-start and validate config but do not execute agents
 * ---------------------------------------------------------------------------
 */

const path = require('node:path');
const fs   = require('node:fs');
const log  = require('./lib/logger');
const { coldStart } = require('./cold-start');
const config = require('./config/polk-county.json');

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = { agents: null, logLevel: 'info', dryRun: false };

  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--agents'    && argv[i + 1]) args.agents    = argv[++i].split(',').map((s) => s.trim().padStart(2, '0'));
    if (argv[i] === '--log-level' && argv[i + 1]) args.logLevel  = argv[++i];
    if (argv[i] === '--dry-run')                  args.dryRun    = true;
  }

  return args;
}

// ---------------------------------------------------------------------------
// Agent registry  (loaded lazily to avoid import overhead for disabled agents)
// ---------------------------------------------------------------------------

const AGENT_MODULES = {
  '01': './agents/01-plat-expiration-scanner',
  '02': './agents/02-distress-scanner',
  '03': './agents/03-builder-demand-scanner',
  '04': './agents/04-opportunity-scorer',
  '05': './agents/05-quick-flip-filter',
  '06': './agents/06-builder-buybox-profiler',
};

function resolveAgentList(requested) {
  if (!requested) {
    // Default execution order: Agent 06 seeds buy-box data first, then 01-05
    const enabled = Object.entries(config.agents)
      .filter(([, v]) => v.enabled)
      .map(([k]) => k.padStart(2, '0'));
    const has06 = enabled.includes('06');
    const rest  = enabled.filter((id) => id !== '06').sort();
    return has06 ? ['06', ...rest] : rest;
  }

  const unknown = requested.filter((id) => !AGENT_MODULES[id]);
  if (unknown.length) {
    throw new Error(`Unknown agent IDs: ${unknown.join(', ')}. Valid: ${Object.keys(AGENT_MODULES).join(', ')}`);
  }

  return requested;
}

// ---------------------------------------------------------------------------
// Pipeline execution
// ---------------------------------------------------------------------------

async function runPipeline(ctx, agentIds) {
  log.info(`Running ${agentIds.length} agent(s): ${agentIds.join(', ')}\n`, undefined, 'pipeline');

  const pipelineStart = Date.now();

  for (const id of agentIds) {
    const agentCfg = config.agents[id];
    const label = agentCfg?.id ?? `agent-${id}`;

    log.info(`${'─'.repeat(60)}`, undefined, 'pipeline');
    log.info(`Agent ${id}  ·  ${label}`, undefined, 'pipeline');
    log.info(`${'─'.repeat(60)}`, undefined, 'pipeline');

    let agentModule;
    try {
      agentModule = require(AGENT_MODULES[id]);
    } catch (err) {
      log.error(`Failed to load agent ${id}: ${err.message}`, undefined, 'pipeline');
      ctx.agentResults[id] = { error: err.message, status: 'load-failed' };
      continue;
    }

    const agentStart = Date.now();
    try {
      const result = await agentModule.run(ctx);
      ctx.agentResults[id] = result;
      log.info(`Agent ${id} complete  (${Date.now() - agentStart}ms)\n`, undefined, 'pipeline');
    } catch (err) {
      log.error(`Agent ${id} threw an unhandled error: ${err.message}`, undefined, 'pipeline');
      ctx.agentResults[id] = { error: err.message, status: 'runtime-error' };
      log.warn(`Continuing pipeline despite agent ${id} failure\n`, undefined, 'pipeline');
    }
  }

  const totalMs = Date.now() - pipelineStart;

  // Write final pipeline manifest
  const manifest = {
    runId: ctx.runId,
    county: ctx.county,
    state: ctx.state,
    fips: ctx.fips,
    startedAt: ctx.startedAt,
    finishedAt: new Date().toISOString(),
    totalMs,
    agentIds,
    agentResults: Object.fromEntries(
      Object.entries(ctx.agentResults).map(([id, r]) => [
        id,
        { status: r.status ?? 'ok', summary: r.summary ?? null, error: r.error ?? null },
      ]),
    ),
  };

  fs.writeFileSync(
    path.join(ctx.runDir, 'pipeline-manifest.json'),
    JSON.stringify(manifest, null, 2),
  );

  return { totalMs, manifest };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  log.setLevel(args.logLevel);

  // Cold start — validates environment, connectivity, creates run directory
  const ctx = await coldStart();

  if (args.dryRun) {
    log.info('--dry-run flag set. Exiting after cold start.', undefined, 'pipeline');
    process.exit(0);
  }

  // Resolve which agents to run
  let agentIds;
  try {
    agentIds = resolveAgentList(args.agents);
  } catch (err) {
    log.error(err.message, undefined, 'pipeline');
    process.exit(1);
  }

  if (!agentIds.length) {
    log.warn('No agents enabled. Set "enabled": true in config/polk-county.json.', undefined, 'pipeline');
    process.exit(0);
  }

  // Run pipeline
  const { totalMs, manifest } = await runPipeline(ctx, agentIds);

  // Final summary
  const C = '\x1b[36m', B = '\x1b[1m', G = '\x1b[32m', R = '\x1b[0m';
  process.stdout.write(
    `\n${B}${C}Pipeline complete${R}  ·  run ${manifest.runId}  ·  ${totalMs}ms\n` +
    `${G}Artifacts → ${ctx.runDir}${R}\n\n`,
  );
}

main().catch((err) => {
  log.error(`Fatal: ${err.message}`, undefined, 'pipeline');
  if (process.env.DEBUG) log.error(err.stack, undefined, 'pipeline');
  process.exit(1);
});
