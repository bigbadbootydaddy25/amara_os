from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from .env, which is owner-readable only and never committed."""

    database_url: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""

    # HIFLD ArcGIS FeatureServer layer URLs (no /query suffix).
    # VERIFY BEFORE FIRST RUN: these host names/item IDs are the commonly published
    # HIFLD endpoints but could not be confirmed live from this environment
    # (outbound access to arcgis.com is blocked here). Look the layer up on
    # https://hifld-geoplatform.hub.arcgis.com, open "View API Resource", and
    # copy the exact FeatureServer layer URL if these don't resolve.
    hifld_substations_url: str = (
        "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Substations/FeatureServer/0"
    )
    hifld_transmission_lines_url: str = (
        "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
        "Electric_Power_Transmission_Lines/FeatureServer/0"
    )

    # EIA-860 annual data file. VERIFY BEFORE FIRST RUN: same network caveat as above.
    eia860_year: int = 2023
    eia860_zip_url_template: str = "https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"

    target_state: str = "TX"
    target_counties: str = "Collin,Grayson,Fannin,Tarrant,Denton,Dallas,Johnson,Ellis"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
