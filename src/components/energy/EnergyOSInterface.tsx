'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNeuralStore } from '@/stores/neural-store';
import { startSimulation, stopSimulation } from '@/lib/neural-simulation';

// ── Texas border path (viewBox 0 0 900 640) ──────────────────────────────────
const TX = [
  'M 85,22',    // NW panhandle
  'L 315,22',   // NE panhandle
  'L 315,108',  // SE panhandle
  'L 762,108',  // NE Texas
  'L 768,175',
  'L 772,255',
  'L 768,318',
  'L 760,372',
  'L 738,408',  // heading toward Gulf
  'L 705,440',
  'L 665,468',
  'L 618,494',
  'L 558,518',
  'L 495,538',
  'L 432,552',
  'L 372,560',
  'L 315,560',
  'L 278,570',  // Brownsville area
  'L 248,555',
  'L 215,520',  // Rio Grande
  'L 188,480',
  'L 162,438',
  'L 135,392',
  'L 108,346',
  'L 82,296',
  'L 60,245',   // Big Bend
  'L 45,195',
  'L 42,155',   // El Paso
  'L 52,118',
  'L 85,108',   // NM corner
  'Z',
].join(' ');

// Basin sub-region boundaries
const PERMIAN_OUTLINE = 'M 85,175 L 245,175 L 290,340 L 275,490 L 215,520 L 188,480 L 162,438 L 135,392 L 108,346 L 82,296 L 60,245 L 45,195 L 42,155 L 52,118 L 85,108 Z';
const DELAWARE_OUTLINE = 'M 245,175 L 355,175 L 375,330 L 360,490 L 275,490 L 290,340 Z';

// Well pad positions inside Texas
const WELL_PADS: { x: number; y: number; r: number; alert?: boolean; id: string }[] = [
  // Permian Basin (west)
  { x: 138, y: 258, r: 3.8, alert: true,  id: 'W01' },
  { x: 162, y: 298, r: 3.2, id: 'W02' },
  { x: 182, y: 332, r: 4.5, alert: true,  id: 'W03' },
  { x: 158, y: 368, r: 2.8, id: 'W04' },
  { x: 192, y: 395, r: 3.5, alert: true,  id: 'W05' },
  { x: 218, y: 362, r: 3.0, id: 'W06' },
  { x: 205, y: 428, r: 2.5, id: 'W07' },
  { x: 232, y: 408, r: 3.8, alert: true,  id: 'W08' },
  { x: 248, y: 375, r: 3.2, id: 'W09' },
  { x: 268, y: 342, r: 2.8, id: 'W10' },
  // Delaware Basin
  { x: 285, y: 295, r: 4.2, alert: true,  id: 'W11' },
  { x: 308, y: 328, r: 3.5, id: 'W12' },
  { x: 325, y: 362, r: 4.8, alert: true,  id: 'W13' },
  { x: 342, y: 395, r: 3.0, id: 'W14' },
  { x: 318, y: 422, r: 2.8, id: 'W15' },
  // Central Texas
  { x: 438, y: 348, r: 2.5, id: 'W16' },
  { x: 462, y: 382, r: 2.8, id: 'W17' },
  { x: 492, y: 415, r: 3.0, alert: true,  id: 'W18' },
  // Eagle Ford (south-central)
  { x: 405, y: 482, r: 3.2, id: 'W19' },
  { x: 438, y: 498, r: 2.5, id: 'W20' },
  { x: 472, y: 485, r: 3.5, alert: true,  id: 'W21' },
  { x: 505, y: 498, r: 2.8, id: 'W22' },
  // Barnett / Fort Worth
  { x: 568, y: 192, r: 3.5, id: 'W23' },
  { x: 598, y: 218, r: 4.2, alert: true,  id: 'W24' },
  { x: 625, y: 202, r: 2.8, id: 'W25' },
  { x: 648, y: 238, r: 3.0, id: 'W26' },
  { x: 618, y: 255, r: 2.5, id: 'W27' },
  // East Texas
  { x: 668, y: 308, r: 2.2, id: 'W28' },
  { x: 695, y: 342, r: 2.5, id: 'W29' },
  { x: 718, y: 312, r: 2.2, id: 'W30' },
];

const ACTIVE_COUNT = WELL_PADS.length;
const ALERT_COUNT  = WELL_PADS.filter((w) => w.alert).length;

// HUD circle SVG helper
function HUDCircle({ size, label }: { size: number; label: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className="opacity-70">
      <circle cx="50" cy="50" r="46" fill="none" stroke="#00aaff" strokeWidth="0.5" opacity="0.4" />
      <circle cx="50" cy="50" r="38" fill="none" stroke="#00ccff" strokeWidth="0.4" opacity="0.5"
        strokeDasharray="4 2" />
      <circle cx="50" cy="50" r="28" fill="none" stroke="#00aaff" strokeWidth="0.4" opacity="0.4" />
      <circle cx="50" cy="50" r="16" fill="none" stroke="#00ccff" strokeWidth="0.5" opacity="0.6" />
      <circle cx="50" cy="50" r="4"  fill="#00ddff" opacity="0.9" />
      {/* tick marks */}
      {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        const x1 = 50 + 43 * Math.cos(rad);
        const y1 = 50 + 43 * Math.sin(rad);
        const x2 = 50 + 46 * Math.cos(rad);
        const y2 = 50 + 46 * Math.sin(rad);
        return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#00aaff" strokeWidth="0.8" opacity="0.6" />;
      })}
      <text x="50" y="54" textAnchor="middle" fill="#00ccff" fontSize="7" fontFamily="monospace" opacity="0.8">
        {label}
      </text>
    </svg>
  );
}

// Side data panel
function DataPanel({ title, value, unit, bars }: { title: string; value: string; unit: string; bars: number[] }) {
  return (
    <div className="border border-[#ff8c0020] bg-[#0a0c1280] px-3 py-2 backdrop-blur-sm">
      <div className="font-mono text-[8px] uppercase tracking-[0.3em] text-[#ff8c00]/50">{title}</div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className="font-mono text-lg font-bold text-[#ff8c00]">{value}</span>
        <span className="font-mono text-[8px] text-[#ff8c00]/50">{unit}</span>
      </div>
      <div className="mt-1.5 flex items-end gap-0.5" style={{ height: 18 }}>
        {bars.map((h, i) => (
          <div
            key={i}
            className="w-1.5 bg-[#ff8c00]"
            style={{ height: `${h}%`, opacity: 0.3 + h / 150 }}
          />
        ))}
      </div>
    </div>
  );
}

export function EnergyOSInterface() {
  const [tick, setTick] = useState(0);
  const [scanY, setScanY] = useState(0);
  const agents = useNeuralStore((s) => s.agents);
  const latestActivity = useNeuralStore((s) => s.latestActivity);
  const totalNuclear = useNeuralStore((s) => s.totalNuclear);

  useEffect(() => {
    startSimulation();
    return () => stopSimulation();
  }, []);

  // twinkle tick
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1800);
    return () => clearInterval(id);
  }, []);

  // scan line
  useEffect(() => {
    let frame = 0;
    let start: number | null = null;
    const duration = 4000;
    const step = (ts: number) => {
      if (!start) start = ts;
      const elapsed = (ts - start) % duration;
      setScanY(elapsed / duration);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, []);

  const nuclearAgent = agents.find((a) => a.state === 'nuclear');

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#020914]">

      {/* ── deep space gradient ───────────────────────────────────────────── */}
      <div className="pointer-events-none absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 80% 60% at 50% 45%, rgba(0,20,60,0.55) 0%, rgba(2,9,20,0.95) 70%)' }} />

      {/* ── Earth horizon arc ─────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute -top-[280px] left-1/2 -translate-x-1/2"
        style={{ width: '210vw', height: '560px' }}>
        <div className="h-full w-full rounded-full"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(0,40,120,0.20) 0%, transparent 65%)',
            boxShadow: '0 -2px 0 rgba(0,160,255,0.35), 0 -8px 40px rgba(0,100,200,0.18), inset 0 -20px 60px rgba(0,60,160,0.08)',
            border: '1px solid rgba(0,160,255,0.22)',
          }} />
      </div>

      {/* ── background star dust ─────────────────────────────────────────── */}
      <svg className="pointer-events-none absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
        {Array.from({ length: 120 }, (_, i) => {
          const cx = (((i * 137.508) % 100)).toFixed(1);
          const cy = (((i * 97.31 + 13) % 100)).toFixed(1);
          const r  = (0.5 + (i % 5) * 0.3).toFixed(1);
          const op = (0.15 + (i % 7) * 0.07).toFixed(2);
          return <circle key={i} cx={`${cx}%`} cy={`${cy}%`} r={r} fill="#a0c8ff" opacity={op} />;
        })}
      </svg>

      {/* ── main holographic map ──────────────────────────────────────────── */}
      <div className="absolute inset-0 flex items-center justify-center">
        <svg
          viewBox="0 0 900 620"
          className="h-full max-h-screen w-full max-w-screen"
          style={{ maxWidth: '90vw', maxHeight: '85vh' }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* glow filter */}
            <filter id="glow-lg" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="12" result="b1" />
              <feGaussianBlur in="SourceGraphic" stdDeviation="5"  result="b2" />
              <feMerge><feMergeNode in="b1" /><feMergeNode in="b2" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="glow-sm" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b1" />
              <feMerge><feMergeNode in="b1" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="glow-pt" x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>

            {/* clip path */}
            <clipPath id="tx-clip"><path d={TX} /></clipPath>

            {/* grid pattern */}
            <pattern id="grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
              <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#00aaff" strokeWidth="0.35" opacity="1" />
            </pattern>

            {/* scan gradient */}
            <linearGradient id="scan-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00ccff" stopOpacity="0" />
              <stop offset="45%" stopColor="#00ccff" stopOpacity="0" />
              <stop offset="50%" stopColor="#00ccff" stopOpacity="0.18" />
              <stop offset="55%" stopColor="#00ccff" stopOpacity="0" />
              <stop offset="100%" stopColor="#00ccff" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* grid fill inside Texas */}
          <rect
            x="0" y="0" width="900" height="620"
            fill="url(#grid)"
            clipPath="url(#tx-clip)"
            opacity="0.28"
          />

          {/* interior fill — dark tinted navy */}
          <path d={TX} fill="rgba(0,30,80,0.22)" />

          {/* basin sub-regions */}
          <path d={PERMIAN_OUTLINE}  fill="none" stroke="#00aaff" strokeWidth="0.6" strokeDasharray="6 4" opacity="0.30" />
          <path d={DELAWARE_OUTLINE} fill="none" stroke="#00aaff" strokeWidth="0.6" strokeDasharray="6 4" opacity="0.25" />

          {/* Texas border — fat outer glow */}
          <path d={TX} fill="none" stroke="#0044cc" strokeWidth="18" opacity="0.18" filter="url(#glow-lg)" />
          {/* Texas border — mid glow */}
          <path d={TX} fill="none" stroke="#0088ff" strokeWidth="6"  opacity="0.50" filter="url(#glow-sm)" />
          {/* Texas border — crisp line */}
          <path d={TX} fill="none" stroke="#00d4ff" strokeWidth="1.5" opacity="0.95" />
          {/* Texas border — bright inner edge */}
          <path d={TX} fill="none" stroke="#ffffff"  strokeWidth="0.5" opacity="0.55" />

          {/* scan line (animates top→bottom inside Texas) */}
          <rect
            x="0" y="0" width="900" height="620"
            fill="url(#scan-grad)"
            clipPath="url(#tx-clip)"
            transform={`translate(0, ${(scanY * 2 - 0.5) * 620})`}
          />

          {/* well pad data points */}
          {WELL_PADS.map((pad, idx) => {
            const phase = (tick + idx) % 3;
            const bright = pad.alert && phase === 0;
            return (
              <g key={pad.id} filter="url(#glow-pt)">
                {/* outer ring for alerts */}
                {pad.alert && (
                  <circle cx={pad.x} cy={pad.y} r={pad.r * 2.8}
                    fill="none" stroke={bright ? '#ffffff' : '#00ddff'}
                    strokeWidth="0.6" opacity={bright ? 0.7 : 0.25} />
                )}
                {/* glow blob */}
                <circle cx={pad.x} cy={pad.y} r={pad.r * 1.8}
                  fill={pad.alert ? '#00aaff' : '#004488'}
                  opacity={bright ? 0.55 : 0.22} />
                {/* core dot */}
                <circle cx={pad.x} cy={pad.y} r={pad.r}
                  fill={bright ? '#ffffff' : (pad.alert ? '#00eeff' : '#0088cc')}
                  opacity={bright ? 1.0 : 0.78} />
              </g>
            );
          })}

          {/* basin labels */}
          {[
            { label: 'PERMIAN BASIN',  x: 172, y: 460, anchor: 'middle' },
            { label: 'DELAWARE BASIN', x: 490, y: 358, anchor: 'middle' },
            { label: 'FORT WORTH',     x: 630, y: 175, anchor: 'middle' },
            { label: 'EAGLE FORD',     x: 455, y: 520, anchor: 'middle' },
          ].map(({ label, x, y, anchor }) => (
            <text key={label} x={x} y={y} textAnchor={anchor as 'middle'}
              fill="white" fontSize="13" fontFamily="monospace"
              fontWeight="700" letterSpacing="3" opacity="0.82"
              style={{ textShadow: '0 0 12px rgba(0,180,255,0.8)' }}>
              {label}
            </text>
          ))}

          {/* connection lines from edges to points of interest */}
          {[
            { x1: 820, y1: 220, x2: 648, y2: 238 },
            { x1: 820, y1: 380, x2: 718, y2: 342 },
            { x1: 45,  y1: 520, x2: 162, y2: 438 },
          ].map((l, i) => (
            <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke="#00aaff" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.25" />
          ))}
        </svg>
      </div>

      {/* ── left side panels ──────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 flex flex-col gap-1.5 p-4">
        <DataPanel title="Wellhead Pressure" value="4,820" unit="PSI"
          bars={[45, 62, 55, 70, 68, 75, 60, 82, 78, 65, 88, 72]} />
        <DataPanel title="Production Rate" value="12.4" unit="MBBL/D"
          bars={[38, 52, 48, 65, 72, 58, 80, 75, 62, 88, 70, 66]} />
        <DataPanel title="Gas-Oil Ratio" value="1,240" unit="SCF/BBL"
          bars={[55, 60, 58, 65, 70, 62, 68, 75, 72, 78, 65, 80]} />
        <DataPanel title="Water Cut" value="28.3" unit="%"
          bars={[30, 35, 28, 42, 38, 45, 40, 48, 35, 52, 44, 50]} />
        {/* sonar circle */}
        <div className="mt-2 flex justify-center">
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}>
            <HUDCircle size={90} label="SCAN" />
          </motion.div>
        </div>
      </div>

      {/* ── right side panels ─────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 flex flex-col gap-1.5 p-4">
        <DataPanel title="Reservoir Temp" value="218" unit="°F"
          bars={[60, 65, 62, 70, 75, 68, 72, 80, 76, 82, 78, 85]} />
        <DataPanel title="Casing Integrity" value="99.1" unit="%"
          bars={[90, 92, 91, 95, 93, 96, 94, 97, 95, 98, 96, 99]} />
        <DataPanel title="Injection Rate" value="8,200" unit="BPD"
          bars={[40, 48, 45, 55, 52, 60, 58, 65, 62, 70, 68, 72]} />
        <DataPanel title="NPT Events" value={String(ALERT_COUNT)} unit="ACTIVE"
          bars={[20, 35, 28, 42, 38, 50, 45, 35, 55, 40, 48, 60]} />
        <div className="mt-2 flex justify-center">
          <motion.div animate={{ rotate: -360 }} transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}>
            <HUDCircle size={90} label="OPS" />
          </motion.div>
        </div>
      </div>

      {/* ── bottom-left HUD circles ───────────────────────────────────────── */}
      <div className="pointer-events-none absolute bottom-16 left-4 flex items-end gap-3">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}>
          <HUDCircle size={72} label="GEO" />
        </motion.div>
        <motion.div animate={{ rotate: -360 }} transition={{ duration: 14, repeat: Infinity, ease: 'linear' }}>
          <HUDCircle size={108} label="BASIN" />
        </motion.div>
      </div>

      {/* ── bottom-right HUD ─────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute bottom-16 right-4">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 16, repeat: Infinity, ease: 'linear' }}>
          <HUDCircle size={108} label="TOPO" />
        </motion.div>
      </div>

      {/* ── bottom status bar ─────────────────────────────────────────────── */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center gap-8 border-t border-[#00aaff]/20 bg-[#010810]/80 px-6 py-2.5 backdrop-blur-md">
        {/* NPT alerts */}
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/45">NPT Alerts:</span>
          <motion.span
            key={ALERT_COUNT + totalNuclear}
            initial={{ scale: 1.4, color: '#ff5500' }}
            animate={{ scale: 1.0, color: '#ffffff' }}
            transition={{ duration: 0.4 }}
            className="font-mono text-2xl font-black text-white"
          >
            {ALERT_COUNT + totalNuclear}
          </motion.span>
        </div>

        <div className="h-5 w-px bg-[#00aaff]/20" />

        {/* active well pads */}
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/45">Active Well Pads</span>
          <span className="font-mono text-2xl font-black text-white">{ACTIVE_COUNT}</span>
        </div>

        <div className="h-5 w-px bg-[#00aaff]/20" />

        {/* agent status dots */}
        <div className="flex items-center gap-2">
          {agents.map((a) => {
            const col: Record<string, string> = {
              idle: '#ffffff30', searching: '#00ccff', processing: '#ffd000',
              verified: '#00ff88', nuclear: '#ff5500',
            };
            return (
              <div key={a.id}
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: col[a.state] ?? '#ffffff30', boxShadow: a.state !== 'idle' ? `0 0 5px ${col[a.state]}` : 'none' }}
                title={`${a.name}: ${a.state}`}
              />
            );
          })}
        </div>

        <div className="h-5 w-px bg-[#00aaff]/20" />

        {/* latest activity */}
        <AnimatePresence mode="wait">
          <motion.p key={latestActivity}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
            className="flex-1 truncate font-mono text-[9px] uppercase tracking-widest text-[#00aaff]/55">
            {latestActivity}
          </motion.p>
        </AnimatePresence>

        {/* system time */}
        <div className="shrink-0 font-mono text-[9px] uppercase tracking-widest text-white/30">
          AMARA ENERGY OS · SYS ONLINE
        </div>
      </div>

      {/* ── nuclear alert overlay ─────────────────────────────────────────── */}
      <AnimatePresence>
        {nuclearAgent && (
          <motion.div
            key="nuclear"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center"
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at center, rgba(255,60,0,0.18) 0%, transparent 60%)',
            }} />
            <motion.div
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative rounded border border-orange-500/50 bg-black/85 px-10 py-6 text-center backdrop-blur-xl"
              style={{ boxShadow: '0 0 60px rgba(255,80,0,0.3)' }}
            >
              <motion.p animate={{ opacity: [1, 0, 1] }} transition={{ duration: 0.6, repeat: Infinity }}
                className="font-mono text-[9px] font-bold uppercase tracking-[0.5em] text-orange-400">
                ⚠ Critical Alert
              </motion.p>
              <p className="mt-1 font-mono text-2xl font-black tracking-widest text-orange-300">
                {nuclearAgent.name}
              </p>
              <p className="mt-1.5 font-mono text-[10px] tracking-widest text-white/50">
                NPT EVENT — IMMEDIATE RESPONSE REQUIRED
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
