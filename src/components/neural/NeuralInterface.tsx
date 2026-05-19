'use client';

import dynamic from 'next/dynamic';
import { useEffect } from 'react';
import { AgentPanel } from './AgentPanel';
import { StatusHUD } from './StatusHUD';
import { NuclearAlert } from './NuclearAlert';
import { startSimulation, stopSimulation } from '@/lib/neural-simulation';

const NeuralBrainScene = dynamic(
  () => import('./NeuralBrainScene').then((m) => ({ default: m.NeuralBrainScene })),
  { ssr: false },
);

export function NeuralInterface() {
  useEffect(() => {
    startSimulation();
    return () => stopSimulation();
  }, []);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-black">
      {/* deep space gradient backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(5,15,50,0.85)_0%,rgba(1,2,8,0.98)_70%)]" />

      {/* Three.js scene — full screen, behind UI */}
      <NeuralBrainScene />

      {/* vignette */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_30%,rgba(0,0,0,0.45)_75%,rgba(0,0,0,0.82)_100%)]" />

      {/* AMARA label */}
      <div className="pointer-events-none absolute left-1/2 top-8 -translate-x-1/2 text-center">
        <p className="font-mono text-[9px] uppercase tracking-[0.6em] text-white/20">
          AMARA Energy OS
        </p>
        <p className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.4em] text-white/12">
          Neural Brain Interface
        </p>
      </div>

      {/* overlays */}
      <AgentPanel />
      <StatusHUD />
      <NuclearAlert />
    </main>
  );
}
