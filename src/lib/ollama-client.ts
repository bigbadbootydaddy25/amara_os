import type { ConversationMessage } from '@/types';

const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL?.trim() || 'http://localhost:11434';
const OLLAMA_MODEL = process.env.OLLAMA_MODEL?.trim() || 'llama3.2:3b';

export async function createOllamaChatStream(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<Response> {
  const ollamaMessages = messages.map((m) => ({ role: m.role, content: m.content }));

  return fetch(`${OLLAMA_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: OLLAMA_MODEL,
      messages: ollamaMessages,
      stream: true,
    }),
    cache: 'no-store',
    signal,
  });
}

export async function toSseFromOllamaStream(response: Response): Promise<Response> {
  if (!response.body) {
    return new Response('data: [DONE]\n\n', {
      headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
    });
  }

  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = response.body!.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          for (const line of text.split('\n')) {
            if (!line.trim()) continue;
            try {
              const obj = JSON.parse(line) as {
                message?: { content?: string };
                done?: boolean;
              };
              if (obj.message?.content) {
                const sseChunk = JSON.stringify({
                  choices: [{ delta: { content: obj.message.content } }],
                });
                controller.enqueue(encoder.encode(`data: ${sseChunk}\n\n`));
              }
              if (obj.done) {
                controller.enqueue(encoder.encode('data: [DONE]\n\n'));
              }
            } catch {
              // skip non-JSON lines
            }
          }
        }
      } finally {
        reader.releaseLock();
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
