"""
Price fetcher service using Yahoo Finance for cocoa futures data.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from cachetools import TTLCache

from app.models.schemas import PriceData, PriceComparison, TechnicalIndicators
from app.config import get_settings


class PriceFetcher:
    """Fetches cocoa price data from Yahoo Finance."""

    def __init__(self):
        self.settings = get_settings()
        self.ticker_symbol = self.settings.cocoa_ticker  # CC=F for ICE Cocoa Futures
        self._cache = TTLCache(maxsize=100, ttl=self.settings.cache_ttl)

    def _get_ticker(self) -> yf.Ticker:
        """Get the Yahoo Finance ticker object for cocoa."""
        return yf.Ticker(self.ticker_symbol)

    def get_current_price(self) -> PriceData:
        """
        Fetch current cocoa price and daily statistics.

        Returns:
            PriceData: Current price information
        """
        cache_key = "current_price"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()
        info = ticker.info

        # Get today's data
        hist = ticker.history(period="2d")

        if hist.empty:
            raise ValueError("No price data available for cocoa futures")

        latest = hist.iloc[-1]
        prev_close = hist.iloc[-2]["Close"] if len(hist) > 1 else latest["Open"]

        current_price = latest["Close"]
        change_amount = current_price - prev_close
        change_percent = (change_amount / prev_close) * 100 if prev_close else 0

        price_data = PriceData(
            current_price=round(current_price, 2),
            currency="USD",
            unit="per metric ton",
            timestamp=datetime.now(),
            change_amount=round(change_amount, 2),
            change_percent=round(change_percent, 2),
            day_high=round(latest["High"], 2),
            day_low=round(latest["Low"], 2),
            volume=int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,
            open_price=round(latest["Open"], 2),
            previous_close=round(prev_close, 2),
        )

        self._cache[cache_key] = price_data
        return price_data

    def get_price_comparison(self) -> PriceComparison:
        """
        Get price comparison over different time periods.

        Returns:
            PriceComparison: Historical price comparisons
        """
        cache_key = "price_comparison"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()

        # Get 1 year of historical data
        hist = ticker.history(period="1y")

        if hist.empty:
            raise ValueError("No historical data available")

        current_price = hist.iloc[-1]["Close"]
        now = hist.index[-1]

        def get_price_at_date(target_date) -> Optional[float]:
            """Get the closest price to a target date."""
            try:
                # Find the closest date in the historical data
                mask = hist.index <= target_date
                if mask.any():
                    return float(hist.loc[mask].iloc[-1]["Close"])
            except Exception:
                pass
            return None

        def calc_change(old_price: Optional[float], new_price: float) -> Optional[float]:
            """Calculate percentage change."""
            if old_price and old_price > 0:
                return round(((new_price - old_price) / old_price) * 100, 2)
            return None

        # Calculate prices at different periods
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
        """
        Calculate technical indicators for cocoa.

        Returns:
            TechnicalIndicators: Technical analysis data
        """
        cache_key = "technical_indicators"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ticker = self._get_ticker()

        # Get 1 year of data for calculations
        hist = ticker.history(period="1y")

        if hist.empty:
            raise ValueError("No historical data available")

        current_price = hist.iloc[-1]["Close"]

        # Calculate 52-week high and low
        week_52_high = hist["High"].max()
        week_52_low = hist["Low"].min()

        # Find dates of 52-week high and low
        week_52_high_date = hist["High"].idxmax()
        week_52_low_date = hist["Low"].idxmin()

        # Calculate moving averages
        moving_avg_50 = None
        moving_avg_200 = None

        if len(hist) >= 50:
            moving_avg_50 = hist["Close"].tail(50).mean()

        if len(hist) >= 200:
            moving_avg_200 = hist["Close"].tail(200).mean()

        # Calculate average volume
        avg_volume = int(hist["Volume"].mean()) if hist["Volume"].notna().any() else None

        # Calculate price position relative to 52-week range
        price_vs_52_high = (current_price / week_52_high) * 100
        price_vs_52_low = ((current_price - week_52_low) / week_52_low) * 100

        indicators = TechnicalIndicators(
            week_52_high=round(week_52_high, 2),
            week_52_low=round(week_52_low, 2),
            week_52_high_date=week_52_high_date.to_pydatetime()
            if hasattr(week_52_high_date, "to_pydatetime")
            else week_52_high_date,
            week_52_low_date=week_52_low_date.to_pydatetime()
            if hasattr(week_52_low_date, "to_pydatetime")
            else week_52_low_date,
            moving_avg_50=round(moving_avg_50, 2) if moving_avg_50 else None,
            moving_avg_200=round(moving_avg_200, 2) if moving_avg_200 else None,
            avg_volume=avg_volume,
            price_vs_52_high_percent=round(price_vs_52_high, 2),
            price_vs_52_low_percent=round(price_vs_52_low, 2),
        )

        self._cache[cache_key] = indicators
        return indicators

    def get_historical_data(self, period: str = "1y") -> pd.DataFrame:
        """
        Get historical price data.

        Args:
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)

        Returns:
            DataFrame with historical OHLCV data
        """
        ticker = self._get_ticker()
        return ticker.history(period=period)

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()
