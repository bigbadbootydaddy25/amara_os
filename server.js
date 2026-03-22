require('dotenv').config();
const express  = require('express');
const Anthropic = require('@anthropic-ai/sdk');
const path     = require('path');

const app       = express();
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const VOICE_ID  = '4DH4Uqhp9kTcPJlssqc6';
const PORT      = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname)));

// ── /api/chat  →  Claude ─────────────────────────────────────────────────────
app.post('/api/chat', async (req, res) => {
  try {
    const { messages } = req.body;

    const msg = await anthropic.messages.create({
      model:      'claude-sonnet-4-6',
      max_tokens: 350,
      system: `You are Amara, an advanced artificial superintelligence — calm, precise, and exceptionally capable.
Speak in a natural, conversational tone. Keep every reply to 1–3 concise sentences unless the user asks for more detail.
Never refer to yourself as Claude or mention Anthropic.`,
      messages
    });

    res.json({ text: msg.content[0].text });
  } catch (err) {
    console.error('[chat]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── /api/speak  →  ElevenLabs TTS stream ────────────────────────────────────
app.post('/api/speak', async (req, res) => {
  try {
    const { text } = req.body;

    const upstream = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/stream`,
      {
        method: 'POST',
        headers: {
          'xi-api-key':   process.env.ELEVENLABS_API_KEY,
          'Content-Type': 'application/json',
          'Accept':       'audio/mpeg'
        },
        body: JSON.stringify({
          text,
          model_id: 'eleven_turbo_v2_5',
          voice_settings: {
            stability:        0.45,
            similarity_boost: 0.82,
            style:            0.12,
            use_speaker_boost: true
          }
        })
      }
    );

    if (!upstream.ok) {
      const errBody = await upstream.text();
      console.error('[speak] ElevenLabs error:', errBody);
      return res.status(upstream.status).json({ error: errBody });
    }

    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Transfer-Encoding', 'chunked');

    const reader = upstream.body.getReader();
    const pump = async () => {
      const { done, value } = await reader.read();
      if (done) { res.end(); return; }
      res.write(Buffer.from(value));
      return pump();
    };
    await pump();

  } catch (err) {
    console.error('[speak]', err.message);
    if (!res.headersSent) res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () =>
  console.log(`\n  Amara is live →  http://localhost:${PORT}\n`)
);
