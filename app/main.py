import os
from datetime import datetime 

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.worker import run_once_usgs
from app.models import WatchZoneCreate




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



@app.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    type: str | None = Query(None, max_length=50),
    min_mag: float | None = Query(None, ge=-2, le=10, description="Earthquake magnitude (USGS events only)"),
    since: datetime | None = None,
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(500, gt=0, le=5000),
):
    sql = text("""
        SELECT id, event_type, title, magnitude, magnitude_unit, occurred_at,
               ST_Y(location::geometry) AS lat,
               ST_X(location::geometry) AS lon
        FROM events
        WHERE (CAST(:type AS text) IS NULL OR event_type = :type)
          AND (CAST(:min_mag AS float) IS NULL OR source <> 'usgs' OR magnitude >= :min_mag)
          AND (CAST(:since AS timestamptz) IS NULL OR occurred_at >= :since)
          AND (CAST(:lat AS float) IS NULL OR ST_DWithin(
                location,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_km * 1000))
        ORDER BY occurred_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """)

    params = {
        "limit": limit, "offset": offset, "type": type, "min_mag": min_mag,
        "since": since, "lat": lat, "lon": lon, "radius_km": radius_km,
    }
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


@app.post("/watch-zones", status_code=201)
def create_watch_zone(zone: WatchZoneCreate):
    sql = text("""
        INSERT INTO watch_zones (name, center, radius_km, min_magnitude, webhook_url)
        VALUES (:name, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_km, :min_magnitude, :webhook_url)
        RETURNING id, created_at
    """)
    params = zone.model_dump()
    params["webhook_url"] = str(zone.webhook_url) if zone.webhook_url else None
    with engine.begin() as conn:
        row = conn.execute(sql, params).mappings().one()
    return {**zone.model_dump(), **row}

@app.get("/watch-zones")
def list_watch_zones(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    sql = text("""
        SELECT id, name, radius_km, min_magnitude, webhook_url, created_at,
               ST_Y(center::geometry) AS lat,
               ST_X(center::geometry) AS lon
        FROM watch_zones
        ORDER BY id
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]

@app.delete("/watch-zones/{zone_id}", status_code=204)
def delete_watch_zone(zone_id: int):
    sql = text("DELETE FROM watch_zones WHERE id = :id RETURNING id")
    with engine.begin() as conn:
        deleted = conn.execute(sql, {"id": zone_id}).first()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Watch zone not found")


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
