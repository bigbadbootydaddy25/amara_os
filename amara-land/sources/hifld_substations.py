"""HIFLD Electric Substations (ArcGIS FeatureServer). See app.config for the endpoint URL,
which needs verifying against the live HIFLD Hub listing before first run."""

from datetime import datetime, timezone

from app.config import settings

from .arcgis_client import fetch_all_features
from .base import NormalizedRecord

SOURCE_NAME = "HIFLD Electric Substations"


def _first(props: dict, *keys: str):
    for key in keys:
        if props.get(key) not in (None, ""):
            return props[key]
    return None


def fetch() -> list[NormalizedRecord]:
    retrieved_at = datetime.now(timezone.utc)
    features = fetch_all_features(settings.hifld_substations_url)

    records = []
    for feat in features:
        props = feat.get("properties", {})
        records.append(
            NormalizedRecord(
                data={
                    "source_id": str(_first(props, "ID", "OBJECTID") or ""),
                    "name": _first(props, "NAME"),
                    "operator": _first(props, "OPERATOR", "OPERATOR1"),
                    "max_voltage": _first(props, "MAX_VOLT"),
                    "min_voltage": _first(props, "MIN_VOLT"),
                    "status": _first(props, "STATUS"),
                    "county": _first(props, "COUNTY"),
                    "state": _first(props, "STATE"),
                    "geometry": feat.get("geometry"),
                },
                source=SOURCE_NAME,
                source_url=settings.hifld_substations_url,
                retrieved_at=retrieved_at,
                # HIFLD does not expose a per-record publication date; the layer's overall
                # "last updated" date is only visible on its ArcGIS Hub item page, not in the
                # query response, so it stays unset here rather than guessed.
                dataset_published_at=None,
            )
        )
    return records
