# Cocoa Price Tracker API

A comprehensive API for tracking cocoa commodity prices, market news, and AI-powered analysis.

## Features

- **Real-time Prices**: Current cocoa futures prices from Yahoo Finance
- **Historical Comparison**: Compare prices across different time periods
- **Technical Analysis**: 52-week high/low, 50/200-day moving averages
- **News Aggregation**: Curated cocoa-related news from multiple sources
- **Importance Scoring**: Automated scoring of news impact on prices
- **AI Market Analysis**: AI-generated market overview and outlook using Groq

## Tech Stack

- **Framework**: FastAPI
- **Price Data**: Yahoo Finance (yfinance) - FREE
- **News**: RSS feeds, web scraping - FREE
- **AI Analysis**: Groq (Llama 3.3 70B) - FREE tier
- **Deployment**: Railway.app - FREE tier

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
uvicorn app.main:app --reload
```

6. Open http://localhost:8000/docs for the API documentation.

## Deploy to Railway (Recommended)

Railway is the easiest way to deploy this API.

### Steps:

1. **Get a Groq API Key** (free): https://console.groq.com

2. **Deploy to Railway**:
   - Go to [Railway.app](https://railway.app)
   - Click "New Project" > "Deploy from GitHub repo"
   - Select this repository
   - Railway auto-detects Python and deploys!

3. **Add Environment Variable**:
   - In Railway dashboard, go to your service
   - Click "Variables" tab
   - Add: `GROQ_API_KEY` = your_groq_api_key

4. **Done!** Your API is live at the provided Railway URL.

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

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | - | API key from [Groq Console](https://console.groq.com/) |
| `CACHE_TTL` | No | 3600 | Cache time-to-live in seconds |
| `NEWS_LIMIT` | No | 20 | Default number of news articles |

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
│   └── schemas.py       # Pydantic models
├── services/
│   ├── price_fetcher.py      # Yahoo Finance integration
│   ├── news_scraper.py       # News aggregation
│   ├── importance_analyzer.py # News scoring
│   └── ai_analyzer.py        # Groq AI integration
└── api/
    └── routes.py        # API endpoints
```

## License

MIT License
