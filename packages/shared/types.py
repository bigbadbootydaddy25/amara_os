from pydantic import BaseModel
from typing import Optional, Literal


class LeadPayload(BaseModel):
    address: str
    zip_code: str
    city: str = ""
    state: str = ""
    list_price: float
    sqft: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    year_built: Optional[int] = None
    description: Optional[str] = None
    asset_type: Literal["sfr", "land", "unknown"] = "unknown"
    source: str = "manual"


class EventPayload(BaseModel):
    event_name: str
    payload: dict = {}


class OfferApprovalPayload(BaseModel):
    deal_id: str
    approved_by: str = "system"
    notes: str = ""


class LandLeadPayload(BaseModel):
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


class HealthResponse(BaseModel):
    status: str
    service: str
    note: Optional[str] = None
