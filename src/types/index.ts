export type AmaraState = 'idle' | 'listening' | 'thinking' | 'speaking';

export interface AmaraStore {
  state: AmaraState;
  audioLevel: number;
  isMicActive: boolean;
  transcript: string;
  response: string;
  error: string | null;
  setState: (state: AmaraState) => void;
  setAudioLevel: (level: number) => void;
  setMicActive: (active: boolean) => void;
  setTranscript: (text: string) => void;
  setResponse: (text: string) => void;
  setError: (error: string | null) => void;
}

export interface OrbParticle {
  x: number;
  y: number;
  radius: number;
  baseRadius: number;
  angle: number;
  speed: number;
  orbitRadius: number;
  opacity: number;
  hue: number;
  phase: number;
}

export interface AvatarAnimState {
  mouthOpenness: number;
  eyeGlow: number;
  blinkProgress: number;
  headTilt: number;
  breathScale: number;
  thinkingPulse: number;
}
