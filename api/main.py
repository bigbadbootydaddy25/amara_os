"""
AMARA OS — FastAPI REST API

REST interface for all AMARA pipeline operations.

Endpoints:
  POST /leads/manual        — run pipeline on a single manual lead
  POST /leads/csv           — run pipeline on a CSV upload
  GET  /queue               — view pending offer queue
  GET  /queue/{offer_id}    — get a specific offer record
  GET  /rejections          — view recent rejections
  POST /deals/close         — record a closed deal (triggers learning)
  POST /events              — emit a workflow event
  GET  /workflows           — list registered workflows
  POST /workflows/run       — manually trigger a scheduled workflow
  GET  /workflows/history   — recent job history
  GET  /buyers              — list vault buyers
  POST /entitlement         — run entitlement analysis
  POST /approval            — create approval tracking record
  GET  /approval/{id}       — get approval status
  PATCH /approval/{id}/advance — advance to next stage
  PATCH /approval/{id}/revision — record a revision
  GET  /health              — system health check

Environment variables:
  AMARA_VAULT_ROOT   — absolute path to vault root (default: ./)
  AMARA_DEBUG        — enable debug mode (default: false)
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "AMARA OS",
    description = "Buyer-first real estate acquisition intelligence system",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# Register orchestrator handlers on startup
from system.orchestrator import register_builtin_handlers
register_builtin_handlers()


# ─── Request / Response Models ────────────────────────────────────────────────

class ManualLeadRequest(BaseModel):
    address:    str
    zip_code:   str
    price:      float
    sqft:       int     = 0
    beds:       float   = 0
    baths:      float   = 0
    dom:        int     = 0
    year_built: int     = 0
    lot_size:   float   = 0
    source:     str     = "manual"
    description:str     = ""

class PipelineResultResponse(BaseModel):
    property_id:    str
    address:        str
    zip_code:       str
    classification: str
    decision:       str
    stage_stopped:  str
    final_score:    float
    notes:          list[str]
    offer:          dict | None = None
    rejection:      dict | None = None

class OfferRecordResponse(BaseModel):
    offer_id:           str
    address:            str
    zip_code:           str
    asset_type:         str
    status:             str
    primary_buyer_id:   str
    primary_buyer_name: str
    max_offer:          float
    target_fee:         float
    spread:             float
    final_score:        float
    notes:              str
    vault_deal_id:      str
    queued_at:          str

class CloseDealRequest(BaseModel):
    deal_id:               str
    address:               str
    zip_code:              str
    asset_type:            str = "SFR"
    buyer_id:              str
    buyer_name:            str
    projected_buyer_price: float
    projected_repairs:     float
    projected_mao:         float
    projected_fee:         float
    actual_contract_price: float
    actual_buyer_price:    float
    actual_repairs:        float
    actual_fee:            float
    offer_sent_date:       str | None = None
    contract_date:         str | None = None
    closed_date:           str | None = None
    notes:                 str = ""

class WorkflowEventRequest(BaseModel):
    event_name: str
    payload:    dict = Field(default_factory=dict)

class WorkflowRunRequest(BaseModel):
    workflow_name: str
    payload:       dict = Field(default_factory=dict)

class EntitlementRequest(BaseModel):
    deal_id:             str
    address:             str
    zip_code:            str
    county:              str = ""
    zoning:              str = ""
    has_water:           bool = False
    has_sewer:           bool = False
    has_road:            bool = False
    plat_phase:          str = "raw"
    dead_paper:          bool = False
    permits_stage:       str = "not_started"
    utilities_distance_ft: int = 0

class CreateApprovalRequest(BaseModel):
    deal_id:        str
    address:        str
    zip_code:       str
    county:         str = ""
    entitlement_id: str = ""
    initial_stage:  str = "pre_app"

class AdvanceStageRequest(BaseModel):
    notes: str = ""

class RevisionRequest(BaseModel):
    notes: str = ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pipeline_result_to_dict(result) -> dict:
    d = {
        "property_id":    result.property_id,
        "address":        result.address,
        "zip_code":       result.zip_code,
        "classification": result.classification,
        "decision":       result.decision,
        "stage_stopped":  result.stage_stopped,
        "final_score":    result.final_score,
        "notes":          result.notes,
        "offer":          None,
        "rejection":      None,
    }
    if result.offer:
        o = result.offer
        d["offer"] = {
            "offer_id":           o.offer_id,
            "address":            o.address,
            "zip_code":           o.zip_code,
            "asset_type":         o.asset_type,
            "status":             o.status,
            "primary_buyer_id":   o.primary_buyer_id,
            "primary_buyer_name": o.primary_buyer_name,
            "max_offer":          o.max_offer,
            "target_fee":         o.target_fee,
            "spread":             o.spread,
            "final_score":        o.final_score,
            "notes":              o.notes,
            "vault_deal_id":      o.vault_deal_id,
            "queued_at":          o.queued_at,
        }
    if result.rejection:
        r = result.rejection
        d["rejection"] = {
            "rejection_id": r.rejection_id,
            "stage":        r.stage,
            "reason":       r.reason,
            "logged_at":    r.logged_at,
        }
    return d


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check() -> dict:
    from system.vault import list_vault
    buyer_count = len([f for f in list_vault("buyers") if f.name != "TEMPLATE.md"])
    deal_count  = len([f for f in list_vault("deals")  if f.name != "TEMPLATE.md"])
    return {
        "status":       "ok",
        "version":      "1.0.0",
        "vault": {
            "buyers": buyer_count,
            "deals":  deal_count,
        },
        "date": date.today().isoformat(),
    }


# ─── Leads / Pipeline ─────────────────────────────────────────────────────────

@app.post("/leads/manual", tags=["Pipeline"], response_model=PipelineResultResponse)
def run_manual_lead(req: ManualLeadRequest) -> dict:
    """Run the auto-matcher pipeline on a single manually-entered lead."""
    from system.lead_intake import ingest_manual
    from system.auto_matcher import run_pipeline

    lead = ingest_manual(
        address    = req.address,
        zip_code   = req.zip_code,
        price      = req.price,
        sqft       = req.sqft,
        beds       = req.beds,
        baths      = req.baths,
        dom        = req.dom,
        year_built = req.year_built,
        lot_size   = req.lot_size,
        source     = req.source,
        description= req.description,
    )
    result = run_pipeline(lead)
    return _pipeline_result_to_dict(result)


@app.post("/leads/csv", tags=["Pipeline"])
async def run_csv_leads(file: UploadFile = File(...)) -> dict:
    """Run the auto-matcher pipeline on an uploaded CSV of leads."""
    import tempfile, os
    from system.lead_intake import ingest_from_csv
    from system.auto_matcher import run_batch

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        leads   = ingest_from_csv(tmp_path, source="csv_upload")
        results = run_batch(leads)
    finally:
        os.unlink(tmp_path)

    queued   = [r for r in results if r.decision == "queued"]
    rejected = [r for r in results if r.decision == "rejected"]

    return {
        "total":    len(results),
        "queued":   len(queued),
        "rejected": len(rejected),
        "results":  [_pipeline_result_to_dict(r) for r in results],
    }


# ─── Offer Queue ──────────────────────────────────────────────────────────────

@app.get("/queue", tags=["Offers"])
def get_offer_queue(status: str | None = Query(None)) -> dict:
    """View the pending offer queue. Filter by status (pending/sent/accepted/rejected)."""
    from system.offer_queue import get_queue
    records = get_queue(status=status)
    return {
        "count":  len(records),
        "offers": [
            {
                "offer_id":           r.offer_id,
                "address":            r.address,
                "zip_code":           r.zip_code,
                "asset_type":         r.asset_type,
                "status":             r.status,
                "primary_buyer_id":   r.primary_buyer_id,
                "primary_buyer_name": r.primary_buyer_name,
                "max_offer":          r.max_offer,
                "target_fee":         r.target_fee,
                "spread":             r.spread,
                "final_score":        r.final_score,
                "vault_deal_id":      r.vault_deal_id,
                "queued_at":          r.queued_at,
            }
            for r in records
        ],
    }


@app.get("/queue/{offer_id}", tags=["Offers"])
def get_offer(offer_id: str) -> dict:
    """Get a specific offer record by ID."""
    from system.offer_queue import get_queue
    records = get_queue()
    record  = next((r for r in records if r.offer_id == offer_id), None)
    if not record:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return {
        "offer_id":           record.offer_id,
        "address":            record.address,
        "zip_code":           record.zip_code,
        "asset_type":         record.asset_type,
        "status":             record.status,
        "primary_buyer_id":   record.primary_buyer_id,
        "primary_buyer_name": record.primary_buyer_name,
        "secondary_buyer_ids":record.secondary_buyer_ids,
        "max_offer":          record.max_offer,
        "target_fee":         record.target_fee,
        "spread":             record.spread,
        "final_score":        record.final_score,
        "notes":              record.notes,
        "vault_deal_id":      record.vault_deal_id,
        "queued_at":          record.queued_at,
        "sent_at":            record.sent_at,
    }


@app.get("/rejections", tags=["Offers"])
def get_rejections() -> dict:
    """View recent rejection log."""
    from system.offer_queue import get_rejections
    records = get_rejections()
    return {
        "count":      len(records),
        "rejections": [
            {
                "rejection_id": r.rejection_id,
                "address":      r.address,
                "zip_code":     r.zip_code,
                "stage":        r.stage,
                "reason":       r.reason,
                "logged_at":    r.logged_at,
            }
            for r in records
        ],
    }


# ─── Deals ────────────────────────────────────────────────────────────────────

@app.post("/deals/close", tags=["Deals"])
def close_deal(req: CloseDealRequest) -> dict:
    """
    Record a closed deal and run the full learning protocol.
    Triggers: deal result record, buyer update, market observation, corridor update.
    """
    from system.learning_engine import DealOutcome, run_full_learning_protocol

    def _parse_date(s: str | None):
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    outcome = DealOutcome(
        deal_id               = req.deal_id,
        address               = req.address,
        zip_code              = req.zip_code,
        asset_type            = req.asset_type,
        buyer_id              = req.buyer_id,
        buyer_name            = req.buyer_name,
        projected_buyer_price = req.projected_buyer_price,
        projected_repairs     = req.projected_repairs,
        projected_mao         = req.projected_mao,
        projected_fee         = req.projected_fee,
        actual_contract_price = req.actual_contract_price,
        actual_buyer_price    = req.actual_buyer_price,
        actual_repairs        = req.actual_repairs,
        actual_fee            = req.actual_fee,
        offer_sent_date       = _parse_date(req.offer_sent_date),
        contract_date         = _parse_date(req.contract_date),
        closed_date           = _parse_date(req.closed_date),
        notes                 = req.notes,
    )

    report = run_full_learning_protocol(outcome)

    return {
        "deal_id":         report.deal_id,
        "address":         report.address,
        "fee_gap":         report.fee_gap,
        "repair_gap":      report.repair_gap,
        "buyer_price_gap": report.buyer_price_gap,
        "mao_verdict":     report.mao_verdict,
        "repair_verdict":  report.repair_verdict,
        "buyer_verdict":   report.buyer_verdict,
        "observation_id":  report.observation_id,
        "vault_updates":   report.vault_updates,
        "recommendations": {
            "mao":    report.mao_adjustment,
            "repair": report.repair_adjustment,
            "buyer":  report.buyer_adjustment,
        },
    }


# ─── Workflows / Events ───────────────────────────────────────────────────────

@app.post("/events", tags=["Orchestration"])
def emit_event(req: WorkflowEventRequest) -> dict:
    """Emit a workflow event to be processed by registered handlers."""
    from system.orchestrator import dispatch_event, process_events
    evt  = dispatch_event(req.event_name, req.payload)
    jobs = process_events()
    completed = next((j for j in jobs if j.workflow_name == req.event_name), None)
    return {
        "event_id":   evt.event_id,
        "event_name": evt.event_name,
        "processed":  evt.processed,
        "job": {
            "job_id":         completed.job_id     if completed else None,
            "status":         completed.status     if completed else "no_handler",
            "result_summary": completed.result_summary if completed else None,
            "error":          completed.error_message if completed else None,
        } if completed else None,
    }


@app.get("/workflows", tags=["Orchestration"])
def list_workflows() -> dict:
    """List all registered workflow definitions."""
    from system.orchestrator import _scheduled, ALL_WORKFLOWS
    return {
        "count": len(ALL_WORKFLOWS),
        "workflows": [
            {
                "name":         w.name,
                "trigger_type": w.trigger_type,
                "schedule":     w.schedule_cron or None,
                "event":        w.event_name or None,
                "enabled":      w.enabled,
                "description":  w.description,
            }
            for w in ALL_WORKFLOWS
        ],
    }


@app.post("/workflows/run", tags=["Orchestration"])
def trigger_workflow(req: WorkflowRunRequest) -> dict:
    """Manually trigger a scheduled workflow by name."""
    from system.orchestrator import run_scheduled
    job = run_scheduled(req.workflow_name, req.payload)
    return {
        "job_id":         job.job_id,
        "workflow_name":  job.workflow_name,
        "status":         job.status,
        "result_summary": job.result_summary,
        "error":          job.error_message,
        "duration_ms":    job.duration_ms(),
    }


@app.get("/workflows/history", tags=["Orchestration"])
def workflow_history(limit: int = Query(20, ge=1, le=100)) -> dict:
    """View recent workflow job history."""
    from system.orchestrator import get_job_history
    jobs = get_job_history(limit=limit)
    return {
        "count": len(jobs),
        "jobs": [
            {
                "job_id":         j.job_id,
                "workflow_name":  j.workflow_name,
                "status":         j.status,
                "attempt":        j.attempt_number,
                "result_summary": j.result_summary,
                "error":          j.error_message,
                "duration_ms":    j.duration_ms(),
                "created_at":     j.created_at.isoformat(),
            }
            for j in jobs
        ],
    }


# ─── Buyers ───────────────────────────────────────────────────────────────────

@app.get("/buyers", tags=["Buyers"])
def list_buyers() -> dict:
    """List all active buyers from the vault."""
    from system.buyer_discovery import load_buyers_from_vault
    buyers = load_buyers_from_vault()
    return {
        "count":  len(buyers),
        "buyers": [
            {"buyer_id": bid, "name": name, "zip_codes": zips}
            for bid, name, zips in buyers
        ],
    }


# ─── Entitlement ──────────────────────────────────────────────────────────────

@app.post("/entitlement", tags=["Land"])
def run_entitlement(req: EntitlementRequest) -> dict:
    """Run entitlement analysis on a land deal."""
    from system.entitlement_engine import quick_entitlement_screen, write_entitlement_to_vault

    result = quick_entitlement_screen(
        deal_id      = req.deal_id,
        address      = req.address,
        zip_code     = req.zip_code,
        zoning       = req.zoning,
        has_water    = req.has_water,
        has_sewer    = req.has_sewer,
        has_road     = req.has_road,
        plat_phase   = req.plat_phase,
        dead_paper   = req.dead_paper,
        permits_stage= req.permits_stage,
    )

    vault_file = write_entitlement_to_vault(result)

    return {
        "entitlement_id":           result.entitlement_id,
        "deal_id":                  result.deal_id,
        "address":                  result.address,
        "entitlement_score":        result.entitlement_score,
        "builder_readiness_score":  result.builder_readiness_score,
        "risk_level":               result.risk_level,
        "time_to_build_months":     result.time_to_build_months,
        "grade":                    result.grade(),
        "is_builder_ready":         result.is_builder_ready(),
        "components": {
            "zoning":     result.zoning_score,
            "infra":      result.infra_score,
            "plat":       result.plat_score,
            "permits":    result.permit_score,
            "density":    result.density_score,
        },
        "flags": {
            "zoning_change_required": result.zoning_change_required,
            "infrastructure_gap":     result.infrastructure_gap,
            "dead_paper":             result.dead_paper,
        },
        "risk_factors":          result.risk_factors,
        "opportunities":         result.opportunities,
        "recommended_actions":   result.recommended_actions,
        "vault_file":            vault_file,
    }


# ─── Approval Tracking ────────────────────────────────────────────────────────

@app.post("/approval", tags=["Land"])
def create_approval(req: CreateApprovalRequest) -> dict:
    """Create an approval tracking record for a land deal."""
    from system.approval_tracker import create_approval_record

    record = create_approval_record(
        deal_id        = req.deal_id,
        address        = req.address,
        zip_code       = req.zip_code,
        county         = req.county,
        entitlement_id = req.entitlement_id,
        initial_stage  = req.initial_stage,
    )
    return {
        "approval_id":    record.approval_id,
        "deal_id":        record.deal_id,
        "address":        record.address,
        "current_stage":  record.current_stage,
        "department":     record.department,
        "progress_pct":   record.progress_pct(),
        "likely_next_step": record.likely_next_step,
    }


@app.get("/approval/{approval_id}", tags=["Land"])
def get_approval(approval_id: str) -> dict:
    """Get approval status for a land deal."""
    from system.approval_tracker import get_record, _refresh_backlog

    record = get_record(approval_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Approval record {approval_id} not found")

    _refresh_backlog(record)

    return {
        "approval_id":        record.approval_id,
        "deal_id":            record.deal_id,
        "address":            record.address,
        "zip_code":           record.zip_code,
        "current_stage":      record.current_stage,
        "stage_label":        record.stage_label(),
        "department":         record.department,
        "days_in_stage":      record.compute_days_in_stage(),
        "expected_duration":  record.expected_duration,
        "progress_pct":       record.progress_pct(),
        "revision_count":     record.revision_count,
        "continuance_count":  record.continuance_count,
        "comment_rounds":     record.comment_rounds,
        "backlog_score":      record.backlog_score,
        "backlog_flag":       record.backlog_flag,
        "likely_next_step":   record.likely_next_step,
        "notes":              record.notes,
        "updated_at":         record.updated_at,
    }


@app.patch("/approval/{approval_id}/advance", tags=["Land"])
def advance_approval_stage(approval_id: str, req: AdvanceStageRequest) -> dict:
    """Advance an approval record to the next pipeline stage."""
    from system.approval_tracker import advance_stage, get_record

    try:
        record = advance_stage(approval_id, notes=req.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "approval_id":    record.approval_id,
        "previous_stage": record.current_stage,
        "current_stage":  record.current_stage,
        "stage_label":    record.stage_label(),
        "progress_pct":   record.progress_pct(),
        "likely_next_step": record.likely_next_step,
    }


@app.patch("/approval/{approval_id}/revision", tags=["Land"])
def log_revision(approval_id: str, req: RevisionRequest) -> dict:
    """Record a revision request on an approval."""
    from system.approval_tracker import record_revision

    try:
        record = record_revision(approval_id, notes=req.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "approval_id":    record.approval_id,
        "revision_count": record.revision_count,
        "backlog_score":  record.backlog_score,
        "backlog_flag":   record.backlog_flag,
        "likely_next_step": record.likely_next_step,
    }


@app.get("/approval", tags=["Land"])
def list_approvals(backlogged_only: bool = Query(False)) -> dict:
    """List all approval records, optionally filtered to backlogged deals."""
    from system.approval_tracker import get_all_records, get_backlogged_deals, _refresh_backlog

    records = get_backlogged_deals() if backlogged_only else get_all_records()
    for r in records:
        _refresh_backlog(r)

    return {
        "count":   len(records),
        "records": [
            {
                "approval_id":    r.approval_id,
                "address":        r.address,
                "current_stage":  r.current_stage,
                "days_in_stage":  r.compute_days_in_stage(),
                "backlog_score":  r.backlog_score,
                "backlog_flag":   r.backlog_flag,
                "progress_pct":   r.progress_pct(),
                "likely_next_step": r.likely_next_step,
            }
            for r in records
        ],
    }
