'use strict';

/**
 * Agent 05 — Quick Flip Filter  (Polk County FL)
 * ─────────────────────────────────────────────────
 * Depends on: Agent 04 output (agentResults['04'].findings)
 *
 * Rules:
 *  • Score ≥ 90 → Kill Shot Brief generated.
 *  • Score ≥ 95 → Brief sent via Telegram bot (TELEGRAM_BOT_TOKEN env, chat_id 7977783351).
 *  • If any required field is missing real data → brief is HELD, not sent.
 *  • Airtable push on AIRTABLE_API_KEY env var.
 *  • OpenClaw outreach via local gateway (http://127.0.0.1:18789/messages).
 *  • Ollama llama3 used for brief text generation.
 *
 * PERMANENT EXCLUSION (hardcoded, never override):
 *  HomeVestors and all franchisee DBAs are excluded from all matches,
 *  briefs, Airtable pushes, and outreach. This cannot be overridden.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-05');

const AGENT_ID      = '05-quick-flip-filter';
const AGENT_VERSION = '2.0.0';

const BRIEF_THRESHOLD  = 90;
const TELEGRAM_THRESHOLD = 95;

const TELEGRAM_CHAT_ID = '7977783351';
const AIRTABLE_BASE_ID = 'app0jn857ZwVzQs8i';
const AIRTABLE_TABLE   = 'Land Pipeline';
const OPENCLAW_URL     = 'http://127.0.0.1:18789/messages';
const OLLAMA_URL       = 'http://127.0.0.1:11434/api/generate';
const OLLAMA_MODEL     = 'llama3';

// ── PERMANENT EXCLUSION — HomeVestors and all franchisee DBAs ─────────────────
// This list is hardcoded and MUST NOT be removed, overridden, or made configurable.
const EXCLUDED_ENTITIES = [
  'HOMEVESTORS',
  'HOME VESTORS',
  'WE BUY UGLY HOUSES',
  'WE BUY UGLY HOMES',
  'UGLY HOUSES',
  'UGLY HOMES',
];

function isExcluded(name) {
  if (!name) return false;
  const upper = name.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ');
  return EXCLUDED_ENTITIES.some((ex) => upper.includes(ex));
}

// ── Required fields for a non-held brief ──────────────────────────────────────

const REQUIRED_FIELDS = [
  'subdivName',
  'representativeParcelId',
  'representativeOwner',
  'compositeScore',
  'parcelCount',
  'totalAcres',
];

function missingRequiredFields(finding) {
  return REQUIRED_FIELDS.filter((f) => {
    const v = finding[f];
    return v === null || v === undefined || v === '';
  });
}

// ── Ollama brief generation ────────────────────────────────────────────────────

async function generateBrief(finding) {
  const prompt = `You are a concise land acquisition analyst. Write a Kill Shot Brief for this opportunity.

Subdivision: ${finding.subdivName}
Parcel ID: ${finding.representativeParcelId}
Owner: ${finding.representativeOwner}
Acres: ${finding.totalAcres}
Lots: ${finding.parcelCount}
Composite Score: ${finding.compositeScore}/100
Plat Category: ${finding.platCategory}
Distress Flags: ${finding.distressFlags?.join(', ') || 'None'}
Demand Level: ${finding.demandLevel}
Nearby Permits (1mi): ${finding.nearbyPermits}
Buy-Box Matches: ${finding.buyBoxMatches?.map((b) => b.builder).join(', ') || 'None'}

Write 3–5 sentences. Focus on the actionable opportunity. No fluff. No speculation beyond the data. Output only the brief text, no headers.`;

  try {
    const resp = await fetch(OLLAMA_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: OLLAMA_MODEL, prompt, stream: false }),
      signal: AbortSignal.timeout(30_000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return (data.response ?? '').trim() || null;
  } catch {
    return null;  // Ollama offline → brief text unavailable → brief held
  }
}

// ── Telegram delivery ─────────────────────────────────────────────────────────

async function sendTelegram(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    log.warn('TELEGRAM_BOT_TOKEN not set — Telegram delivery skipped');
    return false;
  }

  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text, parse_mode: 'Markdown' }),
      signal: AbortSignal.timeout(15_000),
    });
    if (!resp.ok) {
      log.warn(`Telegram delivery failed: HTTP ${resp.status}`);
      return false;
    }
    return true;
  } catch (err) {
    log.warn(`Telegram delivery error: ${err.message}`);
    return false;
  }
}

// ── Airtable push ─────────────────────────────────────────────────────────────

async function pushAirtable(fields) {
  const key = process.env.AIRTABLE_API_KEY;
  if (!key) {
    log.warn('AIRTABLE_API_KEY not set — Airtable push skipped');
    return false;
  }

  const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${encodeURIComponent(AIRTABLE_TABLE)}`;
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization':  `Bearer ${key}`,
        'Content-Type':   'application/json',
      },
      body: JSON.stringify({ fields }),
      signal: AbortSignal.timeout(15_000),
    });
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      log.warn(`Airtable push failed: HTTP ${resp.status} — ${body.slice(0, 200)}`);
      return false;
    }
    return true;
  } catch (err) {
    log.warn(`Airtable push error: ${err.message}`);
    return false;
  }
}

// ── OpenClaw outreach ─────────────────────────────────────────────────────────

async function sendOpenClaw(payload) {
  try {
    const resp = await fetch(OPENCLAW_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(10_000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// ── Format Telegram message ───────────────────────────────────────────────────

function formatTelegramMessage(finding, brief) {
  const bb = (finding.buyBoxMatches ?? []).map((b) => `• ${b.builder} (${b.appetite})`).join('\n') || 'None';
  return [
    `🏗 *KILL SHOT BRIEF — Polk County FL*`,
    ``,
    `*${finding.subdivName}*`,
    `Score: ${finding.compositeScore}/100  |  Category: ${finding.platCategory}`,
    `Lots: ${finding.parcelCount}  |  Acres: ${finding.totalAcres}`,
    `Parcel: ${finding.representativeParcelId}`,
    `Owner: ${finding.representativeOwner}`,
    ``,
    `*Distress:* ${finding.distressFlags?.join(', ') || 'None'}`,
    `*Demand:* ${finding.demandLevel} (${finding.nearbyPermits} permits nearby)`,
    `*Builder Matches:*\n${bb}`,
    ``,
    brief ? `*Brief:*\n${brief}` : `_Brief generation unavailable — manual review required._`,
  ].join('\n');
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);

  const startedAt = Date.now();

  const agent04 = ctx.agentResults?.['04'];
  const scoredFindings = agent04?.findings ?? [];

  if (!scoredFindings.length) {
    log.error('INSUFFICIENT DATA - DO NOT SCORE — Agent 04 returned zero scored findings. Nothing to filter.');
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, briefsGenerated: 0, briefsSent: 0, briefsHeld: 0 }, findings: [] };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  log.info(`Evaluating ${scoredFindings.length} scored findings`);
  log.info(`Brief threshold: ${BRIEF_THRESHOLD}+  |  Telegram threshold: ${TELEGRAM_THRESHOLD}+`);

  const findings = [];
  let briefsGenerated = 0;
  let briefsSent      = 0;
  let briefsHeld      = 0;
  let excluded        = 0;

  for (const finding of scoredFindings) {
    // ── HomeVestors exclusion (permanent, non-overridable) ──
    const ownerExcluded   = isExcluded(finding.representativeOwner);
    const builderExcluded = (finding.buyBoxMatches ?? []).some((b) => isExcluded(b.builder));
    if (ownerExcluded || builderExcluded) {
      log.warn(`EXCLUDED — ${finding.subdivName}: HomeVestors entity detected. Skipping permanently.`);
      excluded++;
      continue;
    }

    if (finding.compositeScore < BRIEF_THRESHOLD) {
      findings.push({ ...finding, briefStatus: 'BELOW_THRESHOLD', briefText: null });
      continue;
    }

    // ── Required field check ──
    const missing = missingRequiredFields(finding);
    if (missing.length > 0) {
      log.warn(`HELD — ${finding.subdivName}: Missing required fields: ${missing.join(', ')}`);
      findings.push({ ...finding, briefStatus: 'HELD', briefText: null, heldReason: `Missing: ${missing.join(', ')}` });
      briefsHeld++;
      continue;
    }

    // ── Generate brief via Ollama ──
    const briefText = await generateBrief(finding);
    if (!briefText) {
      log.warn(`HELD — ${finding.subdivName}: Ollama unavailable or returned empty brief.`);
      findings.push({ ...finding, briefStatus: 'HELD', briefText: null, heldReason: 'Ollama unavailable' });
      briefsHeld++;
      continue;
    }

    briefsGenerated++;

    let telegramSent  = false;
    let airtableSent  = false;
    let openclawSent  = false;

    // ── Telegram delivery (≥95) ──
    if (finding.compositeScore >= TELEGRAM_THRESHOLD) {
      const msg = formatTelegramMessage(finding, briefText);
      telegramSent = await sendTelegram(msg);
      if (telegramSent) {
        briefsSent++;
        log.info(`Telegram sent — ${finding.subdivName} (score: ${finding.compositeScore})`);
      }
    }

    // ── Airtable push ──
    airtableSent = await pushAirtable({
      'Subdivision':    finding.subdivName,
      'Parcel ID':      finding.representativeParcelId,
      'Owner':          finding.representativeOwner,
      'Score':          finding.compositeScore,
      'Category':       finding.platCategory,
      'Lots':           finding.parcelCount,
      'Acres':          finding.totalAcres,
      'Demand Level':   finding.demandLevel,
      'Distress Flags': (finding.distressFlags ?? []).join(', '),
      'Builder Matches':(finding.buyBoxMatches ?? []).map((b) => b.builder).join(', '),
      'Brief':          briefText,
      'Status':         'NEW',
    });

    // ── OpenClaw outreach (for builder contacts in buy-box matches) ──
    for (const match of (finding.buyBoxMatches ?? [])) {
      if (!match.email) continue;
      openclawSent = await sendOpenClaw({
        channel:  'email',
        to:       match.email,
        subject:  `Land Opportunity — ${finding.subdivName}, Polk County FL`,
        body:     briefText,
        metadata: {
          subdivName:  finding.subdivName,
          score:       finding.compositeScore,
          lots:        finding.parcelCount,
          acres:       finding.totalAcres,
        },
      });
    }

    findings.push({
      ...finding,
      briefStatus:  'SENT',
      briefText,
      telegramSent,
      airtableSent,
      openclawSent,
    });
  }

  const summary = {
    totalScanned:    scoredFindings.length,
    excluded,
    aboveThreshold:  briefsGenerated + briefsHeld,
    briefsGenerated,
    briefsSent,
    briefsHeld,
    durationMs:      Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Findings evaluated: ${summary.totalScanned}`);
  log.info(`   Excluded (HomeVestors): ${excluded}`);
  log.info(`   Briefs generated:   ${briefsGenerated}`);
  log.info(`   Briefs sent (Telegram): ${briefsSent}`);
  log.info(`   Briefs held:        ${briefsHeld}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings };
}

module.exports = { run };
