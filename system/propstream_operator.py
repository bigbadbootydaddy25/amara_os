"""
AMARA OS — PropStream Operator
Structured schemas and processing logic for PropStream exports.
Converts raw PropStream data into vault-ready buyer and deal files.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from system.vault import (
    write_vault_file,
    read_vault_file,
    next_id,
    list_vault,
)
from system.config import (
    BUYER_STATUS_ACTIVE,
    ASSET_TYPE_SFR,
    ACTIVITY_HOT,
    ACTIVITY_WARM,
    ACTIVITY_COLD,
    ACTIVITY_UNKNOWN,
)


# ─── Data Schemas ─────────────────────────────────────────────────────────────

@dataclass
class PropStreamCashBuyer:
    """Represents a cash buyer record extracted from PropStream export."""
    entity_name: str
    mailing_address: str
    mailing_city: str
    mailing_state: str
    mailing_zip: str
    purchase_count: int
    purchase_zips: list[str]
    avg_purchase_price: float
    min_purchase_price: float
    max_purchase_price: float
    last_purchase_date: str
    purchase_history: list[dict] = field(default_factory=list)
    raw_source: str = "PropStream"

    def is_qualified(self) -> bool:
        """Meets minimum criteria to be added to buyer vault."""
        return (
            self.purchase_count >= 2
            and self.avg_purchase_price > 0
            and bool(self.entity_name.strip())
        )

    def looks_like_investor(self) -> bool:
        """Heuristic check — LLC/investor keywords in entity name."""
        investor_keywords = [
            "llc", "holdings", "capital", "investments", "properties",
            "group", "realty", "acquisitions", "ventures", "enterprise",
            "partners", "fund", "trust", "equity",
        ]
        name_lower = self.entity_name.lower()
        return any(kw in name_lower for kw in investor_keywords)


@dataclass
class PropStreamDistressedProperty:
    """Represents a distressed property record from PropStream export."""
    address: str
    city: str
    state: str
    zip_code: str
    estimated_value: float
    equity_pct: float
    distress_type: str          # pre_foreclosure / tax_delinquent / vacant / bankruptcy
    last_sale_date: str
    last_sale_price: float
    owner_name: str
    owner_mailing_address: str
    owner_mailing_state: str
    beds: int = 0
    baths: float = 0
    sqft: float = 0
    year_built: int = 0
    raw_source: str = "PropStream"

    def has_equity(self) -> bool:
        return self.equity_pct >= 20

    def is_high_equity(self) -> bool:
        return self.equity_pct >= 40

    def distress_score(self) -> int:
        """
        Score 0–3 based on stacked distress signals.
        Higher = more motivated seller.
        """
        score = 0
        if self.distress_type in ("pre_foreclosure", "tax_delinquent", "bankruptcy"):
            score += 1
        if self.owner_mailing_state != self.state:
            score += 1  # Absentee out-of-state
        if self.equity_pct >= 40:
            score += 1
        return score


@dataclass
class ZipHeatData:
    """Aggregated ZIP corridor heat data from PropStream cash buyer analysis."""
    zip_code: str
    city: str
    state: str
    cash_buyer_count: int
    total_cash_transactions: int
    median_cash_price: float
    min_cash_price: float
    max_cash_price: float
    analysis_period_months: int = 24

    def activity_level(self) -> str:
        if self.cash_buyer_count >= 5 and self.total_cash_transactions >= 10:
            return ACTIVITY_HOT
        elif self.cash_buyer_count >= 3 or self.total_cash_transactions >= 5:
            return ACTIVITY_WARM
        elif self.cash_buyer_count >= 1:
            return ACTIVITY_COLD
        else:
            return ACTIVITY_UNKNOWN


# ─── CSV Import ───────────────────────────────────────────────────────────────

PROPSTREAM_BUYER_FIELD_MAP = {
    # PropStream column name → internal field
    "Buyer Name": "entity_name",
    "Mailing Address": "mailing_address",
    "Mailing City": "mailing_city",
    "Mailing State": "mailing_state",
    "Mailing ZIP": "mailing_zip",
    "# of Purchases": "purchase_count",
    "Avg Purchase Price": "avg_purchase_price",
    "Min Purchase Price": "min_purchase_price",
    "Max Purchase Price": "max_purchase_price",
    "Last Purchase Date": "last_purchase_date",
}

PROPSTREAM_PROPERTY_FIELD_MAP = {
    "Property Address": "address",
    "City": "city",
    "State": "state",
    "ZIP": "zip_code",
    "Estimated Value": "estimated_value",
    "Equity %": "equity_pct",
    "Distress Type": "distress_type",
    "Last Sale Date": "last_sale_date",
    "Last Sale Price": "last_sale_price",
    "Owner Name": "owner_name",
    "Owner Mailing Address": "owner_mailing_address",
    "Owner Mailing State": "owner_mailing_state",
    "Beds": "beds",
    "Baths": "baths",
    "Sq Ft": "sqft",
    "Year Built": "year_built",
}


def _parse_money(val: str) -> float:
    """Parse PropStream money strings like '$125,000' → 125000.0"""
    if not val:
        return 0.0
    return float(re.sub(r"[^\d.]", "", val) or 0)


def _parse_pct(val: str) -> float:
    """Parse '42%' → 42.0"""
    if not val:
        return 0.0
    return float(re.sub(r"[^\d.]", "", val) or 0)


def _parse_int(val: str) -> int:
    if not val:
        return 0
    try:
        return int(re.sub(r"[^\d]", "", val) or 0)
    except ValueError:
        return 0


def load_cash_buyer_export(csv_path: str | Path) -> list[PropStreamCashBuyer]:
    """
    Load a PropStream cash buyer export CSV.
    Returns list of PropStreamCashBuyer records.
    """
    buyers = []
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"PropStream export not found: {csv_path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                buyer = PropStreamCashBuyer(
                    entity_name=row.get("Buyer Name", "").strip(),
                    mailing_address=row.get("Mailing Address", ""),
                    mailing_city=row.get("Mailing City", ""),
                    mailing_state=row.get("Mailing State", ""),
                    mailing_zip=row.get("Mailing ZIP", ""),
                    purchase_count=_parse_int(row.get("# of Purchases", "0")),
                    purchase_zips=[row.get("ZIP", "").strip()],
                    avg_purchase_price=_parse_money(row.get("Avg Purchase Price", "0")),
                    min_purchase_price=_parse_money(row.get("Min Purchase Price", "0")),
                    max_purchase_price=_parse_money(row.get("Max Purchase Price", "0")),
                    last_purchase_date=row.get("Last Purchase Date", ""),
                )
                buyers.append(buyer)
            except Exception:
                continue  # Skip malformed rows

    return buyers


def load_distressed_property_export(csv_path: str | Path) -> list[PropStreamDistressedProperty]:
    """
    Load a PropStream distressed property export CSV.
    Returns list of PropStreamDistressedProperty records.
    """
    properties = []
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"PropStream export not found: {csv_path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                prop = PropStreamDistressedProperty(
                    address=row.get("Property Address", "").strip(),
                    city=row.get("City", ""),
                    state=row.get("State", ""),
                    zip_code=row.get("ZIP", "").strip(),
                    estimated_value=_parse_money(row.get("Estimated Value", "0")),
                    equity_pct=_parse_pct(row.get("Equity %", "0")),
                    distress_type=row.get("Distress Type", "unknown").lower().replace(" ", "_"),
                    last_sale_date=row.get("Last Sale Date", ""),
                    last_sale_price=_parse_money(row.get("Last Sale Price", "0")),
                    owner_name=row.get("Owner Name", "").strip(),
                    owner_mailing_address=row.get("Owner Mailing Address", ""),
                    owner_mailing_state=row.get("Owner Mailing State", ""),
                    beds=_parse_int(row.get("Beds", "0")),
                    baths=float(re.sub(r"[^\d.]", "", row.get("Baths", "0")) or 0),
                    sqft=float(re.sub(r"[^\d.]", "", row.get("Sq Ft", "0")) or 0),
                    year_built=_parse_int(row.get("Year Built", "0")),
                )
                properties.append(prop)
            except Exception:
                continue

    return properties


# ─── Vault Writers ────────────────────────────────────────────────────────────

def create_buyer_from_propstream(buyer: PropStreamCashBuyer) -> tuple[str, Path] | None:
    """
    Convert a PropStreamCashBuyer into a vault buyer file.
    Returns (buyer_id, path) or None if buyer doesn't qualify.
    """
    if not buyer.is_qualified():
        return None

    buyer_id = next_id("BUY", "buyers")
    today = date.today().isoformat()
    name_slug = re.sub(r"[^\w]", "_", buyer.entity_name)[:40]
    filename = f"{buyer_id}_{name_slug}.md"

    template = read_vault_file("buyers", "TEMPLATE.md") or ""

    content = f"# {buyer.entity_name}\n\n"
    content += f"## Entity\n{buyer.entity_name}\n\n"
    content += f"## ZIP Codes\n"
    for z in sorted(set(buyer.purchase_zips)):
        content += f"- {z}\n"
    content += "\n"
    content += f"## Deal Activity\n"
    content += f"- Deals last 12 months: (verify — PropStream shows {buyer.purchase_count} total over search period)\n"
    content += f"- Deals last 24 months: {buyer.purchase_count}\n\n"
    content += f"## Buy Box\n"
    content += f"- Price Range: ${buyer.min_purchase_price:,.0f} – ${buyer.max_purchase_price:,.0f}\n"
    content += f"- Property Type: SFR\n"
    content += f"- Condition: unknown — contact to verify\n"
    content += f"- Strategy: unknown — contact to verify\n\n"
    content += f"## Notes\nSource: PropStream cash buyer export. {buyer.purchase_count} cash transactions identified. "
    content += f"Last purchase: {buyer.last_purchase_date}. "
    content += f"Avg purchase price: ${buyer.avg_purchase_price:,.0f}. "
    content += f"Contact not yet verified — needs outreach to confirm buy box and close timeline.\n\n"
    content += "---\n\n<!-- AMARA OS Extended Fields -->\n\n"
    content += f"## Identity\n"
    content += f"- **ID:** {buyer_id}\n"
    content += f"- **Phone:** (not yet obtained)\n"
    content += f"- **Email:** (not yet obtained)\n"
    content += f"- **Contact Method:** (unknown — outreach needed)\n"
    content += f"- **Source:** PropStream cash buyer export\n"
    content += f"- **Added:** {today}\n"
    content += f"- **Last Contact:** (never)\n"
    content += f"- **Status:** active\n\n"
    content += "## Verified Proof of Funds\n- [ ] Yes  [ ] No\n- POF Amount: $\n- POF Date Verified:\n\n"
    content += "## Performance Metrics\n- Deals Shown: 0\n- Deals Accepted: 0\n- Acceptance Rate: 0%\n- Total Volume Closed: $0\n\n"
    content += "## Deal History\n| Date | Deal ID | Type | Address | Accepted? | Fee | Notes |\n"
    content += "|------|---------|------|---------|-----------|-----|-------|\n|      |         |      |         |           |     |       |\n\n"
    content += "## Buy Box Updates\n| Date | Field Changed | Old Value | New Value | Reason |\n"
    content += "|------|---------------|-----------|-----------|--------|\n|      |               |           |           |        |\n"

    path = write_vault_file("buyers", filename, content)
    return buyer_id, path


def screen_distressed_properties(
    properties: list[PropStreamDistressedProperty],
    active_buyer_zips: list[str],
) -> list[PropStreamDistressedProperty]:
    """
    Filter distressed properties to those in active buyer ZIPs with equity.
    Enforces buyer-first: only return properties where a buyer likely exists.
    """
    return [
        p for p in properties
        if p.zip_code in active_buyer_zips
        and p.has_equity()
        and p.estimated_value > 0
    ]


def create_deal_stub_from_propstream(
    prop: PropStreamDistressedProperty,
    buyer_id: str,
    buyer_name: str,
) -> tuple[str, Path]:
    """
    Create a deal stub file from a PropStream distressed property record.
    Buyer must be confirmed before calling this function.
    """
    deal_id = next_id("DEAL", "deals")
    today = date.today().isoformat()
    addr_slug = re.sub(r"[^\w]", "_", prop.address)[:40]
    filename = f"{deal_id}_{addr_slug}.md"

    content = f"# {prop.address}, {prop.city} {prop.state} {prop.zip_code}\n\n"
    content += f"## ZIP\n{prop.zip_code}\n\n"
    content += f"## Price\n${prop.estimated_value:,.0f} (PropStream estimated value — confirm with seller)\n\n"
    content += f"## Repairs\n(not yet estimated — field inspection required)\n\n"
    content += f"## Buyer Match\n{buyer_id} — {buyer_name}\n(Matched by ZIP corridor. Confirm buyer interest before progressing.)\n\n"
    content += f"## MAO\n(Cannot calculate — repairs not yet estimated)\n\n"
    content += f"## Assignment Fee\n(TBD)\n\n"
    content += f"## Status\nprospecting\n\n"
    content += "---\n\n<!-- AMARA OS Extended Fields -->\n\n"
    content += f"## Identity\n- **Deal ID:** {deal_id}\n- **Type:** SFR\n- **APN:** (pull from county)\n- **Created:** {today}\n\n"
    content += f"## Seller\n- **Name:** {prop.owner_name}\n"
    content += f"- **Motivation:** {prop.distress_type.replace('_', ' ').title()}\n"
    content += f"- **Timeline:** (unknown — contact required)\n\n"
    content += f"## Valuation\n- **ARV:** $ (pull comps)\n- **Comp 1:**\n- **Comp 2:**\n- **Comp 3:**\n\n"
    content += f"## PropStream Data\n"
    content += f"- Estimated Value: ${prop.estimated_value:,.0f}\n"
    content += f"- Equity: {prop.equity_pct:.0f}%\n"
    content += f"- Distress Signal: {prop.distress_type}\n"
    content += f"- Last Sale: {prop.last_sale_date} at ${prop.last_sale_price:,.0f}\n"
    content += f"- Distress Score: {prop.distress_score()}/3\n\n"
    content += "## Outcome\n- **Closed Date:**\n- **Contract Price:** $\n- **Buyer Price:** $\n- **Assignment Fee Collected:** $\n\n"
    content += "## Lessons Learned\n"

    path = write_vault_file("deals", filename, content)
    return deal_id, path


# ─── Session Log ──────────────────────────────────────────────────────────────

def log_propstream_session(
    market: str,
    search_type: str,
    records_reviewed: int,
    buyers_created: int,
    deals_created: int,
    observations: list[str],
    notes: str = "",
) -> Path:
    """
    Log a PropStream work session to the observations vault.
    Every session with actionable output must be logged.
    """
    from system.vault import next_id, write_vault_file
    obs_id = next_id("OBS", "observations")
    today = date.today().isoformat()
    filename = f"{obs_id}_{today}_PropStream_{market.replace(' ', '_')}.md"

    content = f"# PropStream Session — {market}\n\n"
    content += f"## Market\n\n- {market}\n\n"
    content += f"## Insight\n\n"
    content += f"- Search type: {search_type}\n"
    content += f"- Records reviewed: {records_reviewed}\n"
    content += f"- Buyers added to vault: {buyers_created}\n"
    content += f"- Deal stubs created: {deals_created}\n"
    for obs in observations:
        content += f"- {obs}\n"
    content += "\n"
    content += f"## Impact\n\n- {buyers_created} new buyers added to pipeline. {deals_created} properties flagged for follow-up.\n\n"
    content += f"## Action\n\n- Outreach required on {buyers_created} new buyer(s) to verify buy box.\n"
    content += f"- Field visits or seller contact needed on {deals_created} deal stub(s) before MAO can be calculated.\n"
    if notes:
        content += f"- {notes}\n"
    content += "\n---\n\n<!-- AMARA OS Extended Fields -->\n\n"
    content += f"## Identity\n- **ID:** {obs_id}\n- **Date:** {today}\n- **Type:** market\n- **Related Deal:**\n- **Related Buyer:**\n"

    path = write_vault_file("observations", filename, content)
    return path
