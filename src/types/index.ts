export type AmaraState = 'idle' | 'listening' | 'thinking' | 'speaking';

export * from './contractor-intel';
export type ConversationRole = 'system' | 'user' | 'assistant';

// ---------------------------------------------------------------------------
// Lead validation types — REAL DATA ONLY, no placeholders
// ---------------------------------------------------------------------------

export type DispositionStrategy =
  | 'assignment'
  | 'double-close'
  | 'entitlement-cleanup-flip'
  | 'builder-flip'
  | 'jv'
  | 'land-banking'
  | 'wholesale'
  | 'builder-resale';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface PropertyData {
  county: string;
  city: string;
  apn: string;
  ownerName: string;
  mailingAddress: string;
  siteAddress: string;
  acreage: number;
  zoning: string;
}

export interface EntitlementData {
  subdivisionName: string;
  tentativeMapStatus: string;
  finalMapStatus: string;
  permitStatus: string;
  entitlementStatus: string;
  extensionReinstatementIssue: string;
  utilityStatus: string;
  infrastructureStatus: string;
}

export interface DistressData {
  taxDelinquency: string | null;
  bankruptcy: string | null;
  foreclosure: string | null;
  mechanicsLiens: string | null;
  dissolvedLlcStatus: string | null;
  lenderDistress: string | null;
  pacerReference: string | null;
  secReference: string | null;
  inactivityDurationMonths: number;
}

export interface DispositionIntelligence {
  nearbyBuilders: string[];
  nearbyPermitActivity: string;
  likelyBuyers: string[];
  buyerDemandScore: number;
  liquidityScore: number;
  speedToDispositionScore: number;
  likelyExitStrategies: DispositionStrategy[];
}

export interface LeadSources {
  sourceUrls: string[];
  documentReferences: string[];
  docketReferences: string[];
}

export interface LeadScoring {
  confidenceScore: number;
  estimatedSpreadPotential: string;
  riskLevel: RiskLevel;
}

export interface VerifiedLead {
  id: string;
  createdAt: string;
  property: PropertyData;
  entitlement: EntitlementData;
  distress: DistressData;
  disposition: DispositionIntelligence;
  sources: LeadSources;
  scoring: LeadScoring;
}

export interface RejectedLead {
  id: string;
  createdAt: string;
  whyItLookedInteresting: string;
  missingProof: string[];
  sourcesChecked: string[];
  nextVerificationStep: string;
  partialData: Partial<VerifiedLead>;
}

export interface LeadValidationResult {
  valid: boolean;
  lead?: VerifiedLead;
  rejected?: RejectedLead;
  errors: string[];
  warnings: string[];
}

export interface ValidateLeadRequestBody {
  lead: Partial<VerifiedLead> & {
    whyItLookedInteresting?: string;
    nextVerificationStep?: string;
  };
}

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
