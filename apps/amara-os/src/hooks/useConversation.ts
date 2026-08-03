'use client';

import { useCallback, useEffect, useRef } from 'react';
import { truncateForTts } from '@/lib/audio-utils';
import { useAmaraStore } from '@/stores/amara-store';
import type { ConversationMessage } from '@/types';

interface UseConversationOptions {
  speak: (text: string) => Promise<void>;
}

function extractDelta(data: string): string {
  if (!data || data === '[DONE]') {
    return '';
  }

  try {
    const payload = JSON.parse(data) as {
      choices?: Array<{
        delta?: { content?: string | Array<{ text?: string }> };
        message?: { content?: string };
      }>;
    };
    const content = payload.choices?.[0]?.delta?.content;

    if (typeof content === 'string') {
      return content;
    }

    if (Array.isArray(content)) {
      return content.map((part) => part.text || '').join('');
    }

    return payload.choices?.[0]?.message?.content || '';
  } catch {
    return '';
  }
}

function processSseEvents(
  payload: string,
  currentResponse: string,
  onPartial: (text: string) => void,
): string {
  let nextResponse = currentResponse;

  for (const event of payload.split('\n\n')) {
    if (!event.trim()) {
      continue;
    }

    for (const line of event.split('\n')) {
      if (!line.startsWith('data: ')) {
        continue;
      }

      const delta = extractDelta(line.slice(6).trim());
      if (!delta) {
        continue;
      }

      nextResponse += delta;
      onPartial(nextResponse);
    }
  }

  return nextResponse;
}

async function parseSseStream(
  stream: ReadableStream<Uint8Array>,
  onPartial: (text: string) => void,
): Promise<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullResponse = '';

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    fullResponse = processSseEvents(events.join('\n\n'), fullResponse, onPartial);
  }

  buffer += decoder.decode();
  fullResponse = processSseEvents(buffer, fullResponse, onPartial);

  return fullResponse.trim();
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as { error?: string } | null;
    if (payload?.error) {
      return payload.error;
    }
  }

  return (await response.text().catch(() => response.statusText)).trim() || response.statusText;
}

export function useConversation({ speak }: UseConversationOptions) {
  const historyRef = useRef<ConversationMessage[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const cancelPending = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const handleSpeechComplete = useCallback(
    async (transcript: string) => {
      const store = useAmaraStore.getState();
      const message = transcript.trim();

      if (!message) {
        store.setState('idle');
        return;
      }

      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        store.setError('Offline. Reconnect to the internet to talk with AMARA.');
        store.setState('idle');
        return;
      }

      cancelPending();
      const controller = new AbortController();
      abortRef.current = controller;

      store.setError(null);
      store.setTranscript(message);
      store.setInterimTranscript('');
      store.setResponse('');
      store.setState('thinking');

      let fullResponse = '';

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message,
            history: historyRef.current,
          }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(await readErrorMessage(response));
        }

        fullResponse = await parseSseStream(response.body, (partialText) => {
          useAmaraStore.getState().setResponse(partialText);
        });

        if (!fullResponse) {
          throw new Error('Received an empty response');
        }

        historyRef.current = [
          ...historyRef.current,
          { role: 'user', content: message } satisfies ConversationMessage,
          { role: 'assistant', content: fullResponse } satisfies ConversationMessage,
        ].slice(-20);
        useAmaraStore.getState().setResponse(fullResponse);
        await speak(truncateForTts(fullResponse));
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          store.setState('idle');
          return;
        }

        if (fullResponse) {
          console.error('TTS error:', error);
          store.setError('Speech output unavailable. Listening for your next question.');
          store.setState('idle');
          return;
        }

        console.error('Conversation error:', error);
        store.setError('Failed to get a response from AMARA.');
        store.triggerErrorPulse();
        store.setState('idle');
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [cancelPending, speak],
  );

  useEffect(() => cancelPending, [cancelPending]);

  return {
    cancelPending,
    handleSpeechComplete,
  };
}
