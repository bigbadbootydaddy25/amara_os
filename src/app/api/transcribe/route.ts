import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  const apiKey = process.env.OPENAI_API_KEY?.trim();

  if (!apiKey) {
    return NextResponse.json({ error: 'OpenAI API key not configured' }, { status: 500 });
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ error: 'Invalid form data' }, { status: 400 });
  }

  const audioFile = formData.get('audio') as File | null;

  if (!audioFile || audioFile.size === 0) {
    return NextResponse.json({ transcript: '' });
  }

  const whisperForm = new FormData();
  whisperForm.append('file', audioFile, 'audio.webm');
  whisperForm.append('model', 'whisper-1');
  whisperForm.append('language', 'en');

  try {
    const response = await fetch('https://api.openai.com/v1/audio/transcriptions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}` },
      body: whisperForm,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Whisper API error');
      return NextResponse.json({ error: errorText }, { status: response.status });
    }

    const result = (await response.json()) as { text?: string };
    return NextResponse.json({ transcript: result.text?.trim() ?? '' });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Transcription failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
