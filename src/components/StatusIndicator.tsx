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
  const isCallCaptureEnabled = useAmaraStore((store) => store.isCallCaptureEnabled);
  const callTranscripts = useAmaraStore((store) => store.callTranscripts);
  const { label, tone } = STATE_STYLES[state];

  return (
    <div className="pointer-events-none fixed bottom-8 left-1/2 z-30 flex -translate-x-1/2 flex-col items-center gap-2">
      {isCallCaptureEnabled ? (
        <div className="flex items-center gap-1.5 rounded-full border border-red-400/20 bg-red-900/20 px-2.5 py-1 text-[9px] font-mono uppercase tracking-[0.4em] text-red-300/70">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" />
          Live Call{callTranscripts.length > 0 ? ` · ${callTranscripts.length}` : ''}
        </div>
      ) : null}
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.45em] opacity-30">
        <span className={`relative inline-flex h-2 w-2 ${tone}`}>
          <span className="absolute inset-0 animate-ping rounded-full bg-current opacity-40" />
          <span className="relative rounded-full bg-current" />
        </span>
        <span className={tone}>{label}</span>
      </div>
    </div>
  );
}
