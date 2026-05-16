"""Bridge between the AEGIS Neuron Network and the QuickCash Houston module."""
import csv
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .config import (
    EXPECTED_BUYER_TARGET_FILES,
    EXPECTED_QUICKCASH_FILES,
    KNOWN_STRIKE_BOARD,
    OPENCLAW_TASKS_DIR,
    QUICKCASH_AEGIS_OUTPUTS,
    QUICKCASH_ROOT,
)
from .events import make_event
from .event_store import append_event


def ensure_quickcash_outputs_exist() -> Dict:
    """
    Check whether QUICKCASH_ROOT and expected output files exist.

    If not, attempt to run the QuickCash CLI. If that fails (or the root
    doesn't exist at all), log a NEURON_FAILED event and return a task dict
    instead of raising or faking data.
    """
    if not QUICKCASH_ROOT.exists():
        error_msg = f"QUICKCASH_ROOT does not exist: {QUICKCASH_ROOT}"
        _log_neuron_failed("quickcash_bridge.ensure_quickcash_outputs_exist", error_msg)
        return {
            "status": "QUICKCASH_NOT_AVAILABLE",
            "error": error_msg,
            "task": f"Install and run QuickCash Houston module at {QUICKCASH_ROOT}",
        }

    # Check which files are already present
    found = {}
    missing = {}
    for key, path in EXPECTED_QUICKCASH_FILES.items():
        if path.exists():
            found[key] = str(path)
        else:
            missing[key] = str(path)

    if missing:
        # Attempt to generate them via the CLI
        try:
            result = subprocess.run(
                ["python", "-m", "aegis_neurons.cli", "houston-all"],
                cwd=QUICKCASH_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr or "Non-zero exit from QuickCash CLI")
            # Re-check after run
            for key, path in EXPECTED_QUICKCASH_FILES.items():
                if path.exists():
                    found[key] = str(path)
                    missing.pop(key, None)
        except Exception as exc:
            error_msg = str(exc)
            _log_neuron_failed("quickcash_bridge.ensure_quickcash_outputs_exist", error_msg)
            return {
                "status": "QUICKCASH_NOT_AVAILABLE",
                "error": error_msg,
                "task": f"Install and run QuickCash Houston module at {QUICKCASH_ROOT}",
                "found_files": found,
                "missing_files": missing,
            }

    return {
        "status": "QUICKCASH_AVAILABLE" if not missing else "QUICKCASH_PARTIAL",
        "found_files": found,
        "missing_files": missing,
    }


def load_strike_board() -> Dict:
    """
    Read the strike board CSV if it exists, else fall back to KNOWN_STRIKE_BOARD.
    Returns a dict with 'properties' list and 'source' indicator.
    """
    csv_path = EXPECTED_QUICKCASH_FILES["strike_board"]
    if csv_path.exists():
        properties = []
        try:
            with csv_path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    properties.append(dict(row))
            return {
                "source": "VERIFIED_SOURCE",
                "source_file": str(csv_path),
                "properties": properties,
                "count": len(properties),
            }
        except Exception as exc:
            _log_neuron_failed("quickcash_bridge.load_strike_board", str(exc))
            # Fall through to config fallback

    # Config fallback — data is from a prior completed QuickCash run, not fabricated
    return {
        "source": "NOTE_USING_CONFIG_FALLBACK",
        "source_file": "backend/aegis_neuron_network/config.py",
        "properties": KNOWN_STRIKE_BOARD,
        "count": len(KNOWN_STRIKE_BOARD),
        "note": "CSV not found at expected path. Using known strike board from config. Run QuickCash to regenerate.",
    }


def load_buyer_targets() -> Dict:
    """
    Read all buyer target CSV files. Counts rows per file.
    All buyer targets preserve NOT_CONFIRMED_BUYER status.
    """
    results = {}
    total_count = 0

    for key, path in EXPECTED_BUYER_TARGET_FILES.items():
        if key == "buyer_summary":
            # Markdown, not CSV
            if path.exists():
                results[key] = {
                    "path": str(path),
                    "type": "markdown",
                    "exists": True,
                }
            else:
                results[key] = {"path": str(path), "type": "markdown", "exists": False}
            continue

        if not path.exists():
            results[key] = {
                "path": str(path),
                "exists": False,
                "count": 0,
                "buyers": [],
                "buyer_status": "NOT_CONFIRMED_BUYER",
            }
            continue

        try:
            buyers = []
            with path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    entry = dict(row)
                    # Enforce NOT_CONFIRMED_BUYER regardless of what CSV says
                    entry["buyer_status"] = "NOT_CONFIRMED_BUYER"
                    buyers.append(entry)
            total_count += len(buyers)
            results[key] = {
                "path": str(path),
                "exists": True,
                "count": len(buyers),
                "buyers": buyers,
                "buyer_status": "NOT_CONFIRMED_BUYER",
            }
        except Exception as exc:
            _log_neuron_failed(f"quickcash_bridge.load_buyer_targets[{key}]", str(exc))
            results[key] = {
                "path": str(path),
                "exists": True,
                "count": 0,
                "buyers": [],
                "buyer_status": "NOT_CONFIRMED_BUYER",
                "error": str(exc),
            }

    return {
        "files": results,
        "total_buyer_target_count": total_count,
        "buyer_status": "NOT_CONFIRMED_BUYER",
    }


def load_markdown_outputs() -> Dict:
    """
    Read all expected markdown output files.
    Returns dict of filename -> content (or SOURCE_NEEDED if missing).
    """
    outputs = {}
    md_keys = ["strike_brief", "buyer_demand_needed", "buyer_verification_tasks",
               "openclaw_buyer_research", "payoff_verification", "title_risk"]
    for key in md_keys:
        path = EXPECTED_QUICKCASH_FILES[key]
        if path.exists():
            try:
                outputs[key] = {
                    "path": str(path),
                    "exists": True,
                    "content": path.read_text(encoding="utf-8"),
                }
            except Exception as exc:
                outputs[key] = {"path": str(path), "exists": True, "content": None, "error": str(exc)}
        else:
            outputs[key] = {
                "path": str(path),
                "exists": False,
                "content": None,
                "status": "SOURCE_NEEDED",
            }
    return outputs


def run_quickcash_houston_all() -> Dict:
    """Explicitly trigger the QuickCash Houston-all CLI run."""
    return ensure_quickcash_outputs_exist()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_neuron_failed(neuron: str, error: str) -> None:
    """Emit a NEURON_FAILED event to the event log."""
    ev = make_event(
        event_type="NEURON_FAILED",
        source=neuron,
        payload={"neuron": neuron, "error": error},
        verification_status="SOURCE_NEEDED",
        status="FAILED",
        notes=error,
    )
    try:
        append_event(ev)
    except Exception:
        pass  # Never let logging failures break the caller
