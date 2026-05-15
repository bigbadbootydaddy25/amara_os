import { create } from 'zustand';
import type { OsintStore } from '@/types';

export const useOsintStore = create<OsintStore>((set) => ({
  isOpen: false,
  isScanning: false,
  result: null,
  error: null,
  history: [],
  setOpen: (isOpen) => set({ isOpen }),
  setScanning: (isScanning) => set({ isScanning }),
  setResult: (result) => set({ result }),
  setError: (error) => set({ error }),
  pushHistory: (result) =>
    set((state) => ({ history: [result, ...state.history].slice(0, 20) })),
}));
