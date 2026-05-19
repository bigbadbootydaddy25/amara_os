import { create } from 'zustand';

export type AgentState = 'idle' | 'searching' | 'processing' | 'verified' | 'nuclear';

export interface AgentActivity {
  timestamp: number;
  message: string;
}

export interface Agent {
  id: string;
  name: string;
  color: string;
  mission: string;
  sources: string[];
  state: AgentState;
  signalCount: number;
  verifiedCount: number;
  activityLog: AgentActivity[];
}

export const AGENT_CONFIG: Pick<Agent, 'id' | 'name' | 'color' | 'mission' | 'sources'>[] = [
  { id: 'recon', name: 'RECON', color: '#00d4ff', mission: 'Property reconnaissance & parcel intel', sources: ['Clark County Assessor', 'Google Maps API', 'OpenStreetMap'] },
  { id: 'intel', name: 'INTEL', color: '#7c3aed', mission: 'Contractor background intelligence', sources: ['NV SOS', 'CSLB Database', 'BBB Records'] },
  { id: 'nexus', name: 'NEXUS', color: '#f59e0b', mission: 'Ownership relationship mapping', sources: ['LinkedIn', 'Court Records', 'Beneficial Ownership DB'] },
  { id: 'sentinel', name: 'SENTINEL', color: '#ef4444', mission: 'Distress alert monitoring', sources: ['MLS Feed', 'Foreclosure DB', 'NOD Registry'] },
  { id: 'vector', name: 'VECTOR', color: '#10b981', mission: 'Lead scoring & underwrite', sources: ['Distress Signal Matrix', 'Market Comps', 'ARV Model'] },
  { id: 'cipher', name: 'CIPHER', color: '#f97316', mission: 'Document & title analysis', sources: ['Permit Records', 'Title DB', 'PACER Court Filings'] },
  { id: 'pulse', name: 'PULSE', color: '#ec4899', mission: 'Real-time market pulse', sources: ['MLS Feed', 'Zillow API', 'Redfin Data'] },
  { id: 'apex', name: 'APEX', color: '#8b5cf6', mission: 'Deal approval & LOI generation', sources: ['Comps DB', 'Risk Matrix', 'Acquisition Criteria'] },
];

function makeAgent(cfg: (typeof AGENT_CONFIG)[0]): Agent {
  return { ...cfg, state: 'idle', signalCount: 0, verifiedCount: 0, activityLog: [] };
}

interface NeuralStore {
  agents: Agent[];
  selectedAgentId: string | null;
  latestActivity: string;
  nuclearAgentId: string | null;
  totalVerified: number;
  totalNuclear: number;
  setAgentState: (id: string, state: AgentState) => void;
  addActivity: (id: string, message: string) => void;
  selectAgent: (id: string | null) => void;
  clearNuclear: () => void;
}

export const useNeuralStore = create<NeuralStore>((set) => ({
  agents: AGENT_CONFIG.map(makeAgent),
  selectedAgentId: null,
  latestActivity: 'Fleet online — awaiting targets',
  nuclearAgentId: null,
  totalVerified: 0,
  totalNuclear: 0,

  setAgentState: (id, state) =>
    set((s) => {
      const prev = s.agents.find((a) => a.id === id);
      const wasNuclear = prev?.state === 'nuclear';
      const agents = s.agents.map((a) => (a.id === id ? { ...a, state } : a));
      return {
        agents,
        nuclearAgentId:
          state === 'nuclear' ? id : s.nuclearAgentId === id ? null : s.nuclearAgentId,
        totalNuclear:
          state === 'nuclear' && !wasNuclear ? s.totalNuclear + 1 : s.totalNuclear,
      };
    }),

  addActivity: (id, message) =>
    set((s) => {
      const agents = s.agents.map((a) => {
        if (a.id !== id) return a;
        const isVerified = /verified/i.test(message);
        return {
          ...a,
          signalCount: a.signalCount + 1,
          verifiedCount: isVerified ? a.verifiedCount + 1 : a.verifiedCount,
          activityLog: [{ timestamp: Date.now(), message }, ...a.activityLog.slice(0, 19)],
        };
      });
      return {
        agents,
        latestActivity: message,
        totalVerified: agents.reduce((n, a) => n + a.verifiedCount, 0),
      };
    }),

  selectAgent: (id) => set({ selectedAgentId: id }),

  clearNuclear: () =>
    set((s) => ({
      agents: s.agents.map((a) => (a.state === 'nuclear' ? { ...a, state: 'idle' as AgentState } : a)),
      nuclearAgentId: null,
    })),
}));
