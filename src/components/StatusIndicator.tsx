'use client';

import { useAmaraStore } from '@/stores/amara-store';
import type { AmaraState } from '@/types';

const STATE_CONFIG: Record<AmaraState, { label: string; dotColor: string }> = {
  idle:      { label: 'IDLE',       dotColor: 'rgba(255,255,255,0.35)' },
  listening: { label: 'LISTENING',  dotColor: '#00d4ff' },
  thinking:  { label: 'PROCESSING', dotColor: '#00d4ff' },
  speaking:  { label: 'SPEAKING',   dotColor: '#00d4ff' },
};

export function StatusIndicator() {
  const state = useAmaraStore((s) => s.state);
  const { label, dotColor } = STATE_CONFIG[state];

  return (
    <div
      className="pointer-events-none fixed bottom-8 left-1/2 z-30 flex -translate-x-1/2 flex-col items-center gap-2"
      style={{ fontFamily: "'Share Tech Mono', monospace" }}
    >
      {/* AMARA name */}
      <span
        style={{
          color: '#00d4ff',
          fontSize: '2rem',
          letterSpacing: '0.55em',
          lineHeight: 1,
          textShadow: '0 0 18px rgba(0,212,255,0.45)',
        }}
      >
        AMARA
      </span>

      {/* Status row */}
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          color: '#ffffff',
          fontSize: '0.62rem',
          letterSpacing: '0.45em',
          opacity: 0.55,
        }}
      >
        <span
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: dotColor,
            boxShadow: state !== 'idle' ? `0 0 6px ${dotColor}` : 'none',
          }}
        />
        {label}
      </span>
    </div>
  );
}
