import asyncio
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from workers.remote.engine import RunConfig, run_once, run_continuous
from workers.remote.scraper import ScrapeConfig, scrape_zip

logger = logging.getLogger(__name__)
app = FastAPI(title="amara-remote")


class EventIn(BaseModel):
    event_name: str
    payload: dict = {}


class RunRequest(BaseModel):
    regions: list[str] = []
    markets: list[str] = []
    concurrency: int = 4
    dom_min: int = 90
    source: str = "redfin"
    max_pages: int = 3
    write_vault_stubs: bool = True
    output_dir: str = "output"


class ScrapeRequest(BaseModel):
    zip_code: str
    dom_min: int = 90
    price_min: int = 0
    price_max: int = 999_999
    max_pages: int = 3
    source: str = "redfin"


# Background run tracking (in-memory, simple)
_last_summary: dict = {}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "remote"}


@app.post("/events")
async def post_event(event: EventIn):
    logger.info("Event received: %s", event.event_name)
    return {"received": True, "event_name": event.event_name, "queued": True}


@app.post("/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    """
    Trigger a deal generation run across all (or selected) markets.
    Runs in background; check /run/status for results.
    """
    config = RunConfig(
        regions=req.regions,
        markets=req.markets,
        concurrency=req.concurrency,
        dom_min=req.dom_min,
        source=req.source,
        max_pages_per_zip=req.max_pages,
        write_vault_stubs=req.write_vault_stubs,
        output_dir=Path(req.output_dir),
    )

    async def _run():
        global _last_summary
        try:
            summary = await run_once(config)
            import dataclasses
            _last_summary = dataclasses.asdict(summary)
        except Exception as e:
            _last_summary = {"error": str(e)}

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Run triggered in background. Poll /run/status."}


@app.get("/run/status")
async def run_status():
    if not _last_summary:
        return {"status": "no_run_yet"}
    return _last_summary


@app.post("/scrape/zip")
async def scrape_single_zip(req: ScrapeRequest):
    """Scrape a single ZIP and return raw listings."""
    config = ScrapeConfig(
        dom_min=req.dom_min,
        price_min=req.price_min,
        price_max=req.price_max,
        max_pages=req.max_pages,
        source=req.source,
    )
    listings = await scrape_zip(req.zip_code, config)
    return {
        "zip_code": req.zip_code,
        "count": len(listings),
        "listings": [
            {
                "address": l.address,
                "price": l.price,
                "beds": l.beds,
                "baths": l.baths,
                "sqft": l.sqft,
                "dom": l.dom,
                "keywords": l.keywords,
                "url": l.url,
            }
            for l in listings
        ],
    }


@app.get("/deals/latest")
async def latest_deals():
    """Return the most recent deal output file."""
    latest = Path("output/deals_latest.json")
    if not latest.exists():
        return {"status": "no_deals_yet"}
    import json
    return json.loads(latest.read_text())
