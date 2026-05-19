'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNeuralStore, AGENT_CONFIG } from '@/stores/neural-store';

export function NuclearAlert() {
  const nuclearId = useNeuralStore((s) => s.nuclearAgentId);
  const clearNuclear = useNeuralStore((s) => s.clearNuclear);

  const cfg = AGENT_CONFIG.find((c) => c.id === nuclearId) ?? null;

  useEffect(() => {
    if (!nuclearId) return;
    const t = setTimeout(clearNuclear, 4000);
    return () => clearTimeout(t);
  }, [nuclearId, clearNuclear]);

  return (
    <AnimatePresence>
      {nuclearId && cfg && (
        <motion.div
          key={nuclearId + '-alert'}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center"
        >
          {/* radial flash */}
          <motion.div
            initial={{ opacity: 0.9 }}
            animate={{ opacity: [0.9, 0.2, 0.7, 0.1, 0.5, 0] }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(circle at center, rgba(255,80,0,0.55) 0%, rgba(255,40,0,0.18) 45%, transparent 70%)',
            }}
          />

          {/* scanlines */}
          <div
            className="absolute inset-0 opacity-20"
            style={{
              backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.4) 2px, rgba(0,0,0,0.4) 4px)',
            }}
          />

          {/* alert card */}
          <motion.div
            initial={{ scale: 0.82, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 420, damping: 28 }}
            className="relative z-10 flex flex-col items-center rounded-lg border border-orange-500/40 bg-black/80 px-10 py-7 text-center backdrop-blur-xl"
            style={{ boxShadow: '0 0 60px rgba(255,80,0,0.35), 0 0 120px rgba(255,40,0,0.15)' }}
          >
            <motion.p
              animate={{ opacity: [1, 0, 1, 0, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              className="font-mono text-[10px] font-bold uppercase tracking-[0.5em] text-orange-400"
            >
              ⚠ NUCLEAR
            </motion.p>
            <p className="mt-2 font-mono text-3xl font-black tracking-widest text-orange-300">
              {cfg.name}
            </p>
            <p className="mt-2 max-w-[240px] font-mono text-[11px] leading-relaxed text-white/55">
              Priority target confirmed — initiate acquisition protocol
            </p>
            <div className="mt-4 h-px w-full bg-orange-500/30" />
            <p className="mt-3 font-mono text-[9px] uppercase tracking-[0.4em] text-orange-500/60">
              Alert auto-dismisses
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
