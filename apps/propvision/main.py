import sys
import uuid
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, "/workspace")

from system.lead_intake import ingest_manual
from system.auto_matcher import run_pipeline
from system.entitlement_engine import quick_entitlement_screen
from system.orchestrator import dispatch_event, process_events
from system.offer_queue import get_queue

app = FastAPI(title="amara-propvision")


class SFRLeadIn(BaseModel):
    address: str
    zip_code: str
    list_price: float
    city: str = ""
    state: str = ""
    sqft: int = 0
    beds: int = 0
    baths: float = 0
    year_built: int = 0
    description: str = ""


class LandLeadIn(BaseModel):
    address: str
    zip_code: str
    acres: float
    asking_price: float
    zoning: str = "unknown"
    has_water: bool = False
    has_sewer: bool = False
    has_road: bool = False
    plat_phase: str = "none"
    dead_paper: bool = False
    permits_stage: str = "none"


class EventIn(BaseModel):
    event_name: str
    payload: dict = {}


class OfferApprovalIn(BaseModel):
    deal_id: str
    approved_by: str = "system"
    notes: str = ""


def _safe_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _safe_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_safe_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_dict(v) for k, v in obj.items()}
    return obj


@app.get("/health")
async def health():
    return {"status": "ok", "service": "propvision"}


@app.post("/underwrite/sfr")
async def underwrite_sfr(lead: SFRLeadIn):
    prop = ingest_manual(
        address=lead.address,
        zip_code=lead.zip_code,
        city=lead.city,
        state=lead.state,
        list_price=lead.list_price,
        beds=lead.beds,
        baths=lead.baths,
        sqft=lead.sqft,
        year_built=lead.year_built,
        description=lead.description,
    )
    result = run_pipeline(prop)
    return _safe_dict(result)


@app.post("/underwrite/land")
async def underwrite_land(lead: LandLeadIn):
    deal_id = f"LAND-{uuid.uuid4().hex[:6].upper()}"
    result = quick_entitlement_screen(
        deal_id=deal_id,
        address=lead.address,
        zip_code=lead.zip_code,
        zoning=lead.zoning,
        has_water=lead.has_water,
        has_sewer=lead.has_sewer,
        has_road=lead.has_road,
        plat_phase=lead.plat_phase,
        dead_paper=lead.dead_paper,
        permits_stage=lead.permits_stage,
    )
    return _safe_dict(result)


@app.post("/events")
async def post_event(event: EventIn):
    evt = dispatch_event(event.event_name, event.payload)
    jobs = process_events()
    return {"event_id": evt.event_id, "jobs": [_safe_dict(j) for j in jobs]}


@app.post("/offers/queue")
async def queue_offer_approval(approval: OfferApprovalIn):
    evt = dispatch_event("offer_approved", {
        "deal_id": approval.deal_id,
        "approved_by": approval.approved_by,
        "notes": approval.notes,
    })
    jobs = process_events()
    return {"event_id": evt.event_id, "queued": len(jobs), "jobs": [_safe_dict(j) for j in jobs]}


@app.get("/queue")
async def get_offer_queue():
    queue = get_queue()
    return {"count": len(queue), "offers": [_safe_dict(o) for o in queue]}
