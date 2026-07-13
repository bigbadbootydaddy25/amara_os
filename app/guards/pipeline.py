"""Buyer-first doctrine guard for the deal pipeline.

Hard rule: a deal can never transition into `offer` without a confirmed
buyer price on file. Mirrored at the data layer by the `deals_buyer_first`
trigger in migrations/001_workspaces.sql -- this is the application-level
copy of that same rule, enforced before a write is even attempted.
"""

from __future__ import annotations

DEAL_STATES = ("lead", "under_contract", "buyer_matching", "offer", "closed", "dead")


class BuyerFirstViolation(ValueError):
    pass


def transition_deal_state(
    next_state: str,
    *,
    confirmed_buyer_price: float | None,
) -> str:
    if next_state not in DEAL_STATES:
        raise ValueError(f"unknown deal state: {next_state!r}")
    if next_state == "offer" and confirmed_buyer_price is None:
        raise BuyerFirstViolation(
            "cannot transition to 'offer' without a confirmed_buyer_price"
        )
    return next_state
