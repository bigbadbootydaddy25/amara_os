'use strict';

/**
 * Agent 05 — Market Comp Aggregator
 * Aggregates recent comparable sales and land-value estimates for flagged parcels.
 *
 * STATUS: STUB — not yet implemented.
 * Receives ctx (RunContext) and the result from Agent 01 via ctx.agentResults['01'].
 */

const fs  = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-05');

const AGENT_ID      = '05-market-comp-aggregator';
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
