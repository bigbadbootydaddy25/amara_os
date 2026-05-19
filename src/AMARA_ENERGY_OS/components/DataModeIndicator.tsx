'use client';

import { motion } from 'framer-motion';
import { useEnergyStore } from '../stores/energy-store';

export function DataModeIndicator() {
  const mode = useEnergyStore((s) => s.dataMode);
  const isDemo = mode === 'DEMO';

  return (
    <div className="pointer-events-none absolute left-1/2 top-3 z-40 -translate-x-1/2">
      <motion.div
        animate={{ opacity: [0.75, 1, 0.75] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
        className="flex items-center gap-2 rounded-full border px-4 py-1"
        style={{
          borderColor:  isDemo ? 'rgba(255,140,0,0.35)' : 'rgba(0,255,136,0.35)',
          background:   isDemo ? 'rgba(255,80,0,0.08)'  : 'rgba(0,200,100,0.08)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background: isDemo ? '#ff8c00' : '#00ff88',
            boxShadow:  isDemo ? '0 0 6px #ff8c00' : '0 0 6px #00ff88',
          }}
        />
        <span
          className="font-mono text-[8px] font-bold uppercase tracking-[0.45em]"
          style={{ color: isDemo ? '#ff8c00' : '#00ff88' }}
        >
          {isDemo ? 'Demo Data Mode' : 'Live Data Mode'}
        </span>
      </motion.div>
    </div>
  );
}
