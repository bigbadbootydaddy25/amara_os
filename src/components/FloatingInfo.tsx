'use client';

import { AnimatePresence, motion } from 'framer-motion';
import type { DealCard } from '@/types';

// Floating response text — fades in left side, dissolves 3s after speaking ends
interface FloatingTextProps {
  text: string;
  visible: boolean;
}

export function FloatingText({ text, visible }: FloatingTextProps) {
  return (
    <AnimatePresence>
      {visible && text && (
        <motion.div
          key="floating-text"
          className="pointer-events-none absolute left-[6%] top-1/2 z-20 max-w-[28vw] -translate-y-1/2"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -10 }}
          transition={{ duration: 0.4 }}
        >
          <p
            className="text-sm leading-relaxed"
            style={{
              color: 'rgba(255,255,255,0.88)',
              fontFamily: 'var(--font-mono, monospace)',
              letterSpacing: '0.02em',
              textShadow: '0 0 20px rgba(0,212,255,0.2)',
            }}
          >
            {text}
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Floating deal card — appears right side, amber glow, YES/NO actions
interface DealCardDisplayProps {
  deal: DealCard | null;
  onYes: () => void;
  onNo: () => void;
}

export function DealCardDisplay({ deal, onYes, onNo }: DealCardDisplayProps) {
  return (
    <AnimatePresence>
      {deal && (
        <motion.div
          key="deal-card"
          className="absolute right-[6%] top-1/2 z-20 -translate-y-1/2"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 10 }}
          transition={{ duration: 0.5 }}
        >
          <div
            style={{
              color: 'rgba(255,184,0,0.95)',
              textShadow: '0 0 15px rgba(255,184,0,0.3)',
              fontFamily: 'var(--font-mono, monospace)',
              maxWidth: '22vw',
            }}
          >
            <p className="text-xs font-bold uppercase tracking-widest mb-2 opacity-60">Deal</p>
            <p className="text-sm font-semibold leading-snug mb-1">{deal.address}</p>
            <p className="text-xs opacity-80">
              Score: {deal.score} | List: ${deal.price?.toLocaleString() ?? '?'} | MAO: ${deal.mao?.toLocaleString() ?? '?'}
            </p>
            {deal.buyer && (
              <p className="text-xs opacity-70 mt-1">Buyer: {deal.buyer}</p>
            )}
            <div className="flex gap-8 mt-4">
              <button
                onClick={onYes}
                className="text-sm font-mono tracking-widest uppercase opacity-80 hover:opacity-100 transition-opacity"
                style={{ color: 'rgba(0,212,255,0.9)', textShadow: '0 0 10px rgba(0,212,255,0.4)' }}
              >
                YES
              </button>
              <button
                onClick={onNo}
                className="text-sm font-mono tracking-widest uppercase opacity-80 hover:opacity-100 transition-opacity"
                style={{ color: 'rgba(255,255,255,0.6)' }}
              >
                NO
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Mic indicator — bottom center, pulsing dot only
interface MicIndicatorProps {
  active: boolean;
}

export function MicIndicator({ active }: MicIndicatorProps) {
  return (
    <AnimatePresence>
      {active && (
        <motion.div
          key="mic-dot"
          className="pointer-events-none absolute bottom-8 left-1/2 z-20 -translate-x-1/2"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className="h-2 w-2 rounded-full"
            style={{ background: 'rgba(0,212,255,0.9)', boxShadow: '0 0 8px rgba(0,212,255,0.6)' }}
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
