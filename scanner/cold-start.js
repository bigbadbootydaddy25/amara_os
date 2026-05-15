'use strict';

const fs   = require('node:fs');
const path = require('node:path');
const os   = require('node:os');
const log  = require('./lib/logger');
const { ping } = require('./lib/polk-county-client');
const config = require('./config/polk-county.json');

const MIN_NODE_MAJOR = 18;          // native fetch requires 18+
const PIPELINE_VERSION = '1.0.0';

// ---------------------------------------------------------------------------
// Checks
// ---------------------------------------------------------------------------

function checkNodeVersion() {
  const major = parseInt(process.versions.node.split('.')[0], 10);
  if (major < MIN_NODE_MAJOR) {
    throw new Error(
      `Node.js ${MIN_NODE_MAJOR}+ required (native fetch). Found: ${process.versions.node}`,
    );
  }
  log.info(`Node.js ${process.versions.node} — OK`, undefined, 'cold-start');
}

function ensureOutputDirectory(outputDir) {
  const abs = path.resolve(__dirname, outputDir);
  if (!fs.existsSync(abs)) {
    fs.mkdirSync(abs, { recursive: true });
    log.info(`Created output directory: ${abs}`, undefined, 'cold-start');
  } else {
    log.info(`Output directory: ${abs}`, undefined, 'cold-start');
  }
  return abs;
}

function checkDiskSpace(outputDir) {
  // Rough guard: skip on platforms that don't support statvfs easily.
  // Real space check would use statvfs binding; we just stat the dir.
  const abs = path.resolve(__dirname, outputDir);
  try {
    fs.accessSync(abs, fs.constants.W_OK);
    log.info('Output directory is writable — OK', undefined, 'cold-start');
  } catch {
    throw new Error(`Output directory not writable: ${abs}`);
  }
}

async function checkConnectivity() {
  log.info('Checking Polk County GIS connectivity…', undefined, 'cold-start');
  const result = await ping();
  if (result.ok) {
    log.info(`GIS reachable — ${result.message}`, undefined, 'cold-start');
  } else {
    // Non-fatal — scanners fall back to offline data / mock mode.
    log.warn(
      `GIS unreachable (${result.message}). Agents will run in offline/mock mode.`,
      undefined,
      'cold-start',
    );
  }
  return result.ok;
}

function buildRunContext(outputDir) {
  const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const runDir = path.join(outputDir, runId);
  fs.mkdirSync(runDir, { recursive: true });

  return {
    runId,
    runDir,
    startedAt: new Date().toISOString(),
    county: config.county,
    state: config.state,
    fips: config.fips,
    pipelineVersion: PIPELINE_VERSION,
    node: process.versions.node,
    platform: `${os.type()} ${os.release()}`,
    agentResults: {},     // populated by run-land-scanner.js as agents complete
  };
}

// ---------------------------------------------------------------------------
// Main cold-start sequence
// ---------------------------------------------------------------------------

/**
 * Runs the full cold-start protocol and returns a RunContext object.
 * Throws on unrecoverable errors (bad Node version, unwritable output, etc.).
 */
async function coldStart() {
  const C = '\x1b[36m';
  const B = '\x1b[1m';
  const R = '\x1b[0m';

  process.stdout.write(
    `\n${B}${C}` +
    `╔══════════════════════════════════════════════════════════════════╗\n` +
    `║          AMARA OS · LAND INTELLIGENCE PIPELINE  v${PIPELINE_VERSION}          ║\n` +
    `║         Polk County, FL  ·  FIPS ${config.fips}  ·  OSINT Mode          ║\n` +
    `╚══════════════════════════════════════════════════════════════════╝${R}\n\n`,
  );

  log.info('Cold start sequence initiated', undefined, 'cold-start');

  // 1. Runtime check
  checkNodeVersion();

  // 2. Config summary
  log.info(
    `Target: ${config.county} County, ${config.state}  ·  FIPS ${config.fips}`,
    undefined,
    'cold-start',
  );
  log.info(
    `Agents enabled: ${Object.entries(config.agents)
      .filter(([, v]) => v.enabled)
      .map(([k, v]) => `${k}:${v.id}`)
      .join(', ') || 'none'}`,
    undefined,
    'cold-start',
  );

  // 3. Output directory
  const outputDir = ensureOutputDirectory(config.pipeline.outputDir);
  checkDiskSpace(config.pipeline.outputDir);

  // 4. Network / GIS connectivity
  const gisOnline = await checkConnectivity();

  // 5. Run context
  const ctx = buildRunContext(outputDir);
  ctx.gisOnline = gisOnline;

  // Write context manifest to run directory
  fs.writeFileSync(
    path.join(ctx.runDir, 'context.json'),
    JSON.stringify(ctx, null, 2),
  );

  log.info(`Run ID: ${ctx.runId}`, undefined, 'cold-start');
  log.info(`Run artifacts: ${ctx.runDir}`, undefined, 'cold-start');
  log.info('Cold start complete — pipeline ready\n', undefined, 'cold-start');

  return ctx;
}

module.exports = { coldStart };
