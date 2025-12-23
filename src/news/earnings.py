"""Earnings calendar and detection."""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from src.news.sources import RSSFetcher, NewsItem
from src.common.time import now_utc, parse_iso

logger = logging.getLogger(__name__)


# Keywords indicating earnings content
EARNINGS_KEYWORDS = [
    "earnings", "quarterly results", "Q1", "Q2", "Q3", "Q4",
    "revenue", "EPS", "guidance", "outlook", "reports",
    "8-K", "10-Q", "10-K", "financial results"
]

# Keywords for earnings surprises
SURPRISE_KEYWORDS = [
    "beats", "misses", "exceeds", "falls short", "surpasses",
    "better than expected", "worse than expected"
]


def is_earnings_related(title: str, summary: str = "") -> bool:
    """Check if content is earnings-related."""
    combined = (title + " " + summary).lower()
    return any(kw.lower() in combined for kw in EARNINGS_KEYWORDS)


def detect_earnings_surprise(title: str, summary: str = "") -> Optional[str]:
    """
    Detect if this is an earnings beat or miss.
    
    Returns: "beat", "miss", or None
    """
    combined = (title + " " + summary).lower()
    
    beat_words = ["beats", "exceeds", "surpasses", "better than expected", "tops"]
    miss_words = ["misses", "falls short", "worse than expected", "below"]
    
    has_beat = any(word in combined for word in beat_words)
    has_miss = any(word in combined for word in miss_words)
    
    if has_beat and not has_miss:
        return "beat"
    elif has_miss and not has_beat:
        return "miss"
    return None


def extract_earnings_metrics(text: str) -> Dict[str, Any]:
    """
    Extract earnings metrics from text.
    
    Returns dict with EPS, revenue if found.
    """
    metrics = {}
    text_lower = text.lower()
    
    # EPS patterns: "$1.23 EPS", "EPS of $1.23", "earnings of $1.23 per share"
    eps_patterns = [
        r'\$(\d+\.?\d*)\s*(?:per share|eps)',
        r'eps\s*(?:of\s*)?\$(\d+\.?\d*)',
        r'earnings?\s*of\s*\$(\d+\.?\d*)\s*per share'
    ]
    
    for pattern in eps_patterns:
        match = re.search(pattern, text_lower)
        if match:
            metrics["eps"] = float(match.group(1))
            break
    
    # Revenue patterns: "$10.5B revenue", "revenue of $10.5 billion"
    revenue_patterns = [
        r'\$(\d+\.?\d*)\s*(b|m|billion|million)\s*(?:in\s*)?revenue',
        r'revenue\s*(?:of\s*)?\$(\d+\.?\d*)\s*(b|m|billion|million)'
    ]
    
    for pattern in revenue_patterns:
        match = re.search(pattern, text_lower)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if unit in ("b", "billion"):
                metrics["revenue_billions"] = value
            else:
                metrics["revenue_millions"] = value
            break
    
    return metrics


class EarningsTracker:
    """Track and process earnings news."""
    
    def __init__(self, watchlist_tickers: List[str]):
        self.tickers = set(t.upper() for t in watchlist_tickers)
        self.fetcher = RSSFetcher()
    
    def fetch_earnings_news(self) -> List[Dict[str, Any]]:
        """
        Fetch recent earnings news.
        
        Returns earnings-related items for watchlist tickers.
        """
        # Fetch from earnings category
        items = self.fetcher.fetch_category("earnings")
        
        # Also check general news for earnings mentions
        general = self.fetcher.fetch_category("general")
        
        earnings_items = []
        
        for item in items + general:
            # Convert NewsItem to dict if needed
            if hasattr(item, "to_dict"):
                item_dict = item.to_dict()
            else:
                item_dict = item
            
            title = item_dict.get("title", "")
            summary = item_dict.get("summary", "")
            
            # Check if earnings-related
            if not is_earnings_related(title, summary):
                continue
            
            # Check for ticker mentions
            combined = title + " " + summary
            mentioned_tickers = []
            for ticker in self.tickers:
                if ticker in combined.upper() or f"${ticker}" in combined.upper():
                    mentioned_tickers.append(ticker)
            
            if mentioned_tickers:
                item_dict["tickers"] = mentioned_tickers
                item_dict["category"] = "earnings"
                item_dict["earnings_type"] = detect_earnings_surprise(title, summary)
                item_dict["earnings_metrics"] = extract_earnings_metrics(combined)
                earnings_items.append(item_dict)
        
        return earnings_items
    
    def create_earnings_summary(self, item: Dict[str, Any]) -> str:
        """Create a summary for earnings news."""
        tickers = item.get("tickers", [])
        ticker_str = ", ".join(tickers) if tickers else "Company"
        
        surprise = item.get("earnings_type")
        metrics = item.get("earnings_metrics", {})
        
        parts = [f"**{ticker_str}** earnings:"]
        
        if surprise == "beat":
            parts.append("📈 *Beat expectations*")
        elif surprise == "miss":
            parts.append("📉 *Missed expectations*")
        
        if metrics.get("eps"):
            parts.append(f"• EPS: ${metrics['eps']:.2f}")
        
        if metrics.get("revenue_billions"):
            parts.append(f"• Revenue: ${metrics['revenue_billions']:.1f}B")
        elif metrics.get("revenue_millions"):
            parts.append(f"• Revenue: ${metrics['revenue_millions']:.0f}M")
        
        return "\n".join(parts)
