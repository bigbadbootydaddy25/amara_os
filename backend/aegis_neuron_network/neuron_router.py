"""Neuron Router — orchestrates all AEGIS Neuron Network pipeline runs."""
from datetime import datetime, timezone
from typing import Dict, List

from . import quickcash_bridge
from .cognitive.buyer_demand_neuron import BuyerDemandNeuron
from .cognitive.deal_classification_neuron import DealClassificationNeuron
from .cognitive.lead_validation_neuron import LeadValidationNeuron
from .cognitive.mirofish_scenario_neuron import MirofishScenarioNeuron
from .cognitive.payoff_task_neuron import PayoffTaskNeuron
from .cognitive.source_integrity_neuron import SourceIntegrityNeuron
from .cognitive.title_risk_neuron import TitleRiskNeuron
from .config import (
    EVENT_LOG_PATH,
    STATUS_DIR,
)
from .event_store import event_counts, read_events
from .events import make_event
from .event_store import append_event
from .motor.amara_brain_sync import AmaraBrainSync
from .motor.openclaw_task_writer import OpenClawTaskWriter
from .motor.outreach_task_writer import OutreachTaskWriter
from .output.failed_neuron_writer import FailedNeuronWriter
from .output.money_brief_writer import MoneyBriefWriter
from .output.status_writer import StatusWriter
from .sensory.hermes_buyer_demand_agent import HermesBuyerDemandAgent
from .sensory.hermes_foreclosure_source_agent import HermesForeclosureSourceAgent
from .sensory.hermes_propstream_agent import HermesPropstreamAgent
from .sensory.hermes_quickcash_agent import HermesQuickCashAgent


def _safe_run(name: str, fn, failures: List[Dict]):
    """Run fn(), catch any exception, log to failures list. Returns result or error dict."""
    try:
        return fn()
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        failure = {
            "neuron": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "traceback": tb,
            "recommended_action": f"Investigate {name} error and re-run after fixing root cause",
        }
        failures.append(failure)
        # Also log to event store
        try:
            ev = make_event(
                event_type="NEURON_FAILED",
                source=name,
                payload={"neuron": name, "error": str(exc)},
                verification_status="SOURCE_NEEDED",
                status="FAILED",
                notes=str(exc),
            )
            append_event(ev)
        except Exception:
            pass
        return {"status": "FAILED", "error": str(exc), "neuron": name}


class NeuronRouter:
    """
    Orchestrates all AEGIS Neuron Network pipeline runs.
    Each method catches per-neuron exceptions and continues remaining neurons.
    """

    def run_houston_tax_sale(self) -> Dict:
        """Full Houston tax sale pipeline."""
        failures: List[Dict] = []
        results: Dict = {}
        files_created: List[str] = []
        run_timestamp = datetime.now(timezone.utc).isoformat()

        # 1. QuickCash bridge check
        quickcash_data = _safe_run(
            "HermesQuickCashAgent",
            HermesQuickCashAgent().run,
            failures,
        )
        results["HermesQuickCashAgent"] = quickcash_data
        strike_board_data = quickcash_data.get("strike_board", {}) if isinstance(quickcash_data, dict) else {}
        strike_board = strike_board_data.get("properties", []) if isinstance(strike_board_data, dict) else []

        # 2. Source integrity check
        integrity_result = _safe_run(
            "SourceIntegrityNeuron",
            lambda: SourceIntegrityNeuron().run({"strike_board": strike_board, "quickcash": quickcash_data}),
            failures,
        )
        results["SourceIntegrityNeuron"] = integrity_result

        # 3. Lead validation
        validated_board = _safe_run(
            "LeadValidationNeuron",
            lambda: LeadValidationNeuron().run(strike_board),
            failures,
        )
        results["LeadValidationNeuron"] = {"status": "COMPLETED", "count": len(validated_board) if isinstance(validated_board, list) else 0}
        if not isinstance(validated_board, list):
            validated_board = strike_board  # Fall back to unvalidated

        # 4. Deal classification
        classification_result = _safe_run(
            "DealClassificationNeuron",
            lambda: DealClassificationNeuron().run(validated_board),
            failures,
        )
        results["DealClassificationNeuron"] = classification_result
        classifications = {}
        if isinstance(classification_result, dict):
            classifications = classification_result.get("classifications", {})
            if classification_result.get("report_file"):
                files_created.append(classification_result["report_file"])

        # 5. Payoff tasks
        payoff_result = _safe_run(
            "PayoffTaskNeuron",
            lambda: PayoffTaskNeuron().run(validated_board),
            failures,
        )
        results["PayoffTaskNeuron"] = {"status": "COMPLETED", "task_count": payoff_result if isinstance(payoff_result, int) else 0}
        payoff_report = str(
            __import__("backend.aegis_neuron_network.config", fromlist=["REPORTS_DIR"]).REPORTS_DIR
            / "payoff_verification_needed.md"
        )
        files_created.append(payoff_report)

        # 6. Title risk
        title_result = _safe_run(
            "TitleRiskNeuron",
            lambda: TitleRiskNeuron().run(validated_board),
            failures,
        )
        results["TitleRiskNeuron"] = {"status": "COMPLETED", "task_count": title_result if isinstance(title_result, int) else 0}
        from .config import REPORTS_DIR
        files_created.append(str(REPORTS_DIR / "title_risk_checklist.md"))

        # 7. OpenClaw task writer
        openclaw_result = _safe_run(
            "OpenClawTaskWriter",
            lambda: OpenClawTaskWriter().run(validated_board),
            failures,
        )
        results["OpenClawTaskWriter"] = {"status": "COMPLETED", "task_file": openclaw_result}
        if isinstance(openclaw_result, str):
            files_created.append(openclaw_result)

        # 8. Outreach task writer
        outreach_result = _safe_run(
            "OutreachTaskWriter",
            lambda: OutreachTaskWriter().run(validated_board),
            failures,
        )
        results["OutreachTaskWriter"] = {"status": "COMPLETED", "file": outreach_result}
        if isinstance(outreach_result, str):
            files_created.append(outreach_result)

        # 9. Mirofish scenarios
        mirofish_result = _safe_run(
            "MirofishScenarioNeuron",
            lambda: MirofishScenarioNeuron().run(validated_board, classifications),
            failures,
        )
        results["MirofishScenarioNeuron"] = mirofish_result
        if isinstance(mirofish_result, dict) and mirofish_result.get("report_file"):
            files_created.append(mirofish_result["report_file"])

        # 10. AMARA Brain sync
        sync_result = _safe_run(
            "AmaraBrainSync",
            lambda: AmaraBrainSync().run(quickcash_data if isinstance(quickcash_data, dict) else {}),
            failures,
        )
        results["AmaraBrainSync"] = sync_result

        # 11. Money brief
        context = {
            "run_timestamp": run_timestamp,
            "files_created": files_created,
            "strike_board_count": len(validated_board),
            "failure_count": len(failures),
        }
        money_brief_path = _safe_run(
            "MoneyBriefWriter",
            lambda: MoneyBriefWriter().run(context),
            failures,
        )
        results["MoneyBriefWriter"] = {"status": "COMPLETED", "file": money_brief_path}
        if isinstance(money_brief_path, str):
            files_created.append(money_brief_path)

        # 12. Status writer
        results["files_created"] = files_created
        status_path = _safe_run(
            "StatusWriter",
            lambda: StatusWriter().run(results),
            failures,
        )
        results["StatusWriter"] = {"status": "COMPLETED", "file": status_path}
        if isinstance(status_path, str):
            files_created.append(status_path)

        # 13. Failed neuron writer
        failed_path = _safe_run(
            "FailedNeuronWriter",
            lambda: FailedNeuronWriter().run(failures),
            failures,
        )
        results["FailedNeuronWriter"] = {"status": "COMPLETED", "file": failed_path}
        if isinstance(failed_path, str):
            files_created.append(failed_path)

        results["run_timestamp"] = run_timestamp
        results["failures"] = failures
        results["files_created"] = files_created
        results["strike_board_count"] = len(validated_board)
        results["failure_count"] = len(failures)

        return results

    def run_buyer_demand(self) -> Dict:
        """Run buyer demand pipeline."""
        failures: List[Dict] = []
        results: Dict = {}

        buyer_result = _safe_run(
            "HermesBuyerDemandAgent",
            HermesBuyerDemandAgent().run,
            failures,
        )
        results["HermesBuyerDemandAgent"] = buyer_result

        buyer_data = buyer_result.get("buyer_data", {}) if isinstance(buyer_result, dict) else {}

        demand_result = _safe_run(
            "BuyerDemandNeuron",
            lambda: BuyerDemandNeuron().run(buyer_data),
            failures,
        )
        results["BuyerDemandNeuron"] = demand_result
        results["failures"] = failures

        return results

    def run_propstream_tasks(self) -> Dict:
        """Run PropStream session check and task creation."""
        failures: List[Dict] = []
        results: Dict = {}

        propstream_result = _safe_run(
            "HermesPropstreamAgent",
            HermesPropstreamAgent().run,
            failures,
        )
        results["HermesPropstreamAgent"] = propstream_result
        results["failures"] = failures

        return results

    def run_foreclosure_review(self) -> Dict:
        """Run foreclosure source review and parser task creation."""
        failures: List[Dict] = []
        results: Dict = {}

        foreclosure_result = _safe_run(
            "HermesForeclosureSourceAgent",
            HermesForeclosureSourceAgent().run,
            failures,
        )
        results["HermesForeclosureSourceAgent"] = foreclosure_result
        results["failures"] = failures

        return results

    def run_all(self) -> Dict:
        """Run all pipelines in sequence, collect all results."""
        all_results: Dict = {}

        houston_results = self.run_houston_tax_sale()
        all_results["houston_tax_sale"] = houston_results

        buyer_results = self.run_buyer_demand()
        all_results["buyer_demand"] = buyer_results

        propstream_results = self.run_propstream_tasks()
        all_results["propstream_tasks"] = propstream_results

        foreclosure_results = self.run_foreclosure_review()
        all_results["foreclosure_review"] = foreclosure_results

        # Aggregate counts
        all_failures = (
            houston_results.get("failures", [])
            + buyer_results.get("failures", [])
            + propstream_results.get("failures", [])
            + foreclosure_results.get("failures", [])
        )

        all_files = houston_results.get("files_created", [])

        counts = event_counts()

        all_results["summary"] = {
            "total_failures": len(all_failures),
            "total_files_created": len(all_files),
            "event_counts": counts,
            "strike_board_count": houston_results.get("strike_board_count", 0),
            "buyer_target_count": (
                buyer_results.get("HermesBuyerDemandAgent", {}).get("buyer_target_count", "QUICKCASH_NOT_AVAILABLE")
                if isinstance(buyer_results.get("HermesBuyerDemandAgent"), dict)
                else "QUICKCASH_NOT_AVAILABLE"
            ),
            "openclaw_task_file": houston_results.get("OpenClawTaskWriter", {}).get("task_file", "NOT_CREATED"),
            "money_brief_file": houston_results.get("MoneyBriefWriter", {}).get("file", "NOT_CREATED"),
            "status_file": houston_results.get("StatusWriter", {}).get("file", "NOT_CREATED"),
            "failed_neuron_file": houston_results.get("FailedNeuronWriter", {}).get("file", "NOT_CREATED"),
        }

        return all_results

    def get_status(self) -> Dict:
        """Read status file and event log, return status dict."""
        status_file = STATUS_DIR / "neuron_network_status.md"
        status_content = None
        if status_file.exists():
            try:
                status_content = status_file.read_text(encoding="utf-8")
            except Exception:
                pass

        counts = event_counts()
        recent_events = read_events(limit=20)

        return {
            "status_file": str(status_file),
            "status_file_exists": status_file.exists(),
            "status_content": status_content,
            "event_counts": counts,
            "recent_events": recent_events,
            "event_log": str(EVENT_LOG_PATH),
        }
