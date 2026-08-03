import { NextRequest, NextResponse } from 'next/server';
import { streamElevenLabsTts } from '@/lib/elevenlabs-tts';
import type { TtsRequestBody } from '@/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<TtsRequestBody>;
    const text = body.text?.trim();

    if (!text) {
      return NextResponse.json({ error: 'No text provided' }, { status: 400 });
    }

    const response = await streamElevenLabsTts(text, request.signal);

    if (!response.ok || !response.body) {
      const error = (await response.text().catch(() => response.statusText)).trim();
      return NextResponse.json(
        { error: `TTS failed: ${error || response.statusText}` },
        { status: response.status || 500 },
      );
    }

    return new Response(response.body, {
      headers: {
        'Content-Type': response.headers.get('content-type') || 'audio/mpeg',
        'Cache-Control': 'no-cache, no-transform',
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'TTS request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
