'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { estimateListeningLevel } from '@/lib/audio-utils';
import { useAmaraStore } from '@/stores/amara-store';
import type { VoiceInputOptions } from '@/types';

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type WindowWithSpeechRecognition = Window & typeof globalThis & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  length: number;
  [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
  message?: string;
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: ((event: Event) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: ((event: Event) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

const SILENCE_TIMEOUT_MS = 1500;
const RESTART_DELAY_MS = 100;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const recognitionWindow = window as WindowWithSpeechRecognition;
  return recognitionWindow.SpeechRecognition || recognitionWindow.webkitSpeechRecognition || null;
}

export function useVoiceInput({ enabled = true, onSpeechComplete }: VoiceInputOptions) {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const restartTimerRef = useRef<number | null>(null);
  const finalTranscriptRef = useRef('');
  const callbackRef = useRef(onSpeechComplete);
  const enabledRef = useRef(enabled);
  const manualStopRef = useRef(false);
  const startPendingRef = useRef(false);
  const isListeningRef = useRef(false);
  const [isListening, setIsListening] = useState(false);
  const isSupported = useMemo(() => Boolean(getSpeechRecognitionConstructor()), []);

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  const clearRestartTimer = useCallback(() => {
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  }, []);

  const completeSpeech = useCallback(() => {
    const transcript = finalTranscriptRef.current.trim();

    if (!transcript) {
      return;
    }

    manualStopRef.current = true;
    clearSilenceTimer();
    useAmaraStore.getState().setAudioLevel(0);
    useAmaraStore.getState().setMicActive(false);
    useAmaraStore.getState().setInterimTranscript('');
    useAmaraStore.getState().setTranscript(transcript);
    useAmaraStore.getState().setState('thinking');

    try {
      recognitionRef.current?.stop();
    } catch {}

    finalTranscriptRef.current = '';
    void callbackRef.current(transcript);
  }, [clearSilenceTimer]);

  const scheduleCompletion = useCallback(() => {
    clearSilenceTimer();
    silenceTimerRef.current = window.setTimeout(() => {
      silenceTimerRef.current = null;
      completeSpeech();
    }, SILENCE_TIMEOUT_MS);
  }, [clearSilenceTimer, completeSpeech]);

  const stopListening = useCallback(() => {
    manualStopRef.current = true;
    startPendingRef.current = false;
    clearSilenceTimer();
    clearRestartTimer();
    isListeningRef.current = false;
    setIsListening(false);
    useAmaraStore.getState().setMicActive(false);
    useAmaraStore.getState().setAudioLevel(0);

    try {
      recognitionRef.current?.stop();
    } catch {}
  }, [clearRestartTimer, clearSilenceTimer]);

  const initialiseRecognition = useCallback(() => {
    if (recognitionRef.current || !isSupported) {
      return recognitionRef.current;
    }

    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      return null;
    }

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      startPendingRef.current = false;
      isListeningRef.current = true;
      setIsListening(true);
      useAmaraStore.getState().setMicActive(true);
      useAmaraStore.getState().setError(null);
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let receivedFinalTranscript = false;

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const text = result[0]?.transcript?.trim();

        if (!text) {
          continue;
        }

        if (result.isFinal) {
          finalTranscriptRef.current = `${finalTranscriptRef.current} ${text}`.trim();
          receivedFinalTranscript = true;
        } else {
          interimTranscript = `${interimTranscript} ${text}`.trim();
        }
      }

      const visibleTranscript = [finalTranscriptRef.current, interimTranscript].filter(Boolean).join(' ').trim();

      if (!visibleTranscript) {
        return;
      }

      const store = useAmaraStore.getState();
      store.setError(null);
      store.setState('listening');
      store.setTranscript(visibleTranscript);
      store.setInterimTranscript(interimTranscript);
      store.setAudioLevel(estimateListeningLevel(visibleTranscript));

      if (receivedFinalTranscript) {
        scheduleCompletion();
      }
    };

    recognition.onerror = (event) => {
      const store = useAmaraStore.getState();

      if (event.error === 'no-speech') {
        return;
      }

      if (event.error === 'audio-capture') {
        manualStopRef.current = true;
        store.setError('No microphone detected. Connect a microphone to use AMARA.');
        store.setState('idle');
        store.setMicActive(false);
        return;
      }

      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        manualStopRef.current = true;
        store.setError('Microphone access needed. Allow microphone permission to activate AMARA.');
        store.setState('idle');
        store.setMicActive(false);
        return;
      }

      if (event.error === 'network') {
        store.setError('Speech recognition lost connection. Retrying…');
      }
    };

    recognition.onend = () => {
      startPendingRef.current = false;
      isListeningRef.current = false;
      setIsListening(false);
      useAmaraStore.getState().setMicActive(false);
      useAmaraStore.getState().setAudioLevel(0);

      if (manualStopRef.current || !enabledRef.current) {
        manualStopRef.current = false;
        return;
      }

      const currentState = useAmaraStore.getState().state;
      if (currentState === 'speaking' || currentState === 'thinking') {
        return;
      }

      clearRestartTimer();
      restartTimerRef.current = window.setTimeout(() => {
        if (manualStopRef.current || startPendingRef.current || isListeningRef.current || !enabledRef.current) {
          return;
        }

        try {
          startPendingRef.current = true;
          recognition.start();
        } catch {
          startPendingRef.current = false;
        }
      }, RESTART_DELAY_MS);
    };

    recognitionRef.current = recognition;
    return recognition;
  }, [clearRestartTimer, isSupported, scheduleCompletion]);

  const startListening = useCallback(async () => {
    const store = useAmaraStore.getState();

    if (!enabled) {
      return;
    }

    if (!isSupported) {
      store.setVoiceSupported(false);
      store.setError('Voice not supported in this browser. Use Chrome.');
      return;
    }

    const currentState = store.state;
    if (currentState === 'speaking' || currentState === 'thinking') {
      return;
    }

    const recognition = initialiseRecognition();
    if (!recognition || isListeningRef.current || startPendingRef.current) {
      return;
    }

    manualStopRef.current = false;
    clearRestartTimer();
    clearSilenceTimer();
    finalTranscriptRef.current = '';
    store.setVoiceSupported(true);
    store.setError(null);
    store.setInterimTranscript('');

    try {
      startPendingRef.current = true;
      recognition.start();
    } catch (error) {
      startPendingRef.current = false;
      if (!(error instanceof DOMException) || error.name !== 'InvalidStateError') {
        store.setError('Unable to start speech recognition.');
      }
    }
  }, [clearRestartTimer, clearSilenceTimer, enabled, initialiseRecognition, isSupported]);

  useEffect(() => {
    callbackRef.current = onSpeechComplete;
    enabledRef.current = enabled;
  }, [enabled, onSpeechComplete]);

  useEffect(() => {
    useAmaraStore.getState().setVoiceSupported(isSupported);

    if (!isSupported && enabled) {
      useAmaraStore.getState().setError('Voice not supported in this browser. Use Chrome.');
    }
  }, [enabled, isSupported]);

  useEffect(() => {
    if (!enabled) {
      const timer = window.setTimeout(() => {
        stopListening();
      }, 0);

      return () => {
        window.clearTimeout(timer);
      };
    }
  }, [enabled, stopListening]);

  useEffect(() => {
    return () => {
      clearSilenceTimer();
      clearRestartTimer();
      try {
        recognitionRef.current?.abort();
      } catch {}
    };
  }, [clearRestartTimer, clearSilenceTimer]);

  return {
    isListening,
    isSupported,
    startListening,
    stopListening,
  };
}
