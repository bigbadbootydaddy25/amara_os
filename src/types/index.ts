export type AmaraState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'ingesting' | 'alert';

export interface DealCard {
  address: string;
  score: number;
  buyer: string | null;
  mao: number | null;
  price: number | null;
  weight?: number;
}

export interface IQEvent {
  type: 'IQ_GAIN' | 'IQ_CURRENT' | 'IQ_MILESTONE';
  iq?: number;
  before?: number;
  after?: number;
  amount?: number;
  reason?: string;
}
export type ConversationRole = 'system' | 'user' | 'assistant';

export interface ConversationMessage {
  role: ConversationRole;
  content: string;
}

export interface ChatRequestBody {
  message: string;
  history?: ConversationMessage[];
}

export interface TtsRequestBody {
  text: string;
}

export interface VoiceInputOptions {
  enabled?: boolean;
  onSpeechComplete: (transcript: string) => Promise<void> | void;
}

export interface AmaraStore {
  state: AmaraState;
  audioLevel: number;
  isMicActive: boolean;
  isVoiceSupported: boolean;
  isOnline: boolean;
  transcript: string;
  interimTranscript: string;
  response: string;
  error: string | null;
  errorPulse: number;
  setState: (state: AmaraState) => void;
  setAudioLevel: (level: number) => void;
  setMicActive: (active: boolean) => void;
  setVoiceSupported: (supported: boolean) => void;
  setOnline: (online: boolean) => void;
  setTranscript: (text: string) => void;
  setInterimTranscript: (text: string) => void;
  setResponse: (text: string) => void;
  setError: (error: string | null) => void;
  triggerErrorPulse: () => void;
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
