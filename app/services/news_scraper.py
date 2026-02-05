"""
News scraper service for fetching cocoa-related news from multiple sources.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser
from cachetools import TTLCache
import httpx
import re

from app.models.schemas import NewsArticle
from app.config import get_settings


class NewsScraper:
    """Scrapes and aggregates cocoa-related news from multiple sources."""

    # Keywords for filtering cocoa-related news
    COCOA_KEYWORDS = [
        "cocoa",
        "cacao",
        "chocolate",
        "ivory coast",
        "côte d'ivoire",
        "ghana cocoa",
        "cocoa beans",
        "cocoa prices",
        "cocoa futures",
        "cocoa production",
        "cocoa harvest",
        "cocoa farmers",
        "cocoa market",
        "commodity cocoa",
    ]

    # Secondary keywords that might indicate relevance
    SECONDARY_KEYWORDS = [
        "commodity",
        "agricultural",
        "west africa",
        "soft commodities",
        "futures",
        "crops",
        "harvest",
        "farming",
    ]

    def __init__(self):
        self.settings = get_settings()
        self._cache = TTLCache(maxsize=100, ttl=self.settings.cache_ttl)
        self._http_client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

    def _is_cocoa_related(self, title: str, summary: str = "") -> bool:
        """
        Check if an article is related to cocoa.

        Args:
            title: Article title
            summary: Article summary/description

        Returns:
            bool: True if article is cocoa-related
        """
        text = f"{title} {summary}".lower()

        # Check primary keywords (strong match)
        for keyword in self.COCOA_KEYWORDS:
            if keyword.lower() in text:
                return True

        return False

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        try:
            return date_parser.parse(date_str)
        except (ValueError, TypeError):
            return None

    def _fetch_rss_feed(self, url: str, source_name: str) -> list[NewsArticle]:
        """
        Fetch and parse an RSS feed.

        Args:
            url: RSS feed URL
            source_name: Name of the news source

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))

                # Filter for cocoa-related news
                if self._is_cocoa_related(title, summary):
                    # Clean up summary (remove HTML tags)
                    if summary:
                        soup = BeautifulSoup(summary, "html.parser")
                        summary = soup.get_text(separator=" ", strip=True)
                        # Truncate long summaries
                        if len(summary) > 500:
                            summary = summary[:497] + "..."

                    article = NewsArticle(
                        title=title,
                        summary=summary if summary else None,
                        url=link,
                        source=source_name,
                        published_date=self._parse_date(published),
                        importance_score=0.5,  # Default score, will be updated by analyzer
                    )
                    articles.append(article)

        except Exception as e:
            print(f"Error fetching RSS feed {url}: {e}")

        return articles

    def _scrape_investing_com(self) -> list[NewsArticle]:
        """
        Scrape cocoa news from Investing.com.

        Returns:
            List of NewsArticle objects
        """
        articles = []
        url = "https://www.investing.com/commodities/us-cocoa-news"

        try:
            response = self._http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find news articles
            news_items = soup.select("article.js-article-item, div.articleItem")

            for item in news_items[:10]:  # Limit to 10 articles
                title_elem = item.select_one("a.title, .title a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem.get("href", "")

                if link and not link.startswith("http"):
                    link = f"https://www.investing.com{link}"

                # Get summary if available
                summary_elem = item.select_one("p, .textDiv")
                summary = summary_elem.get_text(strip=True) if summary_elem else None

                # Get date if available
                date_elem = item.select_one("time, .date, span.date")
                date_str = date_elem.get("datetime", date_elem.get_text()) if date_elem else None

                article = NewsArticle(
                    title=title,
                    summary=summary,
                    url=link,
                    source="Investing.com",
                    published_date=self._parse_date(date_str),
                    importance_score=0.6,  # Higher default for commodity-specific source
                )
                articles.append(article)

        except Exception as e:
            print(f"Error scraping Investing.com: {e}")

        return articles

    def _scrape_reuters_commodities(self) -> list[NewsArticle]:
        """
        Fetch cocoa news from Reuters commodities section via RSS.

        Returns:
            List of NewsArticle objects
        """
        # Reuters commodities RSS
        rss_url = "https://www.reutersagency.com/feed/?best-topics=commodities&post_type=best"
        return self._fetch_rss_feed(rss_url, "Reuters")

    def _search_google_news(self) -> list[NewsArticle]:
        """
        Search for cocoa news via Google News RSS.

        Returns:
            List of NewsArticle objects
        """
        articles = []

        # Google News RSS search for cocoa
        search_queries = [
            "cocoa+prices",
            "cocoa+market",
            "cocoa+futures",
            "cocoa+production+africa",
        ]

        for query in search_queries:
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

            try:
                feed = feedparser.parse(url)

                for entry in feed.entries[:5]:  # Limit per query
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    # Extract source from title (Google News format: "Title - Source")
                    source = "Google News"
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        if len(parts) == 2:
                            title, source = parts

                    article = NewsArticle(
                        title=title,
                        summary=None,
                        url=link,
                        source=source,
                        published_date=self._parse_date(published),
                        importance_score=0.5,
                    )
                    articles.append(article)

            except Exception as e:
                print(f"Error fetching Google News for {query}: {e}")

        return articles

    def fetch_all_news(self, limit: Optional[int] = None) -> list[NewsArticle]:
        """
        Fetch news from all sources and combine them.

        Args:
            limit: Maximum number of articles to return

        Returns:
            List of NewsArticle objects sorted by date
        """
        cache_key = f"all_news_{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        all_articles = []

        # Fetch from multiple sources
        all_articles.extend(self._search_google_news())
        all_articles.extend(self._scrape_investing_com())

        # Fetch from RSS feeds
        rss_sources = [
            ("https://www.investing.com/rss/news_301.rss", "Investing.com"),
            (
                "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
                "CNBC",
            ),
        ]

        for rss_url, source_name in rss_sources:
            all_articles.extend(self._fetch_rss_feed(rss_url, source_name))

        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # Sort by date (most recent first), handling None dates
        unique_articles.sort(
            key=lambda x: x.published_date or datetime.min, reverse=True
        )

        # Apply limit
        if limit:
            unique_articles = unique_articles[: limit]
        else:
            unique_articles = unique_articles[: self.settings.news_limit]

        self._cache[cache_key] = unique_articles
        return unique_articles

    def search_news(self, query: str) -> list[NewsArticle]:
        """
        Search for specific news related to a query.

        Args:
            query: Search query

        Returns:
            List of matching NewsArticle objects
        """
        # Combine query with cocoa for more relevant results
        search_query = f"cocoa {query}"
        encoded_query = search_query.replace(" ", "+")

        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        articles = []
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                source = "Google News"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        title, source = parts

                article = NewsArticle(
                    title=title,
                    summary=None,
                    url=link,
                    source=source,
                    published_date=self._parse_date(published),
                    importance_score=0.5,
                )
                articles.append(article)

        except Exception as e:
            print(f"Error searching news: {e}")

        return articles

    def clear_cache(self):
        """Clear the news cache."""
        self._cache.clear()

    def __del__(self):
        """Cleanup HTTP client on destruction."""
        try:
            self._http_client.close()
        except Exception:
            pass
