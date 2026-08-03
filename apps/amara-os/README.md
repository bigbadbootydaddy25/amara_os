# AMARA OS

Voice-activated animated AI assistant with a fullscreen procedural avatar, reactive background orbs, and demo-mode state cycling.

## Setup

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment variables

Copy `.env.local.example` to `.env.local` and fill in values as needed.

- `ELEVENLABS_API_KEY` — ElevenLabs API key for future TTS integration
- `ELEVENLABS_VOICE_ID` — default ElevenLabs voice id
- `OPENCLAW_GATEWAY_URL` — optional websocket gateway URL
- `OPENCLAW_GATEWAY_TOKEN` — optional websocket auth token
- `OPENAI_API_KEY` — optional OpenAI fallback key
- `OPENAI_MODEL` — fallback OpenAI model name
- `NEXT_PUBLIC_DEMO_MODE` — `true` enables automatic state cycling demo mode

## Notes

Task 1 provides the visual foundation only. Task 2 will add voice input, TTS, and AI backend integration.
