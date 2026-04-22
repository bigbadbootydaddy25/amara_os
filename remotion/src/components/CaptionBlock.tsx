import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { AMARA_SCRIPT } from '../data/amaraScript';

const FADE_IN_FRAMES = 8;
const FADE_OUT_FRAMES = 6;

// Fine-tuned caption typography — cinematic, not social-media
const CAPTION_STYLE: React.CSSProperties = {
  fontFamily: '"Helvetica Neue", "Helvetica", "Arial", sans-serif',
  fontWeight: 300,
  fontSize: 36,
  letterSpacing: '0.055em',
  lineHeight: 1.58,
  color: 'rgba(218, 232, 255, 0.93)',
  textShadow:
    '0 0 28px rgba(80, 158, 255, 0.50), 0 1px 4px rgba(0, 0, 0, 0.90)',
  whiteSpace: 'pre-line',
  textAlign: 'center',
};

const ACCENT_LINE_STYLE: React.CSSProperties = {
  marginTop: 11,
  height: 1,
  background:
    'linear-gradient(to right, transparent 0%, rgba(70, 150, 255, 0.45) 30%, rgba(90, 170, 255, 0.55) 50%, rgba(70, 150, 255, 0.45) 70%, transparent 100%)',
};

export const CaptionBlock: React.FC = () => {
  const frame = useCurrentFrame();

  const active = AMARA_SCRIPT.find(
    (seg) => frame >= seg.startFrame && frame <= seg.endFrame,
  );

  if (!active) return null;

  const { text, startFrame, endFrame } = active;
  const local = frame - startFrame;
  const duration = endFrame - startFrame;

  // Fade-in
  const fadeIn = interpolate(local, [0, FADE_IN_FRAMES], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  // Fade-out
  const fadeOut = interpolate(
    local,
    [duration - FADE_OUT_FRAMES, duration],
    [1, 0],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  const opacity = Math.min(fadeIn, fadeOut);

  // Blur + translate reveal
  const blur = interpolate(local, [0, FADE_IN_FRAMES], [7, 0], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  const translateY = interpolate(local, [0, FADE_IN_FRAMES], [10, 0], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        // Lower-third position — enough breathing room from frame edge
        paddingBottom: 96,
        paddingLeft: 160,
        paddingRight: 160,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          filter: `blur(${blur}px)`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <div style={CAPTION_STYLE}>{text}</div>
        <div style={ACCENT_LINE_STYLE} />
      </div>
    </AbsoluteFill>
  );
};
