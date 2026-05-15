'use strict';

/**
 * Agent 03 — Lien Encumbrance Scanner
 * Scans for tax liens, lis pendens, mortgages, and code-enforcement actions on flagged parcels.
 *
 * STATUS: STUB — not yet implemented.
 * Receives ctx (RunContext) and the result from Agent 01 via ctx.agentResults['01'].
 */

const fs  = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-03');

const AGENT_ID      = '03-lien-encumbrance-scanner';
const AGENT_VERSION = '0.0.0-stub';

async function run(ctx) {
  log.info('Agent not yet implemented — stub pass-through');

  const result = {
    agentId: AGENT_ID,
    agentVersion: AGENT_VERSION,
    status: 'stub',
    findings: [],
  };

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify(result, null, 2));

  return result;
}

module.exports = { run };
