"""Failed Neuron Writer — writes a report of any neurons that failed during the pipeline run."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import FAILED_NEURONS_DIR


class FailedNeuronWriter:
    """
    Writes a report of failed neurons to FAILED_NEURONS_DIR.
    Each failure includes: neuron name, timestamp, error message, recommended action.
    """

    def run(self, failures: List[Dict]) -> str:
        FAILED_NEURONS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = FAILED_NEURONS_DIR / "latest_failed_neurons.md"

        now = datetime.now(timezone.utc).isoformat()

        lines = [
            "# Failed Neurons Report",
            f"Generated: {now}",
            f"Total Failures: {len(failures)}",
            "",
        ]

        if not failures:
            lines += [
                "## Result",
                "No failed neurons in this run.",
                "",
                "All neurons completed or were skipped gracefully.",
            ]
        else:
            lines += [
                "## Failed Neurons",
                "",
            ]
            for failure in failures:
                neuron = failure.get("neuron", "UNKNOWN_NEURON")
                timestamp = failure.get("timestamp", now)
                error = failure.get("error", "No error message provided")
                action = failure.get("recommended_action", "Investigate error and re-run neuron")

                lines += [
                    f"### {neuron}",
                    f"- Timestamp: {timestamp}",
                    f"- Error: {error}",
                    f"- Recommended Action: {action}",
                    "",
                ]

            lines += [
                "---",
                "",
                "## General Recovery Steps",
                "1. Check the event log for NEURON_FAILED events",
                "2. Verify that source files exist at expected paths",
                "3. Ensure all required directories exist",
                "4. Re-run only the failed neurons after fixing root cause",
                "5. Do NOT fake data to bypass failures — write SOURCE_NEEDED tasks instead",
            ]

        report_path.write_text("\n".join(lines), encoding="utf-8")

        return str(report_path)
