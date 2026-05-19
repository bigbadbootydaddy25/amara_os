import { create } from 'zustand';
import type { WellPad, LayerState, EnergyAgent, AgentStatus, DataMode } from '../types';
import { MOCK_WELLS } from '../data/wells.mock';
import { INITIAL_AGENTS, AGENT_FINDINGS } from '../data/agents.mock';

interface EnergyStore {
  // ── data mode ──────────────────────────────────────────────────────────────
  dataMode: DataMode;

  // ── wells ──────────────────────────────────────────────────────────────────
  wells: WellPad[];
  selectedWellId: string | null;
  selectWell: (id: string | null) => void;

  // ── layers ─────────────────────────────────────────────────────────────────
  layers: LayerState;
  toggleLayer: (key: keyof LayerState) => void;

  // ── agents ─────────────────────────────────────────────────────────────────
  agents: EnergyAgent[];
  agentPanelOpen: boolean;
  setAgentPanelOpen: (open: boolean) => void;
  tickAgent: () => void;

  // ── activity ticker ────────────────────────────────────────────────────────
  latestActivity: string;
}

export const useEnergyStore = create<EnergyStore>((set, get) => ({
  dataMode: 'DEMO',

  wells: MOCK_WELLS,
  selectedWellId: null,
  selectWell: (id) => set({ selectedWellId: id }),

  layers: {
    wells:          true,
    leases:         false,
    units:          false,
    pipelines:      false,
    producing:      false,
    shutIn:         false,
    duc:            false,
    titleRisk:      false,
    curativeNeeded: false,
    nptAlerts:      false,
  },
  toggleLayer: (key) =>
    set((s) => ({ layers: { ...s.layers, [key]: !s.layers[key] } })),

  agents: INITIAL_AGENTS,
  agentPanelOpen: true,

  setAgentPanelOpen: (open) => set({ agentPanelOpen: open }),

  tickAgent: () => {
    const agents = get().agents;
    const idx = Math.floor(Math.random() * agents.length);
    const agent = agents[idx];
    const pool = AGENT_FINDINGS[agent.id] ?? [];
    const finding = pool[Math.floor(Math.random() * pool.length)] ?? agent.finding;

    const statusCycle: Record<AgentStatus, AgentStatus> = {
      idle:      'scanning',
      scanning:  'analyzing',
      analyzing: Math.random() < 0.25 ? 'critical' : 'flagged',
      flagged:   'idle',
      critical:  'idle',
    };
    const nextStatus = statusCycle[agent.status];

    const updatedAgents = agents.map((a, i) =>
      i === idx
        ? { ...a, status: nextStatus, finding, findingTs: Date.now() }
        : a,
    );

    set({ agents: updatedAgents, latestActivity: finding });
  },

  latestActivity: 'AMARA Energy OS online — all systems nominal',
}));

// ── simulation timer (started by EnergyOSApp, stopped on unmount) ────────────
let _timer: ReturnType<typeof setInterval> | null = null;

export function startEnergySimulation() {
  if (_timer !== null) return;
  _timer = setInterval(() => useEnergyStore.getState().tickAgent(), 3200);
}

export function stopEnergySimulation() {
  if (_timer !== null) { clearInterval(_timer); _timer = null; }
}
