"""News filtering and impact scoring."""

import json
import os
import logging
import re
from typing import List, Dict, Any, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default watchlist path
WATCHLIST_PATH = Path("config/watchlists.json")


def load_watchlists(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load watchlist configuration."""
    path = path or WATCHLIST_PATH
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Watchlist not found: {path}, using defaults")
        return get_default_watchlists()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid watchlist JSON: {e}")
        return get_default_watchlists()


def get_default_watchlists() -> Dict[str, Any]:
    """Return default watchlist if config not found."""
    return {
        "tickers": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"],
        "ai_keywords": [
            "AI", "artificial intelligence", "LLM", "GPT", "ChatGPT",
            "OpenAI", "Anthropic", "NVIDIA", "GPU", "inference", "training"
        ],
        "macro_keywords": [
            "CPI", "FOMC", "Fed", "interest rate", "Treasury", "inflation"
        ],
        "trusted_sources": ["reuters.com", "bloomberg.com", "sec.gov"]
    }


def extract_tickers(text: str, watchlist: List[str]) -> List[str]:
    """
    Extract ticker symbols from text.
    
    Only returns tickers that are in the watchlist.
    """
    # Common patterns for ticker mentions
    # $AAPL, AAPL, (AAPL), etc.
    text_upper = text.upper()
    found = []
    
    for ticker in watchlist:
        # Check various patterns
        patterns = [
            f"${ticker}",  # $AAPL
            f"({ticker})",  # (AAPL)
            f" {ticker} ",  # AAPL
            f" {ticker}.",  # AAPL.
            f" {ticker},",  # AAPL,
            f" {ticker}'",  # AAPL's
        ]
        
        for pattern in patterns:
            if pattern.upper() in text_upper or text_upper.startswith(ticker + " "):
                if ticker not in found:
                    found.append(ticker)
                break
    
    return found


def matches_keywords(text: str, keywords: List[str]) -> List[str]:
    """
    Check if text matches any keywords.
    
    Returns list of matched keywords.
    """
    text_lower = text.lower()
    matched = []
    
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)
    
    return matched


def calculate_impact_score(
    news_item: Dict[str, Any],
    watchlists: Dict[str, Any]
) -> int:
    """
    Calculate impact score for a news item.
    
    Score is 0-100 where higher = more important.
    """
    score = 30  # Base score
    
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")
    category = news_item.get("category", "general")
    source = news_item.get("source", "")
    combined = title + " " + summary
    
    # Ticker matches
    tickers = extract_tickers(combined, watchlists.get("tickers", []))
    score += len(tickers) * 15  # +15 per matched ticker
    
    # AI keyword matches
    ai_keywords = matches_keywords(combined, watchlists.get("ai_keywords", []))
    score += min(len(ai_keywords) * 10, 30)  # Up to +30
    
    # Macro keyword matches
    macro_keywords = matches_keywords(combined, watchlists.get("macro_keywords", []))
    score += min(len(macro_keywords) * 10, 30)  # Up to +30
    
    # Category bonuses
    if category == "earnings":
        score += 15
    elif category == "macro":
        score += 10
    elif category == "ai":
        score += 10
    
    # Trusted source bonus
    trusted = watchlists.get("trusted_sources", [])
    if any(ts in source.lower() for ts in trusted):
        score += 10
    
    # Action words bonus
    action_words = ["launches", "announces", "releases", "acquires", "reports", "warns"]
    if any(word in combined.lower() for word in action_words):
        score += 10
    
    return min(100, max(0, score))


def should_post(
    news_item: Dict[str, Any],
    watchlists: Dict[str, Any],
    min_score: int = 40
) -> bool:
    """
    Determine if a news item should be posted.
    
    Args:
        news_item: The news item to check
        watchlists: Watchlist configuration
        min_score: Minimum impact score to post
    
    Returns:
        True if the item should be posted.
    """
    # Calculate score
    score = calculate_impact_score(news_item, watchlists)
    news_item["impact_score"] = score  # Store for later use
    
    if score < min_score:
        return False
    
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")
    category = news_item.get("category", "general")
    combined = title + " " + summary
    
    # Category-specific rules
    if category == "earnings":
        # Earnings: always post if watchlist ticker
        tickers = extract_tickers(combined, watchlists.get("tickers", []))
        return len(tickers) > 0
    
    elif category == "ai":
        # AI: need keyword match + action word
        ai_keywords = matches_keywords(combined, watchlists.get("ai_keywords", []))
        action_words = ["launches", "announces", "releases", "introduces", "unveils"]
        has_action = any(word in combined.lower() for word in action_words)
        return len(ai_keywords) > 0 and (has_action or score >= 60)
    
    elif category == "macro":
        # Macro: need macro keyword match
        macro_keywords = matches_keywords(combined, watchlists.get("macro_keywords", []))
        return len(macro_keywords) > 0
    
    else:
        # General: high score threshold
        return score >= 60


def filter_news(
    items: List[Dict[str, Any]],
    watchlists: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Filter news items based on watchlists and scoring.
    
    Returns only items that should be posted.
    """
    if watchlists is None:
        watchlists = load_watchlists()
    
    filtered = []
    
    for item in items:
        if should_post(item, watchlists):
            # Add matched tickers to item
            combined = item.get("title", "") + " " + item.get("summary", "")
            item["tickers"] = extract_tickers(combined, watchlists.get("tickers", []))
            item["matched_keywords"] = {
                "ai": matches_keywords(combined, watchlists.get("ai_keywords", [])),
                "macro": matches_keywords(combined, watchlists.get("macro_keywords", []))
            }
            filtered.append(item)
    
    # Sort by impact score
    filtered.sort(key=lambda x: x.get("impact_score", 0), reverse=True)
    
    return filtered


def categorize_item(item: Dict[str, Any]) -> str:
    """
    Determine the best category/channel for a news item.
    
    Returns: "ai", "earnings", "macro", "market_alerts"
    """
    category = item.get("category", "general")
    
    if category == "earnings":
        return "earnings"
    elif category == "macro":
        return "macro"
    elif category == "ai":
        return "ai"
    
    # Check matched keywords
    matched = item.get("matched_keywords", {})
    if matched.get("macro"):
        return "macro"
    elif matched.get("ai"):
        return "ai"
    
    # Check tickers
    if item.get("tickers"):
        return "earnings"
    
    return "market_alerts"
