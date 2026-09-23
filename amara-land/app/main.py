from fastapi import FastAPI, HTTPException

from .db import ensure_postgis, get_connection

app = FastAPI(title="amara-land")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict:
    """Confirms the Supabase Postgres connection works and PostGIS is enabled."""
    try:
        with get_connection() as conn:
            ensure_postgis(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT ST_AsText(ST_MakePoint(%s, %s))", (-96.8, 33.2))
                row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "postgis_point": row[0] if row else None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
