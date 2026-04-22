import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { AMARA_SCRIPT } from '../data/amaraScript';

// Expanding ring pulse on "Let's begin."
const TRIGGER_FRAME = AMARA_SCRIPT.find((s) => s.id === 'l15')?.startFrame ?? 978;
const PULSE_DURATION = 82;

export const AuthorityPulse: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const local = frame - TRIGGER_FRAME;
  if (local < 0 || local > PULSE_DURATION) return null;

  const progress = interpolate(local, [0, PULSE_DURATION], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  const opacity = interpolate(
    local,
    [0, 12, PULSE_DURATION - 16, PULSE_DURATION],
    [0, 0.50, 0.24, 0],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  const cx = width / 2;
  const cy = height * 0.47;
  const maxRx = width * 0.32;
  const maxRy = height * 0.38;
  const rx = interpolate(progress, [0, 1], [55, maxRx]);
  const ry = interpolate(progress, [0, 1], [34, maxRy]);

  // Second ring — slightly delayed
  const progress2 = interpolate(local, [10, PULSE_DURATION], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });
  const opacity2 = interpolate(
    local,
    [10, 24, PULSE_DURATION - 8, PULSE_DURATION],
    [0, 0.28, 0.12, 0],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );
  const rx2 = interpolate(progress2, [0, 1], [40, maxRx * 0.82]);
  const ry2 = interpolate(progress2, [0, 1], [26, maxRy * 0.82]);

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <svg
        width={width}
        height={height}
        style={{ position: 'absolute', inset: 0 }}
      >
        <defs>
          <filter id="pulseGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="7" />
          </filter>
        </defs>
        {/* Blurred outer halo */}
        <ellipse
          cx={cx} cy={cy} rx={rx} ry={ry}
          fill="none"
          stroke={`rgba(60, 140, 255, ${opacity * 0.6})`}
          strokeWidth="2.5"
          filter="url(#pulseGlow)"
        />
        {/* Sharp primary ring */}
        <ellipse
          cx={cx} cy={cy} rx={rx} ry={ry}
          fill="none"
          stroke={`rgba(80, 160, 255, ${opacity})`}
          strokeWidth="0.9"
        />
        {/* Secondary ring */}
        <ellipse
          cx={cx} cy={cy} rx={rx2} ry={ry2}
          fill="none"
          stroke={`rgba(100, 180, 255, ${opacity2})`}
          strokeWidth="0.55"
        />
      </svg>
    </AbsoluteFill>
  );
};
