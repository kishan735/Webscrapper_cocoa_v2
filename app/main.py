"""
Main FastAPI application for the Cocoa Price Tracker API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router
from app import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    print(f"Starting Cocoa Price Tracker API v{__version__}")
    yield
    # Shutdown
    print("Shutting down Cocoa Price Tracker API")


# Create FastAPI application
app = FastAPI(
    title="Cocoa Price Tracker API",
    description="""
## Cocoa Commodity Price Tracker

A comprehensive API for tracking cocoa prices, market news, and AI-powered analysis.

### Features

- **Real-time Prices**: Get current cocoa futures prices from Yahoo Finance
- **Historical Comparison**: Compare prices across different time periods
- **Technical Analysis**: 52-week high/low, moving averages, and more
- **News Aggregation**: Curated cocoa-related news from multiple sources
- **Importance Scoring**: AI-powered scoring of news impact on prices
- **Market Overview**: AI-generated summary of current market conditions
- **Market Outlook**: AI-powered predictions and trends to watch

### Data Sources

- **Prices**: Yahoo Finance (ICE Cocoa Futures - CC=F)
- **News**: Google News, Investing.com, Reuters, and other sources
- **Analysis**: Powered by Groq LLM (Llama 3.3 70B)

### Rate Limits

Data is cached for 1 hour by default to optimize performance and reduce API calls.
Use the `/cache/clear` endpoint to force a refresh.
    """,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Cocoa Price Tracker API",
        "version": __version__,
        "description": "API for tracking cocoa prices and market analysis",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": {
            "price": "/api/v1/price",
            "price_comparison": "/api/v1/price/comparison",
            "technical": "/api/v1/price/technical",
            "news": "/api/v1/news",
            "market_overview": "/api/v1/market/overview",
            "market_outlook": "/api/v1/market/outlook",
            "full_analysis": "/api/v1/analysis",
            "key_factors": "/api/v1/factors",
        },
    }


# Health check at root level (for Render health checks)
@app.get("/health", tags=["System"])
async def root_health():
    """Root-level health check for deployment platforms."""
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
