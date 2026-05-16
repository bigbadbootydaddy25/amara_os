# Standalone FastAPI on port 8088. Not integrated into Next.js app/main — Next.js uses TypeScript routes only.
"""AMARA-AEGIS Neuron Network — Standalone FastAPI backend on port 8088."""
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from .config import DAILY_MONEY_BRIEFS_DIR, PORT
from .neuron_router import NeuronRouter

app = FastAPI(
    title="AMARA-AEGIS Neuron Network API",
    description=(
        "Standalone FastAPI backend on port 8088. "
        "Not integrated into Next.js app/main — Next.js uses TypeScript routes only."
    ),
    version="1.0.0",
)

router = NeuronRouter()


@app.get("/aegis-neurons/status")
def get_status() -> Dict[str, Any]:
    """Return current AEGIS Neuron Network status and event counts."""
    return router.get_status()


@app.post("/aegis-neurons/run-houston-tax-sale")
def run_houston_tax_sale() -> Dict[str, Any]:
    """Run the full Houston tax sale pipeline."""
    results = router.run_houston_tax_sale()
    return {
        "status": "COMPLETED",
        "strike_board_count": results.get("strike_board_count", 0),
        "files_created": len(results.get("files_created", [])),
        "failure_count": len(results.get("failures", [])),
        "run_timestamp": results.get("run_timestamp"),
    }


@app.post("/aegis-neurons/run-buyer-demand")
def run_buyer_demand() -> Dict[str, Any]:
    """Run the buyer demand pipeline."""
    results = router.run_buyer_demand()
    hermes_result = results.get("HermesBuyerDemandAgent", {})
    return {
        "status": "COMPLETED",
        "buyer_target_count": hermes_result.get("buyer_target_count", 0) if isinstance(hermes_result, dict) else 0,
        "failure_count": len(results.get("failures", [])),
    }


@app.post("/aegis-neurons/run-all")
def run_all() -> Dict[str, Any]:
    """Run all AEGIS Neuron Network pipelines."""
    results = router.run_all()
    summary = results.get("summary", {})
    return {
        "status": "COMPLETED",
        "summary": summary,
        "no_fake_data": "VERIFIED",
        "note": f"Standalone FastAPI on port {PORT}. Not integrated with Next.js routes.",
    }


@app.get("/aegis-neurons/latest-money-brief", response_class=PlainTextResponse)
def get_latest_money_brief() -> str:
    """Return the latest AMARA-AEGIS Daily Money Brief as plain text."""
    brief_path = DAILY_MONEY_BRIEFS_DIR / "latest_money_brief.md"
    if brief_path.exists():
        return brief_path.read_text(encoding="utf-8")
    return (
        "# No Money Brief Found\n\n"
        "Run the pipeline first:\n"
        "  python -m backend.aegis_neuron_network.cli run-all\n\n"
        "Or POST to /aegis-neurons/run-all\n"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
