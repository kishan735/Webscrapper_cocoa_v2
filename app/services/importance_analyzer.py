"""
Importance analyzer for scoring news and factors based on their potential impact on cocoa prices.
"""

import re
from typing import Optional
from app.models.schemas import NewsArticle


class ImportanceAnalyzer:
    """
    Analyzes and scores news articles and market factors based on their
    potential impact on cocoa prices.
    """

    # High impact keywords with their base scores
    HIGH_IMPACT_KEYWORDS = {
        # Supply-related (high impact)
        "shortage": 0.9,
        "supply crisis": 0.95,
        "crop failure": 0.9,
        "disease outbreak": 0.85,
        "drought": 0.85,
        "flood": 0.8,
        "weather disaster": 0.85,
        "hurricane": 0.8,
        "pest": 0.75,
        "black pod": 0.85,
        "swollen shoot": 0.85,
        # Production regions
        "ivory coast": 0.8,
        "côte d'ivoire": 0.8,
        "ghana": 0.75,
        "nigeria": 0.65,
        "cameroon": 0.6,
        "ecuador": 0.55,
        "west africa": 0.75,
        # Price-related
        "price surge": 0.85,
        "record high": 0.85,
        "record low": 0.85,
        "price crash": 0.9,
        "rally": 0.7,
        "plunge": 0.8,
        # Policy and regulation
        "export ban": 0.9,
        "tariff": 0.75,
        "sanction": 0.8,
        "government intervention": 0.75,
        "regulation": 0.65,
        "subsidy": 0.6,
        # Market structure
        "futures": 0.6,
        "hedge": 0.5,
        "speculation": 0.65,
        "stockpile": 0.7,
        "inventory": 0.65,
    }

    # Medium impact keywords
    MEDIUM_IMPACT_KEYWORDS = {
        # Demand-related
        "chocolate demand": 0.55,
        "consumption": 0.5,
        "import": 0.5,
        "export": 0.55,
        # Quality and sustainability
        "quality": 0.45,
        "sustainable": 0.4,
        "fair trade": 0.35,
        "certification": 0.35,
        # Market analysis
        "forecast": 0.5,
        "outlook": 0.5,
        "analysis": 0.4,
        "report": 0.45,
        "estimate": 0.45,
        # Industry
        "processor": 0.5,
        "grinder": 0.55,
        "manufacturer": 0.45,
        "trader": 0.5,
    }

    # Sentiment modifiers
    POSITIVE_SENTIMENT = [
        "increase",
        "rise",
        "surge",
        "gain",
        "boost",
        "improve",
        "recovery",
        "strong",
        "bullish",
        "uptick",
        "grow",
    ]

    NEGATIVE_SENTIMENT = [
        "decrease",
        "fall",
        "drop",
        "decline",
        "loss",
        "weak",
        "bearish",
        "downturn",
        "slump",
        "crash",
        "concern",
        "fear",
        "risk",
        "threat",
        "crisis",
    ]

    # Time sensitivity keywords (recent events score higher)
    URGENCY_KEYWORDS = [
        "breaking",
        "urgent",
        "just in",
        "alert",
        "immediate",
        "today",
        "this week",
        "now",
    ]

    def calculate_importance_score(
        self, title: str, summary: Optional[str] = None
    ) -> float:
        """
        Calculate the importance score for a news article.

        Args:
            title: Article title
            summary: Article summary (optional)

        Returns:
            float: Importance score between 0 and 1
        """
        text = f"{title} {summary or ''}".lower()
        score = 0.3  # Base score

        # Check high impact keywords
        for keyword, keyword_score in self.HIGH_IMPACT_KEYWORDS.items():
            if keyword.lower() in text:
                score = max(score, keyword_score)

        # Check medium impact keywords (additive, but capped)
        medium_bonus = 0
        for keyword, keyword_score in self.MEDIUM_IMPACT_KEYWORDS.items():
            if keyword.lower() in text:
                medium_bonus += 0.1
        score += min(medium_bonus, 0.2)  # Cap medium bonus at 0.2

        # Urgency bonus
        for keyword in self.URGENCY_KEYWORDS:
            if keyword.lower() in text:
                score += 0.05
                break  # Only apply once

        # Ensure score is within bounds
        return min(max(score, 0.0), 1.0)

    def analyze_sentiment(self, title: str, summary: Optional[str] = None) -> str:
        """
        Analyze the sentiment of a news article.

        Args:
            title: Article title
            summary: Article summary (optional)

        Returns:
            str: 'positive', 'negative', or 'neutral'
        """
        text = f"{title} {summary or ''}".lower()

        positive_count = sum(1 for word in self.POSITIVE_SENTIMENT if word in text)
        negative_count = sum(1 for word in self.NEGATIVE_SENTIMENT if word in text)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def estimate_price_impact(
        self, title: str, summary: Optional[str] = None
    ) -> Optional[str]:
        """
        Estimate the potential price impact of a news event.

        Args:
            title: Article title
            summary: Article summary (optional)

        Returns:
            str: Brief description of potential price impact
        """
        text = f"{title} {summary or ''}".lower()

        # Supply disruption scenarios
        supply_keywords = ["shortage", "crop failure", "drought", "flood", "disease"]
        if any(kw in text for kw in supply_keywords):
            return "Potential supply disruption could push prices higher"

        # Demand scenarios
        if "demand" in text:
            if any(word in text for word in ["increase", "rise", "strong", "grow"]):
                return "Increased demand may support higher prices"
            elif any(word in text for word in ["decrease", "fall", "weak", "decline"]):
                return "Weakening demand may put downward pressure on prices"

        # Production scenarios
        if "production" in text or "harvest" in text:
            if any(word in text for word in ["increase", "rise", "bumper", "record"]):
                return "Higher production may lead to lower prices"
            elif any(word in text for word in ["decrease", "fall", "decline", "poor"]):
                return "Lower production may support higher prices"

        # Price movement reporting
        if "price" in text:
            if any(word in text for word in ["surge", "rally", "jump", "soar"]):
                return "Market showing bullish momentum"
            elif any(word in text for word in ["drop", "fall", "plunge", "crash"]):
                return "Market showing bearish momentum"

        # Weather impact
        if any(word in text for word in ["weather", "rain", "drought", "el niño"]):
            return "Weather conditions may affect upcoming harvests"

        # Policy impact
        if any(word in text for word in ["tariff", "ban", "sanction", "regulation"]):
            return "Policy changes may affect trade flows and prices"

        return None

    def analyze_article(self, article: NewsArticle) -> NewsArticle:
        """
        Analyze a news article and update its importance score and analysis.

        Args:
            article: NewsArticle to analyze

        Returns:
            Updated NewsArticle with importance score and analysis
        """
        article.importance_score = self.calculate_importance_score(
            article.title, article.summary
        )
        article.sentiment = self.analyze_sentiment(article.title, article.summary)
        article.impact_analysis = self.estimate_price_impact(
            article.title, article.summary
        )

        return article

    def analyze_articles(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """
        Analyze multiple articles and sort by importance.

        Args:
            articles: List of NewsArticle objects

        Returns:
            List of analyzed articles sorted by importance score
        """
        analyzed = [self.analyze_article(article) for article in articles]
        analyzed.sort(key=lambda x: x.importance_score, reverse=True)
        return analyzed

    def identify_key_factors(
        self, articles: list[NewsArticle]
    ) -> list[dict]:
        """
        Identify key factors affecting cocoa prices from news articles.

        Args:
            articles: List of analyzed NewsArticle objects

        Returns:
            List of key factors with their importance
        """
        factors = {}

        factor_patterns = [
            (r"weather|drought|flood|rain", "Weather conditions"),
            (r"disease|pest|black pod", "Crop diseases and pests"),
            (r"production|harvest|yield", "Production levels"),
            (r"demand|consumption", "Consumer demand"),
            (r"supply|shortage|surplus", "Supply situation"),
            (r"price|cost", "Price movements"),
            (r"export|import|trade", "Trade dynamics"),
            (r"ivory coast|ghana|west africa", "West African markets"),
            (r"regulation|government|policy", "Policy and regulation"),
            (r"currency|dollar|exchange", "Currency fluctuations"),
        ]

        for article in articles:
            text = f"{article.title} {article.summary or ''}".lower()

            for pattern, factor_name in factor_patterns:
                if re.search(pattern, text):
                    if factor_name not in factors:
                        factors[factor_name] = {
                            "name": factor_name,
                            "mention_count": 0,
                            "avg_importance": 0,
                            "total_importance": 0,
                        }
                    factors[factor_name]["mention_count"] += 1
                    factors[factor_name]["total_importance"] += article.importance_score

        # Calculate average importance and sort
        result = []
        for factor in factors.values():
            if factor["mention_count"] > 0:
                factor["avg_importance"] = round(
                    factor["total_importance"] / factor["mention_count"], 2
                )
                result.append(
                    {
                        "factor": factor["name"],
                        "mentions": factor["mention_count"],
                        "importance": factor["avg_importance"],
                    }
                )

        result.sort(key=lambda x: (x["importance"], x["mentions"]), reverse=True)
        return result
