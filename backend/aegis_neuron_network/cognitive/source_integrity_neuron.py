"""Source Integrity Neuron — scans all data for contamination strings and invalid statuses."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..config import AMARA_BRAIN_AEGIS_ROOT, CONTAMINATION_STRINGS, FAILED_NEURONS_DIR
from ..events import make_event
from ..event_store import append_event


def _scan_value(value: Any, contamination_strings: List[str]) -> List[str]:
    """Recursively scan a value for any contamination strings. Returns list of hits."""
    hits = []
    if isinstance(value, str):
        for cs in contamination_strings:
            if cs.upper() in value.upper():
                hits.append(f"Found '{cs}' in value: {value[:100]!r}")
    elif isinstance(value, dict):
        for v in value.values():
            hits.extend(_scan_value(v, contamination_strings))
    elif isinstance(value, (list, tuple)):
        for item in value:
            hits.extend(_scan_value(item, contamination_strings))
    return hits


class SourceIntegrityNeuron:
    """
    Scans all string values in the provided data dict for contamination strings.
    Also checks buyer target statuses for illegal CONFIRMED_BUYER promotions.
    Fails closed: if contamination found, writes alert and emits CONTAMINATION_DETECTED.
    """

    def run(self, data: Dict) -> Dict:
        contamination_hits = []

        # 1. Scan for raw contamination strings
        string_hits = _scan_value(data, CONTAMINATION_STRINGS)
        contamination_hits.extend(string_hits)

        # 2. Check buyer statuses — CONFIRMED_BUYER without source is contamination
        buyer_status_hits = self._check_buyer_statuses(data)
        contamination_hits.extend(buyer_status_hits)

        if contamination_hits:
            # Fail closed — write alert file
            FAILED_NEURONS_DIR.mkdir(parents=True, exist_ok=True)
            alert_path = FAILED_NEURONS_DIR / "contamination_alert.md"
            alert_content = f"""# CONTAMINATION ALERT
Generated: {datetime.now(timezone.utc).isoformat()}
Status: CONTAMINATED — PIPELINE HALTED

## Details
{chr(10).join(f'- {hit}' for hit in contamination_hits)}

## Required Action
1. Do NOT proceed with contaminated data
2. Identify source of contamination
3. Remove all fake/test/demo/sample data
4. Re-run pipeline with clean data only

## Hard Rules Violated
- No fake data, no demo leads, no fake buyers
- Never use TEST_DATA_NOT_REAL, FAKE, SAMPLE, DEMO strings
- Never promote NOT_CONFIRMED_BUYER to CONFIRMED_BUYER without source

## Verification Status
CONTAMINATION_DETECTED — All outputs from this run are suspect
"""
            alert_path.write_text(alert_content, encoding="utf-8")

            ev = make_event(
                event_type="CONTAMINATION_DETECTED",
                source="SourceIntegrityNeuron",
                payload={
                    "contamination_hits": contamination_hits,
                    "alert_file": str(alert_path),
                },
                source_file=str(alert_path),
                verification_status="SOURCE_NEEDED",
                status="FAILED",
                notes="Contamination detected. Pipeline should not proceed.",
            )
            append_event(ev)

            return {
                "neuron": "SourceIntegrityNeuron",
                "status": "CONTAMINATED",
                "details": contamination_hits,
                "alert_file": str(alert_path),
            }

        # Clean
        ev = make_event(
            event_type="SOURCE_INTEGRITY_CHECKED",
            source="SourceIntegrityNeuron",
            payload={
                "result": "CLEAN",
                "contamination_strings_checked": CONTAMINATION_STRINGS,
                "buyer_status_checked": True,
            },
            verification_status="VERIFIED_SOURCE",
            status="COMPLETED",
            notes="No contamination strings or invalid buyer statuses found.",
        )
        append_event(ev)

        return {
            "neuron": "SourceIntegrityNeuron",
            "status": "CLEAN",
        }

    def _check_buyer_statuses(self, data: Dict) -> List[str]:
        """Walk the data looking for any buyer_status == CONFIRMED_BUYER."""
        hits = []
        self._walk_for_buyer_status(data, hits)
        return hits

    def _walk_for_buyer_status(self, value: Any, hits: List[str]) -> None:
        if isinstance(value, dict):
            if value.get("buyer_status") == "CONFIRMED_BUYER":
                hits.append(
                    f"CONFIRMED_BUYER status found without source verification: {value}"
                )
            for v in value.values():
                self._walk_for_buyer_status(v, hits)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._walk_for_buyer_status(item, hits)
