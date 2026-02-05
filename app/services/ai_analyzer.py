"""
AI Analyzer service using Groq for generating market insights and analysis.
"""

import json
from typing import Optional
from datetime import datetime
from groq import Groq
from cachetools import TTLCache

from app.config import get_settings
from app.models.schemas import (
    PriceData,
    PriceComparison,
    TechnicalIndicators,
    NewsArticle,
    MarketOverview,
    MarketOutlook,
)


class AIAnalyzer:
    """
    Uses Groq's LLM to analyze cocoa market data and generate insights.
    """

    def __init__(self):
        self.settings = get_settings()
        self._cache = TTLCache(maxsize=50, ttl=self.settings.cache_ttl)

        if self.settings.groq_api_key:
            self.client = Groq(api_key=self.settings.groq_api_key)
        else:
            self.client = None

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        """
        Make a call to Groq's API.

        Args:
            system_prompt: System message for context
            user_prompt: User message with the actual query

        Returns:
            str: Model's response
        """
        if not self.client:
            raise ValueError("Groq API key not configured")

        response = self.client.chat.completions.create(
            model=self.settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        return response.choices[0].message.content

    def generate_market_overview(
        self,
        price_data: PriceData,
        price_comparison: PriceComparison,
        news_articles: list[NewsArticle],
        key_factors: list[dict],
    ) -> MarketOverview:
        """
        Generate a comprehensive market overview using AI.

        Args:
            price_data: Current price information
            price_comparison: Historical price comparisons
            news_articles: Recent news articles
            key_factors: Key factors identified from news

        Returns:
            MarketOverview: AI-generated market overview
        """
        cache_key = f"overview_{price_data.current_price}_{len(news_articles)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Prepare news summaries for the prompt
        news_summaries = []
        for article in news_articles[:10]:  # Limit to top 10
            news_summaries.append(
                f"- {article.title} (Importance: {article.importance_score:.1f}, "
                f"Sentiment: {article.sentiment or 'N/A'})"
            )

        # Prepare key factors
        factors_text = "\n".join(
            f"- {f['factor']}: {f['mentions']} mentions, importance {f['importance']}"
            for f in key_factors[:5]
        )

        system_prompt = """You are an expert commodities analyst specializing in cocoa markets.
        Provide clear, concise, and actionable market analysis. Focus on facts and avoid speculation.
        Always respond with valid JSON matching the required format."""

        user_prompt = f"""Analyze the current cocoa market based on this data:

CURRENT PRICE DATA:
- Current Price: ${price_data.current_price} per metric ton
- Daily Change: {price_data.change_percent:+.2f}%
- Day Range: ${price_data.day_low} - ${price_data.day_high}

PRICE CHANGES:
- 1 Week: {price_comparison.change_1_week or 'N/A'}%
- 1 Month: {price_comparison.change_1_month or 'N/A'}%
- 3 Months: {price_comparison.change_3_months or 'N/A'}%
- 1 Year: {price_comparison.change_1_year or 'N/A'}%

KEY FACTORS IDENTIFIED:
{factors_text}

RECENT NEWS:
{chr(10).join(news_summaries)}

Provide a market overview in this JSON format:
{{
    "summary": "2-3 sentence summary of current market conditions",
    "key_factors": ["factor 1", "factor 2", "factor 3"],
    "supply_conditions": "brief description of supply situation",
    "demand_conditions": "brief description of demand situation",
    "weather_impact": "any weather-related impacts or null",
    "geopolitical_factors": "any geopolitical factors or null"
}}

Respond ONLY with valid JSON, no other text."""

        try:
            response = self._call_groq(system_prompt, user_prompt)

            # Parse the JSON response
            # Clean up the response in case it has markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            data = json.loads(response)

            overview = MarketOverview(
                summary=data.get("summary", "Market analysis temporarily unavailable"),
                key_factors=data.get("key_factors", []),
                supply_conditions=data.get("supply_conditions"),
                demand_conditions=data.get("demand_conditions"),
                weather_impact=data.get("weather_impact"),
                geopolitical_factors=data.get("geopolitical_factors"),
            )

            self._cache[cache_key] = overview
            return overview

        except Exception as e:
            # Return a default overview if AI analysis fails
            return MarketOverview(
                summary=f"Cocoa is currently trading at ${price_data.current_price} per metric ton, "
                f"with a daily change of {price_data.change_percent:+.2f}%.",
                key_factors=[f["factor"] for f in key_factors[:3]] if key_factors else [],
                supply_conditions=None,
                demand_conditions=None,
                weather_impact=None,
                geopolitical_factors=None,
            )

    def generate_market_outlook(
        self,
        price_data: PriceData,
        price_comparison: PriceComparison,
        technical_indicators: TechnicalIndicators,
        news_articles: list[NewsArticle],
    ) -> MarketOutlook:
        """
        Generate market outlook and predictions using AI.

        Args:
            price_data: Current price information
            price_comparison: Historical price comparisons
            technical_indicators: Technical analysis data
            news_articles: Recent news articles

        Returns:
            MarketOutlook: AI-generated market outlook
        """
        cache_key = f"outlook_{price_data.current_price}_{technical_indicators.week_52_high}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Prepare news for context
        news_context = "\n".join(
            f"- {a.title} ({a.sentiment or 'neutral'})"
            for a in news_articles[:5]
        )

        system_prompt = """You are an expert commodities analyst specializing in cocoa markets.
        Provide balanced market outlooks based on available data. Be clear about uncertainties.
        Always respond with valid JSON matching the required format."""

        user_prompt = f"""Generate a cocoa market outlook based on this data:

CURRENT SITUATION:
- Price: ${price_data.current_price}/MT
- 52-Week High: ${technical_indicators.week_52_high}
- 52-Week Low: ${technical_indicators.week_52_low}
- Price vs 52W High: {technical_indicators.price_vs_52_high_percent:.1f}%
- 50-Day MA: ${technical_indicators.moving_avg_50 or 'N/A'}
- 200-Day MA: ${technical_indicators.moving_avg_200 or 'N/A'}

RECENT PRICE TRENDS:
- 1 Month Change: {price_comparison.change_1_month or 'N/A'}%
- 3 Month Change: {price_comparison.change_3_months or 'N/A'}%
- 1 Year Change: {price_comparison.change_1_year or 'N/A'}%

RECENT NEWS SENTIMENT:
{news_context}

Provide an outlook in this JSON format:
{{
    "short_term_outlook": "1-4 week outlook",
    "medium_term_outlook": "1-3 month outlook",
    "long_term_outlook": "3-12 month outlook or null if uncertain",
    "trends_to_watch": ["trend 1", "trend 2", "trend 3"],
    "risk_factors": ["risk 1", "risk 2"],
    "opportunities": ["opportunity 1", "opportunity 2"],
    "confidence_level": "low/medium/high"
}}

Respond ONLY with valid JSON, no other text."""

        try:
            response = self._call_groq(system_prompt, user_prompt)

            # Clean up and parse JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            data = json.loads(response)

            outlook = MarketOutlook(
                short_term_outlook=data.get(
                    "short_term_outlook", "Analysis pending"
                ),
                medium_term_outlook=data.get(
                    "medium_term_outlook", "Analysis pending"
                ),
                long_term_outlook=data.get("long_term_outlook"),
                trends_to_watch=data.get("trends_to_watch", []),
                risk_factors=data.get("risk_factors", []),
                opportunities=data.get("opportunities", []),
                confidence_level=data.get("confidence_level", "medium"),
            )

            self._cache[cache_key] = outlook
            return outlook

        except Exception as e:
            # Return a default outlook if AI analysis fails
            return MarketOutlook(
                short_term_outlook="Market analysis temporarily unavailable. "
                "Please check back later for updated insights.",
                medium_term_outlook="Unable to generate medium-term outlook at this time.",
                long_term_outlook=None,
                trends_to_watch=[],
                risk_factors=["Data temporarily unavailable"],
                opportunities=[],
                confidence_level="low",
            )

    def enhance_news_article(self, article: NewsArticle) -> NewsArticle:
        """
        Use AI to enhance news article with deeper analysis.

        Args:
            article: NewsArticle to enhance

        Returns:
            Enhanced NewsArticle with AI-generated insights
        """
        if not self.client:
            return article

        system_prompt = """You are a cocoa market expert. Analyze news headlines
        for their potential impact on cocoa prices. Be concise and specific."""

        user_prompt = f"""Analyze this cocoa-related news:

Title: {article.title}
Summary: {article.summary or 'No summary available'}

Provide a brief (1-2 sentence) analysis of how this might impact cocoa prices.
Response should be plain text, not JSON."""

        try:
            response = self._call_groq(system_prompt, user_prompt)
            article.impact_analysis = response.strip()
        except Exception:
            pass

        return article

    def generate_quick_summary(
        self, price_data: PriceData, news_count: int
    ) -> str:
        """
        Generate a quick one-line summary for the dashboard.

        Args:
            price_data: Current price data
            news_count: Number of recent news articles

        Returns:
            str: Quick summary string
        """
        direction = "up" if price_data.change_percent > 0 else "down"
        return (
            f"Cocoa at ${price_data.current_price}/MT, "
            f"{direction} {abs(price_data.change_percent):.1f}% today. "
            f"{news_count} relevant news items."
        )

    def is_available(self) -> bool:
        """Check if the AI analyzer is available (API key configured)."""
        return self.client is not None

    def clear_cache(self):
        """Clear the analysis cache."""
        self._cache.clear()
