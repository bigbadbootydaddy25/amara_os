'use client';

import { create } from 'zustand';
import type { AgentId, AgentState, AgentStatus, IntelFinding } from '@/types/agents';
import { AGENT_DEFINITIONS } from '@/types/agents';

interface AgentStore {
  agents: Record<AgentId, AgentState>;
  findings: IntelFinding[];
  selectedAgentId: AgentId | null;
  amaraStatus: 'dormant' | 'online' | 'nuclear';
  totalVerified: number;
  nuclearCount: number;
  streamActive: boolean;

  setAgentStatus: (id: AgentId, status: AgentStatus, task?: string) => void;
  addFinding: (finding: IntelFinding) => void;
  setSelectedAgent: (id: AgentId | null) => void;
  setAmaraStatus: (status: 'dormant' | 'online' | 'nuclear') => void;
  tickSimulation: () => void;
  clearSelected: () => void;
}

const initAgents = (): Record<AgentId, AgentState> => {
  const result = {} as Record<AgentId, AgentState>;
  for (const def of AGENT_DEFINITIONS) {
    result[def.id] = {
      id: def.id,
      status: 'idle',
      lastActivity: null,
      findingsCount: 0,
      currentTask: null,
      verifiedTargets: [],
      pulseIntensity: 0.3,
    };
  }
  return result;
};

const SEARCH_TASKS: Record<AgentId, string[]> = {
  'dla-scout': [
    'Scanning DLA bulk fuel solicitations…',
    'Cross-referencing DIBBS awards Q1-Q4…',
    'Mapping aviation fuel depot contracts…',
  ],
  'sam-hunter': [
    'Querying SAM.gov for NAICS 424710…',
    'Hunting expiring solicitations 0–90 days…',
    'Extracting entity CAGE codes…',
  ],
  'usaspending-tracker': [
    'Pulling obligated fuel awards >$1M…',
    'Tracing prime → subcontractor chains…',
    'Computing award velocity by agency…',
  ],
  'fmcsa-mapper': [
    'Mapping licensed hazmat tanker carriers…',
    'Cross-referencing DOT carrier safety records…',
    'Identifying fleet size by fuel type…',
  ],
  'fuel-supplier-mapper': [
    'Mapping petroleum terminal operators…',
    'Tracing rack-to-bulk distribution chains…',
    'Identifying EIA-registered bulk terminals…',
  ],
  'distress-intel': [
    'Scanning OFAC SDN list for fuel entities…',
    'Checking PACER for recent bankruptcies…',
    'Flagging suppliers with performance issues…',
  ],
  'buyer-matcher': [
    'Matching open fuel demands to primes…',
    'Building buyer→prime→sub award chains…',
    'Scoring relationship access opportunities…',
  ],
  mirofish: [
    'Detecting broker network patterns…',
    'Cross-referencing recurring facilitators…',
    'Mapping shell entity clusters…',
  ],
};

export const useAgentStore = create<AgentStore>((set, get) => ({
  agents: initAgents(),
  findings: [],
  selectedAgentId: null,
  amaraStatus: 'online',
  totalVerified: 0,
  nuclearCount: 0,
  streamActive: false,

  setAgentStatus: (id, status, task) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [id]: {
          ...state.agents[id],
          status,
          currentTask: task ?? state.agents[id].currentTask,
          pulseIntensity:
            status === 'idle'
              ? 0.3
              : status === 'searching'
                ? 0.6
                : status === 'processing'
                  ? 0.8
                  : status === 'verified'
                    ? 1.0
                    : 1.2,
          lastActivity: new Date().toISOString(),
        },
      },
    })),

  addFinding: (finding) =>
    set((state) => {
      const agent = state.agents[finding.agentId];
      const isNuclear = finding.value === 'nuclear';
      return {
        findings: [finding, ...state.findings].slice(0, 200),
        agents: {
          ...state.agents,
          [finding.agentId]: {
            ...agent,
            findingsCount: agent.findingsCount + 1,
            verifiedTargets: finding.verified
              ? [finding.title, ...agent.verifiedTargets].slice(0, 20)
              : agent.verifiedTargets,
          },
        },
        totalVerified: finding.verified ? state.totalVerified + 1 : state.totalVerified,
        nuclearCount: isNuclear ? state.nuclearCount + 1 : state.nuclearCount,
        amaraStatus: isNuclear ? 'nuclear' : state.amaraStatus,
      };
    }),

  setSelectedAgent: (id) => set({ selectedAgentId: id }),
  clearSelected: () => set({ selectedAgentId: null }),
  setAmaraStatus: (amaraStatus) => set({ amaraStatus }),

  // Visual-only simulation tick — drives UI state, never produces business data
  tickSimulation: () => {
    const state = get();
    const ids = Object.keys(state.agents) as AgentId[];
    const randomId = ids[Math.floor(Math.random() * ids.length)];
    const agent = state.agents[randomId];
    const def = AGENT_DEFINITIONS.find((d) => d.id === randomId)!;
    const tasks = SEARCH_TASKS[randomId];
    const task = tasks[Math.floor(Math.random() * tasks.length)];

    const transitions: Partial<Record<AgentStatus, AgentStatus>> = {
      idle: 'searching',
      searching: 'processing',
      processing: Math.random() > 0.3 ? 'verified' : 'idle',
      verified: 'idle',
      nuclear: 'verified',
    };

    const next = transitions[agent.status] ?? 'idle';
    get().setAgentStatus(randomId, next, task);

    // Emit a visual-only finding marker (no real data, no business claims)
    if (next === 'verified') {
      const isNuclear = Math.random() < 0.08;
      get().addFinding({
        id: `sim_${Date.now()}_${Math.random().toString(36).slice(2)}`,
        agentId: randomId,
        timestamp: new Date().toISOString(),
        title: `[VISUAL MOCK] ${def.label} signal detected`,
        sourceUrl: '',
        verified: true,
        value: isNuclear ? 'nuclear' : Math.random() > 0.5 ? 'high' : 'medium',
        summary: task,
      });
    }

    set({ streamActive: next === 'processing' || next === 'verified' });
  },
}));
