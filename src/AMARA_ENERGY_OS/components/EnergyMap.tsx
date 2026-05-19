'use client';

import { useEffect, useRef, useState } from 'react';
import { useEnergyStore } from '../stores/energy-store';
import { MOCK_PIPELINES, MOCK_LEASES, MOCK_UNITS } from '../data/wells.mock';

// ── Texas border path (viewBox 0 0 900 640) ──────────────────────────────────
const TX = [
  'M 85,22',  'L 315,22', 'L 315,108', 'L 762,108',
  'L 768,175', 'L 772,255', 'L 768,318', 'L 760,372',
  'L 738,408', 'L 705,440', 'L 665,468', 'L 618,494',
  'L 558,518', 'L 495,538', 'L 432,552', 'L 372,560',
  'L 315,560', 'L 278,570', 'L 248,555',
  'L 215,520', 'L 188,480', 'L 162,438', 'L 135,392',
  'L 108,346', 'L 82,296', 'L 60,245', 'L 45,195',
  'L 42,155', 'L 52,118', 'L 85,108', 'Z',
].join(' ');

const BASIN_BOUNDARY = {
  permian: 'M 85,175 L 245,175 L 290,340 L 275,490 L 215,520 L 188,480 L 162,438 L 135,392 L 108,346 L 82,296 L 60,245 L 45,195 L 42,155 L 52,118 L 85,108 Z',
  delaware:'M 245,175 L 355,175 L 375,330 L 360,490 L 275,490 L 290,340 Z',
};

const BASIN_LABELS = [
  { text: 'PERMIAN BASIN',  x: 172, y: 460 },
  { text: 'DELAWARE BASIN', x: 490, y: 355 },
  { text: 'FORT WORTH',     x: 630, y: 175 },
  { text: 'EAGLE FORD',     x: 455, y: 520 },
  { text: 'EAST TEXAS',     x: 698, y: 325 },
];

// dot color logic
function wellDotColor(
  well: import('../types').WellPad,
  layers: import('../types').LayerState,
): { fill: string; glow: string; ring: boolean } {
  if (layers.nptAlerts && (well.nptRisk === 'Critical' || well.nptRisk === 'High')) {
    return { fill: '#ff3300', glow: '#ff3300', ring: true };
  }
  if (layers.titleRisk && well.titleFlags.length > 0) {
    return { fill: '#ff8c00', glow: '#ff8c00', ring: true };
  }
  if (layers.curativeNeeded && well.curativeFlags.length > 0) {
    return { fill: '#ffd000', glow: '#ffd000', ring: true };
  }
  if (well.nptRisk === 'Critical') return { fill: '#ff3300', glow: '#ff3300', ring: true };
  if (well.nptRisk === 'High')     return { fill: '#ff8c00', glow: '#ff8c00', ring: true };
  if (well.productionStatus === 'Producing')     return { fill: '#00ddff', glow: '#00aaff', ring: false };
  if (well.productionStatus === 'Shut-In')       return { fill: '#ffd000', glow: '#aa8800', ring: false };
  if (well.productionStatus === 'DUC')           return { fill: '#aa55ff', glow: '#7733cc', ring: false };
  return { fill: '#00aaff', glow: '#0066cc', ring: false };
}

function wellVisible(
  well: import('../types').WellPad,
  layers: import('../types').LayerState,
): boolean {
  if (!layers.wells) return false;
  const statusFiltersActive = layers.producing || layers.shutIn || layers.duc;
  if (statusFiltersActive) {
    if (layers.producing && well.productionStatus === 'Producing') return true;
    if (layers.shutIn    && well.productionStatus === 'Shut-In')   return true;
    if (layers.duc       && well.productionStatus === 'DUC')       return true;
    return false;
  }
  return true;
}

export function EnergyMap() {
  const wells      = useEnergyStore((s) => s.wells);
  const layers     = useEnergyStore((s) => s.layers);
  const selectedId = useEnergyStore((s) => s.selectedWellId);
  const selectWell = useEnergyStore((s) => s.selectWell);

  const [tick, setTick]   = useState(0);
  const [scanY, setScanY] = useState(0);

  // twinkle tick
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1800);
    return () => clearInterval(id);
  }, []);

  // scan line
  useEffect(() => {
    let raf = 0;
    let start: number | null = null;
    const dur = 4000;
    const step = (ts: number) => {
      if (!start) start = ts;
      setScanY(((ts - start) % dur) / dur);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <svg
        viewBox="0 0 900 640"
        className="h-full max-h-screen w-full max-w-screen"
        style={{ maxWidth: '90vw', maxHeight: '85vh' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* glow filters */}
          <filter id="glow-lg" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="12" result="b1"/>
            <feGaussianBlur in="SourceGraphic" stdDeviation="5"  result="b2"/>
            <feMerge><feMergeNode in="b1"/><feMergeNode in="b2"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="glow-sm" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b1"/>
            <feMerge><feMergeNode in="b1"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="glow-pt" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="glow-red" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>

          {/* clip & patterns */}
          <clipPath id="tx-clip"><path d={TX}/></clipPath>
          <pattern id="grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#00aaff" strokeWidth="0.35" opacity="1"/>
          </pattern>
          <linearGradient id="scan-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#00ccff" stopOpacity="0"/>
            <stop offset="47%"  stopColor="#00ccff" stopOpacity="0"/>
            <stop offset="50%"  stopColor="#00ccff" stopOpacity="0.20"/>
            <stop offset="53%"  stopColor="#00ccff" stopOpacity="0"/>
            <stop offset="100%" stopColor="#00ccff" stopOpacity="0"/>
          </linearGradient>
        </defs>

        {/* grid fill */}
        <rect x="0" y="0" width="900" height="640" fill="url(#grid)" clipPath="url(#tx-clip)" opacity="0.28"/>

        {/* interior dark tint */}
        <path d={TX} fill="rgba(0,30,80,0.22)"/>

        {/* basin sub-regions */}
        <path d={BASIN_BOUNDARY.permian}  fill="none" stroke="#00aaff" strokeWidth="0.6" strokeDasharray="6 4" opacity="0.28"/>
        <path d={BASIN_BOUNDARY.delaware} fill="none" stroke="#00aaff" strokeWidth="0.6" strokeDasharray="6 4" opacity="0.22"/>

        {/* leases layer */}
        {layers.leases && MOCK_LEASES.map((l) => (
          <g key={l.id}>
            <polygon points={l.points} fill="rgba(255,140,0,0.08)" stroke="#ff8c00" strokeWidth="0.8" strokeDasharray="4 3" opacity="0.55"/>
          </g>
        ))}

        {/* units layer */}
        {layers.units && MOCK_UNITS.map((u) => (
          <g key={u.id}>
            <polygon points={u.points} fill="rgba(0,170,255,0.06)" stroke="#00aaff" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.45"/>
          </g>
        ))}

        {/* pipelines layer */}
        {layers.pipelines && MOCK_PIPELINES.map((p, i) => (
          <g key={i}>
            <path d={p.d} fill="none" stroke="#ff8c00" strokeWidth="1.5" strokeDasharray="8 4" opacity="0.45" filter="url(#glow-sm)"/>
            <path d={p.d} fill="none" stroke="#ff8c00" strokeWidth="0.5" opacity="0.80"/>
          </g>
        ))}

        {/* Texas border — outer glow */}
        <path d={TX} fill="none" stroke="#0044cc" strokeWidth="18" opacity="0.18" filter="url(#glow-lg)"/>
        {/* Texas border — mid glow */}
        <path d={TX} fill="none" stroke="#0088ff" strokeWidth="6"  opacity="0.50" filter="url(#glow-sm)"/>
        {/* Texas border — crisp */}
        <path d={TX} fill="none" stroke="#00d4ff" strokeWidth="1.5" opacity="0.95"/>
        {/* Texas border — white inner edge */}
        <path d={TX} fill="none" stroke="#ffffff"  strokeWidth="0.5" opacity="0.55"/>

        {/* scan line */}
        <rect x="0" y="0" width="900" height="640"
          fill="url(#scan-grad)"
          clipPath="url(#tx-clip)"
          transform={`translate(0, ${(scanY * 2 - 0.5) * 640})`}
        />

        {/* well pads */}
        {layers.wells && wells.map((well, idx) => {
          if (!wellVisible(well, layers)) return null;
          const { fill, glow, ring } = wellDotColor(well, layers);
          const phase  = (tick + idx) % 4;
          const bright = ring && phase === 0;
          const sel    = well.id === selectedId;
          return (
            <g
              key={well.id}
              style={{ cursor: 'pointer' }}
              onClick={() => selectWell(sel ? null : well.id)}
              filter="url(#glow-pt)"
            >
              {/* selected highlight ring */}
              {sel && (
                <circle cx={well.x} cy={well.y} r={12}
                  fill="none" stroke="#ffffff" strokeWidth="1" opacity="0.6"/>
              )}
              {/* alert outer ring */}
              {ring && (
                <circle cx={well.x} cy={well.y} r={bright ? 9 : 7}
                  fill="none" stroke={glow}
                  strokeWidth={bright ? 1.2 : 0.8}
                  opacity={bright ? 0.90 : 0.35}
                  filter="url(#glow-red)"
                />
              )}
              {/* glow blob */}
              <circle cx={well.x} cy={well.y} r={5}
                fill={fill}
                opacity={bright ? 0.50 : 0.20}
              />
              {/* core dot */}
              <circle cx={well.x} cy={well.y} r={sel ? 4.5 : 3}
                fill={bright ? '#ffffff' : fill}
                opacity={bright ? 1.0 : 0.88}
              />
            </g>
          );
        })}

        {/* basin labels */}
        {BASIN_LABELS.map(({ text, x, y }) => (
          <text key={text} x={x} y={y} textAnchor="middle"
            fill="white" fontSize="13" fontFamily="monospace"
            fontWeight="700" letterSpacing="3" opacity="0.80">
            {text}
          </text>
        ))}

        {/* connection lines from edges */}
        {[
          { x1: 820, y1: 220, x2: 648, y2: 238 },
          { x1: 820, y1: 380, x2: 718, y2: 342 },
          { x1: 45,  y1: 520, x2: 162, y2: 438 },
        ].map((l, i) => (
          <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
            stroke="#00aaff" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.22"/>
        ))}

        {/* well ID tooltip on hover (SVG title for native tooltip) */}
        {layers.wells && wells.map((well) => wellVisible(well, layers) && (
          <title key={well.id + '-title'}>{`${well.name} — ${well.apiNumber}`}</title>
        ))}
      </svg>
    </div>
  );
}
