import type { ConversationMessage } from '@/types';

const OPENAI_CHAT_COMPLETIONS_URL = 'https://api.openai.com/v1/chat/completions';

export async function createOpenAIChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<Response> {
  const apiKey = process.env.OPENAI_API_KEY?.trim();

  if (!apiKey) {
    throw new Error('OpenAI API key not configured');
  }

  return fetch(OPENAI_CHAT_COMPLETIONS_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: process.env.OPENAI_MODEL || 'gpt-4o',
      messages,
      stream: true,
    }),
    cache: 'no-store',
    signal,
  });
}
