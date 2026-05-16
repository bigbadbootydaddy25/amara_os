"""Deal Classification Neuron — classifies each strike board property by deal type."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import TAX_SALE_STRIKES_DIR
from ..events import make_event
from ..event_store import append_event

# Classification rules keyed on address fragments (case-insensitive)
CLASSIFICATION_RULES = [
    {
        "match_fragments": ["1307 prairie"],
        "deal_type": "DOWNTOWN_COMMERCIAL_PORTFOLIO_CONTROL",
        "entity": "BENDANMAR LIMITED",
        "risk_flags": [],
        "notes": (
            "Part of Bendanmar Limited downtown commercial portfolio. "
            "Entity control verification required. "
            "Payoff and title: SOURCE_NEEDED."
        ),
    },
    {
        "match_fragments": ["415 caroline"],
        "deal_type": "DOWNTOWN_COMMERCIAL_PORTFOLIO_CONTROL",
        "entity": "BENDANMAR LIMITED",
        "risk_flags": [],
        "notes": (
            "Part of Bendanmar Limited downtown commercial portfolio. "
            "Entity control verification required. "
            "Payoff and title: SOURCE_NEEDED."
        ),
    },
    {
        "match_fragments": ["800 tidwell"],
        "deal_type": "PRE_AUCTION_COMMERCIAL_OWNER_RESCUE",
        "entity": "USER_PROVIDED_UNVERIFIED",
        "risk_flags": ["AUTO_USE_ENVIRONMENTAL_RISK"],
        "notes": (
            "Commercial auto use — environmental risk must be verified before any offer. "
            "Owner: USER_PROVIDED_UNVERIFIED. Payoff and title: SOURCE_NEEDED."
        ),
    },
    {
        "match_fragments": ["813 w 30"],
        "deal_type": "PRE_AUCTION_OWNER_RESCUE_WHOLESALE",
        "sub_type": "77018_INFILL",
        "entity": "USER_PROVIDED_UNVERIFIED",
        "risk_flags": [],
        "notes": (
            "77018 infill opportunity. Owner (Jason Castaneda) not confirmed. "
            "Payoff and title: SOURCE_NEEDED."
        ),
    },
    {
        "match_fragments": ["1516 w 34"],
        "deal_type": "LAND_REDEVELOPMENT_VERIFY",
        "sub_type": "VALUATION_CONFLICT",
        "entity": "USER_PROVIDED_UNVERIFIED",
        "risk_flags": ["VALUATION_CONFLICT"],
        "notes": (
            "Land redevelopment candidate. Valuation conflict — do not use AVM as final ARV. "
            "SOURCE_NEEDED for all data."
        ),
    },
]


def _classify_property(prop: Dict) -> Dict:
    """Apply classification rules to a single property dict."""
    address = (prop.get("address") or prop.get("name") or "").lower()
    for rule in CLASSIFICATION_RULES:
        if any(frag in address for frag in rule["match_fragments"]):
            result = dict(prop)
            result["deal_type"] = rule["deal_type"]
            result["risk_flags"] = rule.get("risk_flags", [])
            result["classification_notes"] = rule["notes"]
            if "sub_type" in rule:
                result["sub_type"] = rule["sub_type"]
            result["payoff_status"] = "UNVERIFIED"
            result["title_status"] = "UNVERIFIED"
            result["owner_status"] = "USER_PROVIDED_UNVERIFIED"
            return result

    # No rule matched — default
    result = dict(prop)
    result["deal_type"] = "UNCLASSIFIED"
    result["risk_flags"] = []
    result["classification_notes"] = "No classification rule matched. SOURCE_NEEDED."
    result["payoff_status"] = "UNVERIFIED"
    result["title_status"] = "UNVERIFIED"
    result["owner_status"] = "SOURCE_NEEDED"
    return result


class DealClassificationNeuron:
    """
    Classifies strike board properties by deal type.
    Writes a classification report to TAX_SALE_STRIKES_DIR.
    """

    def run(self, strike_board: List[Dict]) -> Dict:
        classifications = {}
        classified_list = []

        for prop in strike_board:
            classified = _classify_property(prop)
            key = classified.get("address") or classified.get("name") or f"rank_{classified.get('rank', '?')}"
            classifications[key] = classified
            classified_list.append(classified)

        # Write classification report
        TAX_SALE_STRIKES_DIR.mkdir(parents=True, exist_ok=True)
        report_path = TAX_SALE_STRIKES_DIR / "deal_classification.md"

        lines = [
            "# Deal Classification Report",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Properties Classified: {len(classified_list)}",
            "",
            "## Important Notes",
            "- Payoff amounts: UNVERIFIED — do not call minimum bid 'final payoff'",
            "- Title status: UNVERIFIED — do not call title verified without source",
            "- Owner information: USER_PROVIDED_UNVERIFIED — do not contact without verification",
            "- AVM values not used as final ARV — source override required",
            "",
            "## Classifications",
        ]

        for c in classified_list:
            lines += [
                "",
                f"### Rank {c.get('rank', '?')}: {c.get('name', c.get('address', 'UNKNOWN'))}",
                f"- Address: {c.get('address', 'SOURCE_NEEDED')}",
                f"- Entity: {c.get('entity', 'SOURCE_NEEDED')}",
                f"- Deal Type: {c.get('deal_type', 'UNCLASSIFIED')}",
            ]
            if c.get("sub_type"):
                lines.append(f"- Sub Type: {c['sub_type']}")
            lines += [
                f"- Risk Flags: {', '.join(c.get('risk_flags', [])) or 'None identified'}",
                f"- Payoff Status: {c.get('payoff_status', 'UNVERIFIED')}",
                f"- Title Status: {c.get('title_status', 'UNVERIFIED')}",
                f"- Owner Status: {c.get('owner_status', 'SOURCE_NEEDED')}",
                f"- Notes: {c.get('classification_notes', '')}",
            ]

        report_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="DEALS_CLASSIFIED",
            source="DealClassificationNeuron",
            payload={
                "property_count": len(classified_list),
                "report_file": str(report_path),
                "deal_types": [c.get("deal_type") for c in classified_list],
            },
            source_file=str(report_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="All classifications are unverified pending payoff/title/owner confirmation.",
        )
        append_event(ev)

        return {
            "neuron": "DealClassificationNeuron",
            "status": "COMPLETED",
            "classifications": classifications,
            "classified_list": classified_list,
            "report_file": str(report_path),
            "property_count": len(classified_list),
        }
