"""
AMARA OS — Approval Tracker

Tracks land deal approvals through the municipal/county entitlement pipeline.
Monitors stage progression, flags backlog, and predicts next steps.

Tracks:
- current_stage, department, last_activity_date
- revision_count, continuance_count, comment_rounds
- days_in_stage, expected_stage_duration
- backlog_score (0.0–1.0), backlog_flag
- likely_next_step

Integrates with entitlement_engine.py for per-deal entitlement tracking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from system.vault import write_vault_file, read_vault_file, list_vault, next_id
from system.entitlement_engine import EntitlementResult


# ─── Stage Definitions ────────────────────────────────────────────────────────

APPROVAL_STAGES = [
    "pre_app",
    "preliminary_plat",
    "final_plat",
    "permits",
    "utilities",
    "complete",
]

STAGE_LABELS = {
    "pre_app":          "Pre-Application",
    "preliminary_plat": "Preliminary Plat",
    "final_plat":       "Final Plat",
    "permits":          "Building Permits",
    "utilities":        "Utility Extensions",
    "complete":         "Complete",
}

# Expected duration for each stage (calendar days, typical)
EXPECTED_STAGE_DURATIONS = {
    "pre_app":          30,
    "preliminary_plat": 90,
    "final_plat":       60,
    "permits":          45,
    "utilities":        90,
    "complete":         0,
}

DEPARTMENTS = {
    "pre_app":          "Planning",
    "preliminary_plat": "Planning",
    "final_plat":       "Engineering",
    "permits":          "Building & Permits",
    "utilities":        "Public Works",
    "complete":         "N/A",
}


# ─── Approval Record ──────────────────────────────────────────────────────────

@dataclass
class ApprovalRecord:
    approval_id:        str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:6].upper()}")
    deal_id:            str = ""
    entitlement_id:     str = ""
    address:            str = ""
    zip_code:           str = ""
    county:             str = ""

    # Stage
    current_stage:      str = "pre_app"
    department:         str = "Planning"
    last_activity_date: date | None = None
    next_hearing_date:  date | None = None
    stage_entered_date: date | None = None

    # Revision tracking
    revision_count:     int = 0
    continuance_count:  int = 0
    comment_rounds:     int = 0

    # Computed
    days_in_stage:      int = 0      # updated on access
    expected_duration:  int = 0

    # Backlog
    backlog_score:      float = 0.0   # 0.0–1.0
    backlog_flag:       bool  = False
    likely_next_step:   str   = ""

    # Meta
    notes:              str   = ""
    last_contact:       str   = ""   # name/contact at department
    created_at:         str   = field(default_factory=lambda: date.today().isoformat())
    updated_at:         str   = field(default_factory=lambda: date.today().isoformat())

    def compute_days_in_stage(self, today: date | None = None) -> int:
        today = today or date.today()
        if self.stage_entered_date:
            return (today - self.stage_entered_date).days
        return 0

    def stage_label(self) -> str:
        return STAGE_LABELS.get(self.current_stage, self.current_stage)

    def progress_pct(self) -> float:
        """Percentage through the full approval pipeline."""
        try:
            idx = APPROVAL_STAGES.index(self.current_stage)
        except ValueError:
            return 0.0
        return round(idx / (len(APPROVAL_STAGES) - 1), 2)

    def summary(self) -> str:
        backlog = f" [BACKLOG {self.backlog_score:.2f}]" if self.backlog_flag else ""
        days    = self.compute_days_in_stage()
        return (
            f"[{self.approval_id}]{backlog} — {self.address}\n"
            f"  Stage: {self.stage_label()} | Dept: {self.department} | "
            f"Days in Stage: {days} / {self.expected_duration}\n"
            f"  Revisions: {self.revision_count} | Continuances: {self.continuance_count} | "
            f"Comment Rounds: {self.comment_rounds}\n"
            f"  Next Step: {self.likely_next_step or 'unknown'}"
        )


# ─── Stage History ────────────────────────────────────────────────────────────

@dataclass
class StageTransition:
    approval_id:  str
    from_stage:   str
    to_stage:     str
    transitioned_at: date
    notes:        str = ""


_stage_history: list[StageTransition] = []
_records: dict[str, ApprovalRecord]   = {}   # keyed by approval_id


# ─── Backlog Scoring ──────────────────────────────────────────────────────────

def _compute_backlog_score(record: ApprovalRecord, today: date | None = None) -> float:
    """
    Score 0.0–1.0 representing how stuck a deal is.
    1.0 = severely backlogged (multiple revisions, way over time).
    """
    today = today or date.today()
    score = 0.0

    days_in = record.compute_days_in_stage(today)
    expected = record.expected_duration or EXPECTED_STAGE_DURATIONS.get(record.current_stage, 60)

    # Time overrun (40% weight)
    if expected > 0:
        overrun_ratio = days_in / expected
        if overrun_ratio >= 3.0:
            score += 0.40
        elif overrun_ratio >= 2.0:
            score += 0.30
        elif overrun_ratio >= 1.5:
            score += 0.20
        elif overrun_ratio >= 1.0:
            score += 0.10

    # Revision count (30% weight)
    if record.revision_count >= 4:
        score += 0.30
    elif record.revision_count >= 2:
        score += 0.20
    elif record.revision_count >= 1:
        score += 0.10

    # Continuance count (20% weight)
    if record.continuance_count >= 3:
        score += 0.20
    elif record.continuance_count >= 2:
        score += 0.15
    elif record.continuance_count >= 1:
        score += 0.08

    # Comment rounds (10% weight)
    if record.comment_rounds >= 3:
        score += 0.10
    elif record.comment_rounds >= 2:
        score += 0.06

    return round(min(score, 1.0), 3)


def _likely_next_step(record: ApprovalRecord) -> str:
    """Predict the most likely next action based on current stage and state."""
    if record.backlog_flag:
        if record.revision_count > 0:
            return f"Respond to revision comments — resubmit to {record.department}"
        if record.continuance_count > 0:
            return f"Attend next hearing (continuance #{record.continuance_count + 1})"
        return f"Follow up with {record.department} — deal may be stalled"

    stage_nexts = {
        "pre_app":          "Submit preliminary plat application",
        "preliminary_plat": "Respond to staff comments; prepare for Planning Commission hearing",
        "final_plat":       "Submit final plat to Engineering; coordinate with surveyor",
        "permits":          "Pull building permits; verify fee schedule",
        "utilities":        "Execute utility extension agreements with Public Works",
        "complete":         "Coordinate with builder — site is shovel-ready",
    }
    return stage_nexts.get(record.current_stage, "Confirm next steps with department")


# ─── Create / Update Records ─────────────────────────────────────────────────

def create_approval_record(
    deal_id:        str,
    address:        str,
    zip_code:       str,
    county:         str = "",
    entitlement_id: str = "",
    initial_stage:  str = "pre_app",
) -> ApprovalRecord:
    """Create a new approval tracking record."""
    today = date.today()
    record = ApprovalRecord(
        deal_id            = deal_id,
        entitlement_id     = entitlement_id,
        address            = address,
        zip_code           = zip_code,
        county             = county,
        current_stage      = initial_stage,
        department         = DEPARTMENTS.get(initial_stage, "Planning"),
        stage_entered_date = today,
        expected_duration  = EXPECTED_STAGE_DURATIONS.get(initial_stage, 60),
    )
    record.likely_next_step = _likely_next_step(record)
    _records[record.approval_id] = record
    _write_approval_to_vault(record)
    return record


def advance_stage(
    approval_id: str,
    notes:       str = "",
    today:       date | None = None,
) -> ApprovalRecord:
    """
    Advance an approval record to the next pipeline stage.
    Logs the transition and updates vault.
    """
    today   = today or date.today()
    record  = _records.get(approval_id)
    if not record:
        raise ValueError(f"Approval record {approval_id} not found")

    current_idx = APPROVAL_STAGES.index(record.current_stage) if record.current_stage in APPROVAL_STAGES else -1
    if current_idx < 0 or current_idx >= len(APPROVAL_STAGES) - 1:
        return record   # already at complete

    next_stage = APPROVAL_STAGES[current_idx + 1]

    # Log transition
    _stage_history.append(StageTransition(
        approval_id     = approval_id,
        from_stage      = record.current_stage,
        to_stage        = next_stage,
        transitioned_at = today,
        notes           = notes,
    ))

    record.current_stage      = next_stage
    record.department         = DEPARTMENTS.get(next_stage, "Planning")
    record.stage_entered_date = today
    record.expected_duration  = EXPECTED_STAGE_DURATIONS.get(next_stage, 60)
    record.updated_at         = today.isoformat()
    record.days_in_stage      = 0
    record.backlog_score      = 0.0
    record.backlog_flag       = False
    record.likely_next_step   = _likely_next_step(record)

    _write_approval_to_vault(record)
    return record


def record_revision(approval_id: str, notes: str = "") -> ApprovalRecord:
    """Log a revision request from the reviewing department."""
    record = _records.get(approval_id)
    if not record:
        raise ValueError(f"Approval record {approval_id} not found")

    record.revision_count += 1
    record.updated_at = date.today().isoformat()
    _refresh_backlog(record)
    _write_approval_to_vault(record)
    return record


def record_continuance(approval_id: str, next_hearing: date | None = None, notes: str = "") -> ApprovalRecord:
    """Log a hearing continuance."""
    record = _records.get(approval_id)
    if not record:
        raise ValueError(f"Approval record {approval_id} not found")

    record.continuance_count += 1
    if next_hearing:
        record.next_hearing_date = next_hearing
    record.updated_at = date.today().isoformat()
    _refresh_backlog(record)
    _write_approval_to_vault(record)
    return record


def record_comment_round(approval_id: str, notes: str = "") -> ApprovalRecord:
    """Log a staff comment round (returned comments on submitted application)."""
    record = _records.get(approval_id)
    if not record:
        raise ValueError(f"Approval record {approval_id} not found")

    record.comment_rounds += 1
    record.updated_at = date.today().isoformat()
    _refresh_backlog(record)
    _write_approval_to_vault(record)
    return record


def _refresh_backlog(record: ApprovalRecord) -> None:
    """Recompute and update backlog score and flag."""
    score = _compute_backlog_score(record)
    record.backlog_score     = score
    record.backlog_flag      = score >= 0.40
    record.days_in_stage     = record.compute_days_in_stage()
    record.likely_next_step  = _likely_next_step(record)


# ─── Refresh All Records ──────────────────────────────────────────────────────

def refresh_all_records(today: date | None = None) -> list[ApprovalRecord]:
    """
    Recompute backlog scores for all active records.
    Returns records with backlog_flag=True sorted by backlog_score desc.
    """
    today = today or date.today()
    for record in _records.values():
        if record.current_stage != "complete":
            _refresh_backlog(record)
    flagged = [r for r in _records.values() if r.backlog_flag]
    flagged.sort(key=lambda r: -r.backlog_score)
    return flagged


def get_all_records() -> list[ApprovalRecord]:
    return list(_records.values())


def get_backlogged_deals() -> list[ApprovalRecord]:
    return [r for r in _records.values() if r.backlog_flag]


def get_record(approval_id: str) -> ApprovalRecord | None:
    return _records.get(approval_id)


# ─── Vault Integration ────────────────────────────────────────────────────────

def _write_approval_to_vault(record: ApprovalRecord) -> None:
    """Write/update approval record in vault."""
    today    = date.today().isoformat()
    slug     = "".join(c if c.isalnum() else "_" for c in record.address)[:30]
    filename = f"{record.approval_id}_{slug}.md"

    history = [t for t in _stage_history if t.approval_id == record.approval_id]
    history_text = "\n".join(
        f"- {t.transitioned_at} · {t.from_stage} → {t.to_stage}{(' — ' + t.notes) if t.notes else ''}"
        for t in history
    ) or "No stage transitions yet"

    backlog_flag = "**YES — REVIEW REQUIRED**" if record.backlog_flag else "No"
    content = f"""# Approval Tracker — {record.address}

## Current Status
- **Stage:** {record.stage_label()}
- **Department:** {record.department}
- **Progress:** {int(record.progress_pct() * 100)}%
- **Days in Stage:** {record.compute_days_in_stage()} / {record.expected_duration} expected

## Revision Activity
- **Revisions:** {record.revision_count}
- **Continuances:** {record.continuance_count}
- **Comment Rounds:** {record.comment_rounds}

## Backlog
- **Backlog Score:** {record.backlog_score:.2f}
- **Backlog Flag:** {backlog_flag}

## Next Step
{record.likely_next_step}

## Stage History
{history_text}

## Notes
{record.notes or 'None'}

## Last Contact
{record.last_contact or 'None'}

---

- **Approval ID:** {record.approval_id}
- **Deal ID:** {record.deal_id}
- **Entitlement:** {record.entitlement_id or 'None'}
- **County:** {record.county or 'Unknown'}
- **Created:** {record.created_at}
- **Updated:** {today}
"""
    write_vault_file("land", filename, content)


# ─── Report ───────────────────────────────────────────────────────────────────

def print_approval_report(records: list[ApprovalRecord] | None = None) -> None:
    records = records or get_all_records()
    active  = [r for r in records if r.current_stage != "complete"]
    done    = [r for r in records if r.current_stage == "complete"]
    flagged = [r for r in active if r.backlog_flag]

    print(f"\n{'═' * 60}")
    print(f"APPROVAL TRACKER — {len(records)} total | {len(active)} active | {len(flagged)} backlogged")
    print(f"{'─' * 60}")

    if flagged:
        print(f"\n⚠  BACKLOGGED ({len(flagged)}):")
        for r in sorted(flagged, key=lambda x: -x.backlog_score):
            print(f"  {r.summary()}")

    if active:
        print(f"\nACTIVE ({len(active)}):")
        for r in sorted(active, key=lambda x: -x.progress_pct()):
            if not r.backlog_flag:
                print(f"  {r.summary()}")

    if done:
        print(f"\nCOMPLETED ({len(done)}):")
        for r in done:
            print(f"  [{r.approval_id}] {r.address} — COMPLETE")

    print(f"{'═' * 60}\n")
