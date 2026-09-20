"""Generic paginated reader for an ArcGIS FeatureServer layer's /query endpoint."""

import requests

PAGE_SIZE = 1000


def fetch_all_features(feature_server_layer_url: str, where: str = "1=1") -> list[dict]:
    """Pages through a FeatureServer layer and returns all features as GeoJSON Feature dicts."""
    features: list[dict] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{feature_server_layer_url}/query",
            params={
                "where": where,
                "outFields": "*",
                "f": "geojson",
                "outSR": 4326,
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS query error for {feature_server_layer_url}: {payload['error']}")
        batch = payload.get("features", [])
        features.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return features
