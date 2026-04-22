import { create } from 'zustand';
import type { AmaraStore } from '@/types';

export const useAmaraStore = create<AmaraStore>((set) => ({
  state: 'idle',
  audioLevel: 0,
  isMicActive: false,
  isVoiceSupported: true,
  isOnline: true,
  transcript: '',
  interimTranscript: '',
  response: '',
  error: null,
  errorPulse: 0,
  activeAgent: 'amara',
  setState: (state) => set({ state }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setMicActive: (isMicActive) => set({ isMicActive }),
  setVoiceSupported: (isVoiceSupported) => set({ isVoiceSupported }),
  setOnline: (isOnline) => set({ isOnline }),
  setTranscript: (transcript) => set({ transcript }),
  setInterimTranscript: (interimTranscript) => set({ interimTranscript }),
  setResponse: (response) => set({ response }),
  setError: (error) => set({ error }),
  triggerErrorPulse: () => set({ errorPulse: Date.now() }),
  setActiveAgent: (activeAgent) => set({ activeAgent }),
}));
