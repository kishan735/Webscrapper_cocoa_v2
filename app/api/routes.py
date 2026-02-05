"""
API routes for the Cocoa Price Tracker.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional

from app.models.schemas import (
    PriceData,
    PriceComparison,
    TechnicalIndicators,
    NewsArticle,
    MarketOverview,
    MarketOutlook,
    CocoaAnalysis,
    HealthCheck,
)
from app.services.price_fetcher import PriceFetcher
from app.services.news_scraper import NewsScraper
from app.services.importance_analyzer import ImportanceAnalyzer
from app.services.ai_analyzer import AIAnalyzer
from app import __version__

router = APIRouter()

# Initialize services
price_fetcher = PriceFetcher()
news_scraper = NewsScraper()
importance_analyzer = ImportanceAnalyzer()
ai_analyzer = AIAnalyzer()


@router.get("/health", response_model=HealthCheck, tags=["System"])
async def health_check():
    """
    Check the health status of the API and its dependencies.
    """
    services = {
        "price_fetcher": "healthy",
        "news_scraper": "healthy",
        "ai_analyzer": "healthy" if ai_analyzer.is_available() else "no_api_key",
    }

    return HealthCheck(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(),
        services=services,
    )


@router.get("/price", response_model=PriceData, tags=["Price"])
async def get_current_price():
    """
    Get the current cocoa price and daily statistics.

    Returns current price, daily change, day high/low, volume, etc.
    """
    try:
        return price_fetcher.get_current_price()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")


@router.get("/price/comparison", response_model=PriceComparison, tags=["Price"])
async def get_price_comparison():
    """
    Get price comparison over different time periods.

    Compares current price to 1 week, 1 month, 3 months, 6 months, and 1 year ago.
    """
    try:
        return price_fetcher.get_price_comparison()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching price comparison: {str(e)}"
        )


@router.get("/price/technical", response_model=TechnicalIndicators, tags=["Price"])
async def get_technical_indicators():
    """
    Get technical indicators for cocoa.

    Returns 52-week high/low, moving averages, and other technical data.
    """
    try:
        return price_fetcher.get_technical_indicators()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching technical indicators: {str(e)}"
        )


@router.get("/news", response_model=list[NewsArticle], tags=["News"])
async def get_news(
    limit: Optional[int] = Query(default=20, ge=1, le=50, description="Number of articles to return"),
    analyze: bool = Query(default=True, description="Whether to analyze articles for importance"),
):
    """
    Get the latest cocoa-related news articles.

    Articles are sorted by importance score when analysis is enabled.
    """
    try:
        articles = news_scraper.fetch_all_news(limit=limit)

        if analyze:
            articles = importance_analyzer.analyze_articles(articles)

        return articles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching news: {str(e)}")


@router.get("/news/search", response_model=list[NewsArticle], tags=["News"])
async def search_news(
    query: str = Query(..., min_length=2, description="Search query"),
    analyze: bool = Query(default=True, description="Whether to analyze articles"),
):
    """
    Search for specific cocoa-related news.

    Searches news sources for articles matching the query.
    """
    try:
        articles = news_scraper.search_news(query)

        if analyze:
            articles = importance_analyzer.analyze_articles(articles)

        return articles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching news: {str(e)}")


@router.get("/market/overview", response_model=MarketOverview, tags=["Market Analysis"])
async def get_market_overview():
    """
    Get an AI-generated overview of the current cocoa market.

    Analyzes price data and news to provide market insights.
    """
    try:
        # Gather all necessary data
        price_data = price_fetcher.get_current_price()
        price_comparison = price_fetcher.get_price_comparison()
        news_articles = news_scraper.fetch_all_news(limit=15)
        analyzed_articles = importance_analyzer.analyze_articles(news_articles)
        key_factors = importance_analyzer.identify_key_factors(analyzed_articles)

        # Generate overview
        overview = ai_analyzer.generate_market_overview(
            price_data=price_data,
            price_comparison=price_comparison,
            news_articles=analyzed_articles,
            key_factors=key_factors,
        )

        return overview
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating market overview: {str(e)}"
        )


@router.get("/market/outlook", response_model=MarketOutlook, tags=["Market Analysis"])
async def get_market_outlook():
    """
    Get an AI-generated market outlook for cocoa.

    Provides short, medium, and long-term outlook with trends to watch.
    """
    try:
        # Gather all necessary data
        price_data = price_fetcher.get_current_price()
        price_comparison = price_fetcher.get_price_comparison()
        technical = price_fetcher.get_technical_indicators()
        news_articles = news_scraper.fetch_all_news(limit=10)
        analyzed_articles = importance_analyzer.analyze_articles(news_articles)

        # Generate outlook
        outlook = ai_analyzer.generate_market_outlook(
            price_data=price_data,
            price_comparison=price_comparison,
            technical_indicators=technical,
            news_articles=analyzed_articles,
        )

        return outlook
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating market outlook: {str(e)}"
        )


@router.get("/analysis", response_model=CocoaAnalysis, tags=["Market Analysis"])
async def get_full_analysis():
    """
    Get a complete cocoa market analysis.

    This is the main endpoint that combines all data:
    - Current price and daily stats
    - Historical price comparison
    - Technical indicators
    - Market overview (AI-generated)
    - Market outlook (AI-generated)
    - Latest news with importance scoring

    This endpoint may take longer as it aggregates data from multiple sources.
    """
    try:
        # Fetch all price data
        price_data = price_fetcher.get_current_price()
        price_comparison = price_fetcher.get_price_comparison()
        technical = price_fetcher.get_technical_indicators()

        # Fetch and analyze news
        news_articles = news_scraper.fetch_all_news(limit=15)
        analyzed_articles = importance_analyzer.analyze_articles(news_articles)
        key_factors = importance_analyzer.identify_key_factors(analyzed_articles)

        # Generate AI analysis
        market_overview = ai_analyzer.generate_market_overview(
            price_data=price_data,
            price_comparison=price_comparison,
            news_articles=analyzed_articles,
            key_factors=key_factors,
        )

        market_outlook = ai_analyzer.generate_market_outlook(
            price_data=price_data,
            price_comparison=price_comparison,
            technical_indicators=technical,
            news_articles=analyzed_articles,
        )

        # Combine into full analysis
        analysis = CocoaAnalysis(
            price_data=price_data,
            price_comparison=price_comparison,
            technical_indicators=technical,
            market_overview=market_overview,
            market_outlook=market_outlook,
            latest_news=analyzed_articles[:10],  # Top 10 articles
            analysis_timestamp=datetime.now(),
            data_freshness="live",
        )

        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating analysis: {str(e)}"
        )


@router.get("/factors", tags=["Market Analysis"])
async def get_key_factors():
    """
    Get key factors currently affecting cocoa prices.

    Analyzes recent news to identify and rank the most important factors.
    """
    try:
        news_articles = news_scraper.fetch_all_news(limit=20)
        analyzed_articles = importance_analyzer.analyze_articles(news_articles)
        factors = importance_analyzer.identify_key_factors(analyzed_articles)

        return {
            "factors": factors,
            "article_count": len(analyzed_articles),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error identifying factors: {str(e)}"
        )


@router.post("/cache/clear", tags=["System"])
async def clear_cache():
    """
    Clear all cached data.

    Forces fresh data fetch on next request.
    """
    try:
        price_fetcher.clear_cache()
        news_scraper.clear_cache()
        ai_analyzer.clear_cache()

        return {"status": "success", "message": "All caches cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")
