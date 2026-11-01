import json
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import URL, create_engine, text
import logging
import time


from pydantic import ValidationError
from app.models import QuakeEvent

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
HEADERS = {"User-Agent": "Meridian/0.1 (github.com/AllanKangethe)"}

POLL_SECONDS = 300

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker")


engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
    )
)

UPSERT = text("""
    INSERT INTO events (source, source_event_id, event_type, magnitude, title,
                        occurred_at, location, raw)
    VALUES ('usgs', :id, :type, :mag, :title, :occurred_at,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            CAST(:raw AS jsonb))
    ON CONFLICT (source, source_event_id) DO UPDATE SET
        magnitude   = EXCLUDED.magnitude,
        title       = EXCLUDED.title,
        occurred_at = EXCLUDED.occurred_at,
        location    = EXCLUDED.location,
        raw         = EXCLUDED.raw
""")


def fetch_feed() -> dict:
    response = httpx.get(FEED_URL, headers=HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.json()

def run_once() -> None:
    features = fetch_feed()["features"]
    store(features)
    log.info("Stored %d events", len(features))


def store(features: list[dict]) -> None:
    skipped = 0
    with engine.begin() as conn:
        for f in features:
            try:
                q = QuakeEvent.from_feature(f)
            except ValidationError as err:
                log.warning("Skipping bad record %s: %s", f.get("id"), err)
                skipped += 1
                continue
            conn.execute(UPSERT, {
                "id": q.id,
                "type": q.type,
                "mag": q.mag,
                "title": q.title,
                "occurred_at": q.time,
                "lon": q.lon,
                "lat": q.lat,
                "raw": json.dumps(f),
            })
    if skipped:
        log.warning("Skipped %d bad records", skipped)



if __name__ == "__main__":
    while True:
        try:
            run_once()
        except Exception:
            log.exception("Ingest run failed; will retry next cycle")
        time.sleep(POLL_SECONDS)

