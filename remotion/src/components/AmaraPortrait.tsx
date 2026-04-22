import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { SCENE_1_END, SCENE_3_START } from '../data/amaraScript';

// ─────────────────────────────────────────────────────────────────────────────
// REPLACE THIS PATH with your AMARA portrait file.
// Place the image at:  public/assets/amara-portrait.png  (or .jpg / .webp)
// ─────────────────────────────────────────────────────────────────────────────
const PORTRAIT_SRC = staticFile('assets/amara-portrait.png');

export const AmaraPortrait: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // ── Emergence spring ──────────────────────────────────────────────────────
  const emerge = spring({
    fps,
    frame,
    config: { damping: 42, stiffness: 32, mass: 1.6 },
    from: 0,
    to: 1,
    delay: 14,
  });

  const opacity = interpolate(emerge, [0, 1], [0, 1]);

  // Very slight scale-in on emergence (1.055 → 1.000)
  const scaleEmerge = interpolate(emerge, [0, 1], [1.055, 1.0]);

  // ── Breathing / micro-float ───────────────────────────────────────────────
  const breathScale = 1 + Math.sin(frame * 0.018) * 0.0038;
  const floatY = Math.sin(frame * 0.021 + 0.9) * 4.5;

  // ── Scene 3: authority pull-in ────────────────────────────────────────────
  const authorityScale = interpolate(
    frame,
    [SCENE_3_START, SCENE_3_START + 90],
    [0, 0.009],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  const finalScale = scaleEmerge * breathScale + authorityScale;

  // ── Eye / face area glow pulses ───────────────────────────────────────────
  const faceGlowIn = interpolate(
    frame,
    [SCENE_1_END, SCENE_1_END + 35],
    [0, 1],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );
  const eyePulse = (Math.sin(frame * 0.065) * 0.28 + 0.72) * faceGlowIn;

  const scene3EyeBoost = interpolate(
    frame,
    [SCENE_3_START, SCENE_3_START + 55],
    [0, 0.48],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  const faceGlowOpacity = eyePulse * 0.30 + scene3EyeBoost * 0.38;

  // ── Portrait dimensions ───────────────────────────────────────────────────
  // Scale to fill the composition height; `objectFit: cover` trims excess width.
  // objectPosition centers on the face (top region for a head+torso portrait).
  const portraitH = height * 1.06;

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {/* Bloom behind portrait — emerges with her */}
      <AbsoluteFill
        style={{
          opacity: interpolate(emerge, [0, 1], [0, 0.55]),
          background:
            'radial-gradient(ellipse 44% 58% at 50% 46%, rgba(30, 88, 210, 0.22) 0%, rgba(14, 42, 120, 0.10) 52%, transparent 100%)',
        }}
      />

      {/* Portrait image */}
      <AbsoluteFill
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity,
          transform: `translateY(${floatY}px) scale(${finalScale})`,
        }}
      >
        <Img
          src={PORTRAIT_SRC}
          style={{
            height: portraitH,
            width: 'auto',
            maxWidth: 'none',
            objectFit: 'cover',
            objectPosition: 'center top',
            display: 'block',
            userSelect: 'none',
            // Subtle desaturation blends her into the dark palette;
            // remove this filter if you prefer full colour.
            filter: 'saturate(0.88) brightness(0.96)',
          }}
        />
      </AbsoluteFill>

      {/* Eye/face area glow — soft blue haze at face level */}
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          opacity: faceGlowOpacity,
          background:
            'radial-gradient(ellipse 30% 20% at 50% 34%, rgba(90, 170, 255, 0.30) 0%, rgba(50, 120, 255, 0.08) 60%, transparent 100%)',
        }}
      />

      {/* Bottom-edge fade — blends portrait into black floor */}
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          background:
            'linear-gradient(to top, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.20) 18%, transparent 42%)',
        }}
      />

      {/* Top-edge fade */}
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          background:
            'linear-gradient(to bottom, rgba(0,0,0,0.40) 0%, transparent 22%)',
        }}
      />
    </AbsoluteFill>
  );
};
