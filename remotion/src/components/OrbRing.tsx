import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { SCENE_3_START } from '../data/amaraScript';

export const OrbRing: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const emerge = spring({
    fps,
    frame,
    config: { damping: 32, stiffness: 55, mass: 1.3 },
    from: 0,
    to: 1,
    delay: 18,
  });

  // Slow, nearly-imperceptible rotation
  const rotationDeg = frame * 0.28;

  // Scene 3 authority boost
  const authorityGlow = interpolate(
    frame,
    [SCENE_3_START, SCENE_3_START + 70],
    [0, 1],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  // Portrait center  — face sits at roughly 47% from top
  const cx = width / 2;
  const cy = height * 0.47;
  const rx = width * 0.235;
  const ry = height * 0.375;

  const baseOpacity = emerge * 0.26;
  const glowOpacity = baseOpacity + authorityGlow * 0.20;

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <svg
        width={width}
        height={height}
        style={{ position: 'absolute', inset: 0, overflow: 'visible' }}
      >
        <defs>
          <filter id="orbGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="softBlur">
            <feGaussianBlur stdDeviation="5" />
          </filter>
        </defs>

        {/* Outer soft halo — blurred */}
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx * 1.08}
          ry={ry * 1.08}
          fill="none"
          stroke={`rgba(55, 130, 255, ${glowOpacity * 0.80})`}
          strokeWidth="1.8"
          filter="url(#softBlur)"
          transform={`rotate(${rotationDeg}, ${cx}, ${cy})`}
        />

        {/* Primary ring — dashed, slow rotate */}
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx}
          ry={ry}
          fill="none"
          stroke={`rgba(70, 150, 255, ${glowOpacity * 0.65})`}
          strokeWidth="0.85"
          strokeDasharray="6 18"
          filter="url(#orbGlow)"
          transform={`rotate(${rotationDeg}, ${cx}, ${cy})`}
        />

        {/* Counter-rotating inner ring */}
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx * 0.76}
          ry={ry * 0.76}
          fill="none"
          stroke={`rgba(100, 175, 255, ${glowOpacity * 0.38})`}
          strokeWidth="0.55"
          strokeDasharray="3 24"
          transform={`rotate(${-rotationDeg * 0.65}, ${cx}, ${cy})`}
        />

        {/* Innermost hairline */}
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx * 0.54}
          ry={ry * 0.54}
          fill="none"
          stroke={`rgba(130, 200, 255, ${glowOpacity * 0.22})`}
          strokeWidth="0.4"
          transform={`rotate(${rotationDeg * 0.35}, ${cx}, ${cy})`}
        />
      </svg>
    </AbsoluteFill>
  );
};
