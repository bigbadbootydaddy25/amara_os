import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';

// Two faint horizontal light passes during Scene 2
const PASSES = [
  { startFrame: 255, duration: 105 },
  { startFrame: 600, duration: 105 },
];

export const ScanLine: React.FC = () => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ pointerEvents: 'none', overflow: 'hidden' }}>
      {PASSES.map((pass, i) => {
        const end = pass.startFrame + pass.duration;

        const progress = interpolate(frame, [pass.startFrame, end], [-0.06, 1.06], {
          extrapolateRight: 'clamp',
          extrapolateLeft: 'clamp',
        });

        const opacity = interpolate(
          frame,
          [pass.startFrame, pass.startFrame + 10, end - 10, end],
          [0, 0.16, 0.16, 0],
          { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
        );

        if (opacity <= 0.001) return null;

        const top = progress * height;

        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              inset: '0 0 auto',
              top,
              height: 140,
              transform: 'translateY(-50%)',
              background:
                'linear-gradient(to bottom, transparent 0%, rgba(50,130,255,0.05) 30%, rgba(60,140,255,0.10) 50%, rgba(50,130,255,0.05) 70%, transparent 100%)',
              opacity,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
