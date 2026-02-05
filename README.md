# Cocoa Price Tracker API

A comprehensive API for tracking cocoa commodity prices, market news, and AI-powered analysis.

## Features

- **Real-time Prices**: Current cocoa futures prices from Yahoo Finance
- **Historical Comparison**: Compare prices across different time periods (1 week, 1 month, 3 months, 6 months, 1 year)
- **Technical Analysis**: 52-week high/low, 50/200-day moving averages
- **News Aggregation**: Curated cocoa-related news from multiple sources
- **Importance Scoring**: Automated scoring of news impact on prices
- **AI Market Analysis**: AI-generated market overview and outlook using Groq

## Tech Stack

- **Framework**: FastAPI
- **Price Data**: Yahoo Finance (yfinance)
- **News**: RSS feeds, web scraping (BeautifulSoup)
- **AI Analysis**: Groq (Llama 3.3 70B)
- **Deployment**: Render.com

## Quick Start

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/kishan735/Webscrapper_cocoa_v2.git
cd Webscrapper_cocoa_v2
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

5. Run the server:
```bash
python -m app.main
# Or with uvicorn directly:
uvicorn app.main:app --reload
```

6. Open http://localhost:8000/docs for the API documentation.

## API Endpoints

### Price Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/price` | Current cocoa price and daily stats |
| `GET /api/v1/price/comparison` | Price comparison over time periods |
| `GET /api/v1/price/technical` | Technical indicators (52w high/low, MAs) |

### News Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/news` | Latest cocoa news with importance scores |
| `GET /api/v1/news/search?query=` | Search for specific news |

### Analysis Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/analysis` | Complete market analysis (combines all data) |
| `GET /api/v1/market/overview` | AI-generated market overview |
| `GET /api/v1/market/outlook` | AI-generated market outlook |
| `GET /api/v1/factors` | Key factors affecting prices |

### System Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `POST /api/v1/cache/clear` | Clear cached data |

## Deployment on Render.com

### Option 1: Using Blueprint (Recommended)

1. Fork this repository
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New" > "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect `render.yaml` and configure the service
6. Add the `GROQ_API_KEY` environment variable in the Render dashboard

### Option 2: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" > "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
5. Add environment variables:
   - `GROQ_API_KEY`: Your Groq API key
   - `CACHE_TTL`: Cache time in seconds (default: 3600)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | - | API key from [Groq Console](https://console.groq.com/) |
| `CACHE_TTL` | No | 3600 | Cache time-to-live in seconds |
| `NEWS_LIMIT` | No | 20 | Default number of news articles |
| `ENVIRONMENT` | No | development | Environment name |

## Data Sources

- **Prices**: Yahoo Finance - ICE Cocoa Futures (CC=F)
- **News**: Google News RSS, Investing.com, CNBC, Reuters
- **Analysis**: Groq API (Llama 3.3 70B Versatile)

## Response Examples

### Current Price
```json
{
  "current_price": 8500.00,
  "currency": "USD",
  "unit": "per metric ton",
  "timestamp": "2024-01-15T10:30:00Z",
  "change_amount": 125.00,
  "change_percent": 1.49,
  "day_high": 8550.00,
  "day_low": 8350.00,
  "volume": 12500,
  "open_price": 8375.00,
  "previous_close": 8375.00
}
```

### News Article
```json
{
  "title": "Cocoa prices surge as West African drought continues",
  "summary": "Cocoa futures hit new highs amid concerns over production...",
  "url": "https://example.com/article",
  "source": "Reuters",
  "published_date": "2024-01-15T08:00:00Z",
  "importance_score": 0.85,
  "sentiment": "negative",
  "impact_analysis": "Supply disruption could push prices higher"
}
```

## Architecture

```
app/
├── __init__.py          # Package initialization
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── models/
│   ├── __init__.py
│   └── schemas.py       # Pydantic models
├── services/
│   ├── __init__.py
│   ├── price_fetcher.py      # Yahoo Finance integration
│   ├── news_scraper.py       # News aggregation
│   ├── importance_analyzer.py # News scoring
│   └── ai_analyzer.py        # Groq AI integration
└── api/
    ├── __init__.py
    └── routes.py        # API endpoints
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
