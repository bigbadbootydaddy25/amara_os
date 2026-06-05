"""
DEED crew config.
All credentials from Mac Keychain only — never hardcoded.
"""
import os
import subprocess
from pathlib import Path

# ── Parcel ───────────────────────────────────────────────────────────────────
PARCEL_ID      = "11-409-19"
DISTRICT       = "Elk"
COUNTY         = "Harrison"
STATE          = "WV"
ACRES          = 118.00
ASSIGNOR       = "Marcus Strunk RPL"
CLIENT         = "Texhoma Land Partners"
PREPARER       = "Scott Schufford"
COMPANY        = "Aces N 8s Acquisitions"
RUN_DATE       = "2026-06-04"
TITLE_TYPE     = "WS"   # White Space — no prior title on file

# ── Paths (Mac-first, cloud fallback) ───────────────────────────────────────
_BASE = Path(os.getenv("DEED_BASE", "/Users/user/aegis_os/deed"))
OUTPUT_DIR     = _BASE / "output"
MAPS_DIR       = OUTPUT_DIR / "maps"
NOTES_FILE     = OUTPUT_DIR / f"DEED_NOTES_{PARCEL_ID}.txt"
OR_FILE        = OUTPUT_DIR / f"{TITLE_TYPE}_{PARCEL_ID}_OR_{RUN_DATE}.xlsx"
PLOT_PNG       = OUTPUT_DIR / f"PLOT_{PARCEL_ID}.png"

# ── LLM (Ollama / OpenClaw) ──────────────────────────────────────────────────
OLLAMA_URL     = os.getenv("OLLAMA_URL",    "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",  "hermes3")
OPENCLAW_URL   = os.getenv("OPENCLAW_URL",  "http://127.0.0.1:18789")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID",   "7977783351")

# ── SMB ──────────────────────────────────────────────────────────────────────
SMB_HOST       = "WVDATA.TEXHOMALP.COM"
SMB_SHARE      = "DATA"
SMB_USER       = "SSchufford"
SMB_MOUNT      = Path("/Volumes/DATA")

# ── Hermes ────────────────────────────────────────────────────────────────────
HERMES_DIR     = Path(os.getenv("HERMES_DIR", "/Users/user/.hermes/hermes-agent"))

# ── Package output ────────────────────────────────────────────────────────────
PKG_NAME       = f"{TITLE_TYPE}_{PARCEL_ID}_OR_{RUN_DATE}"
PKG_DIR        = OUTPUT_DIR / PKG_NAME
OR_PDF_FILE    = PKG_DIR / f"{PKG_NAME}.pdf"

# ── HTTP scraper headers ─────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
TIMEOUT = 30


def keychain(service: str, account: str) -> str | None:
    """Read one password from Mac Keychain. Returns None if unavailable."""
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except FileNotFoundError:
        return None   # Not on Mac
    except Exception:
        return None


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
