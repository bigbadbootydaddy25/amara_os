# Vendored binaries — provenance

These macOS binaries are vendored so `/watch` works without Homebrew. They
are not part of upstream `claude-watch` / `claude-video` — added locally when
this skill was installed into this repo. `scripts/binpath.py` resolves to
these first on macOS, falling back to `PATH` everywhere else (see that file).

| File | Source | Version / tag | SHA-256 |
|---|---|---|---|
| `yt-dlp_macos` | https://github.com/yt-dlp/yt-dlp/releases | `2026.08.19` | `0f192b7ec147ab6288885d6351d9ab67367640029b4377576ef46dd79cf7b202` |
| `ffmpeg-darwin-x64` | https://github.com/descriptinc/ffmpeg-ffprobe-static/releases | `b6.1.2-rc.1` | `4a4a968b98859588e98500ae25973d80a5ca5eed0724222b9f76360dcb72a001` |
| `ffprobe-darwin-x64` | https://github.com/descriptinc/ffmpeg-ffprobe-static/releases | `b6.1.2-rc.1` | `ce5414269f0efa1e88b5e23b57f801d5b9a40be554716544936e0332b4601a62` |

**Verification performed at install time:**
- `yt-dlp_macos` — checksum matched the project's own published
  `SHA2-256SUMS` file for release `2026.08.19` (yt-dlp signs/publishes this
  manifest on every release). ✅ Verified against publisher-signed manifest.
- `ffmpeg-darwin-x64` / `ffprobe-darwin-x64` — `descriptinc/ffmpeg-ffprobe-static`
  does **not** publish a checksums manifest for its releases, so these two are
  verified only by: (a) coming directly from `github.com/descriptinc/...`'s
  release-asset CDN over TLS, (b) matching the expected Mach-O x86_64
  executable format, and (c) the repo being a long-standing, widely-used
  (blessed by Descript, and the same static-ffmpeg lineage other tools like
  `fluent-ffmpeg`/`ffmpeg-static` rely on) source for these binaries. There is
  no independent signature to check them against — re-verify if you have
  reason to distrust this release.

**Re-verifying yt-dlp's checksum yourself:**
```bash
curl -fsSL -o SHA2-256SUMS \
  https://github.com/yt-dlp/yt-dlp/releases/download/2026.08.19/SHA2-256SUMS
grep yt-dlp_macos SHA2-256SUMS
shasum -a 256 bin/yt-dlp_macos
```

**Updating:** these are pinned, not auto-updated. To bump yt-dlp (it releases
frequently and video sites change often), download the new
`yt-dlp_macos` + its `SHA2-256SUMS` entry from
https://github.com/yt-dlp/yt-dlp/releases/latest, verify, replace the file in
this directory, and update the table above.
