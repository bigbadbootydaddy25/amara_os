'use client';

import { useCallback, useEffect, useRef } from 'react';
import { calculateAudioLevelFromFrequencyData } from '@/lib/audio-utils';
import { useAmaraStore } from '@/stores/amara-store';

type AudioContextConstructor = typeof AudioContext;

type WindowWithWebkitAudio = Window & typeof globalThis & {
  webkitAudioContext?: AudioContextConstructor;
};

function getAudioContextConstructor(): AudioContextConstructor | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const { AudioContext: StandardAudioContext, webkitAudioContext } =
    window as WindowWithWebkitAudio;

  return StandardAudioContext || webkitAudioContext || null;
}

export function useVoiceOutput() {
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const animationFrameRef = useRef<number>(0);
  const fetchAbortRef = useRef<AbortController | null>(null);

  const clearMonitoring = useCallback(() => {
    if (animationFrameRef.current) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = 0;
    }

    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }

    useAmaraStore.getState().setAudioLevel(0);
  }, []);

  const stopSpeaking = useCallback(
    (nextState: 'idle' | 'speaking' = 'idle') => {
      fetchAbortRef.current?.abort();
      fetchAbortRef.current = null;

      if (sourceRef.current) {
        const activeSource = sourceRef.current;
        sourceRef.current = null;
        activeSource.onended = null;

        try {
          activeSource.stop(0);
        } catch {}

        activeSource.disconnect();
      }

      clearMonitoring();
      useAmaraStore.getState().setState(nextState);
    },
    [clearMonitoring],
  );

  const primeAudio = useCallback(async () => {
    const AudioContextClass = getAudioContextConstructor();

    if (!AudioContextClass) {
      throw new Error('Web Audio API is not supported in this browser.');
    }

    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContextClass();
    }

    if (audioContextRef.current.state === 'suspended') {
      await audioContextRef.current.resume();
    }

    return audioContextRef.current;
  }, []);

  const speak = useCallback(
    async (text: string) => {
      stopSpeaking('speaking');
      const store = useAmaraStore.getState();
      store.setError(null);
      store.setState('speaking');

      const audioContext = await primeAudio();
      const controller = new AbortController();
      fetchAbortRef.current = controller;

      try {
        const response = await fetch('/api/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const message = (await response.text().catch(() => 'TTS failed')).trim();
          throw new Error(message || 'TTS failed');
        }

        const encodedAudio = await response.arrayBuffer();
        const decodedAudio = await audioContext.decodeAudioData(encodedAudio.slice(0));

        if (controller.signal.aborted) {
          return;
        }

        const source = audioContext.createBufferSource();
        const analyser = audioContext.createAnalyser();
        const data = new Uint8Array(analyser.frequencyBinCount);

        source.buffer = decodedAudio;
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;

        source.connect(analyser);
        analyser.connect(audioContext.destination);

        sourceRef.current = source;
        analyserRef.current = analyser;

        const updateLevel = () => {
          if (!analyserRef.current) {
            return;
          }

          analyserRef.current.getByteFrequencyData(data);
          useAmaraStore.getState().setAudioLevel(calculateAudioLevelFromFrequencyData(data));
          animationFrameRef.current = window.requestAnimationFrame(updateLevel);
        };

        updateLevel();

        await new Promise<void>((resolve, reject) => {
          source.onended = () => {
            source.disconnect();
            sourceRef.current = null;
            clearMonitoring();
            useAmaraStore.getState().setState('idle');
            resolve();
          };

          try {
            source.start(0);
          } catch (error) {
            reject(error);
          }
        });
      } catch (error) {
        clearMonitoring();
        useAmaraStore.getState().setState('idle');

        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }

        throw error;
      } finally {
        if (fetchAbortRef.current === controller) {
          fetchAbortRef.current = null;
        }
      }
    },
    [clearMonitoring, primeAudio, stopSpeaking],
  );

  useEffect(() => {
    return () => {
      stopSpeaking();
      const audioContext = audioContextRef.current;
      if (audioContext && audioContext.state !== 'closed') {
        void audioContext.close();
      }
    };
  }, [stopSpeaking]);

  return {
    primeAudio,
    speak,
    stopSpeaking,
  };
}
