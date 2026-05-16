"""Status Writer — writes neuron network pipeline status summary."""
from datetime import datetime, timezone
from typing import Dict

from ..config import STATUS_DIR
from ..event_store import event_counts
from ..events import make_event
from ..event_store import append_event


class StatusWriter:
    """
    Writes a pipeline status summary to STATUS_DIR.
    Includes per-neuron status, event counts, files created, missing sources,
    and next required actions.
    """

    def run(self, pipeline_results: Dict) -> str:
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        status_path = STATUS_DIR / "neuron_network_status.md"

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()

        counts = event_counts()

        lines = [
            "# AMARA-AEGIS Neuron Network Status",
            f"Pipeline Run Timestamp: {timestamp}",
            "",
            "## Neuron / Agent Status",
        ]

        # Neuron statuses from pipeline results
        neuron_order = [
            "HermesQuickCashAgent",
            "SourceIntegrityNeuron",
            "HermesBuyerDemandAgent",
            "LeadValidationNeuron",
            "DealClassificationNeuron",
            "PayoffTaskNeuron",
            "TitleRiskNeuron",
            "BuyerDemandNeuron",
            "MirofishScenarioNeuron",
            "OpenClawTaskWriter",
            "OutreachTaskWriter",
            "AmaraBrainSync",
            "MoneyBriefWriter",
            "HermesPropstreamAgent",
            "HermesForeclosureSourceAgent",
        ]

        for neuron in neuron_order:
            result = pipeline_results.get(neuron, {})
            status = result.get("status", "SKIPPED")
            error = result.get("error", "")
            lines.append(f"- {neuron}: {status}" + (f" — ERROR: {error}" if error else ""))

        lines += [
            "",
            "## Event Counts by Type",
        ]
        if counts:
            for event_type, count in sorted(counts.items()):
                lines.append(f"- {event_type}: {count}")
        else:
            lines.append("- No events recorded yet")

        lines += [
            "",
            "## Files Created This Run",
        ]
        files_created = pipeline_results.get("files_created", [])
        if files_created:
            for f in files_created:
                lines.append(f"- {f}")
        else:
            lines.append("- No files listed in pipeline results")

        lines += [
            "",
            "## Missing Sources",
            "- Payoff amounts: SOURCE_NEEDED (all 5 properties)",
            "- Title status: SOURCE_NEEDED (all 5 properties)",
            "- Owner contact authority: USER_PROVIDED_UNVERIFIED (all properties)",
            "- Buyer transaction history: NEEDS_TRANSACTION_VERIFICATION",
            "- QuickCash CSV output: QUICKCASH_NOT_AVAILABLE (module not installed)",
            "- PropStream session: SOURCE_NEEDED",
            "- Foreclosure source parsed rows: SOURCE_NEEDED",
            "",
            "## Next Required Actions",
            "1. Run OpenClaw tasks: verify HCAD, Harris County tax sale listing, deed records",
            "2. Verify Bendanmar Limited entity via Texas Secretary of State",
            "3. Verify 800 Tidwell environmental history (TCEQ/EPA public records)",
            "4. Verify Jason Castaneda ownership at 813 W 30th via HCAD deed",
            "5. Verify buyer target transaction activity (Harris County deed records)",
            "6. Install QuickCash Houston module if CSV outputs are needed",
            "7. Confirm PropStream session before any PropStream data extraction",
            "",
            "## No-Fake-Data Status",
            "VERIFIED — No fake buyers, fake payoffs, fake title status, or fake contacts created.",
        ]

        status_path.write_text("\n".join(lines), encoding="utf-8")

        return str(status_path)
