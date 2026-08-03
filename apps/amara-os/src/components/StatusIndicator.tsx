'use client';

import { useAmaraStore } from '@/stores/amara-store';
import type { AmaraState } from '@/types';

const STATE_STYLES: Record<AmaraState, { label: string; tone: string }> = {
  idle: { label: 'IDLE', tone: 'text-gray-500' },
  listening: { label: 'LISTENING...', tone: 'text-cyan-400' },
  thinking: { label: 'THINKING...', tone: 'text-blue-400' },
  speaking: { label: 'SPEAKING', tone: 'text-cyan-300' },
};

export function StatusIndicator() {
  const state = useAmaraStore((store) => store.state);
  const { label, tone } = STATE_STYLES[state];

  return (
    <div className="pointer-events-none fixed bottom-8 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 text-xs font-mono uppercase tracking-[0.45em] opacity-30">
      <span className={`relative inline-flex h-2 w-2 ${tone}`}>
        <span className="absolute inset-0 animate-ping rounded-full bg-current opacity-40" />
        <span className="relative rounded-full bg-current" />
      </span>
      <span className={tone}>{label}</span>
    </div>
  );
}
