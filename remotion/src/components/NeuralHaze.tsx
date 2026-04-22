import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { seededRandom } from '../utils/math';
import { SCENE_1_END } from '../data/amaraScript';

// Radial neural lines emanating from behind AMARA's face — extremely restrained
const LINE_COUNT = 16;
const FACE_CX = 0.5;
const FACE_CY = 0.36;

interface NeuralLine {
  x1n: number; y1n: number;
  x2n: number; y2n: number;
  phase: number;
}

const LINES: NeuralLine[] = Array.from({ length: LINE_COUNT }, (_, i) => {
  const angle = (Math.PI * 2 * i) / LINE_COUNT + seededRandom(i * 7) * 0.38;
  const r1 = 0.055 + seededRandom(i * 13) * 0.055;
  const r2 = 0.13 + seededRandom(i * 17) * 0.115;
  return {
    x1n: FACE_CX + Math.cos(angle) * r1,
    y1n: FACE_CY + Math.sin(angle) * r1 * 0.62,
    x2n: FACE_CX + Math.cos(angle) * r2,
    y2n: FACE_CY + Math.sin(angle) * r2 * 0.62,
    phase: seededRandom(i * 23) * Math.PI * 2,
  };
});

export const NeuralHaze: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const emerge = interpolate(
    frame,
    [SCENE_1_END - 20, SCENE_1_END + 40],
    [0, 1],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  if (emerge <= 0.01) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <svg
        width={width}
        height={height}
        style={{ position: 'absolute', inset: 0 }}
      >
        <defs>
          <filter id="neuralBlur">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        {LINES.map((ln, i) => {
          const flicker =
            0.38 +
            Math.sin(frame * 0.10 + ln.phase) * 0.32 +
            Math.cos(frame * 0.15 + ln.phase * 1.8) * 0.18;
          const opacity = Math.max(0, flicker) * emerge * 0.20;
          return (
            <line
              key={i}
              x1={ln.x1n * width}
              y1={ln.y1n * height}
              x2={ln.x2n * width}
              y2={ln.y2n * height}
              stroke={`rgba(80, 158, 255, ${opacity})`}
              strokeWidth="0.85"
              filter="url(#neuralBlur)"
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
