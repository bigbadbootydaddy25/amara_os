import { truncateForTts } from '@/lib/audio-utils';

const DEFAULT_VOICE_ID = '4DH4Uqhp9kTcPJlssqc6';

export async function streamElevenLabsTts(text: string, signal?: AbortSignal): Promise<Response> {
  const apiKey = process.env.ELEVENLABS_API_KEY?.trim();

  if (!apiKey) {
    throw new Error('ElevenLabs API key not configured');
  }

  const voiceId = process.env.ELEVENLABS_VOICE_ID?.trim() || DEFAULT_VOICE_ID;
  const spokenText = truncateForTts(text);

  if (!spokenText) {
    throw new Error('No text provided');
  }

  return fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'xi-api-key': apiKey,
    },
    body: JSON.stringify({
      text: spokenText,
      model_id: 'eleven_flash_v2_5',
      voice_settings: {
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0,
        use_speaker_boost: true,
        speed: 1,
      },
      output_format: 'mp3_44100_128',
    }),
    cache: 'no-store',
    signal,
  });
}
