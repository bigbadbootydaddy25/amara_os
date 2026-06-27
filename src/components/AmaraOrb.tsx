'use client';

import { useEffect, useRef } from 'react';
import { ThreeOrbRenderer } from '@/canvas/threejs-orb';
import { useAmaraStore } from '@/stores/amara-store';

export function AmaraOrb() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rendererRef = useRef<ThreeOrbRenderer | null>(null);
  const frameRef = useRef<number>(0);
  const lastTimeRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const w = window.innerWidth;
    const h = window.innerHeight;
    const orb = new ThreeOrbRenderer(canvas, w, h);
    rendererRef.current = orb;

    // Expose global API for external system integration
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAState = (
      s: 'idle' | 'listening' | 'processing' | 'speaking',
    ) => {
      // Map 'processing' → internal 'thinking'
      const mapped = s === 'processing' ? 'thinking' : s;
      useAmaraStore.getState().setState(mapped as 'idle' | 'listening' | 'thinking' | 'speaking');
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).triggerWakeWord = () => {
      orb.triggerParticleBurst();
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAOutputAudio = (node: AudioNode) => {
      const ctx = node.context as AudioContext;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      node.connect(analyser);
      orb.setOutputAnalyser(analyser);
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAMicAudio = (node: AudioNode) => {
      const ctx = node.context as AudioContext;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      node.connect(analyser);
      orb.setMicAnalyser(analyser);
    };

    const onResize = () => {
      orb.resize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', onResize, { passive: true });

    let running = true;
    const tick = (t: number) => {
      if (!running) return;
      const dt = lastTimeRef.current ? (t - lastTimeRef.current) / 1000 : 0.016;
      lastTimeRef.current = t;

      const { state } = useAmaraStore.getState();
      orb.setState(state);
      orb.update(dt);
      orb.render();

      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);

    return () => {
      running = false;
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener('resize', onResize);
      orb.dispose();
      rendererRef.current = null;
      delete // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAState;
      delete // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).triggerWakeWord;
      delete // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAOutputAudio;
      delete // eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).setAMARAMicAudio;
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    />
  );
}
