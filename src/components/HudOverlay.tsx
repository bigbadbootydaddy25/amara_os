'use client';

import { useEffect, useState } from 'react';
import { useAmaraStore } from '@/stores/amara-store';

export function HudOverlay() {
  const transcript = useAmaraStore((s) => s.transcript);
  const response = useAmaraStore((s) => s.response);
  const state = useAmaraStore((s) => s.state);
  const [time, setTime] = useState('');
  const [date, setDate] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString('en-GB', { hour12: false }));
      setDate(
        now
          .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
          .toUpperCase(),
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  const showTranscript = !!transcript && state !== 'idle';
  const showResponse = !!response && (state === 'thinking' || state === 'speaking');

  return (
    <div className="pointer-events-none absolute inset-0 z-20" aria-hidden="true">
      {/* Subtle scan lines */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,255,0.011) 2px, rgba(0,212,255,0.011) 3px)',
        }}
      />

      {/* Moving scan sweep */}
      <div
        className="absolute left-0 right-0 h-px opacity-[0.07]"
        style={{
          background: 'linear-gradient(90deg, transparent 0%, rgba(0,212,255,0.9) 50%, transparent 100%)',
          animation: 'amara-scan 12s linear infinite',
        }}
      />

      {/* Corner brackets */}
      <div className="absolute left-5 top-5 h-8 w-8 border-l-2 border-t-2 border-cyan-400/25" />
      <div className="absolute right-5 top-5 h-8 w-8 border-r-2 border-t-2 border-cyan-400/25" />
      <div className="absolute bottom-5 left-5 h-8 w-8 border-b-2 border-l-2 border-violet-400/22" />
      <div className="absolute bottom-5 right-5 h-8 w-8 border-b-2 border-r-2 border-violet-400/22" />

      {/* Top divider line */}
      <div className="absolute left-14 right-14 top-14 h-px bg-gradient-to-r from-transparent via-cyan-400/18 to-transparent" />

      {/* Bottom divider line */}
      <div className="absolute bottom-14 left-14 right-14 h-px bg-gradient-to-r from-transparent via-violet-400/14 to-transparent" />

      {/* AMARA branding — top left */}
      <div className="absolute left-14 top-6 font-mono">
        <div className="text-[10px] tracking-[0.55em] text-cyan-400/52">AMARA</div>
        <div className="mt-0.5 text-[8px] tracking-[0.28em] text-cyan-400/26">AI INTERFACE</div>
      </div>

      {/* Time + date — top right */}
      <div className="absolute right-14 top-6 text-right font-mono">
        <div className="text-[10px] tracking-[0.32em] text-cyan-400/40">{time}</div>
        <div className="mt-0.5 text-[8px] tracking-[0.18em] text-cyan-400/22">{date}</div>
      </div>

      {/* Decorative tick marks along the top line */}
      <div className="absolute left-14 top-14 flex gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-1 w-px bg-cyan-400/18"
          />
        ))}
      </div>
      <div className="absolute right-14 top-14 flex gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-1 w-px bg-cyan-400/18"
          />
        ))}
      </div>

      {/* User transcript — lower left */}
      <div
        className={`absolute bottom-20 left-14 max-w-[26%] font-mono transition-opacity duration-500 ${
          showTranscript ? 'opacity-100' : 'opacity-0'
        }`}
      >
        <div className="mb-1 text-[8px] tracking-[0.42em] text-violet-400/42 uppercase">Input</div>
        <div
          className="text-[10px] leading-snug text-violet-100/40"
          style={{
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {transcript}
        </div>
      </div>

      {/* AMARA response — lower right */}
      <div
        className={`absolute bottom-20 right-14 max-w-[26%] text-right font-mono transition-opacity duration-500 ${
          showResponse ? 'opacity-100' : 'opacity-0'
        }`}
      >
        <div className="mb-1 text-[8px] tracking-[0.42em] text-cyan-400/42 uppercase">Output</div>
        <div
          className="text-[10px] leading-snug text-cyan-100/36"
          style={{
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {response}
        </div>
      </div>
    </div>
  );
}
