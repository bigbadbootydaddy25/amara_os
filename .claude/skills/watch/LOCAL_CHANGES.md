# Local install notes

This directory is `taoufik123-collab/claude-watch` v0.2.0 (tag `v0.2.0`,
commit `f16bc84`), installed as a project skill under `.claude/skills/watch/`
in this repo. See `AUTHORS.md` / `LICENSE` for upstream attribution (MIT) —
claude-watch is itself an additive fork of `bradautomates/claude-video`
v0.1.3.

## What was audited before installing

- Diffed every shared script against `bradautomates/claude-video` — the fork
  is a clean, well-attributed superset (scene-change frames, hook microscope,
  structured `report.md`, Obsidian ingest gate). No behavioral divergence
  beyond what `CHANGELOG.md` documents.
- Read every script end-to-end: no obfuscation, no `eval`/remote code
  execution, no telemetry/beaconing. Network calls are limited to exactly
  what `SKILL.md`'s "Security & Permissions" section discloses — the source
  URL the user gives it (via `yt-dlp`), and `api.groq.com` /
  `api.openai.com` for the Whisper fallback, only when a key is configured.
  API keys are read from `~/.config/watch/.env` (0600) and never logged.
  Subprocess calls to `yt-dlp`/`ffmpeg` use `--`-separated argv and resolved
  absolute paths — no shell-injection surface.
- Confirmed `v0.1.3`'s documented CVE-style hardening (option-injection fix,
  `Path.resolve()` on all media paths) is present in this tag.

## What was changed from upstream for this install

- **Added `bin/`** — vendored macOS static builds of `yt-dlp`, `ffmpeg`, and
  `ffprobe` (see `bin/PROVENANCE.md` for exact versions/checksums), so
  `/watch` works on a fresh Mac with no Homebrew. This was the point of the
  install request; it is not part of upstream.
- **Added `scripts/binpath.py`** — resolves each binary to `bin/<file>` on
  macOS first, falling back to `PATH` (the original upstream behavior)
  everywhere else, including on any other OS or if `bin/` is missing a file.
- **Patched** `scripts/setup.py`, `scripts/download.py`, `scripts/frames.py`,
  `scripts/whisper.py`, `scripts/hook.py` to call `binpath.resolve(name)`
  instead of bare `shutil.which(name)` / literal `"ffmpeg"`/`"yt-dlp"` argv —
  same control flow and error messages, just vendor-aware. `scripts/tests/`
  and `scripts/build-skill.sh` (upstream's own `.skill`-zip packager, not
  used for this install) were left untouched.
- **`hooks/scripts/check-setup.sh`** — the SessionStart status line now also
  counts the vendored `bin/` binaries as "present" on macOS. This hook is
  copied for reference but is **not** wired into `.claude/settings.json` —
  wire it yourself if you want the one-line status on session start.

## Known gaps

- `bin/` binaries are macOS-only (Intel `ffmpeg`/`ffprobe`, universal
  `yt-dlp`). On Linux/Windows this skill falls back to expecting
  `ffmpeg`/`ffprobe`/`yt-dlp` on `PATH`, same as stock upstream.
- `ffmpeg`/`ffprobe` have no publisher-signed checksum to verify against
  (see `bin/PROVENANCE.md`) — only `yt-dlp`'s checksum was verified against
  a signed manifest.
- `yt-dlp` moves fast (frequent releases as sites change their players). The
  vendored copy is pinned to `2026.08.19` — update it periodically per
  `bin/PROVENANCE.md`.
