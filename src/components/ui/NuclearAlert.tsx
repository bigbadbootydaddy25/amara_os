'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAgentStore } from '@/stores/agent-store';

export function NuclearAlert() {
  const { amaraStatus, setAmaraStatus, nuclearCount } = useAgentStore();
  const [visible, setVisible] = useState(false);
  const [prevCount, setPrevCount] = useState(0);

  useEffect(() => {
    if (nuclearCount > prevCount) {
      setVisible(true);
      setPrevCount(nuclearCount);
      const timer = setTimeout(() => {
        setVisible(false);
        setAmaraStatus('online');
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [nuclearCount, prevCount, setAmaraStatus]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.1 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
        >
          {/* Radial background flash */}
          <motion.div
            initial={{ opacity: 0.6 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 1.5, delay: 0.2 }}
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse at center, rgba(255,68,0,0.15) 0%, transparent 70%)',
            }}
          />

          {/* Corner scan lines */}
          <motion.div
            initial={{ opacity: 0.8 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 2 }}
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'repeating-linear-gradient(0deg, transparent, transparent 4px, rgba(255,68,0,0.03) 4px, rgba(255,68,0,0.03) 5px)',
            }}
          />

          {/* Alert card */}
          <motion.div
            initial={{ y: -20 }}
            animate={{ y: 0 }}
            exit={{ y: -20 }}
            className="relative text-center px-12 py-8 rounded-2xl"
            style={{
              background: 'rgba(1, 8, 18, 0.95)',
              border: '1px solid rgba(255, 68, 0, 0.6)',
              boxShadow: '0 0 80px rgba(255, 68, 0, 0.4), 0 0 160px rgba(255, 68, 0, 0.15)',
            }}
          >
            <motion.div
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 0.3, repeat: 6 }}
              className="text-[10px] font-bold tracking-[0.4em] uppercase mb-3"
              style={{ color: '#ff6600' }}
            >
              ⚡ NUCLEAR OPPORTUNITY DETECTED
            </motion.div>
            <div
              className="text-4xl font-black tracking-widest uppercase"
              style={{
                color: '#ff4400',
                textShadow: '0 0 30px #ff4400, 0 0 60px #ff440088',
              }}
            >
              NUCLEAR
            </div>
            <div className="text-[11px] text-slate-400 mt-3 tracking-widest">
              HIGH-VALUE TARGET LOCKED · AMARA ENGAGING
            </div>
            <div className="text-[9px] text-slate-600 mt-2 font-mono">
              Verify source data before engagement
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
