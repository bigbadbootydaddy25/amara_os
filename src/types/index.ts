export type AmaraState = 'idle' | 'listening' | 'thinking' | 'speaking';
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

// OSINT Land Scanner

export type OsintQueryType = 'ip' | 'coordinates' | 'address';

export interface OsintLocation {
  lat?: number;
  lon?: number;
  displayName?: string;
  city?: string;
  region?: string;
  country?: string;
  countryCode?: string;
  zip?: string;
  timezone?: string;
  continent?: string;
}

export interface OsintNetwork {
  isp?: string;
  org?: string;
  as?: string;
  asName?: string;
  isProxy?: boolean;
  isHosting?: boolean;
}

export interface OsintPlace {
  type?: string;
  category?: string;
  osmType?: string;
  osmId?: number;
  importance?: number;
  boundingBox?: [string, string, string, string];
}

export interface OsintScanResult {
  query: string;
  queryType: OsintQueryType;
  timestamp: string;
  location?: OsintLocation;
  network?: OsintNetwork;
  place?: OsintPlace;
}

export interface OsintStore {
  isOpen: boolean;
  isScanning: boolean;
  result: OsintScanResult | null;
  error: string | null;
  history: OsintScanResult[];
  setOpen: (open: boolean) => void;
  setScanning: (scanning: boolean) => void;
  setResult: (result: OsintScanResult | null) => void;
  setError: (error: string | null) => void;
  pushHistory: (result: OsintScanResult) => void;
}
