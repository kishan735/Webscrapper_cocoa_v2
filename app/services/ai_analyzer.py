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
            max_tokens=2500,
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
        Focus on NEWS ANALYSIS and FACTORS affecting prices.
        """
        cache_key = f"overview_{price_data.current_price}_{len(news_articles)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Prepare detailed news for analysis
        news_details = []
        for article in news_articles[:12]:
            news_details.append(
                f"- HEADLINE: {article.title}\n"
                f"  SUMMARY: {article.summary or 'No summary'}\n"
                f"  SENTIMENT: {article.sentiment or 'neutral'}"
            )

        system_prompt = """You are an expert cocoa commodities analyst providing ACTIONABLE intelligence to traders.

CRITICAL RULES - FOLLOW EXACTLY:
1. NEVER use vague phrases like "supply is tight", "demand is weak", "pressure on prices"
2. ALWAYS explain the SPECIFIC REASON: WHO is doing WHAT, WHERE, and WHY it matters
3. Every statement must answer: "What specific event/action is causing this?"
4. Name specific countries, companies, weather events, policies from the news
5. If news doesn't provide specific reasons, say "No specific details available in current news"

BAD EXAMPLE: "Supply conditions are tight, putting pressure on prices"
GOOD EXAMPLE: "Ivory Coast's Cocobod reported 15% lower arrivals in January due to black pod disease in the Sud-Comoé region, reducing available supply for Q1 shipments"

Always respond with valid JSON only."""

        user_prompt = f"""Analyze these cocoa news articles. For each point, provide SPECIFIC REASONS from the news - not generic statements.

NEWS TO ANALYZE:
{chr(10).join(news_details)}

Provide analysis in JSON format. REMEMBER: Every statement needs a SPECIFIC REASON from the news.

{{
    "summary": "2-3 sentences with SPECIFIC events driving the market. Example: 'Ghana's cocoa regulator COCOBOD announced a 20% increase in farmgate prices effective March 1, which is expected to...' NOT 'Supply concerns are affecting prices'",
    "key_factors": [
        "SPECIFIC EVENT from news → SPECIFIC IMPACT (e.g., 'Harmattan winds in Ghana drying pods earlier than usual → May reduce mid-crop yield by estimated 10-15%')",
        "Another SPECIFIC factor with clear cause-effect",
        "Third SPECIFIC factor"
    ],
    "supply_conditions": "SPECIFIC supply situation: What exactly is happening? Which country? What numbers? What cause? Example: 'Ivory Coast arrivals down 23% YoY through January per CCC data, attributed to...' If no specifics in news, say 'No specific supply data in current news'",
    "demand_conditions": "SPECIFIC demand situation: Which buyers? What trends? Example: 'European grinders processed 12% less in Q4 per ECA, citing high prices deterring orders from...' If no specifics, say 'No specific demand data in current news'",
    "weather_impact": "SPECIFIC weather: What weather event? Where exactly? What impact? Example: 'Below-average rainfall in Ghana's Western Region (40mm vs 80mm normal) affecting pod development' or null if none mentioned",
    "geopolitical_factors": "SPECIFIC policy/political: What action? By whom? Example: 'Nigeria's export ban on raw beans effective Feb 1 to boost local processing' or null if none mentioned"
}}

If the news lacks specific details for any field, explicitly state that rather than making vague generalizations."""

        try:
            response = self._call_groq(system_prompt, user_prompt)

            # Parse the JSON response
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
            return MarketOverview(
                summary="Unable to analyze market news at this time.",
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
        Generate market outlook based on news factors and their potential impacts.
        """
        cache_key = f"outlook_{price_data.current_price}_{technical_indicators.week_52_high}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Prepare detailed news for analysis
        news_details = []
        for article in news_articles[:10]:
            news_details.append(
                f"- {article.title} ({article.sentiment or 'neutral'})\n"
                f"  {article.summary or ''}"
            )

        system_prompt = """You are a cocoa market analyst providing SPECIFIC, ACTIONABLE forward-looking analysis.

CRITICAL RULES:
1. NEVER say "prices may rise/fall" without explaining EXACTLY WHY based on specific news
2. Every outlook statement must reference a SPECIFIC factor from the news
3. Trends to watch must be SPECIFIC upcoming events with dates if available
4. Risks must explain the MECHANISM of how they would affect prices

BAD: "Prices may face upward pressure in the short term"
GOOD: "Ghana's mid-crop harvest (April-June) typically adds 20% to annual supply, but black pod disease reports suggest this year's yield may be 15% below normal, maintaining tight supply until main crop in October"

Always respond with valid JSON only."""

        user_prompt = f"""Based on the news below, provide outlook with SPECIFIC REASONS for each prediction.

NEWS:
{chr(10).join(news_details)}

PRICE CONTEXT:
- Current: £{price_data.current_price}/tonne (London)
- 52-Week Range: £{technical_indicators.week_52_low} - £{technical_indicators.week_52_high}

Provide outlook with SPECIFIC CAUSAL EXPLANATIONS:

{{
    "short_term_outlook": "1-4 weeks: What SPECIFIC factors from news will drive prices? Name the event, the mechanism, the expected impact. Example: 'Ivory Coast's mid-crop arrivals beginning late February will be key - if arrivals track 20% below last year as current trends suggest, expect continued tightness'",
    "medium_term_outlook": "1-3 months: What SPECIFIC events are coming up? Example: 'European Easter chocolate demand (peaks March) combined with reported inventory drawdowns at Rotterdam warehouses suggests...'",
    "long_term_outlook": "3-12 months: SPECIFIC structural factors only. Example: 'ICCO forecasts 150,000 tonne deficit for 2024/25 season due to aging tree stock in Ghana' or null if no specific long-term data",
    "trends_to_watch": [
        "SPECIFIC upcoming event with date if known → Why it matters. Example: 'Ghana COCOBOD farmgate price review (expected March) → Higher prices would incentivize production but squeeze processor margins'",
        "Another specific trend with clear market relevance",
        "Third specific trend"
    ],
    "risk_factors": [
        "SPECIFIC risk → MECHANISM of price impact. Example: 'El Niño forecast through Q2 → Typically brings drought to West Africa, reduced pod development, bullish for prices'",
        "Another specific risk with clear mechanism"
    ],
    "opportunities": [
        "SPECIFIC opportunity from news → How to act on it",
        "Another opportunity"
    ],
    "confidence_level": "low/medium/high - explain why based on quality of news data"
}}

If news lacks specific forward-looking information, state that clearly rather than guessing."""

        try:
            response = self._call_groq(system_prompt, user_prompt)

            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            data = json.loads(response)

            outlook = MarketOutlook(
                short_term_outlook=data.get("short_term_outlook", "Analysis pending"),
                medium_term_outlook=data.get("medium_term_outlook", "Analysis pending"),
                long_term_outlook=data.get("long_term_outlook"),
                trends_to_watch=data.get("trends_to_watch", []),
                risk_factors=data.get("risk_factors", []),
                opportunities=data.get("opportunities", []),
                confidence_level=data.get("confidence_level", "medium"),
            )

            self._cache[cache_key] = outlook
            return outlook

        except Exception as e:
            return MarketOutlook(
                short_term_outlook="Market analysis temporarily unavailable.",
                medium_term_outlook="Unable to generate outlook at this time.",
                long_term_outlook=None,
                trends_to_watch=[],
                risk_factors=["Data temporarily unavailable"],
                opportunities=[],
                confidence_level="low",
            )

    def enhance_news_article(self, article: NewsArticle) -> NewsArticle:
        """
        Use AI to enhance news article with deeper analysis.
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
