import Anthropic from '@anthropic-ai/sdk';
import type { ConversationMessage } from '@/types';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// claude-sonnet-4-6: fast reasoning for conversational agent responses
export const REASONING_MODEL = 'claude-sonnet-4-6';
// claude-opus-4-7: deep analysis for MAO calculations and deal scoring
export const ANALYSIS_MODEL = 'claude-opus-4-7';
// claude-haiku-4-5: bulk tasks — data cleaning, tagging, deduplication
export const FAST_MODEL = 'claude-haiku-4-5-20251001';

/**
 * Stream a Claude response and convert it to OpenAI-compatible SSE format
 * so the existing frontend SSE parser works without changes.
 */
export function createAnthropicChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): ReadableStream<Uint8Array> {
  const systemMessage = messages.find((m) => m.role === 'system')?.content ?? '';
  const chatMessages = messages
    .filter((m) => m.role !== 'system')
    .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));

  const encoder = new TextEncoder();

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const stream = anthropic.messages.stream(
        {
          model: REASONING_MODEL,
          max_tokens: 4096,
          ...(systemMessage ? { system: systemMessage } : {}),
          messages: chatMessages,
        },
        { signal },
      );

      try {
        for await (const event of stream) {
          if (
            event.type === 'content_block_delta' &&
            event.delta.type === 'text_delta' &&
            event.delta.text
          ) {
            const data = JSON.stringify({
              choices: [{ delta: { content: event.delta.text } }],
            });
            controller.enqueue(encoder.encode(`data: ${data}\n\n`));
          }
        }

        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      } catch (err) {
        stream.abort();
        controller.error(err);
      }
    },
    cancel() {},
  });
}

export async function testConnection(): Promise<string> {
  const message = await anthropic.messages.create({
    model: FAST_MODEL,
    max_tokens: 64,
    messages: [{ role: 'user', content: 'Say "AMARA online" — nothing else.' }],
  });

  const block = message.content[0];
  return block.type === 'text' ? block.text : '';
}
