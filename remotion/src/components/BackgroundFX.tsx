import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { SCENE_1_END, SCENE_3_START } from '../data/amaraScript';

export const BackgroundFX: React.FC = () => {
  const frame = useCurrentFrame();

  const ambientIn = interpolate(frame, [10, SCENE_1_END], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  // Slow breathe on the ambient glow
  const breathe = Math.sin(frame * 0.022) * 0.07 + 0.93;

  // Scene 3: authority glow surge
  const authorityBrightness = interpolate(
    frame,
    [SCENE_3_START, SCENE_3_START + 80],
    [1, 1.38],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  const ambientOpacity = ambientIn * breathe * authorityBrightness;

  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {/* Primary deep-blue ambient ellipse behind AMARA */}
      <AbsoluteFill
        style={{
          opacity: clamp(ambientOpacity * 0.72, 0, 1),
          background:
            'radial-gradient(ellipse 58% 72% at 50% 47%, rgba(12, 36, 96, 0.60) 0%, rgba(6, 18, 52, 0.28) 52%, transparent 100%)',
        }}
      />
      {/* Cooler, narrower upper bloom (face area) */}
      <AbsoluteFill
        style={{
          opacity: clamp(ambientOpacity * 0.38, 0, 1),
          background:
            'radial-gradient(ellipse 38% 32% at 50% 24%, rgba(24, 72, 200, 0.20) 0%, transparent 100%)',
        }}
      />
      {/* Vignette — always on */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse 88% 88% at 50% 50%, transparent 38%, rgba(0,0,0,0.48) 76%, rgba(0,0,0,0.90) 100%)',
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}
