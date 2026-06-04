"""
Telegram alert client for AMARA DEED crew.
Bot token from TELEGRAM_BOT_TOKEN env var only — Mac Keychain lookup optional.
Hard fail is logged; alert send failure is logged but never crashes the crew.
"""

import logging
import os
import subprocess

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)


def _resolve_token() -> str:
    token = TELEGRAM_BOT_TOKEN.strip()
    if token:
        return token
    # Try Mac Keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "TELEGRAM_BOT_TOKEN", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def send(message: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """
    Send a Telegram message. Returns True on success.
    Logs failure but never raises.
    """
    token = _resolve_token()
    if not token:
        log.warning("TELEGRAM: no bot token found — alert not sent. "
                    "Set TELEGRAM_BOT_TOKEN env var or add to Mac Keychain "
                    "under service 'TELEGRAM_BOT_TOKEN'.")
        return False

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
        if r.status_code == 200:
            log.info("TELEGRAM: alert sent to chat %s", chat_id)
            return True
        log.error("TELEGRAM: send failed HTTP %s — %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.error("TELEGRAM: send exception — %s", e)
        return False


def send_hard_fail(step: str, detail: str) -> None:
    """Send an immediate hard-fail alert."""
    msg = (
        f"🚨 <b>DEED HARD FAIL — {step}</b>\n"
        f"Parcel: 11-409-19 | Harrison County WV\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{detail}"
    )
    send(msg)
