from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="amara-remote")


class EventIn(BaseModel):
    event_name: str
    payload: dict = {}


class ScrapeIn(BaseModel):
    url: str = ""
    task: str = ""


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "remote",
        "note": "stub — browser automation not yet implemented",
    }


@app.post("/events")
async def post_event(event: EventIn):
    return {"received": True, "event_name": event.event_name, "queued": True}


@app.post("/scrape")
async def scrape(body: ScrapeIn):
    return {
        "status": "not_implemented",
        "message": "Browser automation worker is a stub. Connect Playwright or Selenium here.",
    }
