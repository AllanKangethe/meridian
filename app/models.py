from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class QuakeEvent(BaseModel):
    id: str
    type: str
    mag: float | None
    title: str
    time: datetime
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)

    @classmethod
    def from_feature(cls, f: dict) -> "QuakeEvent":
        props = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        return cls(
            id=f.get("id"),
            type=props.get("type"),
            mag=props.get("mag"),
            title=props.get("title"),
            time=props.get("time"),
            lon=coords[0],
            lat=coords[1],
        )

class WatchZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=2000)
    min_magnitude: float = Field(default=0, ge=0, le=10)
    webhook_url: HttpUrl | None = None
