export type AmaraState = 'idle' | 'listening' | 'thinking' | 'speaking';
export type ConversationRole = 'system' | 'user' | 'assistant';
export type AgentName = 'nova' | 'hunter' | 'geo' | 'amara';

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
  activeAgent: AgentName;
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
  setActiveAgent: (agent: AgentName) => void;
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
