import pytest

from app.guards.output_filter import DEFAULT_AI_NAMES, OutputFilterViolation
from app.identity.branding import DEFAULT_BRANDING_LINE, brand_deliverable


def test_branding_renders_scott_schufford_byline():
    out = brand_deliverable("Net to seller: $41,500 after repairs and assignment fee.")
    assert DEFAULT_BRANDING_LINE in out
    assert out.endswith(DEFAULT_BRANDING_LINE)


def test_branded_deliverable_contains_no_ai_system_names():
    out = brand_deliverable("Net to seller: $41,500 after repairs and assignment fee.")
    lowered = out.lower()
    for name in DEFAULT_AI_NAMES:
        assert name.lower() not in lowered


def test_branding_rejects_text_that_names_an_ai_system():
    with pytest.raises(OutputFilterViolation):
        brand_deliverable("This report was drafted by AMARA for the seller.")
