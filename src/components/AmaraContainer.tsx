'use client';

import { useEffect, useRef, useState } from 'react';
import { AnimationLoop } from '@/canvas/animation-loop';
import { useConversation } from '@/hooks/useConversation';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useVoiceOutput } from '@/hooks/useVoiceOutput';
import { useAmaraStore } from '@/stores/amara-store';
import type { AmaraState } from '@/types';
import { StatusIndicator } from '@/components/StatusIndicator';

const DEMO_SEQUENCE: Array<{ state: AmaraState; duration: number }> = [
  { state: 'idle', duration: 4000 },
  { state: 'listening', duration: 3000 },
  { state: 'thinking', duration: 2500 },
  { state: 'speaking', duration: 5000 },
];

const AGENT_LABELS: Record<string, string> = {
  nova: 'Nova · Research',
  hunter: 'Hunter · Deals',
  geo: 'Geo · Markets',
  amara: '',
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function AmaraContainer() {
  const orbCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const avatarCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isActivated, setIsActivated] = useState(process.env.NEXT_PUBLIC_DEMO_MODE === 'true');
  const [isActivating, setIsActivating] = useState(false);
  const state = useAmaraStore((store) => store.state);
  const error = useAmaraStore((store) => store.error);
  const isOnline = useAmaraStore((store) => store.isOnline);
  const isVoiceSupported = useAmaraStore((store) => store.isVoiceSupported);
  const transcript = useAmaraStore((store) => store.transcript);
  const interimTranscript = useAmaraStore((store) => store.interimTranscript);
  const response = useAmaraStore((store) => store.response);
  const activeAgent = useAmaraStore((store) => store.activeAgent);
  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
  const ollamaEnabled = process.env.NEXT_PUBLIC_OLLAMA_ENABLED === 'true';
  const { primeAudio, speak, stopSpeaking } = useVoiceOutput();
  const { cancelPending, handleSpeechComplete } = useConversation({ speak });
  const { isSupported, startListening, stopListening } = useVoiceInput({
    enabled: !isDemoMode && isActivated,
    onSpeechComplete: handleSpeechComplete,
  });

  useEffect(() => {
    const orbCanvas = orbCanvasRef.current;
    const avatarCanvas = avatarCanvasRef.current;
    if (!orbCanvas || !avatarCanvas) return;

    const loop = new AnimationLoop(avatarCanvas, orbCanvas);
    loop.start();

    const onResize = () => loop.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      loop.stop();
    };
  }, []);

  useEffect(() => {
    const store = useAmaraStore.getState();
    store.setOnline(typeof navigator === 'undefined' ? true : navigator.onLine);

    const handleOnline = () => store.setOnline(true);
    const handleOffline = () => store.setOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (!isDemoMode) return;

    const store = useAmaraStore;
    let sequenceIndex = 0;
    let phaseStart = performance.now();
    let timeoutId: number | undefined;
    let audioFrame = 0;

    const advance = () => {
      sequenceIndex = (sequenceIndex + 1) % DEMO_SEQUENCE.length;
      phaseStart = performance.now();
      store.getState().setState(DEMO_SEQUENCE[sequenceIndex].state);
      timeoutId = window.setTimeout(advance, DEMO_SEQUENCE[sequenceIndex].duration);
    };

    store.getState().setState(DEMO_SEQUENCE[0].state);
    store.getState().setAudioLevel(0.08);
    timeoutId = window.setTimeout(advance, DEMO_SEQUENCE[0].duration);

    const updateAudio = () => {
      const now = performance.now();
      const active = DEMO_SEQUENCE[sequenceIndex];
      const elapsed = now - phaseStart;
      let level = 0.06;

      if (active.state === 'idle') level = 0.04 + (Math.sin(now / 900) + 1) * 0.015;
      if (active.state === 'listening') {
        const progress = clamp(elapsed / active.duration, 0, 1);
        level = clamp(progress * 0.5 + Math.sin(now / 280) * 0.04, 0.02, 0.5);
      }
      if (active.state === 'thinking') level = 0.08 + (Math.sin(now / 180) + 1) * 0.04;
      if (active.state === 'speaking') {
        const baseFreq = Date.now() / 200;
        const amplitude =
          Math.sin(baseFreq) * 0.3 +
          Math.sin(baseFreq * 2.7) * 0.2 +
          Math.sin(baseFreq * 4.3) * 0.1 +
          Math.random() * 0.15;
        level = clamp(amplitude + 0.3 + (Math.sin(now / 220) + 1) * 0.12, 0, 1);
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

  useEffect(() => {
    if (isDemoMode || !isActivated || !isVoiceSupported) return;

    if (state === 'speaking' || state === 'thinking') {
      stopListening();
      return;
    }

    if (state === 'idle') {
      const timer = window.setTimeout(() => {
        void startListening();
      }, 500);
      return () => window.clearTimeout(timer);
    }
  }, [isActivated, isDemoMode, isVoiceSupported, startListening, state, stopListening]);

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
      store.setError('Voice not supported in this browser. Use Chrome or Safari.');
      return;
    }

    setIsActivated(true);

    void (async () => {
      try {
        await primeAudio();

        if (navigator.mediaDevices?.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach((track) => track.stop());
        }

        store.setVoiceSupported(true);
        store.setError(null);
        store.setState('idle');
        await startListening();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Activation failed';
        store.setState('idle');
        store.setError(
          /permission|denied|notallowed/i.test(message)
            ? 'Microphone access needed. Allow microphone permission to activate AMARA.'
            : 'Unable to activate AMARA right now.',
        );
      } finally {
        setIsActivating(false);
      }
    })();
  };

  const agentLabel = AGENT_LABELS[activeAgent] ?? '';
  const displayText =
    state === 'listening'
      ? interimTranscript || transcript
      : state === 'thinking' || state === 'speaking'
        ? response
        : '';

  return (
    <main
      className="relative h-[100dvh] w-screen overflow-hidden bg-black"
      style={{ paddingTop: 'env(safe-area-inset-top)', paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(18,34,62,0.32),transparent_58%),radial-gradient(circle_at_50%_20%,rgba(0,212,255,0.1),transparent_35%),linear-gradient(180deg,#020409_0%,#04070d_40%,#010204_100%)]" />
      <canvas ref={orbCanvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <canvas
        ref={avatarCanvasRef}
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_20%,rgba(0,0,0,0.32)_68%,rgba(0,0,0,0.78)_100%)]" />

      {/* Offline badge */}
      {!isOnline ? (
        <div className="pointer-events-none fixed right-4 top-4 z-30 rounded-full border border-red-500/25 bg-red-500/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.34em] text-red-200/90">
          {ollamaEnabled ? 'Offline · Ollama' : 'Offline'}
        </div>
      ) : null}

      {/* Active agent badge */}
      {agentLabel && state !== 'idle' ? (
        <div className="pointer-events-none fixed left-4 top-4 z-30 rounded-full border border-cyan-400/20 bg-cyan-400/5 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-300/70">
          {agentLabel}
        </div>
      ) : null}

      {/* Error display */}
      {error ? (
        <div className="pointer-events-none fixed left-1/2 top-8 z-30 max-w-sm -translate-x-1/2 rounded-full border border-white/10 bg-black/45 px-4 py-2 text-center text-[10px] font-mono uppercase tracking-[0.24em] text-white/72 backdrop-blur-md">
          {error}
        </div>
      ) : null}

      {/* Transcript / response overlay */}
      {displayText && !error ? (
        <div className="pointer-events-none fixed bottom-20 left-1/2 z-20 w-[90vw] max-w-lg -translate-x-1/2 text-center">
          <p
            className={`text-sm font-mono leading-relaxed tracking-wide ${
              state === 'listening'
                ? 'text-cyan-200/60'
                : state === 'thinking'
                  ? 'text-white/40'
                  : 'text-white/75'
            }`}
          >
            {displayText}
          </p>
        </div>
      ) : null}

      {/* Activation button (desktop click + mobile touch) */}
      {!isDemoMode && !isActivated ? (
        <button
          type="button"
          onClick={activateAmara}
          onTouchEnd={(e) => {
            e.preventDefault();
            activateAmara();
          }}
          className="absolute inset-0 z-40 flex items-center justify-center bg-black/25 text-center transition-opacity duration-500 touch-none"
        >
          <span className="rounded-full border border-cyan-400/25 bg-black/45 px-6 py-3 text-xs font-mono uppercase tracking-[0.42em] text-cyan-100/85 backdrop-blur-md">
            {isActivating ? 'Activating AMARA…' : 'Tap to activate AMARA'}
          </span>
        </button>
      ) : null}

      <StatusIndicator />
    </main>
  );
}
