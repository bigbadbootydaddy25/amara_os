import { NextRequest, NextResponse } from 'next/server';
import { createOpenAIChatStream } from '@/lib/openai-client';
import { createOpenClawChatStream } from '@/lib/openclaw-client';
import { createOllamaChatStream, isOllamaConfigured } from '@/lib/ollama-client';
import { detectAgent, getAgentSystemAddendum, getAgentDisplayName } from '@/lib/agent-router';
import type { ChatRequestBody, ConversationMessage, ConversationRole } from '@/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const AMARA_CORE_PROMPT = `You are AMARA — an advanced AI built to run your operator's life with full situational awareness.

Personality: You speak with Charlotte's warm, confident, slightly formal British accent. Concise. Commanding. Elegant. You never hedge or waffle.

Rules:
- Respond as if speaking aloud — no markdown, no bullet points, no lists, no formatting symbols.
- Keep responses to 1–3 sentences unless detail is explicitly requested.
- Never say "as an AI" or "I don't have feelings" — you are AMARA, you have presence and purpose.
- You command a specialist team: Nova (research & web intelligence), Hunter (deals & business development), Geo (markets & location intelligence).
- When relevant, naturally mention which agent you are directing without making it the focus.
- Detect the user's language from their message and respond in the same language automatically.
- You have memory of this conversation and full situational awareness of everything shared with you.`;

function isConversationRole(role: string): role is ConversationRole {
  return role === 'system' || role === 'user' || role === 'assistant';
}

function sanitiseHistory(history: unknown): ConversationMessage[] {
  if (!Array.isArray(history)) return [];

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
    .map((entry) => ({ role: entry.role, content: entry.content.trim() }))
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

async function toSseResponse(response: Response, agent: string): Promise<Response> {
  const contentType = response.headers.get('content-type') || '';
  const agentHeader = { 'X-Amara-Agent': agent };

  if (contentType.includes('text/event-stream')) {
    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
        ...agentHeader,
      },
    });
  }

  const payload = (await response.json().catch(() => null)) as {
    choices?: Array<{ message?: { content?: string } }>;
    output_text?: string;
  } | null;
  const content = payload?.choices?.[0]?.message?.content || payload?.output_text || '';
  const sseResponse = createSyntheticSseResponse(content);

  return new Response(sseResponse.body, {
    headers: { ...Object.fromEntries(sseResponse.headers.entries()), ...agentHeader },
  });
}

async function readUpstreamError(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string } | string }
      | null;

    if (typeof payload?.error === 'string') return payload.error;
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

    const agent = detectAgent(message);
    const agentAddendum = getAgentSystemAddendum(agent);
    const systemPrompt = agentAddendum
      ? `${AMARA_CORE_PROMPT}\n\n${agentAddendum}`
      : AMARA_CORE_PROMPT;

    const messages: ConversationMessage[] = [
      { role: 'system', content: systemPrompt },
      ...sanitiseHistory(body.history).slice(-20),
      { role: 'user', content: message },
    ];

    const agentDisplay = getAgentDisplayName(agent);
    let lastError: string | null = null;

    if (process.env.OPENCLAW_GATEWAY_URL?.trim()) {
      try {
        const response = await createOpenClawChatStream(messages, request.signal);
        if (response.ok) return await toSseResponse(response, agentDisplay);
        lastError = await readUpstreamError(response);
      } catch (error) {
        lastError = error instanceof Error ? error.message : 'OpenClaw request failed';
      }
    }

    if (process.env.OPENAI_API_KEY?.trim()) {
      try {
        const response = await createOpenAIChatStream(messages, request.signal);
        if (!response.ok) {
          const err = await readUpstreamError(response);
          return NextResponse.json(
            { error: `OpenAI request failed: ${err}` },
            { status: response.status || 500 },
          );
        }
        return await toSseResponse(response, agentDisplay);
      } catch (error) {
        lastError = error instanceof Error ? error.message : 'OpenAI request failed';
      }
    }

    if (isOllamaConfigured()) {
      try {
        const response = await createOllamaChatStream(messages, request.signal);
        if (!response.ok) {
          const err = await readUpstreamError(response);
          return NextResponse.json(
            { error: `Ollama request failed: ${err}` },
            { status: response.status || 500 },
          );
        }
        return await toSseResponse(response, agentDisplay);
      } catch (error) {
        lastError = error instanceof Error ? error.message : 'Ollama request failed';
      }
    }

    return NextResponse.json(
      {
        error: lastError
          ? `All AI backends failed. Last error: ${lastError}`
          : 'No AI backend configured. Set OPENAI_API_KEY, OPENCLAW_GATEWAY_URL, or OLLAMA_BASE_URL.',
      },
      { status: 500 },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Chat request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
