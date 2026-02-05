"""
Pydantic schemas for the Cocoa Price Tracker API.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PriceData(BaseModel):
    """Current price data for cocoa."""

    current_price: float = Field(..., description="Current cocoa price in USD per metric ton")
    currency: str = Field(default="USD", description="Currency of the price")
    unit: str = Field(default="per metric ton", description="Price unit")
    timestamp: datetime = Field(..., description="Timestamp of the price data")
    change_amount: float = Field(..., description="Price change amount from previous close")
    change_percent: float = Field(..., description="Price change percentage from previous close")
    day_high: float = Field(..., description="Intraday high price")
    day_low: float = Field(..., description="Intraday low price")
    volume: Optional[int] = Field(None, description="Trading volume")
    open_price: float = Field(..., description="Opening price")
    previous_close: float = Field(..., description="Previous closing price")


class PriceComparison(BaseModel):
    """Price comparison over different time periods."""

    current_price: float = Field(..., description="Current price")
    price_1_week_ago: Optional[float] = Field(None, description="Price 1 week ago")
    price_1_month_ago: Optional[float] = Field(None, description="Price 1 month ago")
    price_3_months_ago: Optional[float] = Field(None, description="Price 3 months ago")
    price_6_months_ago: Optional[float] = Field(None, description="Price 6 months ago")
    price_1_year_ago: Optional[float] = Field(None, description="Price 1 year ago")
    change_1_week: Optional[float] = Field(None, description="Percentage change over 1 week")
    change_1_month: Optional[float] = Field(None, description="Percentage change over 1 month")
    change_3_months: Optional[float] = Field(None, description="Percentage change over 3 months")
    change_6_months: Optional[float] = Field(None, description="Percentage change over 6 months")
    change_1_year: Optional[float] = Field(None, description="Percentage change over 1 year")


class TechnicalIndicators(BaseModel):
    """Technical analysis indicators for cocoa."""

    week_52_high: float = Field(..., description="52-week high price")
    week_52_low: float = Field(..., description="52-week low price")
    week_52_high_date: Optional[datetime] = Field(None, description="Date of 52-week high")
    week_52_low_date: Optional[datetime] = Field(None, description="Date of 52-week low")
    moving_avg_50: Optional[float] = Field(None, description="50-day moving average")
    moving_avg_200: Optional[float] = Field(None, description="200-day moving average")
    avg_volume: Optional[int] = Field(None, description="Average trading volume")
    price_vs_52_high_percent: float = Field(
        ..., description="Current price as percentage of 52-week high"
    )
    price_vs_52_low_percent: float = Field(
        ..., description="Current price as percentage above 52-week low"
    )


class NewsArticle(BaseModel):
    """A news article related to cocoa."""

    title: str = Field(..., description="Article title")
    summary: Optional[str] = Field(None, description="Article summary or description")
    url: str = Field(..., description="Link to the full article")
    source: str = Field(..., description="News source name")
    published_date: Optional[datetime] = Field(None, description="Publication date")
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Importance score from 0 to 1 based on relevance to cocoa prices",
    )
    sentiment: Optional[str] = Field(
        None, description="Sentiment analysis: positive, negative, or neutral"
    )
    impact_analysis: Optional[str] = Field(
        None, description="Brief analysis of potential price impact"
    )


class MarketOverview(BaseModel):
    """Overview of what's happening in the cocoa market."""

    summary: str = Field(..., description="Brief summary of current market conditions")
    key_factors: list[str] = Field(
        default_factory=list, description="Key factors affecting cocoa prices"
    )
    supply_conditions: Optional[str] = Field(None, description="Current supply situation")
    demand_conditions: Optional[str] = Field(None, description="Current demand situation")
    weather_impact: Optional[str] = Field(
        None, description="Weather conditions affecting cocoa production"
    )
    geopolitical_factors: Optional[str] = Field(
        None, description="Geopolitical factors affecting the market"
    )


class MarketOutlook(BaseModel):
    """Market outlook and trends to watch."""

    short_term_outlook: str = Field(..., description="Short-term market outlook (1-4 weeks)")
    medium_term_outlook: str = Field(..., description="Medium-term market outlook (1-3 months)")
    long_term_outlook: Optional[str] = Field(
        None, description="Long-term market outlook (3-12 months)"
    )
    trends_to_watch: list[str] = Field(
        default_factory=list, description="Key trends to monitor"
    )
    risk_factors: list[str] = Field(default_factory=list, description="Risk factors to consider")
    opportunities: list[str] = Field(
        default_factory=list, description="Potential opportunities in the market"
    )
    confidence_level: str = Field(
        default="medium",
        description="Confidence level in the outlook: low, medium, or high",
    )


class CocoaAnalysis(BaseModel):
    """Complete cocoa market analysis combining all data."""

    price_data: PriceData = Field(..., description="Current price information")
    price_comparison: PriceComparison = Field(..., description="Historical price comparison")
    technical_indicators: TechnicalIndicators = Field(..., description="Technical analysis data")
    market_overview: MarketOverview = Field(..., description="Current market overview")
    market_outlook: MarketOutlook = Field(..., description="Future market outlook")
    latest_news: list[NewsArticle] = Field(
        default_factory=list, description="Latest relevant news articles"
    )
    analysis_timestamp: datetime = Field(..., description="When this analysis was generated")
    data_freshness: str = Field(
        default="live", description="Freshness of data: live, cached, or delayed"
    )


class HealthCheck(BaseModel):
    """API health check response."""

    status: str = Field(default="healthy", description="API status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current server timestamp")
    services: dict = Field(default_factory=dict, description="Status of dependent services")
