/* ═══════════════════════════════════════════════════════════════
   AMARA — Command Intelligence Script
   State machine · Boot sequence · Canvas viz · Typewriter
   ═══════════════════════════════════════════════════════════════ */
'use strict';

// ── State definitions ────────────────────────────────────────────
const STATES = ['idle', 'listening', 'thinking', 'responding', 'alert'];
let currentStateIdx = 0;
let typewriterTimer = null;
let vizAnimId = null;
let mouthAnimTimer = null;
let autoAdvanceTimer = null;

// Strategic coaching content per state
const STATE_DATA = {
  idle: {
    text: 'Monitoring 847 active market opportunities across 12 target zones.\n\nSignal filters engaged. Awaiting your directive.',
    confidence: 0,
    rec: '—',
    clock: '—',
    sys: 'SYSTEM NOMINAL',
    badge: 'IDLE',
  },
  listening: {
    text: 'Processing acoustic input. Market context engaged.\n\nGo ahead — I\'m tracking every word.',
    confidence: 0,
    rec: '—',
    clock: '—',
    sys: 'AUDIO INPUT ACTIVE',
    badge: 'LISTENING',
  },
  thinking: {
    text: 'Cross-referencing 23 comparable acquisitions.\n\nRisk-adjusted yield model engaged. Owner distress signals confirmed on 4 leads...',
    confidence: 0,
    rec: 'ANALYSIS IN PROGRESS',
    clock: '—',
    sys: 'PROCESSING',
    badge: 'THINKING',
  },
  responding: {
    text: 'The Henderson pocket off Water Street shows 34% below assessed value. Owner distress confirmed — second missed tax payment, probate pending.\n\nRecommended entry: $287,000. Exit multiple: 1.8×.\n\nI\'d move on this in 72 hours before the servicer files.',
    confidence: 91,
    rec: 'MOVE. 72-HOUR WINDOW.',
    clock: '72 HRS',
    sys: 'RESPONSE ACTIVE',
    badge: 'RESPONDING',
  },
  alert: {
    text: 'PRIORITY SIGNAL DETECTED.\n\n4821 Sunrise Mesa Drive — foreclosure filing confirmed this morning. Acquisition window: 11 days.\n\nThis matches your top buy-box. Equity spread: $94K+. Immediate action recommended.',
    confidence: 97,
    rec: '⚡ EXECUTE NOW',
    clock: '11 DAYS',
    sys: '⚡ PRIORITY ALERT',
    badge: 'ALERT',
  },
};

// ── DOM refs ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const bootOverlay = $('boot-overlay');
const bootFill    = $('boot-fill');
const bootLog     = $('boot-log');
const screen      = $('amara-screen');

const clockEl      = $('clock');
const dateEl       = $('date-display');
const sysLabel     = $('sys-label');
const sysDot       = $('sys-dot');
const modeVal      = $('mode-val');
const priorityVal  = $('priority-val');

const bgLight      = $('bg-light');
const avatarWrap   = $('avatar-wrap');
const avatarGlow   = $('avatar-glow');
const amaraFace    = $('amara-face');
const amaraCore    = document.querySelector('.amara-core');
const stateBadge   = $('state-badge');
const stateDot     = $('state-dot');
const faceScan     = $('face-scan');
const scanLine     = $('scan-line');

const coachingText = $('coaching-text');
const coachingCursor = $('coaching-cursor');
const confFill     = $('conf-fill');
const confVal      = $('conf-val');
const recBox       = $('rec-box');
const playClock    = $('play-clock');

const cycleBtn     = $('cycle-btn');
const stateTrack   = $('state-track');
const stateNodes   = document.querySelectorAll('.state-node');

const canvas       = $('viz-canvas');
const ctx          = canvas.getContext('2d');

// ── Clock ────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2,'0');
  const mm = String(now.getMinutes()).padStart(2,'0');
  const ss = String(now.getSeconds()).padStart(2,'0');
  clockEl.textContent = `${hh}:${mm}:${ss}`;
  dateEl.textContent = now.toLocaleDateString('en-US',{
    weekday:'short', month:'short', day:'numeric', year:'numeric'
  }).toUpperCase();
}
setInterval(updateClock, 1000);
updateClock();

// ── Boot sequence ────────────────────────────────────────────────
const BOOT_LOGS = [
  'INITIALIZING NEURAL CORE...',
  'LOADING MARKET INTELLIGENCE...',
  'CALIBRATING DISTRESS SIGNALS...',
  'ENGAGING DEAL ANALYSIS ENGINE...',
  'SYNCING AMARA COMMAND LAYER...',
  'SYSTEM READY.',
];

async function runBoot() {
  let logIdx = 0;
  let pct = 0;

  await delay(300);

  const interval = setInterval(() => {
    pct += Math.random() * 18 + 6;
    if (pct > 100) pct = 100;
    bootFill.style.width = pct + '%';

    if (logIdx < BOOT_LOGS.length && pct > (logIdx + 1) * (100 / BOOT_LOGS.length)) {
      bootLog.textContent = BOOT_LOGS[logIdx];
      logIdx++;
    }

    if (pct >= 100) {
      clearInterval(interval);
      bootLog.textContent = 'AMARA ONLINE.';
      setTimeout(endBoot, 600);
    }
  }, 90);
}

function endBoot() {
  bootOverlay.style.opacity = '0';
  bootOverlay.style.transition = 'opacity 0.5s ease';
  setTimeout(() => {
    bootOverlay.style.display = 'none';
    screen.classList.remove('hidden');
    // Brief scan sweep across face on reveal
    scanLine.classList.add('scanning');
    setTimeout(() => scanLine.classList.remove('scanning'), 1400);
    // Enter idle state
    applyState('idle');
    startViz();
  }, 500);
}

// ── State machine ────────────────────────────────────────────────
function cycleState() {
  clearTimeout(autoAdvanceTimer);
  currentStateIdx = (currentStateIdx + 1) % STATES.length;
  applyState(STATES[currentStateIdx]);
}

function setStateByName(name) {
  clearTimeout(autoAdvanceTimer);
  const idx = STATES.indexOf(name);
  if (idx === -1) return;
  currentStateIdx = idx;
  applyState(name);
}

function applyState(state) {
  const data = STATE_DATA[state];

  // ── Background center light ──
  bgLight.className = 'bg-centerlight state-' + state;

  // ── Core container class ──
  amaraCore.className = 'amara-core state-' + state;

  // ── Avatar wrap class ──
  avatarWrap.className = 'avatar-wrap state-' + state;

  // ── SVG face class (for CSS mouth animation) ──
  amaraFace.className = 'amara-face ' + state;

  // ── State badge ──
  stateBadge.textContent = data.badge;
  stateBadge.className = 'state-badge ' + state;
  stateDot.className = 'state-pip-dot ' + state;

  // ── Mode display (left panel) ──
  modeVal.textContent = data.badge;
  modeVal.style.color = state === 'alert' ? 'var(--red-bright)' : '';

  // ── System indicator ──
  sysLabel.textContent = data.sys;
  sysDot.className = 'sys-dot' + (state === 'alert' ? ' alert' : '');

  // ── Priority (left panel) ──
  priorityVal.textContent = state === 'alert' ? '⚡ CRITICAL' : '3 FLAGGED';

  // ── Face scan line (thinking only) ──
  if (state === 'thinking') {
    faceScan.classList.add('active');
  } else {
    faceScan.classList.remove('active');
  }

  // ── Recommendation + clock ──
  recBox.textContent = data.rec;
  recBox.style.color = state === 'alert' ? 'var(--red-bright)' : '';
  playClock.textContent = data.clock;
  playClock.style.color = (state === 'alert' || state === 'responding') ? 'var(--red-bright)' : 'var(--gray)';

  // ── Confidence bar ──
  confFill.style.width = data.confidence + '%';
  confVal.textContent = data.confidence ? data.confidence + '% CERTAINTY' : '—';

  // ── State track progress ──
  updateStateTrack(state);

  // ── Typewriter coaching text ──
  startTypewriter(data.text);

  // ── Auto-advance: listening → thinking → responding ──
  if (state === 'listening') {
    autoAdvanceTimer = setTimeout(() => applyState('thinking'), 3200);
  } else if (state === 'thinking') {
    autoAdvanceTimer = setTimeout(() => applyState('responding'), 4000);
  }
}

function updateStateTrack(activeState) {
  const activeIdx = STATES.indexOf(activeState);
  stateNodes.forEach((node, i) => {
    node.classList.remove('active', 'past');
    if (i < activeIdx) node.classList.add('past');
    else if (i === activeIdx) node.classList.add('active');
  });
}

// ── Typewriter effect ────────────────────────────────────────────
function startTypewriter(text) {
  if (typewriterTimer) clearInterval(typewriterTimer);
  coachingText.textContent = '';
  coachingCursor.style.display = 'inline';
  let i = 0;
  typewriterTimer = setInterval(() => {
    if (i < text.length) {
      coachingText.textContent += text[i];
      i++;
    } else {
      clearInterval(typewriterTimer);
      typewriterTimer = null;
      // blink cursor briefly then hide
      setTimeout(() => { coachingCursor.style.display = 'none'; }, 1800);
    }
  }, 18);
}

// ── Canvas voice visualizer ──────────────────────────────────────
let vizPhase = 0;
let vizBars = new Array(28).fill(0);

function startViz() {
  if (vizAnimId) cancelAnimationFrame(vizAnimId);
  drawViz();
}

function drawViz() {
  vizAnimId = requestAnimationFrame(drawViz);
  const W = canvas.width;
  const H = canvas.height;
  const state = STATES[currentStateIdx];

  ctx.clearRect(0, 0, W, H);

  vizPhase += 0.06;

  // Choose color based on state
  let baseColor, glowColor;
  if (state === 'listening') {
    baseColor = 'rgba(220,40,40,';
    glowColor = 'rgba(200,20,20,0.4)';
  } else if (state === 'thinking') {
    baseColor = 'rgba(200,160,0,';
    glowColor = 'rgba(200,140,0,0.35)';
  } else if (state === 'responding') {
    baseColor = 'rgba(30,200,100,';
    glowColor = 'rgba(20,180,80,0.35)';
  } else if (state === 'alert') {
    baseColor = 'rgba(220,20,20,';
    glowColor = 'rgba(200,0,0,0.5)';
  } else {
    baseColor = 'rgba(160,160,180,';
    glowColor = 'rgba(140,140,170,0.2)';
  }

  const barCount = 28;
  const barW = 4;
  const gap = (W - barCount * barW) / (barCount + 1);

  for (let i = 0; i < barCount; i++) {
    let targetH;

    if (state === 'idle') {
      // Gentle sine breath
      targetH = 3 + Math.sin(vizPhase * 0.7 + i * 0.35) * 2.5;
    } else if (state === 'listening') {
      // Reactive random audio bars
      targetH = 4 + Math.abs(Math.sin(vizPhase * 2.2 + i * 0.6)) * 18
               + Math.random() * 10;
    } else if (state === 'thinking') {
      // Scanning pattern — wave that moves
      const wave = Math.sin(vizPhase * 1.8 - i * 0.28);
      targetH = 2 + Math.abs(wave) * 14 + Math.sin(vizPhase * 0.5 + i) * 4;
    } else if (state === 'responding') {
      // Voiced waveform — smoother, rhythmic
      targetH = 4 + Math.abs(Math.sin(vizPhase * 1.4 + i * 0.5)) * 20
               + Math.sin(vizPhase * 3 + i * 1.2) * 4;
    } else if (state === 'alert') {
      // Intense spiking
      targetH = 6 + Math.abs(Math.sin(vizPhase * 3 + i * 0.4)) * 22
               + Math.random() * 12;
    } else {
      targetH = 3;
    }

    // Smooth approach
    vizBars[i] += (targetH - vizBars[i]) * 0.3;
    const bH = Math.max(2, vizBars[i]);
    const x = gap + i * (barW + gap);
    const y = (H - bH) / 2;

    // Glow effect
    ctx.shadowColor = glowColor;
    ctx.shadowBlur = state !== 'idle' ? 8 : 3;

    // Draw bar
    ctx.fillStyle = baseColor + '0.85)';
    ctx.fillRect(x, y, barW, bH);

    // Mirror bottom bar (symmetric waveform)
    ctx.fillStyle = baseColor + '0.35)';
    ctx.fillRect(x, H / 2, barW, bH / 2);
  }

  ctx.shadowBlur = 0;

  // Center line (idle/thinking)
  if (state === 'idle' || state === 'thinking') {
    ctx.strokeStyle = baseColor + '0.2)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, H / 2);
    ctx.lineTo(W, H / 2);
    ctx.stroke();
  }
}

// ── Input handling ───────────────────────────────────────────────
cycleBtn.addEventListener('click', cycleState);

document.addEventListener('keydown', e => {
  if (e.code === 'Space') {
    e.preventDefault();
    cycleState();
  }
  if (e.key === 'a' || e.key === 'A') {
    e.preventDefault();
    setStateByName('alert');
  }
  if (e.key === 'r' || e.key === 'R') {
    e.preventDefault();
    setStateByName('idle');
  }
});

// ── Utilities ────────────────────────────────────────────────────
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Boot ─────────────────────────────────────────────────────────
runBoot();
