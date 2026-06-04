"""
AMARA DEED Crew — central configuration.
All credentials from Mac Keychain or environment variables. Never hardcoded.
"""

import os
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Parcel / Assignment ─────────────────────────────────────────────────────
PARCEL_ID         = os.getenv("DEED_PARCEL_ID",    "11-409-19")
PARCEL_DISTRICT   = os.getenv("DEED_DISTRICT",     "Elk")
PARCEL_COUNTY     = os.getenv("DEED_COUNTY",       "Harrison")
PARCEL_STATE      = os.getenv("DEED_STATE",        "WV")
PARCEL_ACRES      = float(os.getenv("DEED_ACRES",  "118.00"))
ASSIGNMENT_FROM   = os.getenv("DEED_ASSIGNOR",     "Marcus Strunk RPL")
ASSIGNMENT_CLIENT = os.getenv("DEED_CLIENT",       "Texhoma Land Partners")
RUN_DATE          = "2026-06-04"

# ── Local services ──────────────────────────────────────────────────────────
OLLAMA_BASE       = os.getenv("OLLAMA_BASE_URL",   "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL",      "hermes3")
OPENCLAW_BASE     = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789")
NEO4J_URI         = os.getenv("NEO4J_URI",         "bolt://localhost:7687")
QDRANT_HOST       = os.getenv("QDRANT_HOST",       "localhost")
QDRANT_PORT       = int(os.getenv("QDRANT_PORT",   "6333"))

# ── Output paths ────────────────────────────────────────────────────────────
OUTPUT_DIR        = Path(os.getenv("DEED_OUTPUT_DIR",
                          str(Path(__file__).parent / "deed" / "output")))
OR_FILENAME       = f"WS_{PARCEL_ID}_OR_{RUN_DATE}.xlsx"
NOTES_FILENAME    = f"DEED_NOTES_{PARCEL_ID}.txt"

# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "7977783351")

# ── Request headers (impersonate a real browser) ────────────────────────────
SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
SCRAPER_TIMEOUT = 30


def _keychain_password(service: str, account: str) -> str | None:
    """Read a password from Mac Keychain. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass  # Not on Mac
    except Exception as e:
        log.warning("Keychain lookup failed for %s/%s: %s", service, account, e)
    return None


def load_credentials() -> dict:
    """Load all credentials from Mac Keychain → env var fallback."""
    creds = {
        "texhoma_vpn_user":      r"TexhomaLP\WVScottS",
        "texhoma_vpn_pass":      _keychain_password("Texhoma-VPN", r"TexhomaLP\WVScottS"),
        "texhoma_outlook_user":  r"WVTexhoma\SSchufford",
        "texhoma_outlook_pass":  _keychain_password("Texhoma-Outlook", r"WVTexhoma\SSchufford"),
        "texhoma_smb_user":      "SSchufford",
        "texhoma_smb_pass":      _keychain_password("Texhoma-SMB", "SSchufford"),
    }
    # Env var overrides
    if os.getenv("TEXHOMA_VPN_PASS"):
        creds["texhoma_vpn_pass"] = os.getenv("TEXHOMA_VPN_PASS")
    if os.getenv("TEXHOMA_OUTLOOK_PASS"):
        creds["texhoma_outlook_pass"] = os.getenv("TEXHOMA_OUTLOOK_PASS")
    if os.getenv("TEXHOMA_SMB_PASS"):
        creds["texhoma_smb_pass"] = os.getenv("TEXHOMA_SMB_PASS")
    return creds
