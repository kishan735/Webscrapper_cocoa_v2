"""
Price fetcher service for London Cocoa using Yahoo Finance with Investing.com as reference.
"""

import yfinance as yf
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional
import re
from cachetools import TTLCache

from app.models.schemas import PriceData, PriceComparison, TechnicalIndicators
from app.config import get_settings


class PriceFetcher:
    """Fetches London Cocoa price data."""

    # Yahoo Finance ticker for Cocoa
    COCOA_TICKER = "CC=F"

    # Investing.com URL for additional data
    INVESTING_URL = "https://www.investing.com/commodities/london-cocoa"

    def __init__(self):
        self.settings = get_settings()
        self._cache = TTLCache(maxsize=100, ttl=self.settings.cache_ttl)
        self._http_client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def _get_ticker(self) -> yf.Ticker:
        """Get the Yahoo Finance ticker object for cocoa."""
        return yf.Ticker(self.COCOA_TICKER)

    def _try_investing_com(self) -> Optional[dict]:
        """Try to get price from Investing.com as additional source."""
        try:
            response = self._http_client.get(self.INVESTING_URL)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find price in various locations
            price = None

            # Method 1: Look for data-test attributes
            price_elem = soup.select_one('[data-test="instrument-price-last"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._parse_number(price_text)

            # Method 2: Look for specific class patterns
            if not price:
                for elem in soup.select('[class*="instrument-price"], [class*="last-price"], .text-5xl'):
                    text = elem.get_text(strip=True)
                    parsed = self._parse_number(text)
                    if parsed and parsed > 1000:  # Cocoa prices are typically > 1000
                        price = parsed
                        break

            # Method 3: Look in script tags for JSON data
            if not price:
                for script in soup.select('script'):
                    if script.string and 'last' in script.string.lower():
                        # Try to find price patterns like "last":1234.56
                        matches = re.findall(r'"last"[:\s]*([0-9,]+\.?\d*)', script.string)
                        for match in matches:
                            parsed = self._parse_number(match)
                            if parsed and parsed > 1000:
                                price = parsed
                                break

            if price:
                return {"price": price, "currency": "GBP"}

        except Exception as e:
            print(f"Investing.com fetch failed: {e}")

        return None

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse a number from text."""
        if not text:
            return None
        cleaned = re.sub(r'[£$€,\s]', '', str(text).strip())
        cleaned = re.sub(r'[^\d.\-]', '', cleaned)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def get_current_price(self) -> PriceData:
        """
        Fetch current cocoa price.
        Uses Yahoo Finance as primary source.
        """
        cache_key = "current_price"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()

        # Get today's data from Yahoo Finance
        hist = ticker.history(period="5d")

        if hist.empty:
            raise ValueError("No price data available for cocoa futures")

        latest = hist.iloc[-1]
        prev_close = hist.iloc[-2]["Close"] if len(hist) > 1 else latest["Open"]

        current_price = latest["Close"]
        change_amount = current_price - prev_close
        change_percent = (change_amount / prev_close) * 100 if prev_close else 0

        # Try to get London price from Investing.com for reference
        investing_data = self._try_investing_com()

        # Use Investing.com price if available and reasonable
        if investing_data and investing_data.get("price"):
            london_price = investing_data["price"]
            # London Cocoa is in GBP, typically different from USD price
            # Use it if it looks valid
            if london_price > 1000:
                current_price = london_price
                currency = "GBP"
                unit = "per tonne"
                # Recalculate change based on London data would need historical London data
                # For now, keep the percentage from Yahoo as approximate
        else:
            currency = "USD"
            unit = "per metric ton"

        price_data = PriceData(
            current_price=round(current_price, 2),
            currency=currency,
            unit=unit,
            timestamp=datetime.now(),
            change_amount=round(change_amount, 2),
            change_percent=round(change_percent, 2),
            day_high=round(latest["High"], 2),
            day_low=round(latest["Low"], 2),
            volume=int(latest["Volume"]) if latest["Volume"] > 0 else None,
            open_price=round(latest["Open"], 2),
            previous_close=round(prev_close, 2),
        )

        self._cache[cache_key] = price_data
        return price_data

    def get_price_comparison(self) -> PriceComparison:
        """Get price comparison over different time periods."""
        cache_key = "price_comparison"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()
        hist = ticker.history(period="1y")

        if hist.empty:
            raise ValueError("No historical data available")

        current_price = hist.iloc[-1]["Close"]
        now = hist.index[-1]

        def get_price_at_date(target_date) -> Optional[float]:
            try:
                mask = hist.index <= target_date
                if mask.any():
                    return float(hist.loc[mask].iloc[-1]["Close"])
            except Exception:
                pass
            return None

        def calc_change(old_price: Optional[float], new_price: float) -> Optional[float]:
            if old_price and old_price > 0:
                return round(((new_price - old_price) / old_price) * 100, 2)
            return None

        price_1_week = get_price_at_date(now - timedelta(days=7))
        price_1_month = get_price_at_date(now - timedelta(days=30))
        price_3_months = get_price_at_date(now - timedelta(days=90))
        price_6_months = get_price_at_date(now - timedelta(days=180))
        price_1_year = get_price_at_date(now - timedelta(days=365))

        comparison = PriceComparison(
            current_price=round(current_price, 2),
            price_1_week_ago=round(price_1_week, 2) if price_1_week else None,
            price_1_month_ago=round(price_1_month, 2) if price_1_month else None,
            price_3_months_ago=round(price_3_months, 2) if price_3_months else None,
            price_6_months_ago=round(price_6_months, 2) if price_6_months else None,
            price_1_year_ago=round(price_1_year, 2) if price_1_year else None,
            change_1_week=calc_change(price_1_week, current_price),
            change_1_month=calc_change(price_1_month, current_price),
            change_3_months=calc_change(price_3_months, current_price),
            change_6_months=calc_change(price_6_months, current_price),
            change_1_year=calc_change(price_1_year, current_price),
        )

        self._cache[cache_key] = comparison
        return comparison

    def get_technical_indicators(self) -> TechnicalIndicators:
        """Calculate technical indicators for cocoa."""
        cache_key = "technical_indicators"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()
        hist = ticker.history(period="1y")

        if hist.empty:
            raise ValueError("No historical data available")

        current_price = hist.iloc[-1]["Close"]

        week_52_high = hist["High"].max()
        week_52_low = hist["Low"].min()
        week_52_high_date = hist["High"].idxmax()
        week_52_low_date = hist["Low"].idxmin()

        moving_avg_50 = hist["Close"].tail(50).mean() if len(hist) >= 50 else None
        moving_avg_200 = hist["Close"].tail(200).mean() if len(hist) >= 200 else None
        avg_volume = int(hist["Volume"].mean()) if hist["Volume"].notna().any() else None

        price_vs_52_high = (current_price / week_52_high) * 100
        price_vs_52_low = ((current_price - week_52_low) / week_52_low) * 100

        indicators = TechnicalIndicators(
            week_52_high=round(week_52_high, 2),
            week_52_low=round(week_52_low, 2),
            week_52_high_date=week_52_high_date.to_pydatetime() if hasattr(week_52_high_date, "to_pydatetime") else week_52_high_date,
            week_52_low_date=week_52_low_date.to_pydatetime() if hasattr(week_52_low_date, "to_pydatetime") else week_52_low_date,
            moving_avg_50=round(moving_avg_50, 2) if moving_avg_50 else None,
            moving_avg_200=round(moving_avg_200, 2) if moving_avg_200 else None,
            avg_volume=avg_volume,
            price_vs_52_high_percent=round(price_vs_52_high, 2),
            price_vs_52_low_percent=round(price_vs_52_low, 2),
        )

        self._cache[cache_key] = indicators
        return indicators

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()

    def __del__(self):
        """Cleanup HTTP client."""
        try:
            self._http_client.close()
        except:
            pass
