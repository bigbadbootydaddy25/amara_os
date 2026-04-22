import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { seededRandom } from '../utils/math';

interface Particle {
  id: number;
  x: number;      // normalized 0–1
  y: number;      // normalized 0–1
  size: number;   // px
  driftSpeed: number;
  phase: number;
  opacity: number;
}

const COUNT = 44;

const PARTICLES: Particle[] = Array.from({ length: COUNT }, (_, i) => ({
  id: i,
  x: seededRandom(i * 17 + 1),
  y: seededRandom(i * 13 + 2),
  size: 0.9 + seededRandom(i * 11 + 3) * 2.4,
  driftSpeed: 0.055 + seededRandom(i * 7 + 4) * 0.11,
  phase: seededRandom(i * 23 + 5) * Math.PI * 2,
  opacity: 0.07 + seededRandom(i * 19 + 6) * 0.17,
}));

export const Particles: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const globalFade = interpolate(frame, [25, 85], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  if (globalFade <= 0) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {PARTICLES.map((p) => {
        const t = frame * p.driftSpeed + p.phase;
        const driftX = Math.sin(t * 0.68) * 30 + Math.cos(t * 0.29) * 14;
        // Slow upward drift, wrapped
        const rawY = p.y * height + Math.cos(t * 0.52) * 22 - frame * p.driftSpeed * 0.38;
        const py = ((rawY % height) + height) % height;
        const px = p.x * width + driftX;

        const flicker = 0.55 + Math.sin(frame * 0.17 + p.phase * 3.1) * 0.45;
        const opacity = p.opacity * globalFade * Math.max(0, flicker);

        return (
          <div
            key={p.id}
            style={{
              position: 'absolute',
              left: px,
              top: py,
              width: p.size,
              height: p.size,
              borderRadius: '50%',
              background: `rgba(110, 172, 255, ${opacity})`,
              boxShadow: `0 0 ${p.size * 3.5}px rgba(70, 150, 255, ${opacity * 0.55})`,
              transform: 'translate(-50%, -50%)',
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
