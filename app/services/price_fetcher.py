"""
Price fetcher service for London Cocoa from Investing.com
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional
import re
from cachetools import TTLCache

from app.models.schemas import PriceData, PriceComparison, TechnicalIndicators
from app.config import get_settings


class PriceFetcher:
    """Fetches London Cocoa price data from Investing.com"""

    INVESTING_URL = "https://www.investing.com/commodities/london-cocoa"
    HISTORICAL_URL = "https://www.investing.com/commodities/london-cocoa-historical-data"

    def __init__(self):
        self.settings = get_settings()
        self._cache = TTLCache(maxsize=100, ttl=self.settings.cache_ttl)
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        )

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse a number from text, handling commas and currency symbols."""
        if not text:
            return None
        # Remove currency symbols, commas, whitespace
        cleaned = re.sub(r'[£$€,\s]', '', text.strip())
        # Handle parentheses for negative numbers
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        # Remove any remaining non-numeric chars except . and -
        cleaned = re.sub(r'[^\d.\-]', '', cleaned)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _parse_percent(self, text: str) -> Optional[float]:
        """Parse a percentage from text."""
        if not text:
            return None
        cleaned = text.replace('%', '').replace('(', '').replace(')', '').strip()
        return self._parse_number(cleaned)

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page from Investing.com"""
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def get_current_price(self) -> PriceData:
        """
        Fetch current London Cocoa price from Investing.com

        Returns:
            PriceData: Current price information in GBP per tonne
        """
        cache_key = "current_price"
        if cache_key in self._cache:
            return self._cache[cache_key]

        soup = self._fetch_page(self.INVESTING_URL)
        if not soup:
            raise ValueError("Could not fetch price data from Investing.com")

        # Try to find price data - Investing.com structure
        current_price = None
        change_amount = None
        change_percent = None
        prev_close = None
        day_high = None
        day_low = None
        open_price = None

        # Look for the main price element
        # Investing.com uses data attributes and specific classes
        price_elem = soup.select_one('[data-test="instrument-price-last"]')
        if price_elem:
            current_price = self._parse_number(price_elem.get_text())

        # Try alternative selectors if main one fails
        if not current_price:
            price_elem = soup.select_one('.text-5xl, .instrument-price_last__KQzyA, .last-price-value')
            if price_elem:
                current_price = self._parse_number(price_elem.get_text())

        # Look for change amount and percent
        change_elem = soup.select_one('[data-test="instrument-price-change"]')
        if change_elem:
            change_amount = self._parse_number(change_elem.get_text())

        change_pct_elem = soup.select_one('[data-test="instrument-price-change-percent"]')
        if change_pct_elem:
            change_percent = self._parse_percent(change_pct_elem.get_text())

        # Look for additional data in the overview section
        # Try to find Open, High, Low, Prev Close from the data table
        data_items = soup.select('[data-test="overview-item"], .key-info_dd__mWOIW, dd')
        labels = soup.select('[data-test="overview-item-label"], .key-info_dt__LKuAY, dt')

        data_dict = {}
        for i, label in enumerate(labels):
            label_text = label.get_text(strip=True).lower()
            if i < len(data_items):
                value_text = data_items[i].get_text(strip=True)
                data_dict[label_text] = value_text

        # Also try to parse from any visible data
        for item in soup.select('[class*="key-info"], [class*="overview"]'):
            text = item.get_text(strip=True).lower()
            if 'prev' in text and 'close' in text:
                # Try to extract the number after the label
                numbers = re.findall(r'[\d,]+\.?\d*', item.get_text())
                if numbers:
                    prev_close = self._parse_number(numbers[-1])
            elif 'open' in text and 'price' not in text:
                numbers = re.findall(r'[\d,]+\.?\d*', item.get_text())
                if numbers:
                    open_price = self._parse_number(numbers[-1])
            elif 'high' in text:
                numbers = re.findall(r'[\d,]+\.?\d*', item.get_text())
                if numbers:
                    day_high = self._parse_number(numbers[-1])
            elif 'low' in text:
                numbers = re.findall(r'[\d,]+\.?\d*', item.get_text())
                if numbers:
                    day_low = self._parse_number(numbers[-1])

        # Parse from data_dict
        if 'prev. close' in data_dict:
            prev_close = self._parse_number(data_dict['prev. close'])
        if 'open' in data_dict:
            open_price = self._parse_number(data_dict['open'])
        if "day's range" in data_dict:
            range_text = data_dict["day's range"]
            range_parts = range_text.split('-')
            if len(range_parts) == 2:
                day_low = self._parse_number(range_parts[0])
                day_high = self._parse_number(range_parts[1])

        # Fallback calculations
        if current_price:
            if not prev_close and change_amount:
                prev_close = current_price - change_amount
            if not change_amount and prev_close:
                change_amount = current_price - prev_close
            if not change_percent and prev_close and prev_close != 0:
                change_percent = ((current_price - prev_close) / prev_close) * 100

        if not current_price:
            raise ValueError("Could not parse price from Investing.com")

        price_data = PriceData(
            current_price=round(current_price, 2),
            currency="GBP",  # London Cocoa is in British Pounds
            unit="per tonne",
            timestamp=datetime.now(),
            change_amount=round(change_amount, 2) if change_amount else 0.0,
            change_percent=round(change_percent, 2) if change_percent else 0.0,
            day_high=round(day_high, 2) if day_high else round(current_price, 2),
            day_low=round(day_low, 2) if day_low else round(current_price, 2),
            volume=None,  # Volume not easily available from scraping
            open_price=round(open_price, 2) if open_price else round(current_price, 2),
            previous_close=round(prev_close, 2) if prev_close else round(current_price, 2),
        )

        self._cache[cache_key] = price_data
        return price_data

    def get_price_comparison(self) -> PriceComparison:
        """
        Get price comparison over different time periods.
        Note: Limited historical data available from scraping.
        """
        cache_key = "price_comparison"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get current price first
        current_data = self.get_current_price()
        current_price = current_data.current_price

        # For historical comparison, we'll try to scrape historical page
        # or provide limited data
        soup = self._fetch_page(self.HISTORICAL_URL)

        historical_prices = []
        if soup:
            # Try to find historical data table
            rows = soup.select('table tbody tr, [data-test="historical-data-table"] tr')
            for row in rows[:365]:  # Up to 1 year of data
                cells = row.select('td')
                if len(cells) >= 2:
                    date_text = cells[0].get_text(strip=True)
                    price_text = cells[1].get_text(strip=True)
                    price = self._parse_number(price_text)
                    if price:
                        try:
                            # Try to parse date
                            date = datetime.strptime(date_text, "%b %d, %Y")
                            historical_prices.append((date, price))
                        except:
                            pass

        # Calculate comparisons
        now = datetime.now()

        def get_price_at_days_ago(days: int) -> Optional[float]:
            target_date = now - timedelta(days=days)
            # Find closest price to target date
            for date, price in historical_prices:
                if date <= target_date:
                    return price
            return None

        def calc_change(old_price: Optional[float], new_price: float) -> Optional[float]:
            if old_price and old_price > 0:
                return round(((new_price - old_price) / old_price) * 100, 2)
            return None

        price_1_week = get_price_at_days_ago(7)
        price_1_month = get_price_at_days_ago(30)
        price_3_months = get_price_at_days_ago(90)
        price_6_months = get_price_at_days_ago(180)
        price_1_year = get_price_at_days_ago(365)

        comparison = PriceComparison(
            current_price=current_price,
            price_1_week_ago=price_1_week,
            price_1_month_ago=price_1_month,
            price_3_months_ago=price_3_months,
            price_6_months_ago=price_6_months,
            price_1_year_ago=price_1_year,
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
        Calculate technical indicators for London Cocoa.
        """
        cache_key = "technical_indicators"
        if cache_key in self._cache:
            return self._cache[cache_key]

        current_data = self.get_current_price()
        current_price = current_data.current_price

        # Try to get 52-week high/low from the page
        soup = self._fetch_page(self.INVESTING_URL)

        week_52_high = current_price
        week_52_low = current_price

        if soup:
            # Look for 52-week range
            for elem in soup.select('[class*="key-info"], [class*="overview"], dd, span'):
                text = elem.get_text(strip=True).lower()
                if '52' in text and 'week' in text:
                    numbers = re.findall(r'[\d,]+\.?\d*', elem.get_text())
                    if len(numbers) >= 2:
                        vals = [self._parse_number(n) for n in numbers if self._parse_number(n)]
                        if len(vals) >= 2:
                            week_52_low = min(vals)
                            week_52_high = max(vals)

        # If we couldn't find 52-week data, estimate from historical
        comparison = self.get_price_comparison()
        if comparison.price_1_year_ago:
            prices = [p for p in [
                current_price,
                comparison.price_1_week_ago,
                comparison.price_1_month_ago,
                comparison.price_3_months_ago,
                comparison.price_6_months_ago,
                comparison.price_1_year_ago
            ] if p is not None]
            if prices:
                week_52_high = max(week_52_high, max(prices))
                week_52_low = min(week_52_low, min(prices))

        price_vs_52_high = (current_price / week_52_high * 100) if week_52_high else 100
        price_vs_52_low = ((current_price - week_52_low) / week_52_low * 100) if week_52_low else 0

        indicators = TechnicalIndicators(
            week_52_high=round(week_52_high, 2),
            week_52_low=round(week_52_low, 2),
            week_52_high_date=None,  # Not available from scraping
            week_52_low_date=None,
            moving_avg_50=None,  # Would need more historical data
            moving_avg_200=None,
            avg_volume=None,
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
            self._client.close()
        except:
            pass
