"""
City code violations scraper — pulls from city open data portals.

Uses the data.gov API and individual city open data portals (Socrata, ArcGIS)
to pull code enforcement / property violations data for target cities.

All Socrata portals share the same API pattern:
  https://<domain>/resource/<dataset_id>.json?$where=<filter>

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.city_violations_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import ALL_ZIPS, TARGET_ZIPS, ZIP_COUNTY_MAP

# ── Socrata open data endpoints by city ────────────────────────────────────
# dataset_id comes from each city's open data portal (data.cityname.gov)
SOCRATA_ENDPOINTS = {
    "Houston": {
        "domain":     "data.houstontx.gov",
        "dataset_id": "ueqk-nfpb",   # Houston Code Enforcement Cases
        "zip_col":    "violation_zip",
        "addr_col":   "address",
        "type_col":   "violation_description",
        "owner_col":  "",
        "date_col":   "open_date",
    },
    "Dallas": {
        "domain":     "www.dallasopendata.com",
        "dataset_id": "9d9p-mb55",   # Dallas Code Compliance Cases
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "service_type",
        "owner_col":  "",
        "date_col":   "created_date",
    },
    "Austin": {
        "domain":     "data.austintexas.gov",
        "dataset_id": "wqe2-cg3j",   # Austin Code Complaints
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "complaint_type",
        "owner_col":  "",
        "date_col":   "case_opened_date",
    },
    "San Antonio": {
        "domain":     "data.sanantonio.gov",
        "dataset_id": "whkf-6sr6",   # SA Code Violations
        "zip_col":    "zip",
        "addr_col":   "address",
        "type_col":   "violation_type",
        "owner_col":  "",
        "date_col":   "open_date",
    },
    "Phoenix": {
        "domain":     "www.phoenixopendata.com",
        "dataset_id": "wpkh-nixi",
        "zip_col":    "zip_code",
        "addr_col":   "street_address",
        "type_col":   "case_type",
        "owner_col":  "",
        "date_col":   "open_date",
    },
    "Las Vegas": {
        "domain":     "opendata.lasvegasnevada.gov",
        "dataset_id": "bvnc-tqdk",
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "violation_type",
        "owner_col":  "",
        "date_col":   "date_opened",
    },
    "Detroit": {
        "domain":     "data.detroitmi.gov",
        "dataset_id": "9qrg-7k74",   # Detroit Blight Violations
        "zip_col":    "zip_code",
        "addr_col":   "violationaddress",
        "type_col":   "violationdescription",
        "owner_col":  "violationowner",
        "date_col":   "ticketissueddt",
    },
    "Indianapolis": {
        "domain":     "data.indy.gov",
        "dataset_id": "n7a2-x4wk",
        "zip_col":    "zip",
        "addr_col":   "address",
        "type_col":   "violation_type",
        "owner_col":  "property_owner",
        "date_col":   "issue_date",
    },
    "Columbus_OH": {
        "domain":     "data.columbus.gov",
        "dataset_id": "nuak-5dud",
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "violation_type",
        "owner_col":  "",
        "date_col":   "open_date",
    },
    "Louisville": {
        "domain":     "data.louisvilleky.gov",
        "dataset_id": "cqmg-e8e4",
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "violation_description",
        "owner_col":  "",
        "date_col":   "date_opened",
    },
    "Richmond": {
        "domain":     "data.richmondgov.com",
        "dataset_id": "kpge-nkrp",
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "code_section",
        "owner_col":  "owner_name",
        "date_col":   "issue_date",
    },
    "Fresno": {
        "domain":     "data.fresno.gov",
        "dataset_id": "e3ub-7a37",
        "zip_col":    "zip_code",
        "addr_col":   "address",
        "type_col":   "violation_type",
        "owner_col":  "",
        "date_col":   "date_opened",
    },
}

# Additional city portals using ArcGIS REST API
ARCGIS_ENDPOINTS = {
    "Tulsa": {
        "url": "https://mapstulsa.tulsacity.com/arcgis/rest/services/CodeEnforcement/MapServer/0/query",
        "zip_field": "ZIP_CODE",
        "addr_field": "ADDRESS",
        "type_field": "VIOLATION_TYPE",
    },
    "OKC": {
        "url": "https://maps.okc.gov/arcgis/rest/services/Planning/CodeEnforcement/MapServer/0/query",
        "zip_field": "ZIP",
        "addr_field": "ADDRESS",
        "type_field": "CASE_TYPE",
    },
}


class CityViolationsScraper(BaseScraper):
    """
    Scrapes code violations from city open data portals (Socrata + ArcGIS).
    Covers all major target cities.
    """

    SOURCE = "CityOpenData"

    def __init__(self):
        super().__init__(
            name="CityViolationsScraper",
            target_zips=sorted(ALL_ZIPS),
        )

    def _socrata_fetch(self, endpoint: dict, zip_code: str) -> list[dict]:
        """Fetch from a Socrata-based open data portal for a specific ZIP."""
        domain     = endpoint["domain"]
        dataset_id = endpoint["dataset_id"]
        zip_col    = endpoint["zip_col"]
        addr_col   = endpoint["addr_col"]
        type_col   = endpoint["type_col"]
        owner_col  = endpoint.get("owner_col", "")
        date_col   = endpoint.get("date_col", "")

        url = f"https://{domain}/resource/{dataset_id}.json"
        params = {
            "$where":   f"{zip_col}='{zip_code}'",
            "$limit":   1000,
            "$order":   f"{date_col} DESC" if date_col else "",
        }
        resp = self.get(url, params=params)
        if not resp:
            return []
        try:
            rows = resp.json()
        except ValueError:
            return []

        records = []
        for row in rows:
            records.append(self.canonical_record(
                owner_name=str(row.get(owner_col, "")) if owner_col else "",
                address=str(row.get(addr_col, "")),
                zip_code=zip_code,
                distress_type="code_violation",
                filing_date=str(row.get(date_col, "")) if date_col else "",
                source=f"{self.SOURCE}_{domain}",
                raw_data={
                    "violation_type": str(row.get(type_col, "")),
                    "raw": row,
                },
            ))
        return records

    def _arcgis_fetch(self, endpoint: dict, zip_code: str) -> list[dict]:
        """Fetch from an ArcGIS REST feature service for a specific ZIP."""
        params = {
            "where":         f"{endpoint['zip_field']} = '{zip_code}'",
            "outFields":     "*",
            "returnGeometry": "false",
            "f":             "json",
            "resultRecordCount": 500,
        }
        resp = self.get(endpoint["url"], params=params)
        if not resp:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []

        features = data.get("features", [])
        records = []
        for feat in features:
            attrs = feat.get("attributes", {})
            records.append(self.canonical_record(
                address=str(attrs.get(endpoint["addr_field"], "")),
                zip_code=zip_code,
                distress_type="code_violation",
                source=f"{self.SOURCE}_arcgis",
                raw_data={"violation_type": str(attrs.get(endpoint["type_field"], "")), **attrs},
            ))
        return records

    def _city_for_zip(self, zip_code: str) -> str:
        info = ZIP_COUNTY_MAP.get(zip_code, {})
        return info.get("city", "")

    def scrape(self) -> list[dict]:
        all_records = []

        # Group ZIPs by city to avoid duplicate fetches
        city_zip_map: dict[str, list[str]] = {}
        for zip_code in self.target_zips:
            city = self._city_for_zip(zip_code)
            if city:
                city_zip_map.setdefault(city, []).append(zip_code)

        # Socrata endpoints
        for city_name, endpoint in SOCRATA_ENDPOINTS.items():
            city_key = city_name.split()[0] if " " in city_name else city_name
            # Find ZIPs for this city
            matching_zips = city_zip_map.get(city_name, [])
            if not matching_zips:
                # Try partial match
                for k, zips in city_zip_map.items():
                    if city_key.lower() in k.lower():
                        matching_zips = zips
                        break
            if not matching_zips:
                self.log.debug("No target ZIPs for city %s", city_name)
                continue

            for zip_code in matching_zips:
                try:
                    recs = self._socrata_fetch(endpoint, zip_code)
                    all_records.extend(recs)
                    self.log.info("Violations %s ZIP %s: %d", city_name, zip_code, len(recs))
                except Exception as exc:
                    self.log.error("Socrata %s ZIP %s: %s", city_name, zip_code, exc)

        # ArcGIS endpoints
        for city_name, endpoint in ARCGIS_ENDPOINTS.items():
            matching_zips = city_zip_map.get(city_name, [])
            for zip_code in matching_zips:
                try:
                    recs = self._arcgis_fetch(endpoint, zip_code)
                    all_records.extend(recs)
                    self.log.info("ArcGIS %s ZIP %s: %d", city_name, zip_code, len(recs))
                except Exception as exc:
                    self.log.error("ArcGIS %s ZIP %s: %s", city_name, zip_code, exc)

        self.save_raw(all_records, "city_violations_raw.csv")
        return all_records


if __name__ == "__main__":
    CityViolationsScraper().run()
