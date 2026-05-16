"""Mirofish Scenario Neuron — scores exit strategies conservatively for each property."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import REPORTS_DIR
from ..events import make_event
from ..event_store import append_event

# Exit strategy keys
EXIT_STRATEGIES = [
    "pre_auction_owner_rescue",
    "assignment",
    "double_close",
    "buyer_funded_payoff",
    "jv_with_buyer",
    "auction_only",
    "skip",
]

# Conservative base scores (1-10).
# No score above 6 for strategies requiring verified payoff/title.
# Since payoff/title/buyer demand are all unverified, all strategies requiring them are capped at 4.
REQUIRES_VERIFIED_PAYOFF_TITLE = {
    "pre_auction_owner_rescue",
    "assignment",
    "double_close",
    "buyer_funded_payoff",
    "jv_with_buyer",
}

MAX_UNVERIFIED_SCORE = 4  # Hard cap when payoff/title unverified

# Property-specific score overrides (rationale-based, still capped)
PROPERTY_SCORE_HINTS = {
    "1307 prairie": {
        "pre_auction_owner_rescue": 3,
        "assignment": 4,
        "double_close": 3,
        "buyer_funded_payoff": 3,
        "jv_with_buyer": 4,
        "auction_only": 2,
        "skip": 1,
        "rationale": (
            "Downtown commercial. High upside but entity/control (Bendanmar) unverified. "
            "Payoff/title unverified. Score capped at 4 across all active strategies."
        ),
    },
    "415 caroline": {
        "pre_auction_owner_rescue": 3,
        "assignment": 4,
        "double_close": 3,
        "buyer_funded_payoff": 3,
        "jv_with_buyer": 4,
        "auction_only": 2,
        "skip": 1,
        "rationale": (
            "Part of Bendanmar portfolio — same constraints as 1307 Prairie. "
            "Score capped at 4."
        ),
    },
    "800 tidwell": {
        "pre_auction_owner_rescue": 3,
        "assignment": 3,
        "double_close": 2,
        "buyer_funded_payoff": 3,
        "jv_with_buyer": 3,
        "auction_only": 3,
        "skip": 3,
        "rationale": (
            "Environmental risk (auto use) unverified — significantly reduces all active "
            "strategies. Owner unverified. Payoff/title unverified. "
            "Skip score elevated due to environmental uncertainty."
        ),
    },
    "813 w 30": {
        "pre_auction_owner_rescue": 4,
        "assignment": 4,
        "double_close": 3,
        "buyer_funded_payoff": 3,
        "jv_with_buyer": 3,
        "auction_only": 2,
        "skip": 1,
        "rationale": (
            "77018 infill — good location signal but owner (Jason Castaneda) unverified. "
            "Payoff/title unverified. Score capped at 4."
        ),
    },
    "1516 w 34": {
        "pre_auction_owner_rescue": 3,
        "assignment": 3,
        "double_close": 2,
        "buyer_funded_payoff": 2,
        "jv_with_buyer": 3,
        "auction_only": 2,
        "skip": 2,
        "rationale": (
            "Valuation conflict — do not use AVM as final ARV. "
            "Owner unverified. Payoff/title unverified. Lower scores reflect valuation uncertainty."
        ),
    },
}


def _score_property(prop: Dict, deal_type: str) -> Dict:
    """Score exit strategies for a single property conservatively."""
    address = (prop.get("address") or prop.get("name") or "").lower()

    # Find matching hint
    hints = None
    for frag, hint_data in PROPERTY_SCORE_HINTS.items():
        if frag in address:
            hints = hint_data
            break

    scores = {}
    for strategy in EXIT_STRATEGIES:
        if hints and strategy in hints:
            raw = hints[strategy]
        else:
            # Default conservative scores
            raw = 3 if strategy != "skip" else 2

        # Enforce hard cap
        if strategy in REQUIRES_VERIFIED_PAYOFF_TITLE:
            score = min(raw, MAX_UNVERIFIED_SCORE)
        else:
            score = raw

        scores[strategy] = score

    return {
        "address": prop.get("address", "SOURCE_NEEDED"),
        "name": prop.get("name", "SOURCE_NEEDED"),
        "deal_type": deal_type,
        "scores": scores,
        "rationale": hints.get("rationale") if hints else (
            "No property-specific rationale. Default conservative scores applied. "
            "All active strategies capped at 4 (payoff/title/buyer unverified)."
        ),
        "score_cap_reason": (
            f"All strategies requiring verified payoff/title capped at {MAX_UNVERIFIED_SCORE} "
            "because payoff, title, and buyer demand are all SOURCE_NEEDED."
        ),
    }


class MirofishScenarioNeuron:
    """
    Scores exit strategies for each property conservatively.
    No score above 6 for any strategy requiring verified payoff/title.
    """

    def run(self, strike_board: List[Dict], classifications: Dict) -> Dict:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / "mirofish_scenarios.md"

        scenarios = {}
        scenario_list = []

        for prop in strike_board:
            key = prop.get("address") or prop.get("name") or f"rank_{prop.get('rank', '?')}"
            classified = classifications.get(key, {})
            deal_type = classified.get("deal_type", "UNCLASSIFIED")

            scenario = _score_property(prop, deal_type)
            scenarios[key] = scenario
            scenario_list.append(scenario)

        # Write report
        lines = [
            "# Mirofish Scenario Scoring",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Score Interpretation",
            "- Scale: 1 (do not pursue) to 10 (highest priority)",
            "- All scores are CONSERVATIVE — no score above 6 for strategies requiring verified payoff/title",
            f"- Hard cap: {MAX_UNVERIFIED_SCORE} for all strategies requiring payoff/title (currently all unverified)",
            "",
            "## Why Scores Are Low",
            "- Payoff amounts: UNVERIFIED (SOURCE_NEEDED)",
            "- Title status: UNVERIFIED (SOURCE_NEEDED)",
            "- Buyer demand: NOT_CONFIRMED_BUYER (SOURCE_NEEDED)",
            "- Owner contact authority: USER_PROVIDED_UNVERIFIED",
            "- Environmental risk (800 Tidwell): UNVERIFIED",
            "",
            "## Scores by Property",
        ]

        for s in scenario_list:
            lines += [
                "",
                f"### {s['name']}",
                f"**Address:** {s['address']}",
                f"**Deal Type:** {s['deal_type']}",
                "",
                "**Exit Strategy Scores:**",
            ]
            for strategy, score in s["scores"].items():
                lines.append(f"- {strategy}: {score}/10")

            lines += [
                "",
                f"**Rationale:** {s['rationale']}",
                f"**Score Cap Reason:** {s['score_cap_reason']}",
            ]

        lines += [
            "",
            "---",
            "All scenarios remain speculative until payoff/title/buyer demand verified.",
            "Do not use these scores to make offers or commitments.",
        ]

        report_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="DEALS_CLASSIFIED",
            source="MirofishScenarioNeuron",
            payload={
                "property_count": len(scenario_list),
                "report_file": str(report_path),
                "score_cap": MAX_UNVERIFIED_SCORE,
            },
            source_file=str(report_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="Conservative scenario scores generated. All capped due to unverified data.",
        )
        append_event(ev)

        return {
            "neuron": "MirofishScenarioNeuron",
            "status": "COMPLETED",
            "scenarios": scenarios,
            "report_file": str(report_path),
            "property_count": len(scenario_list),
        }
