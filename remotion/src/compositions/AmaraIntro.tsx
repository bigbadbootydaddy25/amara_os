import React from 'react';
import { AbsoluteFill, Audio, staticFile } from 'remotion';
import { BackgroundFX } from '../components/BackgroundFX';
import { OrbRing } from '../components/OrbRing';
import { Particles } from '../components/Particles';
import { ScanLine } from '../components/ScanLine';
import { NeuralHaze } from '../components/NeuralHaze';
import { AmaraPortrait } from '../components/AmaraPortrait';
import { CaptionBlock } from '../components/CaptionBlock';
import { AuthorityPulse } from '../components/AuthorityPulse';

// ─────────────────────────────────────────────────────────────────────────────
// AUDIO SETUP
// Uncomment the <Audio> tags below once you have your files.
//
// Voiceover  → place at:  public/assets/voiceover.mp3
// Ambience   → place at:  public/assets/ambience.mp3
//
// The voiceover starts at frame 0 of the audio file.
// If your voiceover has a short silence at the start you can use:
//   <Audio src={...} startFrom={0} endAt={TOTAL_FRAMES} />
// ─────────────────────────────────────────────────────────────────────────────

export const AmaraIntro: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: '#000000', overflow: 'hidden' }}>
      {/* ── Layer 1: Deep black background + blue ambient atmosphere ── */}
      <BackgroundFX />

      {/* ── Layer 2: Orbital ring energy behind AMARA ── */}
      <OrbRing />

      {/* ── Layer 3: Neural haze — hairline strands from face area ── */}
      <NeuralHaze />

      {/* ── Layer 4: Floating ambient particles ── */}
      <Particles />

      {/* ── Layer 5: Horizontal scan light passes ── */}
      <ScanLine />

      {/* ── Layer 6: AMARA — hero portrait (replace image path in AmaraPortrait.tsx) ── */}
      <AmaraPortrait />

      {/* ── Layer 7: Authority pulse on "Let's begin." ── */}
      <AuthorityPulse />

      {/* ── Layer 8: Captions ── */}
      <CaptionBlock />

      {/*
        ── VOICEOVER ──────────────────────────────────────────────────────────
        Replace 'assets/voiceover.mp3' with your file and uncomment.
      */}
      {/* <Audio src={staticFile('assets/voiceover.mp3')} /> */}

      {/*
        ── BACKGROUND AMBIENCE (optional) ─────────────────────────────────────
        A subtle cinematic drone track. Volume 0.10–0.18 recommended.
        Replace 'assets/ambience.mp3' with your file and uncomment.
      */}
      {/* <Audio src={staticFile('assets/ambience.mp3')} volume={0.13} /> */}
    </AbsoluteFill>
  );
};
