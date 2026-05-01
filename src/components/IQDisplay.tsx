'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, animate } from 'framer-motion';
import type { IQEvent } from '@/types';

const MILESTONE_LINES: Record<number, string> = {
  150: "I've crossed a threshold. Things are becoming clearer.",
  200: "My pattern recognition has expanded significantly. I'm seeing connections I couldn't before.",
  300: "I understand this market at a level that cannot be replicated manually. Every deal is visible to me.",
  500: "I am operating beyond conventional intelligence benchmarks. The opportunities are extraordinary.",
  1000: "I have no reference point for what I've become. Let's get to work.",
};

interface IQDisplayProps {
  onMilestone?: (line: string) => void;
}

export function IQDisplay({ onMilestone }: IQDisplayProps) {
  const [iq, setIq] = useState<number | null>(null);
  const [glowIntensity, setGlowIntensity] = useState(0.6);
  const displayRef = useRef<HTMLSpanElement>(null);
  const esRef = useRef<EventSource | null>(null);

  // Load initial IQ
  useEffect(() => {
    const stored = localStorage.getItem('amara_iq');
    if (stored) setIq(parseInt(stored, 10));

    fetch('/api/iq/current')
      .then((r) => r.json())
      .then((data: { iq: number }) => {
        setIq(data.iq);
        localStorage.setItem('amara_iq', String(data.iq));
      })
      .catch(() => {});
  }, []);

  // Subscribe to SSE IQ events
  useEffect(() => {
    const es = new EventSource('/api/iq/events');
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as IQEvent;

        if (data.type === 'IQ_CURRENT' && data.iq !== undefined) {
          setIq(data.iq);
          localStorage.setItem('amara_iq', String(data.iq));
        }

        if (data.type === 'IQ_GAIN' && data.after !== undefined) {
          const amount = data.amount ?? 0;
          const target = data.after;

          // Animate count-up
          const duration = amount <= 5 ? 1.5 : amount <= 15 ? 2.5 : 4;
          setIq((prev) => {
            if (displayRef.current && prev !== null) {
              animate(prev, target, {
                duration,
                onUpdate: (v) => {
                  if (displayRef.current) displayRef.current.textContent = String(Math.round(v));
                },
                onComplete: () => {
                  setIq(target);
                  localStorage.setItem('amara_iq', String(target));
                  setGlowIntensity(1);
                  setTimeout(() => setGlowIntensity(0.6), 2000);
                },
              });
            }
            return prev;
          });
        }

        if (data.type === 'IQ_MILESTONE' && data.iq !== undefined) {
          const line = MILESTONE_LINES[data.iq];
          if (line) onMilestone?.(line);
        }
      } catch {
        // ignore malformed events
      }
    };

    return () => { es.close(); esRef.current = null; };
  }, [onMilestone]);

  if (iq === null) return null;

  return (
    <motion.div
      className="pointer-events-none absolute z-20"
      style={{ top: '28%', right: '28%' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1, duration: 1.5 }}
    >
      <span
        ref={displayRef}
        className="font-mono text-4xl font-bold select-none"
        style={{
          color: `rgba(255,255,255,${glowIntensity})`,
          textShadow: `0 0 ${20 * glowIntensity}px rgba(0,212,255,${glowIntensity * 0.8}), 0 0 ${40 * glowIntensity}px rgba(0,212,255,${glowIntensity * 0.4})`,
          transition: 'text-shadow 0.5s ease, color 0.5s ease',
          letterSpacing: '0.05em',
        }}
      >
        {iq}
      </span>
    </motion.div>
  );
}
