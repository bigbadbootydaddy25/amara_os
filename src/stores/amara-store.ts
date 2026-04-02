import { create } from 'zustand';
import type { AmaraStore } from '@/types';

export const useAmaraStore = create<AmaraStore>((set) => ({
  state: 'idle',
  audioLevel: 0,
  isMicActive: false,
  transcript: '',
  response: '',
  error: null,
  setState: (state) => set({ state }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setMicActive: (isMicActive) => set({ isMicActive }),
  setTranscript: (transcript) => set({ transcript }),
  setResponse: (response) => set({ response }),
  setError: (error) => set({ error }),
}));
