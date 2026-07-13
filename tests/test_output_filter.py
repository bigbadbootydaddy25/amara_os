import pytest

from app.guards.output_filter import OutputFilterViolation, run_output_filter


def test_blacklist_guard_rejects_homevestors():
    with pytest.raises(OutputFilterViolation):
        run_output_filter("We referred the lead to HomeVestors.")


def test_blacklist_guard_is_case_insensitive():
    with pytest.raises(OutputFilterViolation):
        run_output_filter("homevestors made an offer.")


def test_formula_guard_rejects_arv_percentage():
    with pytest.raises(OutputFilterViolation):
        run_output_filter("Max offer is 70% of ARV minus repairs.")


@pytest.mark.parametrize("phrase", ["75% of ARV", "70 percent of ARV", "65%ARV"])
def test_formula_guard_rejects_variants(phrase):
    with pytest.raises(OutputFilterViolation):
        run_output_filter(f"The offer uses {phrase} as its basis.")


def test_formula_guard_allows_locked_sfr_formula():
    run_output_filter(
        "Net to Seller = Buyer's Max Offer - Repairs - Assignment Fee.",
    )


def test_ai_name_guard_only_applies_to_client_deliverables():
    # Internal text mentioning FOREMAN is fine.
    run_output_filter("FOREMAN routed this task to Ollama.", client_deliverable=False)

    with pytest.raises(OutputFilterViolation):
        run_output_filter("Drafted by FOREMAN.", client_deliverable=True)


def test_clean_client_deliverable_passes():
    run_output_filter(
        "Net to seller after repairs and assignment fee: $41,500.",
        client_deliverable=True,
    )
