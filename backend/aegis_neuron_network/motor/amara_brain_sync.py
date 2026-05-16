"""AMARA Brain Sync — copies QuickCash outputs to AMARA_BRAIN with timestamped backups."""
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from ..config import (
    AMARA_BRAIN_AEGIS_ROOT,
    BUYER_DEMAND_DIR,
    EXPECTED_BUYER_TARGET_FILES,
    EXPECTED_QUICKCASH_FILES,
    OPENCLAW_TASKS_DIR,
    REPORTS_DIR,
    SOURCE_LOGS_DIR,
    TAX_SALE_STRIKES_DIR,
)
from ..events import make_event
from ..event_store import append_event

# Mapping: QuickCash source key -> AMARA_BRAIN destination path
SYNC_MAP = {
    "strike_board": TAX_SALE_STRIKES_DIR / "houston_tax_sale_strike_board.csv",
    "strike_brief": TAX_SALE_STRIKES_DIR / "houston_tax_sale_strike_brief.md",
    "buyer_demand_needed": BUYER_DEMAND_DIR / "buyer_demand_needed.md",
    "buyer_verification_tasks": BUYER_DEMAND_DIR / "buyer_verification_tasks.md",
    "openclaw_buyer_research": OPENCLAW_TASKS_DIR / "openclaw_buyer_research_tasks.md",
    "payoff_verification": REPORTS_DIR / "payoff_verification_needed_quickcash.md",
    "title_risk": REPORTS_DIR / "title_risk_checklist_quickcash.md",
}

BUYER_TARGET_SYNC_MAP = {
    "downtown_commercial": TAX_SALE_STRIKES_DIR / "buyer_targets" / "downtown_commercial_buyers.csv",
    "tidwell_auto": TAX_SALE_STRIKES_DIR / "buyer_targets" / "tidwell_commercial_auto_buyers.csv",
    "infill_77018": TAX_SALE_STRIKES_DIR / "buyer_targets" / "77018_infill_builders.csv",
    "buyer_summary": TAX_SALE_STRIKES_DIR / "buyer_targets" / "buyer_target_summary.md",
}


def _backup_if_exists(dest: Path) -> None:
    """Create a timestamped backup if destination file already exists."""
    if dest.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = dest.with_suffix(f".{ts}{dest.suffix}")
        shutil.copy2(dest, backup)


def _write_source_needed_task(dest: Path, source_key: str) -> None:
    """Write a SOURCE_NEEDED placeholder task if the source file is missing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# SOURCE_NEEDED Task\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"Source file for '{source_key}' was not found at expected QuickCash path.\n\n"
        f"## Required Action\n"
        f"1. Run QuickCash Houston module to generate: {source_key}\n"
        f"2. Re-run AMARA Brain Sync after QuickCash output is available\n\n"
        f"## Verification Status\n"
        f"SOURCE_NEEDED — No data to sync for this file.\n"
    )
    dest.write_text(content, encoding="utf-8")


class AmaraBrainSync:
    """
    Syncs QuickCash output files to AMARA_BRAIN_AEGIS_ROOT.
    Creates timestamped backups if target files already exist.
    Writes SOURCE_NEEDED task files for missing sources.
    """

    def run(self, quickcash_data: Dict) -> Dict:
        synced = []
        skipped = []
        tasks_created = []
        timestamp = datetime.now(timezone.utc).isoformat()

        # Ensure all destination dirs exist
        for d in [
            TAX_SALE_STRIKES_DIR,
            BUYER_DEMAND_DIR,
            OPENCLAW_TASKS_DIR,
            REPORTS_DIR,
            SOURCE_LOGS_DIR,
            TAX_SALE_STRIKES_DIR / "buyer_targets",
        ]:
            d.mkdir(parents=True, exist_ok=True)

        # Sync main QuickCash files
        for key, dest in SYNC_MAP.items():
            src = EXPECTED_QUICKCASH_FILES.get(key)
            if src and src.exists():
                try:
                    _backup_if_exists(dest)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    synced.append({"key": key, "source": str(src), "dest": str(dest)})
                except Exception as exc:
                    skipped.append({"key": key, "reason": str(exc)})
            else:
                task_dest = dest.with_suffix(".source_needed.md")
                _write_source_needed_task(task_dest, key)
                tasks_created.append({"key": key, "task_file": str(task_dest)})
                skipped.append({"key": key, "reason": f"Source file not found: {src}"})

        # Sync buyer target files
        for key, dest in BUYER_TARGET_SYNC_MAP.items():
            src = EXPECTED_BUYER_TARGET_FILES.get(key)
            if src and src.exists():
                try:
                    _backup_if_exists(dest)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    synced.append({"key": f"buyer_target:{key}", "source": str(src), "dest": str(dest)})
                except Exception as exc:
                    skipped.append({"key": f"buyer_target:{key}", "reason": str(exc)})
            else:
                task_dest = dest.with_suffix(".source_needed.md")
                _write_source_needed_task(task_dest, f"buyer_target:{key}")
                tasks_created.append({"key": f"buyer_target:{key}", "task_file": str(task_dest)})
                skipped.append({"key": f"buyer_target:{key}", "reason": f"Source file not found: {src}"})

        sync_report = {
            "timestamp": timestamp,
            "synced_count": len(synced),
            "skipped_count": len(skipped),
            "tasks_created_count": len(tasks_created),
            "synced": synced,
            "skipped": skipped,
            "tasks_created": tasks_created,
        }

        ev = make_event(
            event_type="AMARA_BRAIN_SYNCED",
            source="AmaraBrainSync",
            payload=sync_report,
            verification_status="SOURCE_NEEDED" if skipped else "VERIFIED_SOURCE",
            status="COMPLETED",
            notes=(
                f"Synced {len(synced)} files. "
                f"Skipped {len(skipped)} (source not available). "
                f"Created {len(tasks_created)} SOURCE_NEEDED task files."
            ),
        )
        append_event(ev)

        return sync_report
