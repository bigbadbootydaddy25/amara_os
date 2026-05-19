export type AgentId =
  | 'dla-scout'
  | 'sam-hunter'
  | 'usaspending-tracker'
  | 'fmcsa-mapper'
  | 'fuel-supplier-mapper'
  | 'distress-intel'
  | 'buyer-matcher'
  | 'mirofish';

export type AgentStatus = 'idle' | 'searching' | 'processing' | 'verified' | 'nuclear';

export interface AgentDefinition {
  id: AgentId;
  label: string;
  subLabel: string;
  color: string;
  glowColor: string;
  orbitAngle: number;
  orbitRadius: number;
  description: string;
  dataSources: string[];
}

export interface AgentState {
  id: AgentId;
  status: AgentStatus;
  lastActivity: string | null;
  findingsCount: number;
  currentTask: string | null;
  verifiedTargets: string[];
  pulseIntensity: number;
}

export interface IntelFinding {
  id: string;
  agentId: AgentId;
  timestamp: string;
  title: string;
  sourceUrl: string;
  verified: boolean;
  value: 'low' | 'medium' | 'high' | 'nuclear';
  summary: string;
}

export const AGENT_DEFINITIONS: AgentDefinition[] = [
  {
    id: 'dla-scout',
    label: 'DLA Energy Scout',
    subLabel: 'Defense Logistics',
    color: '#00d4ff',
    glowColor: '#00d4ff',
    orbitAngle: 0,
    orbitRadius: 5.2,
    description: 'Scans DLA Energy contracts for aviation, marine, and bulk fuel solicitations.',
    dataSources: ['dla.mil', 'defense.gov', 'dibbs.dla.mil'],
  },
  {
    id: 'sam-hunter',
    label: 'SAM.gov Hunter',
    subLabel: 'Entity & Solicitation',
    color: '#a855f7',
    glowColor: '#c084fc',
    orbitAngle: (Math.PI * 2) / 8,
    orbitRadius: 5.2,
    description: 'Hunts active solicitations and entity registrations across SAM.gov.',
    dataSources: ['sam.gov', 'beta.sam.gov'],
  },
  {
    id: 'usaspending-tracker',
    label: 'USASpending Tracker',
    subLabel: 'Award Intelligence',
    color: '#06b6d4',
    glowColor: '#67e8f9',
    orbitAngle: (Math.PI * 2 * 2) / 8,
    orbitRadius: 5.2,
    description: 'Tracks awarded contracts, obligated values, and prime contractor relationships.',
    dataSources: ['usaspending.gov', 'fpds.gov'],
  },
  {
    id: 'fmcsa-mapper',
    label: 'FMCSA Carrier Mapper',
    subLabel: 'Logistics Intelligence',
    color: '#f59e0b',
    glowColor: '#fcd34d',
    orbitAngle: (Math.PI * 2 * 3) / 8,
    orbitRadius: 5.2,
    description: 'Maps licensed fuel carriers, tanker operators, and hazmat logistics partners.',
    dataSources: ['fmcsa.dot.gov', 'safer.fmcsa.dot.gov'],
  },
  {
    id: 'fuel-supplier-mapper',
    label: 'Fuel Supplier Mapper',
    subLabel: 'Supply Chain Intel',
    color: '#10b981',
    glowColor: '#6ee7b7',
    orbitAngle: (Math.PI * 2 * 4) / 8,
    orbitRadius: 5.2,
    description: 'Identifies fuel rack operators, terminal owners, and bulk fuel distributors.',
    dataSources: ['eia.gov', 'sec.gov/edgar', 'opencorporates.com'],
  },
  {
    id: 'distress-intel',
    label: 'Distress Intel Agent',
    subLabel: 'Vulnerability Scanner',
    color: '#ef4444',
    glowColor: '#fca5a5',
    orbitAngle: (Math.PI * 2 * 5) / 8,
    orbitRadius: 5.2,
    description: 'Detects supplier failures, sanctions flags, bankruptcy signals, and contract disputes.',
    dataSources: ['ofac.treas.gov', 'pacer.gov', 'sec.gov'],
  },
  {
    id: 'buyer-matcher',
    label: 'Buyer / Prime Matcher',
    subLabel: 'Relationship Engine',
    color: '#3b82f6',
    glowColor: '#93c5fd',
    orbitAngle: (Math.PI * 2 * 6) / 8,
    orbitRadius: 5.2,
    description: 'Matches fuel needs to qualified primes and maps subcontractor award chains.',
    dataSources: ['usaspending.gov', 'sam.gov', 'fpds.gov'],
  },
  {
    id: 'mirofish',
    label: 'MiroFish Simulator',
    subLabel: 'Pattern Recognition',
    color: '#ec4899',
    glowColor: '#f9a8d4',
    orbitAngle: (Math.PI * 2 * 7) / 8,
    orbitRadius: 5.2,
    description: 'Detects hidden broker patterns, shell entities, and recurring facilitator networks.',
    dataSources: ['opencorporates.com', 'sec.gov', 'dnb.com'],
  },
];
