import type { ConversationMessage } from '@/types';

const DEFAULT_OLLAMA_URL = 'http://localhost:11434';

export async function createOllamaChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<Response> {
  const baseUrl = (process.env.OLLAMA_BASE_URL || DEFAULT_OLLAMA_URL).replace(/\/$/, '');
  const model = process.env.OLLAMA_MODEL || 'llama3.2';

  return fetch(`${baseUrl}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: true }),
    cache: 'no-store',
    signal,
  });
}

export function isOllamaConfigured(): boolean {
  return Boolean(process.env.OLLAMA_BASE_URL?.trim() || process.env.OLLAMA_MODEL?.trim());
}
