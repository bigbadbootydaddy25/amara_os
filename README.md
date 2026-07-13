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

---

# AMARA OS Backend (Phase 1)

The Python backend is the foundation and learning substrate for AMARA OS:
a local-first AI operations platform for Aces N 8s / Texhoma Land
Consultants. It runs entirely on this machine -- no VPS, no remote
deployment.

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

Start [Ollama](https://ollama.com) locally and pull the default models:

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

Apply the migrations in `/migrations` (numbered, idempotent) to your
Supabase project, in order, via the Supabase SQL editor or CLI.

Run the API:

```bash
uvicorn app.main:app --reload
```

`GET /health` returns the workspace registry and provider status (Ollama
reachability, whether a Claude API key is present).

## Environment variables (backend)

See `.env.example`:

- `ANTHROPIC_API_KEY` -- Claude API key, used for reasoning-heavy tasks
- `OLLAMA_BASE_URL` -- defaults to `http://localhost:11434`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`

## Architecture

- `app/config.py` -- loads `.env` (secrets) and `config.yaml` (workspace
  registry, active client list, LLM routing table, identity/visual
  constants, Phase 2 presence stubs).
- `app/llm/` -- provider-agnostic `LLMProvider` interface with `ollama`
  (local, default) and `anthropic` (Claude, for reasoning tasks)
  implementations. Streaming-ready from Phase 1.
- `app/foreman/` -- FOREMAN v0: a rule-based task router. `POST /tasks`
  retrieves similar past outcomes, builds a prompt (persona + history +
  payload), calls the routed provider, runs the result through the guard
  rails, writes an outcome_log row, and returns
  `{text, speakable_text, workspace, task_id}`.
- `app/memory/` -- the outcome log: every task execution is recorded;
  `PATCH /outcomes/{id}` lets Scott close the loop with a correction;
  `similar_outcomes()` retrieves past precedent via pgvector similarity.
  This retrieval loop is the Phase 1 self-learning mechanism -- zero model
  training required.
- `app/identity/` -- the AMARA persona prompt (`amara_system.md`) and
  `branding.py`, the single choke point for client deliverables (Scott
  Schufford byline, no AI system names).
- `app/guards/` -- hard-rule enforcement: HomeVestors blacklist, locked
  SFR formula (rejects ARV-percentage patterns), and the buyer-first deal
  pipeline guard.

## Tests

```bash
.venv/bin/pytest
```

## Phase 2 boundary

Out of scope for Phase 1, by design: the full 16-agent roster, REFLECT,
Telegram bridges, Mapbox/PLOT, the Advisory Board, ElevenLabs voice, and
HeyGen LiveAvatar. Phase 1 leaves clean attachment points only:

- Every task result already returns `speakable_text` alongside `text`.
- `LLMProvider.stream()` is implemented now so Phase 2 can consume
  incremental text without changing the interface.
- `config.yaml`'s `presence:` block reserves `elevenlabs_voice_id`,
  `heygen_avatar_id`, and `heygen_mode` -- no code reads them yet.
- `assets/amara-portrait.png` (provided by Scott, not included in this
  repo) is the reserved location for AMARA's portrait, used by the Phase 2
  UI and HeyGen photo-avatar creation.
