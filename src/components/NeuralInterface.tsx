'use client';

import { useEffect, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { useAgentStore } from '@/stores/agent-store';
import { AgentPanel } from '@/components/ui/AgentPanel';
import { StatusHUD } from '@/components/ui/StatusHUD';
import { NuclearAlert } from '@/components/ui/NuclearAlert';

// Dynamically import R3F Canvas (no SSR)
const EnergyBrainCanvas = dynamic(() => import('@/components/neural/EnergyBrainCanvas'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div
        className="text-xs tracking-widest uppercase font-mono"
        style={{ color: '#00d4ff44' }}
      >
        Initialising neural field…
      </div>
    </div>
  ),
});

const TICK_INTERVAL_MS = 2800;

export function NeuralInterface() {
  const { tickSimulation, amaraStatus } = useAgentStore();

  // Drive the visual simulation tick
  useEffect(() => {
    tickSimulation(); // first tick immediately
    const id = setInterval(tickSimulation, TICK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [tickSimulation]);

  const isNuclear = amaraStatus === 'nuclear';

  return (
    <div
      className="fixed inset-0 overflow-hidden"
      style={{ background: '#010812' }}
    >
      {/* Nuclear screen tint */}
      {isNuclear && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 z-10 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(255,40,0,0.08) 0%, transparent 60%)',
          }}
        />
      )}

      {/* AMARA wordmark — top center */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-20 text-center pointer-events-none">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.5 }}
        >
          <div
            className="text-[11px] font-black tracking-[0.6em] uppercase"
            style={{
              color: isNuclear ? '#ff4400' : '#00d4ff',
              textShadow: isNuclear
                ? '0 0 20px #ff4400, 0 0 40px #ff440066'
                : '0 0 20px #00d4ff, 0 0 40px #00d4ff44',
              letterSpacing: '0.5em',
            }}
          >
            AMARA
          </div>
          <div className="text-[8px] text-slate-600 tracking-[0.4em] uppercase mt-1">
            Energy Intelligence OS
          </div>
        </motion.div>
      </div>

      {/* Corner grid decorations */}
      <CornerDecoration position="top-left" />
      <CornerDecoration position="top-right" />
      <CornerDecoration position="bottom-left" />
      <CornerDecoration position="bottom-right" />

      {/* Scan line overlay */}
      <div
        className="absolute inset-0 pointer-events-none z-10"
        style={{
          background:
            'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,212,255,0.008) 3px, rgba(0,212,255,0.008) 4px)',
        }}
      />

      {/* Three.js scene */}
      <div className="absolute inset-0 z-0">
        <Suspense fallback={null}>
          <EnergyBrainCanvas />
        </Suspense>
      </div>

      {/* Agent detail panel */}
      <AgentPanel />

      {/* Bottom HUD */}
      <StatusHUD />

      {/* Nuclear alert overlay */}
      <NuclearAlert />

      {/* Instruction hint — fades after 6s */}
      <InitHint />
    </div>
  );
}

function CornerDecoration({ position }: { position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' }) {
  const isTop = position.includes('top');
  const isLeft = position.includes('left');

  return (
    <div
      className={`absolute z-20 pointer-events-none ${isTop ? 'top-4' : 'bottom-20'} ${isLeft ? 'left-4' : 'right-4'}`}
    >
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <path
          d={
            isLeft
              ? isTop
                ? 'M0 16 L0 0 L16 0'
                : 'M0 16 L0 32 L16 32'
              : isTop
                ? 'M32 16 L32 0 L16 0'
                : 'M32 16 L32 32 L16 32'
          }
          stroke="#00d4ff22"
          strokeWidth="1"
          fill="none"
        />
      </svg>
    </div>
  );
}

function InitHint() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1.5, duration: 1 }}
      exit={{ opacity: 0 }}
      className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 pointer-events-none"
    >
      <motion.div
        animate={{ opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 3, repeat: Infinity }}
        className="text-[9px] text-slate-600 tracking-[0.3em] uppercase text-center font-mono"
      >
        Click an agent to inspect · Agents auto-cycle OSINT tasks
      </motion.div>
    </motion.div>
  );
}
