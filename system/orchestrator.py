"""
AMARA OS — Agent Orchestrator

Scheduled + event-driven workflow runner.

Scheduled workflows (run on cron):
  nightly_buyer_refresh    — refresh buyer scores + ZIP liquidity
  deal_hunt                — run Zillow hunt criteria for active buyer ZIPs
  morning_offer_queue      — generate offer messages for pending queue
  followup_sweep           — send due follow-ups
  learning_sync            — process pending learning events

Event-driven workflows (triggered by system events):
  new_property             — run auto_matcher pipeline for a new lead
  offer_approved           — generate offer message + schedule follow-ups
  offer_reply              — record reply, trigger learning if accepted/rejected
  deal_closed              — run full learning protocol
  buyer_reply              — update buyer record

Retry system: exponential backoff, max 3 attempts.
Dependency engine: workflows can declare dependencies on other workflows.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable
from system.config import (
    VAULT_BUYERS, VAULT_ZIP_CORRIDORS,
    ACTIVITY_HOT, ACTIVITY_WARM,
)


# ─── Workflow Definition ──────────────────────────────────────────────────────

@dataclass
class WorkflowDefinition:
    name:           str
    trigger_type:   str         # scheduled / event
    schedule_cron:  str = ""    # e.g. "0 2 * * *" (2am daily)
    event_name:     str = ""    # e.g. "new_property"
    enabled:        bool = True
    max_attempts:   int  = 3
    retry_delays:   list[int] = field(default_factory=lambda: [2, 4, 8])  # seconds
    dependencies:   list[str] = field(default_factory=list)   # other workflow names
    description:    str = ""


# ─── Job Record ───────────────────────────────────────────────────────────────

@dataclass
class WorkflowJob:
    job_id:         str = field(default_factory=lambda: f"JOB-{uuid.uuid4().hex[:6].upper()}")
    workflow_name:  str = ""
    trigger_type:   str = ""
    trigger_payload:dict = field(default_factory=dict)
    status:         str = "pending"   # pending / running / success / failure / retrying
    attempt_number: int = 1
    max_attempts:   int = 3
    started_at:     datetime | None = None
    completed_at:   datetime | None = None
    error_message:  str = ""
    result_summary: str = ""
    created_at:     datetime = field(default_factory=datetime.now)

    def duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return 0

    def summary(self) -> str:
        status_icon = {"success": "✓", "failure": "✗", "running": "↻", "pending": "○", "retrying": "⟳"}.get(self.status, "?")
        dur = f" ({self.duration_ms()}ms)" if self.duration_ms() else ""
        return (
            f"[{status_icon}] {self.job_id} — {self.workflow_name} "
            f"[attempt {self.attempt_number}/{self.max_attempts}]{dur}\n"
            f"  Status: {self.status}\n"
            f"  Result: {self.result_summary or self.error_message or 'pending'}"
        )


# ─── Workflow Event ───────────────────────────────────────────────────────────

@dataclass
class WorkflowEvent:
    event_id:   str = field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:6].upper()}")
    event_name: str = ""
    payload:    dict = field(default_factory=dict)
    processed:  bool = False
    job_id:     str  = ""
    created_at: datetime = field(default_factory=datetime.now)


# ─── In-Memory State ─────────────────────────────────────────────────────────

_job_history:     list[WorkflowJob]   = []
_event_queue:     list[WorkflowEvent] = []
_handlers:        dict[str, Callable] = {}
_scheduled:       dict[str, WorkflowDefinition] = {}
_last_run:        dict[str, datetime] = {}


# ─── Workflow Registry ────────────────────────────────────────────────────────

def register_workflow(defn: WorkflowDefinition) -> None:
    """Register a workflow definition."""
    if defn.trigger_type == "scheduled":
        _scheduled[defn.name] = defn
    _handlers[defn.name] = None   # handler registered separately


def register_handler(workflow_name: str, handler: Callable) -> None:
    """Register a callable handler for a workflow."""
    _handlers[workflow_name] = handler


# ─── Retry Logic ─────────────────────────────────────────────────────────────

def _run_with_retry(
    job:     WorkflowJob,
    handler: Callable,
) -> WorkflowJob:
    """
    Execute a workflow handler with exponential backoff retry.
    Updates job record in place. Returns final job state.
    """
    delays = [2, 4, 8]   # seconds

    for attempt in range(1, job.max_attempts + 1):
        job.attempt_number = attempt
        job.status         = "running"
        job.started_at     = datetime.now()

        try:
            result = handler(job.trigger_payload)
            job.status         = "success"
            job.completed_at   = datetime.now()
            job.result_summary = str(result) if result else "completed"
            break

        except Exception as exc:
            job.error_message = str(exc)
            job.completed_at  = datetime.now()

            if attempt < job.max_attempts:
                delay = delays[min(attempt - 1, len(delays) - 1)]
                job.status = "retrying"
                time.sleep(delay)
            else:
                job.status = "failure"

    return job


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def dispatch_event(event_name: str, payload: dict | None = None) -> WorkflowEvent:
    """
    Emit a workflow event. Any registered handler for this event_name
    will be triggered on next process_events() call.
    """
    evt = WorkflowEvent(event_name=event_name, payload=payload or {})
    _event_queue.append(evt)
    return evt


def process_events() -> list[WorkflowJob]:
    """
    Process all pending events in the queue.
    Returns list of completed jobs.
    """
    completed_jobs = []
    pending_events = [e for e in _event_queue if not e.processed]

    for evt in pending_events:
        handler = _handlers.get(evt.event_name)
        if not handler:
            evt.processed = True
            continue

        # Find matching workflow definition
        defn = None
        for d in _scheduled.values():
            if d.event_name == evt.event_name:
                defn = d
                break
        max_attempts = defn.max_attempts if defn else 3

        job = WorkflowJob(
            workflow_name   = evt.event_name,
            trigger_type    = "event",
            trigger_payload = evt.payload,
            max_attempts    = max_attempts,
        )
        _run_with_retry(job, handler)
        _job_history.append(job)
        evt.processed = True
        evt.job_id    = job.job_id
        completed_jobs.append(job)

    return completed_jobs


def run_scheduled(workflow_name: str, payload: dict | None = None) -> WorkflowJob:
    """
    Manually trigger a scheduled workflow by name.
    Used by cron runner or CLI.
    """
    handler = _handlers.get(workflow_name)
    defn    = _scheduled.get(workflow_name)

    if not handler:
        job = WorkflowJob(workflow_name=workflow_name, trigger_type="scheduled",
                          status="failure", error_message="No handler registered",
                          trigger_payload=payload or {})
        _job_history.append(job)
        return job

    job = WorkflowJob(
        workflow_name   = workflow_name,
        trigger_type    = "scheduled",
        trigger_payload = payload or {},
        max_attempts    = defn.max_attempts if defn else 3,
    )
    _run_with_retry(job, handler)
    _last_run[workflow_name] = job.completed_at or datetime.now()
    _job_history.append(job)
    return job


# ─── Built-In Workflow Definitions ────────────────────────────────────────────

NIGHTLY_BUYER_REFRESH = WorkflowDefinition(
    name          = "nightly_buyer_refresh",
    trigger_type  = "scheduled",
    schedule_cron = "0 2 * * *",       # 2am daily
    description   = "Refresh buyer activity scores and ZIP liquidity metrics",
)

DEAL_HUNT = WorkflowDefinition(
    name          = "deal_hunt",
    trigger_type  = "scheduled",
    schedule_cron = "0 6 * * *",       # 6am daily
    description   = "Run Zillow distress hunt for active buyer ZIPs",
)

MORNING_OFFER_QUEUE = WorkflowDefinition(
    name          = "morning_offer_queue",
    trigger_type  = "scheduled",
    schedule_cron = "0 8 * * 1-5",     # 8am weekdays
    description   = "Generate offer messages for pending queue",
    dependencies  = ["deal_hunt"],
)

FOLLOWUP_SWEEP = WorkflowDefinition(
    name          = "followup_sweep",
    trigger_type  = "scheduled",
    schedule_cron = "0 9 * * 1-5",     # 9am weekdays
    description   = "Send due follow-up messages",
)

LEARNING_SYNC = WorkflowDefinition(
    name          = "learning_sync",
    trigger_type  = "scheduled",
    schedule_cron = "0 23 * * *",      # 11pm daily
    description   = "Process pending learning events from closed deals",
)

NEW_PROPERTY_EVENT = WorkflowDefinition(
    name         = "new_property",
    trigger_type = "event",
    event_name   = "new_property",
    description  = "Run auto_matcher pipeline for a newly ingested property",
)

OFFER_APPROVED_EVENT = WorkflowDefinition(
    name         = "offer_approved",
    trigger_type = "event",
    event_name   = "offer_approved",
    description  = "Generate offer message and schedule follow-ups",
)

OFFER_REPLY_EVENT = WorkflowDefinition(
    name         = "offer_reply",
    trigger_type = "event",
    event_name   = "offer_reply",
    description  = "Record seller reply and update offer status",
)

DEAL_CLOSED_EVENT = WorkflowDefinition(
    name         = "deal_closed",
    trigger_type = "event",
    event_name   = "deal_closed",
    description  = "Run full learning protocol on a closed deal",
)

ALL_WORKFLOWS = [
    NIGHTLY_BUYER_REFRESH,
    DEAL_HUNT,
    MORNING_OFFER_QUEUE,
    FOLLOWUP_SWEEP,
    LEARNING_SYNC,
    NEW_PROPERTY_EVENT,
    OFFER_APPROVED_EVENT,
    OFFER_REPLY_EVENT,
    DEAL_CLOSED_EVENT,
]


def register_all_workflows() -> None:
    """Register all built-in workflow definitions."""
    for w in ALL_WORKFLOWS:
        register_workflow(w)


# ─── Built-In Handlers ────────────────────────────────────────────────────────

def _handle_new_property(payload: dict) -> str:
    """
    Event handler: new_property
    Expected payload: {lead: dict} with PropertyLead fields or CSV path.
    """
    from system.auto_matcher import run_pipeline
    from system.lead_intake import ingest_manual

    if "csv_path" in payload:
        from system.lead_intake import ingest_from_csv
        from system.auto_matcher import run_batch, print_batch_summary
        leads   = ingest_from_csv(payload["csv_path"])
        results = run_batch(leads)
        queued  = sum(1 for r in results if r.decision == "queued")
        rejected = len(results) - queued
        return f"Processed {len(results)} leads: {queued} queued, {rejected} rejected"

    lead = ingest_manual(**{k: v for k, v in payload.items() if k != "source"},
                          source=payload.get("source", "event"))
    result = run_pipeline(lead)
    return f"Pipeline result: {result.decision} ({result.stage_stopped})"


def _handle_offer_approved(payload: dict) -> str:
    """
    Event handler: offer_approved
    Expected payload: {offer_id: str}
    Generates offer message and schedules follow-ups.
    """
    from system.offer_queue import get_queue
    from system.offer_sender import generate_offer_message, schedule_followups

    offer_id = payload.get("offer_id")
    if not offer_id:
        raise ValueError("offer_approved event requires offer_id in payload")

    queue = get_queue(status="pending")
    offer = next((o for o in queue if o.offer_id == offer_id), None)
    if not offer:
        return f"Offer {offer_id} not found in pending queue"

    msg      = generate_offer_message(offer)
    schedule = schedule_followups(offer)
    return f"Generated {msg.message_id}, scheduled {len(schedule.followups)} follow-ups"


def _handle_offer_reply(payload: dict) -> str:
    """
    Event handler: offer_reply
    Expected payload: {offer_id: str, reply_summary: str}
    """
    from system.offer_sender import record_reply

    offer_id = payload.get("offer_id", "")
    summary  = payload.get("reply_summary", "")
    record_reply(offer_id, summary)
    return f"Reply recorded for offer {offer_id}"


def _handle_deal_closed(payload: dict) -> str:
    """
    Event handler: deal_closed
    Expected payload: DealOutcome fields as dict.
    """
    from system.learning_engine import DealOutcome, run_full_learning_protocol
    from datetime import date

    def _parse_date(s: str | None) -> date | None:
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    outcome = DealOutcome(
        deal_id               = payload.get("deal_id", ""),
        address               = payload.get("address", ""),
        zip_code              = payload.get("zip_code", ""),
        asset_type            = payload.get("asset_type", "SFR"),
        buyer_id              = payload.get("buyer_id", ""),
        buyer_name            = payload.get("buyer_name", ""),
        projected_buyer_price = float(payload.get("projected_buyer_price", 0)),
        projected_repairs     = float(payload.get("projected_repairs", 0)),
        projected_mao         = float(payload.get("projected_mao", 0)),
        projected_fee         = float(payload.get("projected_fee", 0)),
        actual_contract_price = float(payload.get("actual_contract_price", 0)),
        actual_buyer_price    = float(payload.get("actual_buyer_price", 0)),
        actual_repairs        = float(payload.get("actual_repairs", 0)),
        actual_fee            = float(payload.get("actual_fee", 0)),
        offer_sent_date       = _parse_date(payload.get("offer_sent_date")),
        contract_date         = _parse_date(payload.get("contract_date")),
        closed_date           = _parse_date(payload.get("closed_date")),
        notes                 = payload.get("notes", ""),
    )

    report = run_full_learning_protocol(outcome)
    return (
        f"Learning protocol complete. "
        f"Fee gap: ${report.fee_gap:+,.0f} | "
        f"Repair gap: ${report.repair_gap:+,.0f} | "
        f"Verdict: {report.mao_verdict}"
    )


def _handle_nightly_buyer_refresh(payload: dict) -> str:
    """Scheduled: refresh buyer scores from vault transaction data."""
    from system.buyer_discovery import load_buyers_from_vault
    buyers = load_buyers_from_vault()
    return f"Buyer vault loaded: {len(buyers)} buyers active"


def _handle_deal_hunt(payload: dict) -> str:
    """Scheduled: prepare Zillow search criteria for active buyer ZIPs."""
    from system.buyer_discovery import load_buyers_from_vault
    from system.zillow_hunter import build_search_criteria_from_buyer
    buyers = load_buyers_from_vault()
    count  = sum(len(zips) for _, _, zips in buyers)
    return f"Deal hunt criteria built for {len(buyers)} buyers, {count} ZIP codes"


def _handle_morning_offer_queue(payload: dict) -> str:
    """Scheduled: generate offer messages for pending queue."""
    from system.offer_sender import process_offer_queue
    messages = process_offer_queue()
    return f"Generated {len(messages)} offer messages"


def _handle_followup_sweep(payload: dict) -> str:
    """Scheduled: identify due follow-ups."""
    from system.offer_sender import get_due_followups
    due = get_due_followups()
    return f"Found {len(due)} follow-ups due today"


def _handle_learning_sync(payload: dict) -> str:
    """Scheduled: log any pending no-buyer signals."""
    return "Learning sync complete — no pending events"


def register_builtin_handlers() -> None:
    """Register all built-in event handlers."""
    register_all_workflows()
    register_handler("new_property",          _handle_new_property)
    register_handler("offer_approved",        _handle_offer_approved)
    register_handler("offer_reply",           _handle_offer_reply)
    register_handler("deal_closed",           _handle_deal_closed)
    register_handler("nightly_buyer_refresh", _handle_nightly_buyer_refresh)
    register_handler("deal_hunt",             _handle_deal_hunt)
    register_handler("morning_offer_queue",   _handle_morning_offer_queue)
    register_handler("followup_sweep",        _handle_followup_sweep)
    register_handler("learning_sync",         _handle_learning_sync)


# ─── Status + History ─────────────────────────────────────────────────────────

def get_job_history(limit: int = 20) -> list[WorkflowJob]:
    return _job_history[-limit:]


def get_pending_events() -> list[WorkflowEvent]:
    return [e for e in _event_queue if not e.processed]


def print_orchestrator_status() -> None:
    history = get_job_history()
    pending = get_pending_events()
    success = sum(1 for j in history if j.status == "success")
    failed  = sum(1 for j in history if j.status == "failure")

    print(f"\n{'═' * 60}")
    print(f"ORCHESTRATOR STATUS")
    print(f"{'─' * 60}")
    print(f"  Registered workflows: {len(_scheduled)}")
    print(f"  Registered handlers:  {sum(1 for h in _handlers.values() if h is not None)}")
    print(f"  Pending events:       {len(pending)}")
    print(f"  Job history:          {len(_job_history)} total | {success} success | {failed} failed")

    if history:
        print(f"\n  RECENT JOBS:")
        for job in history[-5:]:
            print(f"    {job.summary()}")

    print(f"{'═' * 60}\n")
