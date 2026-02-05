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

        system_prompt = """You are an expert cocoa commodities analyst. Your job is to analyze NEWS and identify FACTORS affecting cocoa prices.

IMPORTANT RULES:
- Focus on analyzing the NEWS CONTENT, not just restating price numbers
- Identify specific factors from the news: weather, disease, politics, demand shifts, currency, etc.
- Explain the CAUSE-EFFECT relationship: what is happening and WHY it affects cocoa prices
- Be specific about countries, regions, and events mentioned in the news
- DO NOT just summarize price movements - explain WHAT IS DRIVING them

Always respond with valid JSON only."""

        user_prompt = f"""Analyze these cocoa market news articles and explain what factors are currently affecting cocoa prices:

NEWS ARTICLES TO ANALYZE:
{chr(10).join(news_details)}

CURRENT PRICE CONTEXT (for reference only):
- Price: ${price_data.current_price}/MT, Daily change: {price_data.change_percent:+.2f}%

Based on the NEWS above, provide analysis in this JSON format:
{{
    "summary": "2-3 sentences explaining the CURRENT SITUATION based on news - what events/factors are driving the market right now. Do NOT just state price numbers.",
    "key_factors": [
        "Factor 1: [Specific factor from news] - [How it affects cocoa prices]",
        "Factor 2: [Specific factor from news] - [How it affects cocoa prices]",
        "Factor 3: [Specific factor from news] - [How it affects cocoa prices]"
    ],
    "supply_conditions": "Based on news: What's happening with cocoa supply? (production issues, harvest conditions, farmer situations in Ivory Coast/Ghana, disease outbreaks, etc.)",
    "demand_conditions": "Based on news: What's happening with cocoa demand? (chocolate industry, consumer trends, major buyers, seasonal demand, etc.)",
    "weather_impact": "Based on news: Any weather events affecting cocoa? (drought, floods, El Nino, harmattan winds, etc.) - null if no weather news",
    "geopolitical_factors": "Based on news: Any political/economic factors? (export policies, currency changes, trade disputes, farmer protests, government actions, etc.) - null if none mentioned"
}}

IMPORTANT: Extract insights FROM THE NEWS. Do not make up factors not mentioned in the articles."""

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

        system_prompt = """You are an expert cocoa market analyst providing forward-looking analysis.

IMPORTANT RULES:
- Base your outlook on the NEWS FACTORS, not just price trends
- Explain HOW each factor could impact prices going forward
- Be specific about CAUSE and EFFECT relationships
- Identify what traders and buyers should WATCH FOR
- Include both bullish and bearish factors
- DO NOT just predict price direction - explain WHY based on factors

Always respond with valid JSON only."""

        user_prompt = f"""Based on current cocoa market news, provide a forward-looking outlook:

RECENT NEWS & EVENTS:
{chr(10).join(news_details)}

PRICE CONTEXT:
- Current: ${price_data.current_price}/MT
- 52-Week Range: ${technical_indicators.week_52_low} - ${technical_indicators.week_52_high}
- YTD Change: {price_comparison.change_1_year or 'N/A'}%

Provide outlook in this JSON format:
{{
    "short_term_outlook": "1-4 weeks: Based on current news factors, what should we expect? Mention specific factors (e.g., 'Ongoing dry weather in Ivory Coast may continue to pressure supply, while...')",
    "medium_term_outlook": "1-3 months: What factors will play out over this period? (harvest seasons, demand cycles, policy changes mentioned in news)",
    "long_term_outlook": "3-12 months: Structural factors to consider (climate trends, industry changes, production capacity) - or null if too uncertain",
    "trends_to_watch": [
        "Trend 1: [Specific event/factor to monitor] - [Why it matters for cocoa prices]",
        "Trend 2: [Specific event/factor to monitor] - [Why it matters for cocoa prices]",
        "Trend 3: [Specific event/factor to monitor] - [Why it matters for cocoa prices]"
    ],
    "risk_factors": [
        "Risk 1: [Specific risk from news] - [Potential impact: bullish/bearish and why]",
        "Risk 2: [Specific risk from news] - [Potential impact: bullish/bearish and why]"
    ],
    "opportunities": [
        "Opportunity 1: [Potential positive development] - [How it could affect market]",
        "Opportunity 2: [Potential positive development] - [How it could affect market]"
    ],
    "confidence_level": "low/medium/high based on clarity of news signals"
}}

Focus on EXPLAINING factors and their IMPACTS, not just stating price predictions."""

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
