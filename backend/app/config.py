from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    db_path: Path = REPO_ROOT / "data" / "cocoa.db"
    frontend_dir: Path = REPO_ROOT / "frontend"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    london_cocoa_investing_url: str = "https://www.investing.com/commodities/london-cocoa-contracts"
    ice_london_cocoa_data_url: str = "https://www.ice.com/products/37089076/London-Cocoa-Futures/data"
    cftc_socrata_endpoint: str = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"
    cftc_london_cocoa_market_name: str = "COCOA - ICE FUTURES U.S."

    backfill_years: int = 2
    intraday_poll_minutes: int = 5
    scheduler_timezone: str = "Europe/London"


settings = Settings()
