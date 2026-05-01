import type { ConversationMessage } from '@/types';

const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL?.trim() || 'http://localhost:11434';
const OLLAMA_MODEL = process.env.OLLAMA_MODEL?.trim() || 'llama3';

export async function createOllamaChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<Response> {
  return fetch(`${OLLAMA_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: OLLAMA_MODEL,
      messages,
      stream: true,
    }),
    cache: 'no-store',
    signal,
  });
}
