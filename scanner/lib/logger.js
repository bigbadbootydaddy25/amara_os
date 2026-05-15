'use strict';

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
const COLOURS = {
  debug: '\x1b[36m',   // cyan
  info:  '\x1b[32m',   // green
  warn:  '\x1b[33m',   // yellow
  error: '\x1b[31m',   // red
  reset: '\x1b[0m',
  dim:   '\x1b[2m',
  bold:  '\x1b[1m',
};

let activeLevel = LEVELS.info;

function timestamp() {
  return new Date().toISOString().replace('T', ' ').slice(0, 23);
}

function pad(str, width) {
  return str.length >= width ? str : str + ' '.repeat(width - str.length);
}

function write(level, agent, message, data) {
  if (LEVELS[level] < activeLevel) return;

  const c = COLOURS[level];
  const prefix = `${COLOURS.dim}${timestamp()}${COLOURS.reset} ${c}${pad(level.toUpperCase(), 5)}${COLOURS.reset}`;
  const tag = agent ? ` ${COLOURS.bold}[${agent}]${COLOURS.reset}` : '';

  process.stdout.write(`${prefix}${tag} ${message}\n`);

  if (data !== undefined) {
    const serialised = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    process.stdout.write(`${COLOURS.dim}${serialised}${COLOURS.reset}\n`);
  }
}

module.exports = {
  setLevel(level) { activeLevel = LEVELS[level] ?? LEVELS.info; },

  debug: (msg, data, agent) => write('debug', agent, msg, data),
  info:  (msg, data, agent) => write('info',  agent, msg, data),
  warn:  (msg, data, agent) => write('warn',  agent, msg, data),
  error: (msg, data, agent) => write('error', agent, msg, data),

  agent(agentId) {
    return {
      debug: (msg, data) => write('debug', agentId, msg, data),
      info:  (msg, data) => write('info',  agentId, msg, data),
      warn:  (msg, data) => write('warn',  agentId, msg, data),
      error: (msg, data) => write('error', agentId, msg, data),
    };
  },

  banner(lines) {
    const bar = '═'.repeat(64);
    process.stdout.write(`\n${COLOURS.bold}${COLOURS['\x1b[36m'] ?? ''}╔${bar}╗\n`);
    for (const line of lines) {
      const padded = line.padStart(Math.floor((64 + line.length) / 2)).padEnd(64);
      process.stdout.write(`║ ${padded} ║\n`);
    }
    process.stdout.write(`╚${bar}╝${COLOURS.reset}\n\n`);
  },
};
