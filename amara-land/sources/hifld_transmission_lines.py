"""HIFLD Electric Power Transmission Lines (ArcGIS FeatureServer). See app.config for the
endpoint URL, which needs verifying against the live HIFLD Hub listing before first run.

Staleness matters here specifically -- the spec flags that this layer has gone long
stretches without a refresh, so `retrieved_at` should always be checked against how old
the underlying data actually is before it's trusted for anything time-sensitive.
"""

from datetime import datetime, timezone

from app.config import settings

from .arcgis_client import fetch_all_features
from .base import NormalizedRecord

SOURCE_NAME = "HIFLD Electric Power Transmission Lines"


def _first(props: dict, *keys: str):
    for key in keys:
        if props.get(key) not in (None, ""):
            return props[key]
    return None


def fetch() -> list[NormalizedRecord]:
    retrieved_at = datetime.now(timezone.utc)
    features = fetch_all_features(settings.hifld_transmission_lines_url)

    records = []
    for feat in features:
        props = feat.get("properties", {})
        records.append(
            NormalizedRecord(
                data={
                    "source_id": str(_first(props, "ID", "OBJECTID") or ""),
                    "voltage": _first(props, "VOLTAGE"),
                    "owner": _first(props, "OWNER"),
                    "status": _first(props, "STATUS"),
                    "geometry": feat.get("geometry"),
                },
                source=SOURCE_NAME,
                source_url=settings.hifld_transmission_lines_url,
                retrieved_at=retrieved_at,
                dataset_published_at=None,
            )
        )
    return records
