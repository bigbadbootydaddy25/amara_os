"""
AMARA Auto Matcher — Main Pipeline Orchestrator

Runs all 10 stages for every incoming lead.

Stage 1  — Lead intake (normalize)
Stage 2  — Property classification
Stage 3  — Buyer lookup
Stage 4  — Comp reading (buyer price determination)
Stage 5  — SFR underwriting (MAO)
Stage 6  — Land / dead paper underwriting (LDP spread)
Stage 7  — Distress + motivation scoring
Stage 8  — Final match score
Stage 9  — Approval gate
Stage 10 — Offer queue or rejection log

For every lead the system answers:
  does a real buyer exist?
  does the property fit the buy box?
  what is the real buyer price?
  what is the MAO or max land value?
  does it clear the profit lock?
  should it be queued for offer?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from system.lead_intake import (
    PropertyLead, ClassificationResult, Classification,
    classify_property,
)
from system.comp_intelligence import (
    underwrite_sfr, underwrite_land,
    SFRUnderwriteResult, LandUnderwriteResult,
    LandSignals,
)
from system.distress_scorer import score_distress, SFRDistressScore, LandDistressScore
from system.match_scorer import (
    compute_sfr_final_score, compute_land_final_score,
    buyer_match_score_from_zip,
    SFRScoreInputs, LandScoreInputs,
    _speed_to_close_score,
)
from system.offer_queue import queue_offer, log_rejection, OfferRecord, RejectionRecord
from system.vault import list_vault, read_vault_file
from system.config import (
    SFR_MIN_ASSIGNMENT_FEE, LAND_MIN_SPREAD,
    ASSET_TYPE_SFR, ASSET_TYPE_LAND,
)


# ─── Buyer Profile (lightweight, read from vault) ────────────────────────────

@dataclass
class VaultBuyer:
    buyer_id:       str
    buyer_name:     str
    zip_codes:      list[str]
    asset_types:    list[str]
    min_price:      float
    max_price:      float
    min_beds:       int
    strategy:       str   # flip / hold / both
    max_repairs:    float = float("inf")


# ─── Pipeline Result ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    property_id:      str
    address:          str
    zip_code:         str
    classification:   str
    decision:         str        # queued / rejected
    stage_stopped:    str        # which stage made the final decision
    offer:            OfferRecord | None         = None
    rejection:        RejectionRecord | None     = None
    final_score:      float                      = 0.0
    notes:            list[str]                  = field(default_factory=list)

    def summary(self) -> str:
        icon = "QUEUED" if self.decision == "queued" else "REJECTED"
        lines = [
            f"[{icon}] {self.address} ({self.zip_code})",
            f"  Classification: {self.classification}",
            f"  Stage: {self.stage_stopped} | Score: {self.final_score:.2f}",
        ]
        if self.offer:
            lines.append(f"  {self.offer.summary()}")
        if self.rejection:
            lines.append(f"  Reason: {self.rejection.reason}")
        return "\n".join(lines)


# ─── Vault Buyer Loader ───────────────────────────────────────────────────────

def _parse_money(text: str) -> float:
    m = re.search(r"\$?([\d,]+)", text or "")
    return float(m.group(1).replace(",", "")) if m else 0.0


def _load_vault_buyers() -> list[VaultBuyer]:
    """Read all active buyer files from buyers/ vault."""
    buyers = []
    for path in list_vault("buyers"):
        if path.name == "TEMPLATE.md":
            continue
        content = path.read_text(encoding="utf-8")
        lines   = content.splitlines()

        buyer_id   = ""
        buyer_name = path.stem.split("_", 1)[-1].replace("_", " ") if "_" in path.stem else path.stem
        zip_codes  = []
        min_price  = 0.0
        max_price  = float("inf")
        min_beds   = 0
        strategy   = "flip"
        asset_types = [ASSET_TYPE_SFR]

        for line in lines:
            l = line.strip()
            if l.startswith("- **ID:**"):
                buyer_id = l.split("**ID:**")[-1].strip()
            if l.startswith("# "):
                buyer_name = l[2:].strip()
            # ZIP codes block — lines starting with "- " that contain 5-digit ZIPs
            zip_matches = re.findall(r"\b(\d{5})\b", l)
            zip_codes.extend(zip_matches)
            # Price range
            if "price range" in l.lower():
                prices = re.findall(r"\$[\d,]+", l)
                if len(prices) >= 2:
                    min_price = _parse_money(prices[0])
                    max_price = _parse_money(prices[1])
                elif len(prices) == 1:
                    max_price = _parse_money(prices[0])
            # Strategy
            if "hold" in l.lower() and "strategy" in l.lower():
                strategy = "hold"
            elif "both" in l.lower() and "strategy" in l.lower():
                strategy = "both"
            # Asset type
            if "land" in l.lower() and "property type" in l.lower():
                asset_types.append(ASSET_TYPE_LAND)
            # Status — skip inactive
            if "**status:**" in l.lower() and "inactive" in l.lower():
                buyer_id = ""  # will be skipped below
                break

        if not buyer_id:
            # Derive ID from filename
            buyer_id = path.stem.split("_")[0] if "_" in path.stem else path.stem

        zip_codes = list(dict.fromkeys(z for z in zip_codes if len(z) == 5))

        if zip_codes:
            buyers.append(VaultBuyer(
                buyer_id    = buyer_id,
                buyer_name  = buyer_name,
                zip_codes   = zip_codes,
                asset_types = asset_types,
                min_price   = min_price,
                max_price   = max_price,
                min_beds    = min_beds,
                strategy    = strategy,
            ))

    return buyers


# ─── Stage 3: Buyer Lookup ────────────────────────────────────────────────────

def _lookup_buyers(
    lead: PropertyLead,
    classification: str,
    buyers: list[VaultBuyer],
) -> tuple[VaultBuyer | None, list[VaultBuyer], float]:
    """
    Stage 3: Find buyers whose buy box matches this lead.
    Returns (primary_buyer, secondary_buyers, match_score).
    Enforces buyer-first: if no buyer found, pipeline stops here.
    """
    matched = []

    target_type = ASSET_TYPE_LAND if classification in (
        Classification.LAND_SUBDIVISION,
        Classification.DEAD_PAPER,
        Classification.INFILL_LOT,
    ) else ASSET_TYPE_SFR

    for buyer in buyers:
        if target_type not in buyer.asset_types:
            continue
        if lead.zip_code not in buyer.zip_codes:
            continue
        if lead.list_price > buyer.max_price * 1.15:
            continue   # price too far above ceiling — skip
        if lead.list_price > 0 and lead.list_price < buyer.min_price:
            continue

        score = buyer_match_score_from_zip(
            buyer_zips      = buyer.zip_codes,
            deal_zip        = lead.zip_code,
            buyer_max_price = buyer.max_price,
            deal_price      = lead.list_price,
            buyer_min_beds  = buyer.min_beds,
            deal_beds       = lead.beds,
        )
        matched.append((score, buyer))

    if not matched:
        return None, [], 0.0

    matched.sort(key=lambda x: -x[0])
    primary_score, primary = matched[0]
    secondary = [b for _, b in matched[1:4]]  # top 3 secondary

    return primary, secondary, primary_score


# ─── Stage 4: Buyer Price Estimate ────────────────────────────────────────────

def _estimate_buyer_price(lead: PropertyLead, buyer: VaultBuyer) -> float:
    """
    Stage 4: Estimate real buyer price without live comp data.
    Uses buyer's max_price as ceiling and list_price as reference.
    A live comp read (playbooks/comps/sfr_comp_reading.md) should
    replace this estimate before final offer.
    """
    if lead.list_price <= 0:
        return 0.0

    # Use 85% of list price as conservative investor entry estimate
    # This is a placeholder — real buyer price comes from comp read
    estimated = lead.list_price * 0.85

    # Cap at buyer's max price
    if buyer.max_price and estimated > buyer.max_price:
        estimated = buyer.max_price

    return round(estimated, -3)  # round to nearest $1,000


def _estimate_repairs(lead: PropertyLead) -> float:
    """
    Fast repair estimate from property age and sqft.
    Returns conservative high estimate.
    """
    if lead.sqft <= 0:
        return 25_000  # default if no sqft

    age = 2026 - (lead.year_built or 1990)

    if age < 10:
        rate = 10    # newer — light cosmetic
    elif age < 25:
        rate = 22    # medium
    elif age < 40:
        rate = 38    # medium-heavy
    else:
        rate = 55    # heavy

    raw = lead.sqft * rate
    return (int(raw / 5_000) + 1) * 5_000  # round up to $5k


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    lead: PropertyLead,
    buyers: list[VaultBuyer] | None = None,
) -> PipelineResult:
    """
    Run all 10 stages for a single lead.
    Returns PipelineResult with decision, score, and vault record.
    """
    notes = []

    # Load buyers from vault if not provided
    if buyers is None:
        buyers = _load_vault_buyers()

    # ── Stage 2: Classification ───────────────────────────────────────────────
    classification = classify_property(lead)
    notes.append(f"Stage 2: {classification.classification}")

    if not classification.is_workable():
        rej = log_rejection(lead, "classification", classification.reject_reason)
        return PipelineResult(
            property_id    = lead.property_id,
            address        = lead.address,
            zip_code       = lead.zip_code,
            classification = classification.classification,
            decision       = "rejected",
            stage_stopped  = "classification",
            rejection      = rej,
            notes          = notes,
        )

    cls = classification.classification

    # ── Stage 3: Buyer Lookup ─────────────────────────────────────────────────
    primary_buyer, secondary_buyers, buyer_match = _lookup_buyers(lead, cls, buyers)

    if not primary_buyer:
        rej = log_rejection(
            lead, "buyer_lookup",
            f"No buyer found for ZIP {lead.zip_code} / type {cls}",
        )
        return PipelineResult(
            property_id    = lead.property_id,
            address        = lead.address,
            zip_code       = lead.zip_code,
            classification = cls,
            decision       = "rejected",
            stage_stopped  = "buyer_lookup",
            rejection      = rej,
            notes          = notes,
        )

    notes.append(f"Stage 3: matched {primary_buyer.buyer_id} ({primary_buyer.buyer_name}) score={buyer_match:.2f}")

    # ── Stage 7: Distress Score (run early — feeds stage 8) ───────────────────
    distress = score_distress(lead)
    notes.append(f"Stage 7: distress={distress.total_distress_score:.2f} [{distress.grade()}]")

    # ── Stages 4–6: Underwriting ──────────────────────────────────────────────
    is_land = cls in (Classification.LAND_SUBDIVISION, Classification.DEAD_PAPER, Classification.INFILL_LOT)

    if not is_land:
        # Stage 4: buyer price estimate
        buyer_price = _estimate_buyer_price(lead, primary_buyer)
        repairs     = _estimate_repairs(lead)

        # Stage 5: SFR underwriting
        uw = underwrite_sfr(
            deal_id       = lead.property_id,
            address       = lead.address,
            zip_code      = lead.zip_code,
            buyer_id      = primary_buyer.buyer_id,
            buyer_price   = buyer_price,
            seller_asking = lead.list_price,
            repairs       = repairs,
        )
        notes.append(f"Stage 5: MAO=${uw.mao:,.0f} fee=${uw.assignment_fee:,.0f} [{uw.decision}]")

        if uw.decision == "no_go":
            rej = log_rejection(lead, "underwriting", uw.decision_reason)
            return PipelineResult(
                property_id    = lead.property_id,
                address        = lead.address,
                zip_code       = lead.zip_code,
                classification = cls,
                decision       = "rejected",
                stage_stopped  = "underwriting",
                rejection      = rej,
                notes          = notes,
            )

        # Stage 8: SFR final score
        urgent = any([
            distress.vacancy_signal,
            distress.probate_signal,
            distress.financial_distress,
        ]) if isinstance(distress, SFRDistressScore) else False

        sfr_inputs = SFRScoreInputs(
            property_id       = lead.property_id,
            buyer_match_score = buyer_match,
            underwrite        = uw,
            distress          = distress,
            comp_confidence   = 0.55,  # conservative — no live comps yet
            speed_to_close    = _speed_to_close_score(lead.dom, urgent),
        )
        score = compute_sfr_final_score(sfr_inputs)
        notes.append(f"Stage 8: final_score={score.final_score:.2f} [{score.grade()}] gate={'PASS' if score.gate_passed else 'FAIL'}")

        # Stage 9: gate
        if not score.gate_passed:
            rej = log_rejection(lead, "approval_gate", score.gate_fail_reason)
            return PipelineResult(
                property_id    = lead.property_id,
                address        = lead.address,
                zip_code       = lead.zip_code,
                classification = cls,
                decision       = "rejected",
                stage_stopped  = "approval_gate",
                rejection      = rej,
                final_score    = score.final_score,
                notes          = notes,
            )

        # Stage 10: queue
        offer = queue_offer(
            lead                 = lead,
            score                = score,
            underwrite           = uw,
            primary_buyer_id     = primary_buyer.buyer_id,
            primary_buyer_name   = primary_buyer.buyer_name,
            secondary_buyer_ids  = [b.buyer_id for b in secondary_buyers],
            notes                = f"Comp read required before sending offer. Estimated buyer price: ${buyer_price:,.0f}.",
        )
        return PipelineResult(
            property_id    = lead.property_id,
            address        = lead.address,
            zip_code       = lead.zip_code,
            classification = cls,
            decision       = "queued",
            stage_stopped  = "offer_queue",
            offer          = offer,
            final_score    = score.final_score,
            notes          = notes,
        )

    else:
        # Stage 6: Land underwriting
        # Use listing price as acquisition price; lot_size as acres
        acres = lead.lot_size if lead.lot_size > 0 else 1.0

        # Median home price: use buyer's max_price as proxy (rough estimate)
        # In production this would come from a comp read
        median_home = primary_buyer.max_price if primary_buyer.max_price < float("inf") else 300_000

        land_distress = distress if isinstance(distress, LandDistressScore) else None
        signals = LandSignals(
            nearby_builders                  = land_distress.builder_adjacency if land_distress else False,
            active_subdivisions              = land_distress.plat_phase_gap if land_distress else False,
            new_construction_prices_available= True,  # assume we have median home data
            expansion_direction_confirmed    = False,
        )

        uw = underwrite_land(
            deal_id           = lead.property_id,
            address           = lead.address,
            acres             = acres,
            median_home_price = median_home,
            asking_price      = lead.list_price,
            signals           = signals,
        )
        notes.append(
            f"Stage 6: spread=${uw.ldp.spread:,.0f} [{uw.decision}] signals={signals.score()}/4"
            if uw.ldp else f"Stage 6: LDP failed"
        )

        if not uw.is_go():
            rej = log_rejection(lead, "underwriting", uw.decision_reason)
            return PipelineResult(
                property_id    = lead.property_id,
                address        = lead.address,
                zip_code       = lead.zip_code,
                classification = cls,
                decision       = "rejected",
                stage_stopped  = "underwriting",
                rejection      = rej,
                notes          = notes,
            )

        # Stage 8: Land score
        land_d = distress if isinstance(distress, LandDistressScore) else LandDistressScore(lead.property_id)
        land_inputs = LandScoreInputs(
            property_id          = lead.property_id,
            builder_match_score  = buyer_match,
            underwrite           = uw,
            distress             = land_d,
            location_score       = 0.50,   # neutral until expansion direction confirmed
            ownership_score      = min(land_d.total_distress_score + 0.20, 1.0),
        )
        score = compute_land_final_score(land_inputs)
        notes.append(f"Stage 8: final_score={score.final_score:.2f} [{score.grade()}] gate={'PASS' if score.gate_passed else 'FAIL'}")

        if not score.gate_passed:
            rej = log_rejection(lead, "approval_gate", score.gate_fail_reason)
            return PipelineResult(
                property_id    = lead.property_id,
                address        = lead.address,
                zip_code       = lead.zip_code,
                classification = cls,
                decision       = "rejected",
                stage_stopped  = "approval_gate",
                rejection      = rej,
                final_score    = score.final_score,
                notes          = notes,
            )

        offer = queue_offer(
            lead                = lead,
            score               = score,
            underwrite          = uw,
            primary_buyer_id    = primary_buyer.buyer_id,
            primary_buyer_name  = primary_buyer.buyer_name,
            secondary_buyer_ids = [b.buyer_id for b in secondary_buyers],
            notes               = f"Land signals: {signals.score()}/4. Confirm builder interest before offer.",
        )
        return PipelineResult(
            property_id    = lead.property_id,
            address        = lead.address,
            zip_code       = lead.zip_code,
            classification = cls,
            decision       = "queued",
            stage_stopped  = "offer_queue",
            offer          = offer,
            final_score    = score.final_score,
            notes          = notes,
        )


def run_batch(
    leads: list[PropertyLead],
    buyers: list[VaultBuyer] | None = None,
) -> list[PipelineResult]:
    """
    Run the pipeline for a batch of leads.
    Returns all results sorted: queued first (by score desc), rejected last.
    """
    if buyers is None:
        buyers = _load_vault_buyers()

    results = [run_pipeline(lead, buyers) for lead in leads]

    results.sort(key=lambda r: (
        0 if r.decision == "queued" else 1,
        -r.final_score,
    ))
    return results


def print_batch_summary(results: list[PipelineResult]) -> None:
    queued   = [r for r in results if r.decision == "queued"]
    rejected = [r for r in results if r.decision == "rejected"]

    print(f"\n{'═' * 60}")
    print(f"AUTO MATCHER — {len(results)} leads processed")
    print(f"  Queued: {len(queued)}   Rejected: {len(rejected)}")
    print(f"{'─' * 60}")

    if queued:
        print(f"\nQUEUED FOR OFFER ({len(queued)}):")
        for r in queued:
            print(f"  {r.summary()}")

    if rejected:
        print(f"\nREJECTED ({len(rejected)}):")
        for r in rejected:
            print(f"  {r.summary()}")

    print(f"{'═' * 60}\n")
