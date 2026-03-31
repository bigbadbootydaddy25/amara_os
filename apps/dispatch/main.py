import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI(title="amara-dispatch")

PROPVISION_URL = os.getenv("PROPVISION_URL", "http://propvision:8082")
REMOTE_URL = os.getenv("REMOTE_URL", "http://remote:8083")

LAND_ZIPS: set[str] = set()

PROPERTY_EVENTS = {"new_property", "offer_approved", "deal_closed"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dispatch"}


@app.post("/route/lead")
async def route_lead(request: Request):
    payload = await request.json()
    asset_type = payload.get("asset_type", "unknown")
    zip_code = payload.get("zip_code", "")

    if asset_type == "land" or zip_code in LAND_ZIPS:
        url = f"{PROPVISION_URL}/underwrite/land"
    else:
        url = f"{PROPVISION_URL}/underwrite/sfr"

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=60)
    return resp.json()


@app.post("/route/event")
async def route_event(request: Request):
    payload = await request.json()
    event_name = payload.get("event_name", "")

    if event_name in PROPERTY_EVENTS:
        url = f"{PROPVISION_URL}/events"
    else:
        url = f"{REMOTE_URL}/events"

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=30)
    return resp.json()


@app.post("/route/offer-approve")
async def route_offer_approve(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{PROPVISION_URL}/offers/queue", json=payload, timeout=30)
    return resp.json()


@app.get("/queue")
async def get_queue():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROPVISION_URL}/queue", timeout=30)
    return resp.json()
