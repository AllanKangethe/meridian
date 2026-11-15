import json
import os
import httpx
from sqlalchemy import URL, create_engine, text
import logging
import time


from pydantic import ValidationError
from app.models import QuakeEvent, NaturalEvent

FEED_URL_USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
FEED_URL_EONET = "https://eonet.gsfc.nasa.gov/api/v3/events?days=30"

HEADERS = {"User-Agent": "Meridian/0.1 (github.com/AllanKangethe)"}

POLL_SECONDS = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %Z",
)
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

UPSERT_USGS = text("""
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

UPSERT_EONET = text("""
    INSERT INTO events (source, source_event_id, event_type, magnitude, magnitude_unit,
                        title, occurred_at, location, raw)
    VALUES ('eonet', :id, :type, :mag, :mag_unit, :title, :occurred_at,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            CAST(:raw AS jsonb))
    ON CONFLICT (source, source_event_id) DO UPDATE SET
        magnitude      = EXCLUDED.magnitude,
        magnitude_unit = EXCLUDED.magnitude_unit,
        title          = EXCLUDED.title,
        occurred_at    = EXCLUDED.occurred_at,
        location       = EXCLUDED.location,
        raw            = EXCLUDED.raw,
        event_type      = EXCLUDED.event_type
""")



def fetch_feed(feed_url: str) -> dict:
    response = httpx.get(feed_url, headers=HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.json()

def run_once_usgs() -> None:
    features = fetch_feed(FEED_URL_USGS)["features"]
    store_usgs(features)
    log.info("USGS: Stored %d events", len(features))


def store_usgs(features: list[dict]) -> None:
    skipped = 0
    with engine.begin() as conn:
        for f in features:
            try:
                q = QuakeEvent.from_feature(f)
            except ValidationError as err:
                log.warning("Skipping bad record %s: %s", f.get("id"), err)
                skipped += 1
                continue
            conn.execute(UPSERT_USGS, {
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
        log.warning("USGS: skipped %d bad records", skipped)


def run_once_eonet() -> None:
    events = fetch_feed(FEED_URL_EONET)['events']
    store_eonet(events)
    log.info("EONET: Stored %d events", len(events))

def store_eonet(events: list[dict]) -> None:
    skipped = 0
    duplicates = 0

    with engine.begin() as conn:
            for e in events:
                try:
                    n = NaturalEvent.from_event(e)
                except ValidationError as err:
                    log.warning("Skipping bad record %s: %s", e.get("id"), err)
                    skipped += 1
                    continue

                if n.type == "earthquake":
                    log.debug("Skipping EONET earthquake %s (USGS already covers quakes)", n.id)
                    duplicates += 1
                    continue
                    
                conn.execute(UPSERT_EONET, {
                    "id": n.id,
                    "type": n.type,
                    "mag": n.mag,
                    "mag_unit": n.mag_unit,
                    "title": n.title,
                    "occurred_at": n.time,
                    "lon": n.lon,
                    "lat": n.lat,
                    "raw": json.dumps(e),
                })
    if skipped:
        log.warning("EONET: skipped %d bad records", skipped)
    if duplicates:
        log.info("EONET: skipped %d earthquakes (covered by USGS)", duplicates) 




if __name__ == "__main__":
    while True:

        # USGS - Earthquakes
        try:
            run_once_usgs()
        except Exception:
            log.exception("Ingest for earthquakes run failed; will retry next cycle")
        
        # EONET - Natural Events
        try:
            run_once_eonet()
        except Exception:
            log.exception("Ingest for natural events run failed; will retry next cycle")
        
        time.sleep(POLL_SECONDS)

