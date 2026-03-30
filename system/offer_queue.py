"""
AMARA Auto Matcher — Stage 10: Offer Queue

Approved deals are placed in the offer queue with all information
the Offer Sender needs: buyer, MAO/max offer, notes, vault link.

Rejected deals are logged with reason. Patterns write to observations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from system.vault import write_vault_file, next_id, read_vault_file
from system.lead_intake import PropertyLead, Classification
from system.match_scorer import SFRFinalScore, LandFinalScore
from system.comp_intelligence import SFRUnderwriteResult, LandUnderwriteResult
from system.config import SFR_MIN_ASSIGNMENT_FEE, LAND_MIN_SPREAD


# ─── Queue Record ─────────────────────────────────────────────────────────────

@dataclass
class OfferRecord:
    offer_id:            str
    property_id:         str
    address:             str
    zip_code:            str
    asset_type:          str             # SFR / land
    status:              str = "pending" # pending / sent / accepted / rejected / expired

    # Buyer routing
    primary_buyer_id:    str       = ""
    primary_buyer_name:  str       = ""
    secondary_buyer_ids: list[str] = field(default_factory=list)

    # Offer math
    max_offer:           float = 0       # MAO for SFR, max land value for land
    target_fee:          float = 0       # assignment fee target
    spread:              float = 0       # land spread (land deals only)

    # Metadata
    final_score:         float = 0
    notes:               str   = ""
    vault_deal_id:       str   = ""      # DEAL-XXXX or LAND-XXXX
    queued_at:           str   = field(default_factory=lambda: datetime.now().isoformat())
    sent_at:             str   = ""

    def summary(self) -> str:
        fee_line = (
            f"Max Offer: ${self.max_offer:,.0f} | Target Fee: ${self.target_fee:,.0f}"
            if self.asset_type.upper() == "SFR"
            else f"Max Land Value: ${self.max_offer:,.0f} | Spread: ${self.spread:,.0f}"
        )
        return (
            f"[{self.status.upper()}] {self.offer_id} — {self.address} ({self.zip_code})\n"
            f"  Buyer: {self.primary_buyer_name} ({self.primary_buyer_id})\n"
            f"  {fee_line}\n"
            f"  Score: {self.final_score:.2f} | Vault: {self.vault_deal_id or 'not created'}"
        )


@dataclass
class RejectionRecord:
    rejection_id: str
    property_id:  str
    address:      str
    zip_code:     str
    stage:        str   # classification / buyer_lookup / underwriting / scoring / approval_gate
    reason:       str
    logged_at:    str = field(default_factory=lambda: datetime.now().isoformat())


# ─── In-memory queue (session-level; persist to vault for durability) ─────────

_offer_queue:    list[OfferRecord]    = []
_rejection_log:  list[RejectionRecord] = []


# ─── Stage 10: Queue Functions ────────────────────────────────────────────────

def queue_offer(
    lead:            PropertyLead,
    score:           SFRFinalScore | LandFinalScore,
    underwrite:      SFRUnderwriteResult | LandUnderwriteResult,
    primary_buyer_id:   str,
    primary_buyer_name: str,
    secondary_buyer_ids: list[str] | None = None,
    notes:           str = "",
) -> OfferRecord:
    """
    Stage 10 (approved path): Place deal in offer queue and create vault stub.
    """
    offer_id  = f"OFFER-{uuid.uuid4().hex[:6].upper()}"
    asset_type = "SFR" if isinstance(underwrite, SFRUnderwriteResult) else "land"

    max_offer  = 0.0
    target_fee = 0.0
    spread     = 0.0

    if isinstance(underwrite, SFRUnderwriteResult):
        max_offer  = underwrite.mao
        target_fee = underwrite.assignment_fee
    else:
        max_offer  = underwrite.ldp.max_land_value if underwrite.ldp else 0
        spread     = underwrite.ldp.spread if underwrite.ldp else 0

    record = OfferRecord(
        offer_id             = offer_id,
        property_id          = lead.property_id,
        address              = lead.address,
        zip_code             = lead.zip_code,
        asset_type           = asset_type,
        primary_buyer_id     = primary_buyer_id,
        primary_buyer_name   = primary_buyer_name,
        secondary_buyer_ids  = secondary_buyer_ids or [],
        max_offer            = max_offer,
        target_fee           = target_fee,
        spread               = spread,
        final_score          = score.final_score,
        notes                = notes,
    )

    # Create vault deal stub
    vault_id = _create_vault_stub(lead, record, underwrite, primary_buyer_id, primary_buyer_name)
    record.vault_deal_id = vault_id

    _offer_queue.append(record)
    return record


def log_rejection(
    lead:   PropertyLead,
    stage:  str,
    reason: str,
) -> RejectionRecord:
    """Stage 10 (rejected path): Log rejection with reason."""
    rec = RejectionRecord(
        rejection_id = f"REJ-{uuid.uuid4().hex[:6].upper()}",
        property_id  = lead.property_id,
        address      = lead.address,
        zip_code     = lead.zip_code,
        stage        = stage,
        reason       = reason,
    )
    _rejection_log.append(rec)
    return rec


def get_queue(status: str | None = None) -> list[OfferRecord]:
    """Return offer queue, optionally filtered by status."""
    if status:
        return [r for r in _offer_queue if r.status == status]
    return list(_offer_queue)


def get_rejections() -> list[RejectionRecord]:
    return list(_rejection_log)


def print_queue_summary() -> None:
    pending = [r for r in _offer_queue if r.status == "pending"]
    print(f"\n{'═' * 55}")
    print(f"OFFER QUEUE — {len(pending)} pending / {len(_offer_queue)} total")
    print(f"{'─' * 55}")
    for r in sorted(_offer_queue, key=lambda x: -x.final_score):
        print(f"  {r.summary()}")
    if _rejection_log:
        print(f"\nREJECTIONS — {len(_rejection_log)} total")
        for r in _rejection_log[-5:]:  # show last 5
            print(f"  [{r.stage.upper()}] {r.address} ({r.zip_code}) — {r.reason}")
    print(f"{'═' * 55}\n")


# ─── Vault Stub Creation ──────────────────────────────────────────────────────

def _create_vault_stub(
    lead:         PropertyLead,
    offer:        OfferRecord,
    underwrite:   SFRUnderwriteResult | LandUnderwriteResult,
    buyer_id:     str,
    buyer_name:   str,
) -> str:
    """
    Auto-create a deal/land stub in the vault for the approved record.
    Returns the vault ID (DEAL-XXXX or LAND-XXXX).
    """
    today  = date.today().isoformat()
    folder = "deals" if offer.asset_type.upper() == "SFR" else "land"

    vault_id   = next_id("DEAL" if folder == "deals" else "LAND", folder)
    addr_slug  = "".join(c if c.isalnum() else "_" for c in lead.address)[:35]
    filename   = f"{vault_id}_{addr_slug}.md"

    if folder == "deals":
        uw = underwrite  # type: SFRUnderwriteResult
        content  = f"# {lead.address}\n\n"
        content += f"## ZIP\n{lead.zip_code}\n\n"
        content += f"## Price\n${lead.list_price:,.0f} (list price — source: {lead.source})\n\n"
        content += f"## Repairs\n${uw.repairs:,.0f} (estimated)\n\n"
        content += f"## Buyer Match\n{buyer_id} — {buyer_name}\n\n"
        content += f"## MAO\n"
        content += f"```\nBuyer Price:   ${uw.buyer_price:>10,.0f}\n"
        content += f"Repairs:     - ${uw.repairs:>10,.0f}\n"
        content += f"Fee (target):- ${'15,000':>10}\n"
        content += f"─────────────────────────────\nMAO:           ${uw.mao:>10,.0f}\n```\n\n"
        content += f"## Assignment Fee\n${offer.target_fee:,.0f} (projected)\n\n"
        content += f"## Status\noffer_queue\n\n"
        content += f"---\n\n<!-- AMARA OS Extended Fields -->\n\n"
        content += f"## Identity\n- **Deal ID:** {vault_id}\n- **Type:** SFR\n"
        content += f"- **Source:** {lead.source}\n- **Created:** {today}\n\n"
        content += f"## Seller\n- **Name:**\n- **Motivation:** {', '.join(lead.keywords[:3]) or 'unknown'}\n"
        content += f"- **Timeline:**\n\n"
        content += f"## Valuation\n- **ARV:** $\n- **Comp 1:**\n- **Comp 2:**\n- **Comp 3:**\n\n"
        content += f"## Auto Matcher\n- **Offer ID:** {offer.offer_id}\n"
        content += f"- **Final Score:** {offer.final_score:.2f}\n"
        content += f"- **Queued:** {today}\n\n"
        content += f"## Outcome\n- **Closed Date:**\n- **Contract Price:** $\n"
        content += f"- **Buyer Price:** $\n- **Assignment Fee Collected:** $\n\n"
        content += f"## Lessons Learned\n"
    else:
        uw = underwrite  # type: LandUnderwriteResult
        ldp = uw.ldp
        content  = f"# {lead.address}\n\n"
        content += f"## ZIP\n{lead.zip_code}\n\n"
        content += f"## Price\n${lead.list_price:,.0f} (asking — source: {lead.source})\n\n"
        content += f"## Repairs\nN/A (land deal)\n\n"
        content += f"## Buyer Match\n{buyer_id} — {buyer_name}\n\n"
        content += f"## MAO\n"
        if ldp:
            content += f"```\nGross Value:      ${ldp.gross_value:>12,.0f}\nDev Cost:       - ${ldp.development_cost:>12,.0f}\n"
            content += f"Builder Profit: - ${ldp.builder_profit:>12,.0f}\n────────────────────────────────\n"
            content += f"Max Land Value:   ${ldp.max_land_value:>12,.0f}\nSpread:           ${ldp.spread:>12,.0f}\n```\n\n"
        content += f"## Assignment Fee\n${offer.spread:,.0f} spread\n\n"
        content += f"## Status\noffer_queue\n\n"
        content += f"---\n\n<!-- AMARA OS Extended Fields -->\n\n"
        content += f"## Identity\n- **Deal ID:** {vault_id}\n- **Type:** Land\n"
        content += f"- **Source:** {lead.source}\n- **Created:** {today}\n\n"
        content += f"## Seller\n- **Name:**\n- **Motivation:** {', '.join(lead.keywords[:3]) or 'unknown'}\n\n"
        content += f"## Auto Matcher\n- **Offer ID:** {offer.offer_id}\n"
        content += f"- **Final Score:** {offer.final_score:.2f}\n- **Queued:** {today}\n\n"
        content += f"## Outcome\n- **Closed Date:**\n- **Contract Price:** $\n"
        content += f"- **Buyer Price:** $\n- **Assignment Fee Collected:** $\n\n"
        content += f"## Lessons Learned\n"

    write_vault_file(folder, filename, content)
    return vault_id
