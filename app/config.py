"""
Configuration settings for the Cocoa Price Tracker API.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    groq_api_key: str = ""

    # Cache settings
    cache_ttl: int = 3600  # 1 hour default

    # News settings
    news_limit: int = 20

    # Environment
    environment: str = "development"

    # Cocoa futures ticker symbols
    cocoa_ticker: str = "CC=F"  # ICE Cocoa Futures
    cocoa_ticker_london: str = "C=F"  # London Cocoa (alternative)

    # News sources RSS feeds for cocoa/commodities
    news_sources: list = [
        "https://www.investing.com/rss/news_301.rss",  # Commodities news
        "https://feeds.bloomberg.com/markets/news.rss",  # Bloomberg markets
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",  # NYT Business
    ]

    # Groq model settings
    groq_model: str = "llama-3.3-70b-versatile"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
