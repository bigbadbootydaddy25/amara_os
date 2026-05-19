'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { EnergyMap }           from './components/EnergyMap';
import { WellDrawer }          from './components/WellDrawer';
import { LayerToggles }        from './components/LayerToggles';
import { AgentActivityPanel }  from './components/AgentActivityPanel';
import { DataModeIndicator }   from './components/DataModeIndicator';
import { useEnergyStore }      from './stores/energy-store';
import { startEnergySimulation, stopEnergySimulation } from './stores/energy-store';

// ── HUD circle SVG ────────────────────────────────────────────────────────────

function HUDCircle({ size, label }: { size: number; label: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className="opacity-65">
      <circle cx="50" cy="50" r="46" fill="none" stroke="#00aaff" strokeWidth="0.5" opacity="0.35"/>
      <circle cx="50" cy="50" r="38" fill="none" stroke="#00ccff" strokeWidth="0.4" opacity="0.45" strokeDasharray="4 2"/>
      <circle cx="50" cy="50" r="28" fill="none" stroke="#00aaff" strokeWidth="0.4" opacity="0.35"/>
      <circle cx="50" cy="50" r="16" fill="none" stroke="#00ccff" strokeWidth="0.5" opacity="0.55"/>
      <circle cx="50" cy="50" r="3.5" fill="#00ddff" opacity="0.85"/>
      {[0,30,60,90,120,150,180,210,240,270,300,330].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        return (
          <line key={deg}
            x1={50 + 43 * Math.cos(rad)} y1={50 + 43 * Math.sin(rad)}
            x2={50 + 46 * Math.cos(rad)} y2={50 + 46 * Math.sin(rad)}
            stroke="#00aaff" strokeWidth="0.8" opacity="0.55"
          />
        );
      })}
      <text x="50" y="54" textAnchor="middle" fill="#00ccff" fontSize="7"
        fontFamily="monospace" opacity="0.75">{label}</text>
    </svg>
  );
}

// ── Side data panel ───────────────────────────────────────────────────────────

function DataPanel({ title, value, unit, bars }: {
  title: string; value: string; unit: string; bars: number[];
}) {
  return (
    <div className="border border-[#ff8c0018] bg-[#0a0c1275] px-3 py-2 backdrop-blur-sm">
      <div className="font-mono text-[7px] uppercase tracking-[0.3em] text-[#ff8c00]/45">{title}</div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className="font-mono text-base font-bold text-[#ff8c00]">{value}</span>
        <span className="font-mono text-[7px] text-[#ff8c00]/45">{unit}</span>
      </div>
      <div className="mt-1.5 flex items-end gap-0.5" style={{ height: 14 }}>
        {bars.map((h, i) => (
          <div key={i} className="w-1 bg-[#ff8c00]" style={{ height: `${h}%`, opacity: 0.28 + h / 140 }}/>
        ))}
      </div>
    </div>
  );
}

// ── spinning HUD wrapper ───────────────────────────────────────────────────────

function SpinHUD({ size, label, dir = 1, speed = 20 }: {
  size: number; label: string; dir?: number; speed?: number;
}) {
  const [angle, setAngle] = useState(0);
  useEffect(() => {
    let raf = 0;
    let prev = performance.now();
    const step = (ts: number) => {
      const dt = (ts - prev) / 1000;
      prev = ts;
      setAngle((a) => a + dir * (360 / speed) * dt);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [dir, speed]);
  return (
    <div style={{ transform: `rotate(${angle}deg)` }}>
      <HUDCircle size={size} label={label} />
    </div>
  );
}

// ── main app ──────────────────────────────────────────────────────────────────

export function EnergyOSApp() {
  const latestActivity = useEnergyStore((s) => s.latestActivity);
  const agents         = useEnergyStore((s) => s.agents);
  const wells          = useEnergyStore((s) => s.wells);

  useEffect(() => {
    startEnergySimulation();
    return () => stopEnergySimulation();
  }, []);

  const nptCount   = wells.filter((w) => w.nptRisk === 'High' || w.nptRisk === 'Critical').length;
  const activeCount = wells.filter((w) => w.productionStatus === 'Producing').length;
  const criticalAgent = agents.find((a) => a.status === 'critical');

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#020914]">

      {/* ── deep space gradient ─────────────────────────────────────────── */}
      <div className="pointer-events-none absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 80% 60% at 50% 45%, rgba(0,20,60,0.50) 0%, rgba(2,9,20,0.95) 70%)' }}/>

      {/* ── Earth horizon ───────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute -top-[280px] left-1/2 -translate-x-1/2"
        style={{ width: '210vw', height: '560px' }}>
        <div className="h-full w-full rounded-full"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(0,40,120,0.18) 0%, transparent 65%)',
            boxShadow: '0 -2px 0 rgba(0,160,255,0.30), 0 -8px 40px rgba(0,100,200,0.14), inset 0 -20px 60px rgba(0,60,160,0.06)',
            border: '1px solid rgba(0,160,255,0.18)',
          }}/>
      </div>

      {/* ── star dust ───────────────────────────────────────────────────── */}
      <svg className="pointer-events-none absolute inset-0 h-full w-full">
        {Array.from({ length: 100 }, (_, i) => (
          <circle key={i}
            cx={`${((i * 137.5) % 100).toFixed(1)}%`}
            cy={`${((i * 97.3 + 13) % 100).toFixed(1)}%`}
            r={(0.5 + (i % 5) * 0.28).toFixed(1)}
            fill="#a0c8ff"
            opacity={((0.12 + (i % 7) * 0.06)).toFixed(2)}
          />
        ))}
      </svg>

      {/* ── Three.js-style holographic map (pure SVG) ───────────────────── */}
      <EnergyMap />

      {/* ── left data panels ────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 flex flex-col gap-1.5 p-4">
        <DataPanel title="Wellhead Pressure" value="4,820" unit="PSI"   bars={[45,62,55,70,68,75,60,82,78,65,88,72]}/>
        <DataPanel title="Production Rate"   value="12.4"  unit="MBBL/D" bars={[38,52,48,65,72,58,80,75,62,88,70,66]}/>
        <DataPanel title="Gas-Oil Ratio"     value="1,240" unit="SCF/BBL" bars={[55,60,58,65,70,62,68,75,72,78,65,80]}/>
        <DataPanel title="Water Cut"         value="28.3"  unit="%"      bars={[30,35,28,42,38,45,40,48,35,52,44,50]}/>
        <div className="mt-2 flex justify-center">
          <SpinHUD size={88} label="GEO" dir={1} speed={22}/>
        </div>
      </div>

      {/* ── right data panels ───────────────────────────────────────────── */}
      <div className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 flex flex-col gap-1.5 p-4">
        <DataPanel title="Reservoir Temp"   value="218"   unit="°F"     bars={[60,65,62,70,75,68,72,80,76,82,78,85]}/>
        <DataPanel title="Casing Integrity" value="99.1"  unit="%"      bars={[90,92,91,95,93,96,94,97,95,98,96,99]}/>
        <DataPanel title="Injection Rate"   value="8,200" unit="BPD"    bars={[40,48,45,55,52,60,58,65,62,70,68,72]}/>
        <DataPanel title="NPT Events"       value={String(nptCount)} unit="ACTIVE" bars={[20,35,28,42,38,50,45,35,55,40,48,60]}/>
        <div className="mt-2 flex justify-center">
          <SpinHUD size={88} label="OPS" dir={-1} speed={14}/>
        </div>
      </div>

      {/* ── bottom-left HUD circles ─────────────────────────────────────── */}
      <div className="pointer-events-none absolute bottom-16 left-4 flex items-end gap-3">
        <SpinHUD size={70}  label="GEO"   dir={1}  speed={20}/>
        <SpinHUD size={106} label="BASIN" dir={-1} speed={16}/>
      </div>

      {/* ── bottom-right HUD ────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute bottom-16 right-4">
        <SpinHUD size={106} label="TOPO" dir={1} speed={18}/>
      </div>

      {/* ── data mode badge ─────────────────────────────────────────────── */}
      <DataModeIndicator />

      {/* ── title top-left ───────────────────────────────────────────────── */}
      <div className="pointer-events-none absolute left-4 top-3 z-30">
        <p className="font-mono text-[9px] font-bold uppercase tracking-[0.5em] text-[#00aaff]/60">
          AMARA Energy OS
        </p>
      </div>

      {/* ── layer toggles ───────────────────────────────────────────────── */}
      <LayerToggles />

      {/* ── agent activity panel ────────────────────────────────────────── */}
      <AgentActivityPanel />

      {/* ── well drawer ─────────────────────────────────────────────────── */}
      <WellDrawer />

      {/* ── critical agent alert flash ──────────────────────────────────── */}
      <AnimatePresence>
        {criticalAgent && (
          <motion.div key="crit"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0"
              style={{ background: 'radial-gradient(circle at center, rgba(255,60,0,0.15) 0%, transparent 55%)' }}/>
            <motion.div
              initial={{ scale: 0.88, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative rounded border border-orange-500/45 bg-black/85 px-10 py-5 text-center backdrop-blur-xl"
              style={{ boxShadow: '0 0 55px rgba(255,80,0,0.25)' }}>
              <motion.p animate={{ opacity: [1,0,1] }} transition={{ duration: 0.6, repeat: Infinity }}
                className="font-mono text-[9px] font-bold uppercase tracking-[0.5em] text-orange-400">
                ⚠ Critical Alert
              </motion.p>
              <p className="mt-1 font-mono text-xl font-black tracking-widest text-orange-300">
                {criticalAgent.name}
              </p>
              <p className="mt-1 font-mono text-[10px] tracking-widest text-white/45">
                {criticalAgent.finding.replace('[DEMO] ', '')}
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── bottom status bar ───────────────────────────────────────────── */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex items-center gap-6 border-t border-[#00aaff]/18 bg-[#010810]/80 px-5 py-2 backdrop-blur-md">
        <div className="flex items-baseline gap-2 shrink-0">
          <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/38">NPT Alerts:</span>
          <span className="font-mono text-xl font-black text-white">{nptCount}</span>
        </div>

        <div className="h-4 w-px shrink-0 bg-[#00aaff]/18"/>

        <div className="flex items-baseline gap-2 shrink-0">
          <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/38">Active Well Pads</span>
          <span className="font-mono text-xl font-black text-white">{activeCount}</span>
        </div>

        <div className="h-4 w-px shrink-0 bg-[#00aaff]/18"/>

        {/* agent status micro-dots */}
        <div className="flex shrink-0 items-center gap-1.5">
          {agents.map((a) => {
            const c: Record<string, string> = {
              idle:'#ffffff28', scanning:'#00ccff', analyzing:'#ffd000', flagged:'#ff8c00', critical:'#ff3300',
            };
            return (
              <div key={a.id} className="h-1.5 w-1.5 rounded-full"
                style={{ background: c[a.status], boxShadow: a.status !== 'idle' ? `0 0 4px ${c[a.status]}` : 'none' }}
                title={`${a.name}: ${a.status}`}/>
            );
          })}
        </div>

        <div className="h-4 w-px shrink-0 bg-[#00aaff]/18"/>

        {/* activity ticker */}
        <AnimatePresence mode="wait">
          <motion.p key={latestActivity}
            initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.18 }}
            className="flex-1 truncate font-mono text-[9px] uppercase tracking-widest text-[#00aaff]/50">
            {latestActivity}
          </motion.p>
        </AnimatePresence>

        <div className="shrink-0 font-mono text-[8px] uppercase tracking-widest text-white/22">
          AMARA Energy OS · Demo Mode
        </div>
      </div>
    </main>
  );
}
