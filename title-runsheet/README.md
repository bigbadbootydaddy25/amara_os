# Title Runsheet App

A standalone mineral-title runsheet pipeline: Postgres storage, Dropbox
folder intake/output, a six-agent abstracting pipeline, and a browser agent
that pulls recorded instruments from a title-search portal (TexasFile by
default) for a given survey tract.

This is a separate app from the rest of this repo (`amara_os`, a voice
assistant) — it lives entirely under `title-runsheet/` with its own
`package.json` and does not share code or dependencies with it.

## ⚠️ Read this before running anything

This was built without access to live Postgres, Dropbox, or portal
credentials. Concretely:

- **Postgres / Dropbox integration code** is complete and should work as-is
  against real credentials — `db/schema.sql`, `src/dropbox/client.ts`.
- **The TexasFile browser-agent selectors** (`src/browser/portals/texasfile.ts`)
  are **best-effort placeholders**, not verified against a live authenticated
  session. Every selector is marked `TODO verify` — run once with
  `PORTAL_HEADLESS=false` against a real TexasFile login/search and correct
  them before trusting the retrieval agent's output. See the comment at the
  top of that file for the verification steps.
- **Field extraction** (`src/agents/extraction/fieldExtractor.ts`) is a
  regex/keyword heuristic over embedded PDF text, not OCR or an LLM. It works
  on text-layer PDFs; scanned image-only instruments come back with no text
  and are flagged as document status `error` for manual handling (or wire in
  an OCR provider — see the TODO in `src/agents/extraction/pdfText.ts`).
- **"The six agents"**: the task that produced this app referred to "the six
  agents as they are," implying a pre-existing spec. No such spec exists
  anywhere in this repository or its history, so the six agents below are a
  reasonable default design for this domain, not a carry-over from elsewhere.
  Rename/restructure them freely — the pipeline stages in
  `src/orchestrator/pipeline.ts` are the only place that wires them together.

## The six agents

| # | Agent | File | Does |
|---|-------|------|------|
| 1 | Intake | `src/agents/intakeAgent.ts` | Indexes every file in the project's Dropbox seller-package folder into `documents`. |
| 2 | Instrument Retrieval (browser agent) | `src/agents/instrumentRetrievalAgent.ts` | Logs into the configured portal, searches the project's Section/Block/Township + County, downloads hits into the Dropbox recorded-instruments folder. |
| 3 | Abstracting | `src/agents/abstractingAgent.ts` | Extracts PDF text and parses runsheet fields (grantor/grantee, dates, volume/page, instrument #, legal description) into `instruments`. |
| 4 | Curative / QC | `src/agents/curativeAgent.ts` | Flags chain-of-title gaps, missing recording data, and low-confidence extractions into `curative_items`. |
| 5 | Runsheet Export | `src/agents/runsheetExportAgent.ts` | Orders instruments chronologically, writes `runsheet_entries`, exports a CSV to Dropbox. |
| 6 | Report | `src/agents/reportAgent.ts` | Renders a Word (.docx) title report (chain-of-title table + curative findings) to Dropbox. |

`src/orchestrator/pipeline.ts` runs all six in order for a project and stops
at the first failing stage. Every agent run is logged to `agent_runs` with
status/summary/error for audit.

## Setup

```bash
cd title-runsheet
npm install
cp .env.example .env   # fill in DATABASE_URL, Dropbox, and portal credentials
npm run migrate        # applies db/schema.sql
npx playwright install chromium   # only needed for the retrieval agent
```

## Usage

```bash
# Create a project scoped to a tract (defaults come from .env DEFAULT_* vars,
# which are pre-set to Section 47, Block 33, T1S, Howard County, TX)
npm run dev -- create-project --name "Smith Minerals"

npm run dev -- list-projects

# Run the full six-agent pipeline for a project
npm run dev -- pipeline <projectId>

# Re-run the pipeline starting partway through (e.g. after fixing selectors)
npm run dev -- pipeline <projectId> --from abstracting

# Run a single agent
npm run dev -- run intake <projectId>
npm run dev -- run retrieval <projectId>
npm run dev -- run abstracting <projectId>
npm run dev -- run curative <projectId>
npm run dev -- run runsheet <projectId>
npm run dev -- run report <projectId>
```

Each project maps to its own Dropbox folders (seller package, recorded
instruments, runsheet export, report export) so multiple tracts/deals can run
side by side without collision.

## Verifying without live credentials

`npm run smoke` exercises Postgres end-to-end (insert synthetic instruments,
run the curative agent, export CSV + a Word report) against `DATABASE_URL`
only — no Dropbox or portal credentials needed. It cleans up the project row
it creates. Useful for confirming a local Postgres/schema setup, or after
editing the curative rules or export templates, without needing the portal
selectors verified first.

## Extending

- **Different portal**: implement `PortalDriver` (`src/browser/types.ts`) for
  a county clerk's own search site, register it in
  `src/browser/portals/index.ts`, and set `PORTAL_NAME` in `.env`.
- **Better extraction**: swap `extractFields()` in
  `src/agents/extraction/fieldExtractor.ts` for an LLM-backed extractor — the
  return shape (`ExtractedFields`) is all `abstractingAgent.ts` depends on.
- **OCR for scanned instruments**: add a fallback in
  `src/agents/extraction/pdfText.ts` when `pdf-parse` returns empty text.
