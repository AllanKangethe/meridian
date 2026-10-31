import os
import time

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.worker import run_once


COOLDOWN_SECONDS = 60
_last_ingest = 0.0

DATABASE_URL = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Meridian")


@app.get("/health")
def health(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


@app.post("/ingest", status_code=202)
def trigger_ingest():
    global _last_ingest
    now = time.monotonic()
    if now - _last_ingest < COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="Ingest ran recently, try again shortly")
    _last_ingest = now
    try:
        run_once()
    except Exception:
        raise HTTPException(status_code=502, detail="Could not fetch from USGS")
    return {"status": "ingested"}

@app.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=500),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(500, gt=0, le=5000),):
    sql = text("""
        SELECT title, magnitude, occurred_at,
               ST_Y(location::geometry) AS lat,
               ST_X(location::geometry) AS lon
        FROM events
        WHERE CAST(:lat AS float) IS NULL
                   OR ST_DWithin(
                        location,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                        :radius_km * 1000
                      )
        ORDER BY occurred_at DESC
        LIMIT :limit
    """)

    params = {"limit": limit, "lat": lat, "lon": lon, "radius_km": radius_km}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]






app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
