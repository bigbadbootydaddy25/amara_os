"""
AMARA OS — Entitlement Intelligence Engine

Analyzes the entitlement position of land deals:
- Zoning (current vs. target, change required)
- Density (units per acre, bonus eligibility)
- Plat status (raw / preliminary / final / recorded)
- Infrastructure (water, sewer, road, utilities)
- Permit pipeline status

Outputs:
- entitlement_score:       0.0–1.0 (how far along the entitlement path)
- builder_readiness_score: 0.0–1.0 (ready for builder engagement)
- risk_level:              low / medium / high / critical
- time_to_build_months:    estimated months until shovel-ready

Land deals must pass entitlement analysis before offer approval.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from system.vault import write_vault_file, read_vault_file, list_vault, next_id
from system.config import VAULT_LAND


# ─── Entitlement Inputs ───────────────────────────────────────────────────────

@dataclass
class ZoningProfile:
    current_zoning:      str    # e.g. "AG", "R1", "R2", "MF-2"
    target_zoning:       str    # what the deal needs to pencil
    change_needed:       bool   = False
    change_type:         str    = ""   # rezone / variance / SUP / PUD / by-right
    change_probability:  float  = 0.5  # 0.0–1.0 estimate of approval likelihood
    notes:               str    = ""


@dataclass
class DensityProfile:
    max_density_per_acre:    float    # allowed units/acre under current/target zoning
    target_units:            int      # number of units the deal is underwritten for
    gross_acres:             float
    net_developable_acres:   float
    density_bonus_eligible:  bool  = False   # affordable housing bonus etc.
    actual_achievable_units: int   = 0       # computed: net_acres × density


@dataclass
class PlatStatus:
    phase:               str    # raw / preliminary / final / recorded
    recorded:            bool   = False
    plat_date:           date | None = None
    subdivision_name:    str    = ""
    ghost_streets:       bool   = False    # platted streets that were never built
    dead_paper:          bool   = False    # platted lots on dead subdivision


@dataclass
class InfrastructureProfile:
    water_available:         bool  = False
    sewer_available:         bool  = False
    road_access:             bool  = False
    utilities_distance_ft:   int   = 0     # 0 = on-site

    def score(self) -> float:
        """0.0–1.0 based on infrastructure availability."""
        points = 0.0
        if self.water_available:   points += 0.30
        if self.sewer_available:   points += 0.30
        if self.road_access:       points += 0.25
        if self.utilities_distance_ft == 0 or self.utilities_distance_ft <= 500:
            points += 0.15
        elif self.utilities_distance_ft <= 1500:
            points += 0.08
        return round(min(points, 1.0), 3)


@dataclass
class PermitPipeline:
    pre_app_submitted:               bool      = False
    pre_app_date:                    date | None = None
    preliminary_plat_submitted:      bool      = False
    preliminary_plat_date:           date | None = None
    final_plat_submitted:            bool      = False
    final_plat_date:                 date | None = None
    permits_issued:                  bool      = False

    def stage(self) -> str:
        """Return the current permit pipeline stage name."""
        if self.permits_issued:
            return "permits_issued"
        if self.final_plat_submitted:
            return "final_plat"
        if self.preliminary_plat_submitted:
            return "preliminary_plat"
        if self.pre_app_submitted:
            return "pre_app"
        return "not_started"

    def progress_score(self) -> float:
        """0.0–1.0 representing how far along the permit process."""
        if self.permits_issued:             return 1.0
        if self.final_plat_submitted:       return 0.75
        if self.preliminary_plat_submitted: return 0.50
        if self.pre_app_submitted:          return 0.25
        return 0.0


# ─── Entitlement Analysis Inputs ─────────────────────────────────────────────

@dataclass
class EntitlementInputs:
    deal_id:        str
    address:        str
    zip_code:       str
    county:         str = ""

    zoning:         ZoningProfile       | None = None
    density:        DensityProfile      | None = None
    plat:           PlatStatus          | None = None
    infrastructure: InfrastructureProfile | None = None
    permits:        PermitPipeline      | None = None


# ─── Entitlement Result ───────────────────────────────────────────────────────

@dataclass
class EntitlementResult:
    deal_id:                str
    address:                str
    zip_code:               str

    entitlement_score:      float    # 0.0–1.0
    builder_readiness_score:float    # 0.0–1.0
    risk_level:             str      # low / medium / high / critical
    time_to_build_months:   int      # estimated months to shovel-ready

    # Component scores
    zoning_score:           float = 0.0
    density_score:          float = 0.0
    plat_score:             float = 0.0
    infra_score:            float = 0.0
    permit_score:           float = 0.0

    # Flags
    zoning_change_required: bool  = False
    dead_paper:             bool  = False
    infrastructure_gap:     bool  = False
    permit_blocker:         bool  = False

    # Notes
    risk_factors:           list[str] = field(default_factory=list)
    opportunities:          list[str] = field(default_factory=list)
    recommended_actions:    list[str] = field(default_factory=list)

    entitlement_id:         str = field(default_factory=lambda: f"ENT-{uuid.uuid4().hex[:6].upper()}")
    analyzed_at:            str = field(default_factory=lambda: date.today().isoformat())

    def grade(self) -> str:
        if self.entitlement_score >= 0.75: return "A"
        if self.entitlement_score >= 0.55: return "B"
        if self.entitlement_score >= 0.35: return "C"
        return "D"

    def is_builder_ready(self) -> bool:
        return self.builder_readiness_score >= 0.60

    def summary(self) -> str:
        lines = [
            f"[{self.risk_level.upper()}] {self.entitlement_id} — {self.address}",
            f"  Entitlement: {self.entitlement_score:.2f} [{self.grade()}] | "
            f"Builder Ready: {self.builder_readiness_score:.2f} | "
            f"Time to Build: ~{self.time_to_build_months}mo",
            f"  Zoning: {self.zoning_score:.2f} | Infra: {self.infra_score:.2f} | "
            f"Permits: {self.permit_score:.2f} | Plat: {self.plat_score:.2f}",
        ]
        if self.risk_factors:
            lines.append(f"  Risks: {'; '.join(self.risk_factors[:3])}")
        if self.recommended_actions:
            lines.append(f"  Actions: {'; '.join(self.recommended_actions[:3])}")
        return "\n".join(lines)


# ─── Scoring Functions ────────────────────────────────────────────────────────

def _score_zoning(z: ZoningProfile | None) -> tuple[float, bool, list[str], list[str]]:
    """Returns (score, change_required, risks, opportunities)."""
    if z is None:
        return 0.50, False, ["Zoning not verified"], []

    risks        = []
    opportunities = []

    if not z.change_needed:
        score = 0.90
        opportunities.append("By-right development — no rezoning risk")
    else:
        base  = z.change_probability
        if z.change_type in ("rezone", "PUD"):
            risks.append(f"Full rezoning required ({z.change_type}) — political risk")
            score = base * 0.60
        elif z.change_type in ("variance", "SUP"):
            risks.append(f"{z.change_type} required — discretionary approval")
            score = base * 0.75
        else:
            score = base * 0.70

    return round(score, 3), z.change_needed, risks, opportunities


def _score_density(d: DensityProfile | None) -> tuple[float, list[str], list[str]]:
    if d is None:
        return 0.50, ["Density not verified"], []

    risks = []
    opps  = []

    achievable = d.net_developable_acres * d.max_density_per_acre
    d.actual_achievable_units = int(achievable)

    if achievable >= d.target_units:
        ratio = achievable / max(d.target_units, 1)
        score = min(0.60 + (ratio - 1.0) * 0.20, 1.0)  # bonus for surplus density
        if d.density_bonus_eligible:
            opps.append(f"Density bonus eligible — potential +{int(achievable * 0.15)} units")
    else:
        shortfall = d.target_units - achievable
        score     = max(0.20, achievable / max(d.target_units, 1) * 0.70)
        risks.append(f"Density shortfall: {int(shortfall)} units below target")

    return round(score, 3), risks, opps


def _score_plat(p: PlatStatus | None) -> tuple[float, bool, list[str], list[str]]:
    if p is None:
        return 0.40, False, ["Plat status unknown"], []

    risks = []
    opps  = []

    phase_scores = {
        "recorded":    1.0,
        "final":       0.85,
        "preliminary": 0.55,
        "raw":         0.25,
    }
    score = phase_scores.get(p.phase, 0.30)

    if p.dead_paper:
        opps.append("Dead paper — platted lots already recorded, minimal entitlement work")
        score = max(score, 0.70)   # dead paper = already entitled in some form
    if p.ghost_streets:
        risks.append("Ghost streets present — may require vacating or replating")
        score *= 0.85

    return round(score, 3), p.dead_paper, risks, opps


def _score_infrastructure(infra: InfrastructureProfile | None) -> tuple[float, bool, list[str], list[str]]:
    if infra is None:
        return 0.40, True, ["Infrastructure status unknown"], []

    score = infra.score()
    risks = []
    opps  = []
    gap   = False

    if not infra.water_available:
        risks.append("No water service — extension required")
        gap = True
    if not infra.sewer_available:
        risks.append("No sewer service — may require package plant or lift station")
        gap = True
    if not infra.road_access:
        risks.append("No road access — access easement or new road required")
        gap = True
    if infra.utilities_distance_ft > 2000:
        risks.append(f"Utilities are {infra.utilities_distance_ft:,} ft away — extension cost is significant")
        gap = True

    if score >= 0.85:
        opps.append("Infrastructure in place — builder-ready site")

    return score, gap, risks, opps


def _score_permits(p: PermitPipeline | None) -> tuple[float, bool, list[str]]:
    if p is None:
        return 0.10, False, ["No permit history — pre-application stage"]

    score   = p.progress_score()
    blocker = False
    risks   = []

    if p.permits_issued:
        risks  = []
        blocker = False
    elif not p.pre_app_submitted:
        risks.append("No pre-application submitted — no city relationship established")

    return score, blocker, risks


# ─── Time-to-Build Estimate ───────────────────────────────────────────────────

def _estimate_time_to_build(
    zoning_change: bool,
    infra_gap:     bool,
    permit_stage:  str,
    density_ok:    bool,
) -> int:
    """
    Estimate months from now to shovel-ready (conservative).
    """
    base_months = 6   # minimum even for shovel-ready sites

    if permit_stage == "permits_issued":
        return max(base_months, 2)
    if permit_stage == "final_plat":
        base_months = 6
    elif permit_stage == "preliminary_plat":
        base_months = 10
    elif permit_stage == "pre_app":
        base_months = 15
    else:
        base_months = 18

    if zoning_change:
        base_months += 12    # rezoning can take 12–18 months
    if infra_gap:
        base_months += 8     # utility extensions take time
    if not density_ok:
        base_months += 4     # variance / density waiver process

    return base_months


# ─── Risk Level ───────────────────────────────────────────────────────────────

def _compute_risk_level(entitlement_score: float, risk_factors: list[str]) -> str:
    critical_keywords = {"rezoning", "no water", "no sewer", "no road"}
    has_critical = any(
        any(kw in r.lower() for kw in critical_keywords)
        for r in risk_factors
    )

    if has_critical or entitlement_score < 0.25:
        return "critical"
    if entitlement_score < 0.40:
        return "high"
    if entitlement_score < 0.65:
        return "medium"
    return "low"


# ─── Main Analysis Function ───────────────────────────────────────────────────

def analyze_entitlement(inputs: EntitlementInputs) -> EntitlementResult:
    """
    Full entitlement analysis for a land deal.
    Scores zoning, density, plat, infrastructure, and permits.
    Returns EntitlementResult with composite scores and recommended actions.
    """
    all_risks  = []
    all_opps   = []
    actions    = []

    # Component scores
    z_score, z_change, z_risks, z_opps = _score_zoning(inputs.zoning)
    d_score, d_risks, d_opps           = _score_density(inputs.density)
    p_score, dead_paper, p_risks, p_opps = _score_plat(inputs.plat)
    i_score, infra_gap, i_risks, i_opps  = _score_infrastructure(inputs.infrastructure)
    pm_score, pm_blocker, pm_risks       = _score_permits(inputs.permits)

    all_risks  = z_risks + d_risks + p_risks + i_risks + pm_risks
    all_opps   = z_opps + d_opps + p_opps + i_opps

    # Weighted entitlement score
    # Zoning 30%, Infrastructure 25%, Plat 20%, Permits 15%, Density 10%
    entitlement_score = (
        z_score  * 0.30
        + i_score  * 0.25
        + p_score  * 0.20
        + pm_score * 0.15
        + d_score  * 0.10
    )

    # Builder readiness score: infrastructure + permits dominate
    builder_ready = (
        i_score  * 0.40
        + pm_score * 0.30
        + p_score  * 0.20
        + z_score  * 0.10
    )

    # Time to build
    density_ok  = (inputs.density is not None and
                   inputs.density.actual_achievable_units >= inputs.density.target_units)
    permit_stage = inputs.permits.stage() if inputs.permits else "not_started"

    time_to_build = _estimate_time_to_build(z_change, infra_gap, permit_stage, density_ok)

    # Risk level
    risk_level = _compute_risk_level(entitlement_score, all_risks)

    # Recommended actions
    if z_change:
        actions.append(f"File {inputs.zoning.change_type or 'zoning'} application with {inputs.county or 'county'}")
    if infra_gap:
        actions.append("Commission utility extension cost estimate before closing")
    if not inputs.permits or inputs.permits.stage() == "not_started":
        actions.append("Schedule pre-application meeting with planning department")
    if dead_paper:
        actions.append("Verify plat recording date and confirm utility availability at platted lots")
    if inputs.density and inputs.density.density_bonus_eligible:
        actions.append("Explore density bonus program to increase unit count")

    result = EntitlementResult(
        deal_id                  = inputs.deal_id,
        address                  = inputs.address,
        zip_code                 = inputs.zip_code,
        entitlement_score        = round(entitlement_score, 3),
        builder_readiness_score  = round(builder_ready, 3),
        risk_level               = risk_level,
        time_to_build_months     = time_to_build,
        zoning_score             = round(z_score, 3),
        density_score            = round(d_score, 3),
        plat_score               = round(p_score, 3),
        infra_score              = round(i_score, 3),
        permit_score             = round(pm_score, 3),
        zoning_change_required   = z_change,
        dead_paper               = dead_paper,
        infrastructure_gap       = infra_gap,
        permit_blocker           = pm_blocker,
        risk_factors             = all_risks,
        opportunities            = all_opps,
        recommended_actions      = actions,
    )

    return result


# ─── Vault Integration ────────────────────────────────────────────────────────

def write_entitlement_to_vault(
    result: EntitlementResult,
    land_vault_id: str = "",
) -> str:
    """
    Write an entitlement analysis record to the vault.
    Appends to the existing land deal file if land_vault_id is provided.
    Returns the filename written.
    """
    today    = date.today().isoformat()
    slug     = "".join(c if c.isalnum() else "_" for c in result.address)[:30]
    filename = f"{result.entitlement_id}_{slug}.md"

    risk_factors_text  = "\n".join(f"- {r}" for r in result.risk_factors) or "None identified"
    opportunities_text = "\n".join(f"- {o}" for o in result.opportunities) or "None identified"
    actions_text       = "\n".join(f"- {a}" for a in result.recommended_actions) or "None"

    content = f"""# Entitlement Analysis — {result.address}

## Scores
| Component | Score |
|-----------|-------|
| Overall Entitlement | {result.entitlement_score:.2f} [{result.grade()}] |
| Builder Readiness | {result.builder_readiness_score:.2f} |
| Zoning | {result.zoning_score:.2f} |
| Infrastructure | {result.infra_score:.2f} |
| Plat Status | {result.plat_score:.2f} |
| Permits | {result.permit_score:.2f} |
| Density | {result.density_score:.2f} |

## Risk Assessment
- **Risk Level:** {result.risk_level.upper()}
- **Time to Build:** ~{result.time_to_build_months} months
- **Zoning Change Required:** {'YES' if result.zoning_change_required else 'No'}
- **Infrastructure Gap:** {'YES' if result.infrastructure_gap else 'No'}
- **Dead Paper:** {'Yes' if result.dead_paper else 'No'}

## Risk Factors
{risk_factors_text}

## Opportunities
{opportunities_text}

## Recommended Actions
{actions_text}

---

- **Entitlement ID:** {result.entitlement_id}
- **Deal:** {result.deal_id} {('| Vault: ' + land_vault_id) if land_vault_id else ''}
- **Analyzed:** {today}
"""

    write_vault_file("land", filename, content)

    # If we have a land vault file, append a summary to it
    if land_vault_id:
        _append_entitlement_to_land_file(land_vault_id, result)

    return filename


def _append_entitlement_to_land_file(land_vault_id: str, result: EntitlementResult) -> None:
    """Append entitlement summary to an existing land vault file."""
    land_files = list_vault("land")
    for path in land_files:
        if land_vault_id in path.name:
            content = path.read_text(encoding="utf-8")
            appendix = (
                f"\n\n## Entitlement Analysis\n"
                f"- **Score:** {result.entitlement_score:.2f} [{result.grade()}]\n"
                f"- **Builder Ready:** {result.builder_readiness_score:.2f}\n"
                f"- **Risk:** {result.risk_level.upper()}\n"
                f"- **Time to Build:** ~{result.time_to_build_months}mo\n"
                f"- **Entitlement ID:** {result.entitlement_id}\n"
            )
            if result.risk_factors:
                appendix += f"- **Key Risk:** {result.risk_factors[0]}\n"
            path.write_text(content + appendix, encoding="utf-8")
            break


# ─── Quick Entitlement Screen ─────────────────────────────────────────────────

def quick_entitlement_screen(
    deal_id:      str,
    address:      str,
    zip_code:     str,
    zoning:       str = "",
    has_water:    bool = False,
    has_sewer:    bool = False,
    has_road:     bool = False,
    plat_phase:   str = "raw",
    dead_paper:   bool = False,
    permits_stage:str = "not_started",
) -> EntitlementResult:
    """
    Fast entitlement screen from basic known facts.
    Used when full entitlement package is not available.
    """
    infra = InfrastructureProfile(
        water_available  = has_water,
        sewer_available  = has_sewer,
        road_access      = has_road,
    )
    plat = PlatStatus(
        phase       = plat_phase,
        dead_paper  = dead_paper,
        recorded    = (plat_phase == "recorded"),
    )

    stage_map = {
        "not_started":       PermitPipeline(),
        "pre_app":           PermitPipeline(pre_app_submitted=True, pre_app_date=date.today()),
        "preliminary_plat":  PermitPipeline(pre_app_submitted=True, preliminary_plat_submitted=True),
        "final_plat":        PermitPipeline(pre_app_submitted=True, preliminary_plat_submitted=True, final_plat_submitted=True),
        "permits_issued":    PermitPipeline(pre_app_submitted=True, preliminary_plat_submitted=True, final_plat_submitted=True, permits_issued=True),
    }
    permits = stage_map.get(permits_stage, PermitPipeline())

    zone_profile = None
    if zoning:
        zone_profile = ZoningProfile(current_zoning=zoning, target_zoning=zoning, change_needed=False)

    inputs = EntitlementInputs(
        deal_id        = deal_id,
        address        = address,
        zip_code       = zip_code,
        zoning         = zone_profile,
        plat           = plat,
        infrastructure = infra,
        permits        = permits,
    )
    return analyze_entitlement(inputs)
