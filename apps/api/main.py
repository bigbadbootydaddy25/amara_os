import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="amara-api")

DISPATCH_URL = os.getenv("DISPATCH_URL", "http://dispatch:8081")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api"}


@app.post("/leads")
async def post_lead(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DISPATCH_URL}/route/lead", json=payload, timeout=30)
    return resp.json()


@app.post("/events")
async def post_event(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DISPATCH_URL}/route/event", json=payload, timeout=30)
    return resp.json()


@app.post("/offers/approve")
async def approve_offer(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DISPATCH_URL}/route/offer-approve", json=payload, timeout=30)
    return resp.json()


@app.get("/queue")
async def get_queue():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DISPATCH_URL}/queue", timeout=30)
    return resp.json()
