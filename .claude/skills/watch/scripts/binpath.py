#!/usr/bin/env python3
"""Resolve required binaries: prefer the skill's vendored bin/, fall back to PATH.

This skill vendors macOS static builds of ffmpeg, ffprobe, and yt-dlp under
`bin/` so /watch works without Homebrew (or any package manager) already
having them installed:

  bin/ffmpeg-darwin-x64   https://github.com/descriptinc/ffmpeg-ffprobe-static
  bin/ffprobe-darwin-x64  https://github.com/descriptinc/ffmpeg-ffprobe-static
  bin/yt-dlp_macos        https://github.com/yt-dlp/yt-dlp/releases

See bin/PROVENANCE.md for exact release tags and checksums.

Vendoring is macOS-only for now. On Linux/Windows (or if bin/ is missing a
binary), resolve() falls through to PATH via shutil.which(), same behavior
as before vendoring existed.
"""
from __future__ import annotations

import platform
import shutil
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

# Logical name -> vendored filename, macOS only.
_VENDORED_NAMES = {
    "ffmpeg": "ffmpeg-darwin-x64",
    "ffprobe": "ffprobe-darwin-x64",
    "yt-dlp": "yt-dlp_macos",
}


def resolve(name: str) -> str | None:
    """Return an absolute path to the `name` binary, vendored copy preferred.

    Falls back to PATH (shutil.which) when not on macOS, when bin/ doesn't
    have that binary, or when the vendored file isn't executable.
    """
    if platform.system() == "Darwin":
        vendored_name = _VENDORED_NAMES.get(name)
        if vendored_name:
            candidate = BIN_DIR / vendored_name
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                return str(candidate)
    return shutil.which(name)


def which_missing(names: list[str]) -> list[str]:
    """Like the REQUIRED_BINARIES check in setup.py, but vendor-aware."""
    return [n for n in names if resolve(n) is None]
