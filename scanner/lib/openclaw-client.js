'use strict';

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('./logger').agent('openclaw');

const ENDPOINT = process.env.OPENCLAW_GATEWAY_URL
  ? `${process.env.OPENCLAW_GATEWAY_URL.replace(/\/$/, '')}/messages`
  : 'http://127.0.0.1:18789/messages';

const QUEUE_FILE = path.resolve(__dirname, '../data/openclaw-failed-queue.json');
const RETRY_MS   = 60_000;

let _retryTimer = null;

function loadQueue() {
  try {
    return fs.existsSync(QUEUE_FILE)
      ? JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf8'))
      : [];
  } catch { return []; }
}

function saveQueue(q) {
  fs.writeFileSync(QUEUE_FILE, JSON.stringify(q, null, 2));
}

async function _post(channel, message) {
  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel, message }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`OpenClaw HTTP ${res.status}`);
}

async function send(channel, message) {
  try {
    await _post(channel, message);
    log.info(`Sent → channel:${channel}`);
    return { ok: true };
  } catch (err) {
    log.warn(`Unreachable (${err.message}) — queuing`);
    const q = loadQueue();
    q.push({ channel, message, queuedAt: new Date().toISOString(), attempts: 0 });
    saveQueue(q);
    _scheduleRetry();
    return { ok: false, queued: true };
  }
}

function _scheduleRetry() {
  if (_retryTimer) return;
  _retryTimer = setTimeout(async () => {
    _retryTimer = null;
    const q = loadQueue();
    if (!q.length) return;
    const remaining = [];
    for (const item of q) {
      try {
        await _post(item.channel, item.message);
        log.info(`Queued message delivered (queued ${item.queuedAt})`);
      } catch {
        item.attempts = (item.attempts ?? 0) + 1;
        remaining.push(item);
      }
    }
    saveQueue(remaining);
    if (remaining.length) _scheduleRetry();
  }, RETRY_MS);
}

module.exports = { send };
