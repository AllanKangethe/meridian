import os

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, text
from fastapi import HTTPException

import time
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


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
