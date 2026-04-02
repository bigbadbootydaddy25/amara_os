'use client';

import { useEffect, useRef } from 'react';
import { AnimationLoop } from '@/canvas/animation-loop';
import { useAmaraStore } from '@/stores/amara-store';
import type { AmaraState } from '@/types';
import { StatusIndicator } from '@/components/StatusIndicator';

const DEMO_SEQUENCE: Array<{ state: AmaraState; duration: number }> = [
  { state: 'idle', duration: 4000 },
  { state: 'listening', duration: 3000 },
  { state: 'thinking', duration: 2500 },
  { state: 'speaking', duration: 5000 },
];

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export function AmaraContainer() {
  const orbCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const avatarCanvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const orbCanvas = orbCanvasRef.current;
    const avatarCanvas = avatarCanvasRef.current;

    if (!orbCanvas || !avatarCanvas) {
      return;
    }

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
    const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE !== 'false';
    if (!demoMode) {
      return;
    }

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

      if (active.state === 'idle') {
        level = 0.04 + (Math.sin(now / 900) + 1) * 0.015;
      }

      if (active.state === 'listening') {
        const progress = clamp(elapsed / active.duration, 0, 1);
        level = clamp(progress * 0.5 + Math.sin(now / 280) * 0.04, 0.02, 0.5);
      }

      if (active.state === 'thinking') {
        level = 0.08 + (Math.sin(now / 180) + 1) * 0.04;
      }

      if (active.state === 'speaking') {
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
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      window.cancelAnimationFrame(audioFrame);
    };
  }, []);

  useEffect(() => {
    let hideCursorTimer: number | undefined;

    const showCursor = () => {
      document.body.classList.add('show-cursor');
      if (hideCursorTimer) {
        window.clearTimeout(hideCursorTimer);
      }
      hideCursorTimer = window.setTimeout(() => {
        document.body.classList.remove('show-cursor');
      }, 2000);
    };

    document.body.classList.remove('show-cursor');
    window.addEventListener('mousemove', showCursor, { passive: true });

    return () => {
      if (hideCursorTimer) {
        window.clearTimeout(hideCursorTimer);
      }
      document.body.classList.remove('show-cursor');
      window.removeEventListener('mousemove', showCursor);
    };
  }, []);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-black">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(18,34,62,0.32),transparent_58%),radial-gradient(circle_at_50%_20%,rgba(0,212,255,0.1),transparent_35%),linear-gradient(180deg,#020409_0%,#04070d_40%,#010204_100%)]" />
      <canvas
        ref={orbCanvasRef}
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      />
      <canvas
        ref={avatarCanvasRef}
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_20%,rgba(0,0,0,0.32)_68%,rgba(0,0,0,0.78)_100%)]" />
      <StatusIndicator />
    </main>
  );
}
