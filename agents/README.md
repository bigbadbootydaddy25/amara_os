# AMARA V12 — Phase 1 back end (Dallas County)

Spec: `docs/AMARA_V12_Cash_Buyer_Engine_SPEC.md`. Ruleset: `AMARA Constitution v2026.10.05`.
Owned by Claude Code; `/ui/` belongs to Cursor and is not touched here.

```
npm run amara -- weekly         # ingest-records → buyer-finder (SFR + lots) → buy-box
npm run amara -- daily          # ingest-research → ingest-records → distress-scout → matcher → morning-brief
npm run amara -- <job> [--as-of YYYY-MM-DD]   # single job: sync-sources | ingest-records | ingest-research | buyer-finder | buy-box | distress-scout | matcher | morning-brief
npm test
```

DB: SQLite at `data/amara.db` (override with `AMARA_DB`). Briefs: `out/briefs/`. Both are git-ignored.

## Gate
`sources.yaml` is the source of truth. A source runs automatically only if `access_status: approved` **and** `mode: auto`
(`agents/lib/sources.ts`). Today only the local `/inbox/research/` folder qualifies. No connector in Phase 1 makes
network calls; everything else is **assisted mode**: pull an export by hand and drop it in `/inbox/records/`.

## Inbox files
- `/inbox/research/*.csv` — Perplexity/Claude feeds (spec §7). Every row tagged `[SR]`, rows without an `evidence_url` discarded, queued in `research_buyers` / `research_deals`.
- `/inbox/records/<prefix>_*.csv` — assisted exports: `deeds_`, `dot_`, `properties_`, `lots_`, `permits_`, `distress_`, `enrichment_`.
  Each row needs a `source` that exists in `sources.yaml`; its `evidence_tier` ([GR] for government records) is stamped with the import date. Non-Dallas rows are rejected until `active_counties` grows.

## Assumptions to confirm (flagged in code/config)
- CAD land-use codes `A1` = SFR, `C1` = vacant residential lot (`agents/config.ts`) — check the DCAD data dictionary.
- `config/dallas-zoning.yaml` is `verified: false`, so Lot Gate zoning/min-size results show UNKNOWN, never PASS, until confirmed.
- Hard-money lender and national-builder/iBuyer lists in `config/` are seed lists.
- Repeat test counts the buyer group (shared registered agent + mailing) as one buyer; `buyers.repeat_basis` records `grantee` vs `group`.
- Morning Brief email is OFF; the brief is built and stored only.
