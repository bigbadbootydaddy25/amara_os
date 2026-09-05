#!/usr/bin/env bash
# SessionStart hook for /watch — one-line status so users know what's wired up.
# Silent on ready state to avoid spam. Points at the installer when something
# is missing.
set -euo pipefail

CONFIG_FILE="$HOME/.config/watch/.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$SCRIPT_DIR/../../bin"

# Warn if the secrets file has loose permissions.
if [[ -f "$CONFIG_FILE" ]]; then
  perms=$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "/watch: WARNING — $CONFIG_FILE has permissions $perms (should be 600)."
    echo "  Fix: chmod 600 $CONFIG_FILE"
  fi
fi

# Load API keys from the config file without exporting them.
read_key() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    echo "${!name}"
    return
  fi
  if [[ -f "$CONFIG_FILE" ]]; then
    awk -F= -v k="$name" '
      /^[[:space:]]*#/ { next }
      $1 == k {
        sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2);
        gsub(/^["'\'']|["'\'']$/, "", $2);
        print $2; exit
      }
    ' "$CONFIG_FILE"
  fi
}

HAS_FFMPEG=""
HAS_YTDLP=""
# Vendored macOS binaries (bin/) count as present, same as setup.py/binpath.py.
if [[ "$(uname -s)" == "Darwin" && -x "$BIN_DIR/ffmpeg-darwin-x64" ]] || command -v ffmpeg >/dev/null 2>&1; then
  HAS_FFMPEG="yes"
fi
if [[ "$(uname -s)" == "Darwin" && -x "$BIN_DIR/yt-dlp_macos" ]] || command -v yt-dlp >/dev/null 2>&1; then
  HAS_YTDLP="yes"
fi

HAS_GROQ="$(read_key GROQ_API_KEY)"
HAS_OPENAI="$(read_key OPENAI_API_KEY)"
SETUP_COMPLETE="$(read_key SETUP_COMPLETE)"

# Fully configured → silent (Claude can surface status on demand via --check).
if [[ "$SETUP_COMPLETE" == "true" && -n "$HAS_FFMPEG" && -n "$HAS_YTDLP" ]]; then
  exit 0
fi

# First-run / partially-configured → one-line hint.
if [[ -z "$HAS_FFMPEG" || -z "$HAS_YTDLP" ]]; then
  echo "/watch: needs ffmpeg + yt-dlp. Run \`python3 $SCRIPT_DIR/../../scripts/setup.py\` once to install and scaffold config."
elif [[ -z "$HAS_GROQ" && -z "$HAS_OPENAI" ]]; then
  echo "/watch: ready for videos with native captions. Add GROQ_API_KEY (preferred) or OPENAI_API_KEY to ~/.config/watch/.env to unlock Whisper fallback."
else
  echo "/watch: ready."
fi
