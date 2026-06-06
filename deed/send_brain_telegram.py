"""
Standalone Telegram brain confirmation sender.
Sends the neural brain update confirmation to bot 7977783351.

Usage: cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/send_brain_telegram.py
"""
import subprocess
import sys

CHAT_ID = "7977783351"

MSG = """\
Neural brain updated — Harrison County WV title playbook locked in
Prepared by: Scott Schufford | Aces N 8s

Layers written:
✓ Neo4j   — 8 nodes + 10 relationships (parcel, owners, instruments, prospect)
✓ Mem0    — 9 persistent facts (IDX URL, VPN, SMB, TAGIS, branding, Dropbox)
✓ Qdrant  — 5 searchable chunks (chain, split estate, workflow, instrument, heirs)
✓ Outcomes — DEED run logged (9/10 steps, CORRECT)
✓ Obsidian — Harrison_County_11-409-19.md case study written
✓ Wiki    — WV_Title_Examination_Playbook.md locked in
✓ Langfuse — run trace logged

Parcel: 11-409-19 | Elk-Outside | Harrison County WV
Client: Texhoma Land Partners — Marcus Strunk RPL
OR: WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx — Marcus format — 3 wells added

Playbook locked for: Texhoma, EQT, 1809 Land Services, Purple Land Management\
"""


def _keychain(service: str, account: str) -> str | None:
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def send():
    import requests

    token = (
        _keychain("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
        or _keychain("TelegramBot",      "TelegramBot")
        or _keychain("telegram",         "bot_token")
    )
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in Mac Keychain.")
        print("Add it with:")
        print('  security add-generic-password -s TELEGRAM_BOT_TOKEN '
              '-a TELEGRAM_BOT_TOKEN -w "<your-token>"')
        sys.exit(1)

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": CHAT_ID, "text": MSG},
        timeout=15,
    )
    if r.ok:
        print(f"✓ Sent to {CHAT_ID}")
        print(MSG)
    else:
        print(f"✗ Telegram error {r.status_code}: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    send()
