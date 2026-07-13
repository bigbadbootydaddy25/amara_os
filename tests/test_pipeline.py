import pytest

from app.guards.pipeline import BuyerFirstViolation, transition_deal_state


def test_buyer_first_blocks_offer_without_confirmed_price():
    with pytest.raises(BuyerFirstViolation):
        transition_deal_state("offer", confirmed_buyer_price=None)


def test_buyer_first_allows_offer_with_confirmed_price():
    assert transition_deal_state("offer", confirmed_buyer_price=125_000.0) == "offer"


def test_buyer_first_does_not_block_earlier_states():
    assert transition_deal_state("under_contract", confirmed_buyer_price=None) == "under_contract"
    assert transition_deal_state("buyer_matching", confirmed_buyer_price=None) == "buyer_matching"


def test_unknown_state_rejected():
    with pytest.raises(ValueError):
        transition_deal_state("won", confirmed_buyer_price=100_000.0)
