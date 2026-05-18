import { create } from 'zustand';
import type {
  ContractorEntity,
  ContractNetworkMap,
  ContractAlert,
  OpportunityScores,
  ContractorIntelRequest,
} from '@/types/contractor-intel';

export type IntelPanelState = 'idle' | 'searching' | 'loaded' | 'error';

export interface ContractorIntelStore {
  panelState: IntelPanelState;
  selectedEntityId: string | null;
  entities: ContractorEntity[];
  network: ContractNetworkMap | null;
  alerts: ContractAlert[];
  lastQuery: ContractorIntelRequest | null;
  error: string | null;
  warnings: string[];
  missingOsintSources: string[];

  setPanelState: (state: IntelPanelState) => void;
  setSelectedEntityId: (id: string | null) => void;
  setEntities: (entities: ContractorEntity[]) => void;
  upsertEntity: (entity: ContractorEntity) => void;
  removeEntity: (id: string) => void;
  setNetwork: (network: ContractNetworkMap | null) => void;
  setAlerts: (alerts: ContractAlert[]) => void;
  setLastQuery: (query: ContractorIntelRequest) => void;
  setError: (error: string | null) => void;
  setWarnings: (warnings: string[]) => void;
  setMissingOsintSources: (sources: string[]) => void;
  clearIntel: () => void;

  // Derived selectors
  getSelectedEntity: () => ContractorEntity | null;
  getHighAlerts: () => ContractAlert[];
  getEntityScores: (id: string) => OpportunityScores | null;
}

export const useContractorIntelStore = create<ContractorIntelStore>((set, get) => ({
  panelState: 'idle',
  selectedEntityId: null,
  entities: [],
  network: null,
  alerts: [],
  lastQuery: null,
  error: null,
  warnings: [],
  missingOsintSources: [],

  setPanelState: (panelState) => set({ panelState }),
  setSelectedEntityId: (selectedEntityId) => set({ selectedEntityId }),

  setEntities: (entities) => set({ entities }),

  upsertEntity: (entity) =>
    set((state) => {
      const index = state.entities.findIndex((e) => e.id === entity.id);
      if (index >= 0) {
        const updated = [...state.entities];
        updated[index] = entity;
        return { entities: updated };
      }
      return { entities: [...state.entities, entity] };
    }),

  removeEntity: (id) =>
    set((state) => ({
      entities: state.entities.filter((e) => e.id !== id),
      selectedEntityId: state.selectedEntityId === id ? null : state.selectedEntityId,
    })),

  setNetwork: (network) => set({ network }),
  setAlerts: (alerts) => set({ alerts }),
  setLastQuery: (lastQuery) => set({ lastQuery }),
  setError: (error) => set({ error }),
  setWarnings: (warnings) => set({ warnings }),
  setMissingOsintSources: (missingOsintSources) => set({ missingOsintSources }),

  clearIntel: () =>
    set({
      panelState: 'idle',
      selectedEntityId: null,
      entities: [],
      network: null,
      alerts: [],
      error: null,
      warnings: [],
      missingOsintSources: [],
    }),

  getSelectedEntity: () => {
    const { entities, selectedEntityId } = get();
    if (!selectedEntityId) return null;
    return entities.find((e) => e.id === selectedEntityId) ?? null;
  },

  getHighAlerts: () => get().alerts.filter((a) => a.priority === 'high'),

  getEntityScores: (id: string) => {
    const entity = get().entities.find((e) => e.id === id);
    return entity?.scores ?? null;
  },
}));
