import type { ConversationMessage } from '@/types';

function normaliseGatewayUrl(url: string): string {
  return url.replace(/^ws:\/\//, 'http://').replace(/^wss:\/\//, 'https://').replace(/\/$/, '');
}

export async function createOpenClawChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<Response> {
  const gatewayUrl = process.env.OPENCLAW_GATEWAY_URL?.trim();
  const gatewayToken = process.env.OPENCLAW_GATEWAY_TOKEN?.trim();

  if (!gatewayUrl) {
    throw new Error('OpenClaw gateway URL not configured');
  }

  return fetch(`${normaliseGatewayUrl(gatewayUrl)}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(gatewayToken ? { Authorization: `Bearer ${gatewayToken}` } : {}),
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
