from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

TYPE_MAP = {
    "wildfires": "wildfire", 
    "severe storms": "storm", 
    "volcanoes": "volcano",
    "earthquakes": "earthquake",
    "floods": "flood",
    "landslides": "landslide",
    "severe storms": "severe storm",
    "temperature extremes": "extreme temperatures"
    }


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



class NaturalEvent(BaseModel):
    id: str
    title: str
    type : str
    mag: float | None
    mag_unit: str | None
    time: datetime
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)

    @classmethod
    def from_event(cls, f: dict) -> "NaturalEvent":
        cats = f.get("categories") or [{}]
        geoms = f.get("geometry") or [{}]
        cat = cats[0]
        geom = geoms[-1]                      # latest observation
        coords = geom.get("coordinates") or [None, None]

        raw_type = (cat.get("title") or "").lower()
        event_type = TYPE_MAP.get(raw_type, raw_type)   # "wildfires" -> "wildfire"

        return cls(
            id=f.get("id"),
            title=f.get("title"),
            type=event_type,
            mag=geom.get("magnitudeValue"),
            mag_unit=geom.get("magnitudeUnit"),
            time=geom.get("date"),
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
