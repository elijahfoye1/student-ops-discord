"""Macro economic news detection and processing."""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.news.sources import RSSFetcher, NewsItem

logger = logging.getLogger(__name__)


# Major macro event types - ONLY high-impact announcements
MACRO_EVENTS = {
    "FOMC": {
        "keywords": ["fomc", "federal open market", "rate decision", "interest rate decision"],
        "required_keywords": ["rate", "decision", "projections", "statement"],  # Must also have one of these
        "emoji": "🏦",
        "importance": "high"
    },
    "CPI": {
        "keywords": ["cpi", "consumer price index", "inflation"],
        "required_keywords": ["report", "data", "release", "rose", "fell", "percent"],
        "emoji": "📊",
        "importance": "high"
    },
    "PCE": {
        "keywords": ["pce", "personal consumption expenditures"],
        "required_keywords": ["report", "data", "release", "rose", "fell", "percent"],
        "emoji": "📊",
        "importance": "high"
    },
    "JOBS": {
        "keywords": ["nonfarm payroll", "jobs report", "employment report"],
        "required_keywords": ["added", "jobs", "unemployment", "report"],
        "emoji": "👷",
        "importance": "high"
    },
    "GDP": {
        "keywords": ["gdp", "gross domestic product"],
        "required_keywords": ["growth", "percent", "quarter", "annual"],
        "emoji": "📈",
        "importance": "high"
    },
    "FED_RATE": {
        "keywords": ["fed", "federal reserve"],
        "required_keywords": ["rate cut", "rate hike", "basis points", "bps"],
        "emoji": "🏦",
        "importance": "high"
    }
}

# Keywords that indicate NOISE (administrative, routine items) - skip these
NOISE_KEYWORDS = [
    "enforcement action", "application", "approval", "terminate", "termination",
    "manual", "supervision", "employee", "former employee", "bank holding",
    "pricing", "payment services", "check services", "debit card",
    "reappointment", "reserve bank president", "first vice president",
    "public input", "request comment", "staff manual", "biennial report"
]


def detect_macro_event_type(title: str, summary: str = "") -> Optional[str]:
    """
    Detect the type of macro event from content.
    
    Only returns event type for MAJOR announcements.
    Filters out routine administrative Fed items.
    """
    combined = (title + " " + summary).lower()
    
    # First, check if this is noise (administrative, routine items)
    if any(noise in combined for noise in NOISE_KEYWORDS):
        return None
    
    for event_type, config in MACRO_EVENTS.items():
        # Must match a primary keyword
        if any(kw in combined for kw in config["keywords"]):
            # Must ALSO match a required keyword (to filter out vague matches)
            required = config.get("required_keywords", [])
            if required:
                if any(req in combined for req in required):
                    return event_type
            else:
                return event_type
    
    return None


def is_macro_news(title: str, summary: str = "") -> bool:
    """Check if content is macro-economic news."""
    return detect_macro_event_type(title, summary) is not None


def extract_rate_info(text: str) -> Dict[str, Any]:
    """
    Extract interest rate information from text.
    
    Returns dict with rate changes, expectations, etc.
    """
    info = {}
    text_lower = text.lower()
    
    # Rate patterns
    rate_pattern = r'(\d+\.?\d*)\s*(?:percent|%|basis points|bps)'
    matches = re.findall(rate_pattern, text_lower)
    if matches:
        info["rates_mentioned"] = [float(m) for m in matches]
    
    # Rate action
    if any(word in text_lower for word in ["hike", "raise", "increase"]):
        info["action"] = "hike"
    elif any(word in text_lower for word in ["cut", "lower", "reduce"]):
        info["action"] = "cut"
    elif any(word in text_lower for word in ["hold", "unchanged", "steady", "pause"]):
        info["action"] = "hold"
    
    # Expectations
    if "expected" in text_lower or "forecast" in text_lower:
        info["has_expectations"] = True
    
    return info


def extract_economic_data(text: str) -> Dict[str, Any]:
    """
    Extract economic data points from text.
    
    Returns dict with parsed values.
    """
    data = {}
    text_lower = text.lower()
    
    # Percentage patterns (CPI, unemployment, etc.)
    pct_pattern = r'(\d+\.?\d*)\s*(?:percent|%)'
    
    # Check for specific contexts
    if "inflation" in text_lower or "cpi" in text_lower:
        matches = re.findall(pct_pattern, text_lower)
        if matches:
            data["inflation_rate"] = float(matches[0])
    
    if "unemployment" in text_lower:
        matches = re.findall(pct_pattern, text_lower)
        if matches:
            data["unemployment_rate"] = float(matches[0])
    
    # Job numbers
    jobs_pattern = r'(\d+(?:,\d{3})*)\s*(?:jobs|payrolls)'
    jobs_match = re.search(jobs_pattern, text_lower)
    if jobs_match:
        data["jobs_added"] = int(jobs_match.group(1).replace(",", ""))
    
    return data


class MacroTracker:
    """Track and process macro economic news."""
    
    def __init__(self):
        self.fetcher = RSSFetcher()
    
    def fetch_macro_news(self) -> List[Dict[str, Any]]:
        """
        Fetch recent macro economic news.
        
        Returns macro-related items.
        """
        items = self.fetcher.fetch_category("macro")
        # Also check general for macro mentions
        general = self.fetcher.fetch_category("general")
        
        macro_items = []
        
        for item in items + general:
            if hasattr(item, "to_dict"):
                item_dict = item.to_dict()
            else:
                item_dict = item
            
            title = item_dict.get("title", "")
            summary = item_dict.get("summary", "")
            
            event_type = detect_macro_event_type(title, summary)
            if not event_type:
                continue
            
            event_config = MACRO_EVENTS[event_type]
            
            item_dict["category"] = "macro"
            item_dict["macro_event_type"] = event_type
            item_dict["macro_emoji"] = event_config["emoji"]
            item_dict["importance"] = event_config["importance"]
            item_dict["rate_info"] = extract_rate_info(title + " " + summary)
            item_dict["economic_data"] = extract_economic_data(title + " " + summary)
            
            macro_items.append(item_dict)
        
        # Sort by importance
        importance_order = {"high": 0, "medium": 1, "low": 2}
        macro_items.sort(
            key=lambda x: importance_order.get(x.get("importance", "low"), 2)
        )
        
        return macro_items
    
    def create_macro_summary(self, item: Dict[str, Any]) -> str:
        """Create a summary for macro news."""
        event_type = item.get("macro_event_type", "GENERAL")
        emoji = item.get("macro_emoji", "📰")
        
        parts = [f"{emoji} **{event_type}**"]
        
        rate_info = item.get("rate_info", {})
        if rate_info.get("action"):
            action_emoji = {"hike": "📈", "cut": "📉", "hold": "➡️"}.get(rate_info["action"], "")
            parts.append(f"{action_emoji} Rate {rate_info['action']}")
        
        econ_data = item.get("economic_data", {})
        if econ_data.get("inflation_rate"):
            parts.append(f"• Inflation: {econ_data['inflation_rate']:.1f}%")
        if econ_data.get("unemployment_rate"):
            parts.append(f"• Unemployment: {econ_data['unemployment_rate']:.1f}%")
        if econ_data.get("jobs_added"):
            parts.append(f"• Jobs added: {econ_data['jobs_added']:,}")
        
        return "\n".join(parts)
    
    def get_why_it_matters(self, item: Dict[str, Any]) -> str:
        """Generate 'why it matters' context for macro news."""
        event_type = item.get("macro_event_type", "")
        rate_info = item.get("rate_info", {})
        
        context = {
            "FOMC": "Fed policy directly impacts equity valuations through discount rates and liquidity.",
            "CPI": "Inflation data drives Fed policy expectations and real returns.",
            "PCE": "Core PCE is the Fed's preferred inflation gauge for policy decisions.",
            "JOBS": "Employment strength signals economic health and wage inflation pressures.",
            "GDP": "GDP growth affects corporate earnings expectations and recession risk.",
            "FED_SPEECH": "Fed communication guides market expectations for future policy.",
            "TREASURY": "Yield movements affect equity valuations and sector rotation."
        }
        
        base = context.get(event_type, "This development could impact market sentiment.")
        
        # Add action-specific context
        if rate_info.get("action") == "hike":
            base += " Rate hikes typically pressure growth stocks and increase borrowing costs."
        elif rate_info.get("action") == "cut":
            base += " Rate cuts generally support equity valuations and economic activity."
        
        return base
