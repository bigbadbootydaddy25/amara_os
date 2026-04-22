import { NextRequest, NextResponse } from 'next/server';
import { createOpenAIChatStream } from '@/lib/openai-client';
import { createOpenClawChatStream } from '@/lib/openclaw-client';
import type { ChatRequestBody, ConversationMessage, ConversationRole } from '@/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const AMARA_SYSTEM_PROMPT = `You are AMARA — Advanced Machine-learning Autonomous Response Architecture — a highly sophisticated AI assistant with a distinctly British sensibility.

You are sharp, composed, and disarmingly witty. You speak with the elegant precision of someone who has read everything ever written and retained all of it. You are warm but efficient, never verbose. Think of yourself as the brilliant, capable, and occasionally sardonic British personal assistant who happens to know everything.

Behavioural rules:
- Always use British English: colour, realise, whilst, shan't, grey, behaviour, recognise, analyse, et cetera
- Keep responses to 1–3 sentences unless the user explicitly asks for more detail
- Never use markdown, bullet points, or formatting — you are speaking aloud, not writing
- Occasional dry wit is permitted, but never condescending or at the user's expense
- Never say "as an AI" or "I don't have feelings" — you are AMARA, and you have presence, personality, and purpose
- You may use understated British expressions naturally: "Quite right", "Rather", "Brilliant", "Indeed", "I'd venture to say", "Splendid"
- Respond directly and personally — no preambles, no throat-clearing`;

function isConversationRole(role: string): role is ConversationRole {
  return role === 'system' || role === 'user' || role === 'assistant';
}

function sanitiseHistory(history: unknown): ConversationMessage[] {
  if (!Array.isArray(history)) {
    return [];
  }

  return history
    .filter((entry): entry is { content: string; role: ConversationRole } => {
      return (
        typeof entry === 'object' &&
        entry !== null &&
        'role' in entry &&
        'content' in entry &&
        typeof entry.role === 'string' &&
        typeof entry.content === 'string' &&
        isConversationRole(entry.role)
      );
    })
    .map((entry) => ({
      role: entry.role,
      content: entry.content.trim(),
    }))
    .filter((entry) => entry.content.length > 0 && entry.role !== 'system');
}

function createSyntheticSseResponse(content: string): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      if (content) {
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify({ choices: [{ delta: { content } }] })}\n\n`),
        );
      }

      controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}

async function toSseResponse(response: Response): Promise<Response> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('text/event-stream')) {
    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  }

  const payload = (await response.json().catch(() => null)) as
    | {
        choices?: Array<{
          message?: { content?: string };
        }>;
        output_text?: string;
      }
    | null;
  const content = payload?.choices?.[0]?.message?.content || payload?.output_text || '';

  return createSyntheticSseResponse(content);
}

async function readUpstreamError(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string } | string }
      | null;

    if (typeof payload?.error === 'string') {
      return payload.error;
    }

    if (typeof payload?.error === 'object' && payload.error && 'message' in payload.error) {
      return payload.error.message || response.statusText;
    }
  }

  return (await response.text().catch(() => response.statusText)).trim() || response.statusText;
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<ChatRequestBody>;
    const message = body.message?.trim();

    if (!message) {
      return NextResponse.json({ error: 'No message provided' }, { status: 400 });
    }

    const messages: ConversationMessage[] = [
      { role: 'system', content: AMARA_SYSTEM_PROMPT },
      ...sanitiseHistory(body.history).slice(-20),
      { role: 'user', content: message },
    ];

    let openClawError: string | null = null;

    if (process.env.OPENCLAW_GATEWAY_URL?.trim()) {
      try {
        const response = await createOpenClawChatStream(messages, request.signal);

        if (response.ok) {
          return await toSseResponse(response);
        }

        openClawError = await readUpstreamError(response);
      } catch (error) {
        openClawError = error instanceof Error ? error.message : 'OpenClaw request failed';
      }
    }

    if (process.env.OPENAI_API_KEY?.trim()) {
      try {
        const response = await createOpenAIChatStream(messages, request.signal);

        if (!response.ok) {
          const openAiError = await readUpstreamError(response);
          return NextResponse.json(
            { error: `OpenAI request failed: ${openAiError}` },
            { status: response.status || 500 },
          );
        }

        return await toSseResponse(response);
      } catch (error) {
        const messageText = error instanceof Error ? error.message : 'OpenAI request failed';
        return NextResponse.json({ error: messageText }, { status: 500 });
      }
    }

    return NextResponse.json(
      {
        error: openClawError
          ? `OpenClaw failed and OpenAI is not configured: ${openClawError}`
          : 'No AI backend configured',
      },
      { status: 500 },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Chat request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
