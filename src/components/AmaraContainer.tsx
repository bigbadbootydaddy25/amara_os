'use client';

import { useEffect, useState } from 'react';
import { AmaraOrb } from '@/components/AmaraOrb';
import { StatusIndicator } from '@/components/StatusIndicator';
import { useConversation } from '@/hooks/useConversation';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useVoiceOutput } from '@/hooks/useVoiceOutput';
import { useAmaraStore } from '@/stores/amara-store';
import type { AmaraState } from '@/types';

const DEMO_SEQUENCE: Array<{ state: AmaraState; duration: number }> = [
  { state: 'idle', duration: 4000 },
  { state: 'listening', duration: 3000 },
  { state: 'thinking', duration: 2500 },
  { state: 'speaking', duration: 5000 },
];

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function AmaraContainer() {
  const [isActivated, setIsActivated] = useState(process.env.NEXT_PUBLIC_DEMO_MODE === 'true');
  const [isActivating, setIsActivating] = useState(false);
  const state = useAmaraStore((s) => s.state);
  const error = useAmaraStore((s) => s.error);
  const isOnline = useAmaraStore((s) => s.isOnline);
  const isVoiceSupported = useAmaraStore((s) => s.isVoiceSupported);
  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
  const { primeAudio, speak, stopSpeaking } = useVoiceOutput();
  const { cancelPending, handleSpeechComplete } = useConversation({ speak });
  const { isSupported, startListening, stopListening } = useVoiceInput({
    enabled: !isDemoMode && isActivated,
    onSpeechComplete: handleSpeechComplete,
  });

  // Online/offline tracking
  useEffect(() => {
    const store = useAmaraStore.getState();
    store.setOnline(typeof navigator === 'undefined' ? true : navigator.onLine);
    const up = () => store.setOnline(true);
    const down = () => store.setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);

  // Demo mode: cycle states + synthetic audio level
  useEffect(() => {
    if (!isDemoMode) return;
    const store = useAmaraStore;
    let seqIdx = 0;
    let phaseStart = performance.now();
    let timeoutId: number | undefined;
    let audioFrame: number;

    const advance = () => {
      seqIdx = (seqIdx + 1) % DEMO_SEQUENCE.length;
      phaseStart = performance.now();
      store.getState().setState(DEMO_SEQUENCE[seqIdx].state);
      timeoutId = window.setTimeout(advance, DEMO_SEQUENCE[seqIdx].duration);
    };
    store.getState().setState(DEMO_SEQUENCE[0].state);
    store.getState().setAudioLevel(0.08);
    timeoutId = window.setTimeout(advance, DEMO_SEQUENCE[0].duration);

    const updateAudio = () => {
      const now = performance.now();
      const active = DEMO_SEQUENCE[seqIdx];
      const elapsed = now - phaseStart;
      let level = 0.06;

      if (active.state === 'idle') {
        level = 0.04 + (Math.sin(now / 900) + 1) * 0.015;
      } else if (active.state === 'listening') {
        const progress = clamp(elapsed / active.duration, 0, 1);
        level = clamp(progress * 0.5 + Math.sin(now / 280) * 0.04, 0.02, 0.5);
      } else if (active.state === 'thinking') {
        level = 0.08 + (Math.sin(now / 180) + 1) * 0.04;
      } else if (active.state === 'speaking') {
        const baseFreq = Date.now() / 200;
        const amplitude =
          Math.sin(baseFreq) * 0.3 +
          Math.sin(baseFreq * 2.7) * 0.2 +
          Math.sin(baseFreq * 4.3) * 0.1 +
          Math.random() * 0.15;
        const cadence = (Math.sin(now / 220) + 1) * 0.12;
        level = clamp(amplitude + 0.3 + cadence, 0, 1);
      }

      store.getState().setAudioLevel(level);
      audioFrame = window.requestAnimationFrame(updateAudio);
    };
    audioFrame = window.requestAnimationFrame(updateAudio);

    return () => {
      if (timeoutId) window.clearTimeout(timeoutId);
      window.cancelAnimationFrame(audioFrame);
    };
  }, [isDemoMode]);

  // Hide cursor after inactivity
  useEffect(() => {
    let hideCursorTimer: number | undefined;
    const showCursor = () => {
      document.body.classList.add('show-cursor');
      if (hideCursorTimer) window.clearTimeout(hideCursorTimer);
      hideCursorTimer = window.setTimeout(() => {
        document.body.classList.remove('show-cursor');
      }, 2000);
    };
    document.body.classList.remove('show-cursor');
    window.addEventListener('mousemove', showCursor, { passive: true });
    return () => {
      if (hideCursorTimer) window.clearTimeout(hideCursorTimer);
      document.body.classList.remove('show-cursor');
      window.removeEventListener('mousemove', showCursor);
    };
  }, []);

  // Voice listening state machine
  useEffect(() => {
    if (isDemoMode || !isActivated || !isVoiceSupported) return;
    if (state === 'speaking' || state === 'thinking') {
      stopListening();
      return;
    }
    if (state === 'idle') {
      const timer = window.setTimeout(() => { void startListening(); }, 500);
      return () => { window.clearTimeout(timer); };
    }
  }, [isActivated, isDemoMode, isVoiceSupported, startListening, state, stopListening]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening();
      stopSpeaking();
      cancelPending();
    };
  }, [cancelPending, stopListening, stopSpeaking]);

  const activateAmara = () => {
    if (isActivating || isDemoMode) return;
    setIsActivating(true);
    const store = useAmaraStore.getState();

    if (!isSupported) {
      setIsActivated(true);
      setIsActivating(false);
      store.setVoiceSupported(false);
      store.setError('Voice not supported in this browser. Use Chrome.');
      return;
    }

    setIsActivated(true);
    void (async () => {
      try {
        await primeAudio();
        if (navigator.mediaDevices?.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach((t) => t.stop());
        }
        store.setVoiceSupported(true);
        store.setError(null);
        store.setState('idle');
        await startListening();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Activation failed';
        store.setState('idle');
        store.setError(
          /permission|denied|notallowed/i.test(msg)
            ? 'Microphone access needed. Allow microphone permission to activate AMARA.'
            : 'Unable to activate AMARA right now.',
        );
      } finally {
        setIsActivating(false);
      }
    })();
  };

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-black">
      {/* Three.js orb canvas */}
      <AmaraOrb />

      {/* Subtle vignette */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_38%,rgba(0,0,0,0.45)_72%,rgba(0,0,0,0.85)_100%)]" />

      {/* Offline badge */}
      {!isOnline ? (
        <div className="pointer-events-none fixed right-6 top-6 z-30 rounded-full border border-red-500/25 bg-red-500/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.34em] text-red-200/90">
          Offline
        </div>
      ) : null}

      {/* Error banner */}
      {error ? (
        <div
          className="pointer-events-none fixed left-1/2 top-8 z-30 max-w-xl -translate-x-1/2 rounded-full border border-white/10 bg-black/45 px-4 py-2 text-center text-[10px] uppercase tracking-[0.24em] text-white/72 backdrop-blur-md"
          style={{ fontFamily: "'Share Tech Mono', monospace" }}
        >
          {error}
        </div>
      ) : null}

      {/* Activation overlay */}
      {!isDemoMode && !isActivated ? (
        <button
          type="button"
          onClick={activateAmara}
          className="absolute inset-0 z-40 flex items-center justify-center bg-black/30 text-center transition-opacity duration-500"
        >
          <span
            className="rounded-full border border-cyan-400/25 bg-black/45 px-6 py-3 text-xs uppercase tracking-[0.42em] text-cyan-100/85 backdrop-blur-md"
            style={{ fontFamily: "'Share Tech Mono', monospace" }}
          >
            {isActivating ? 'Activating AMARA…' : 'Touch to activate AMARA'}
          </span>
        </button>
      ) : null}

      {/* AMARA name + status */}
      <StatusIndicator />
    </main>
  );
}
