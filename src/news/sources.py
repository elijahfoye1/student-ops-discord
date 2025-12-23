"""RSS feed sources for news and market intelligence."""

import logging
import feedparser
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import hashlib

from src.common.time import parse_iso, now_utc

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A normalized news item."""
    id: str
    source: str
    category: str  # "ai", "earnings", "macro", "general"
    title: str
    summary: str
    url: str
    published_at: Optional[str]
    tickers: List[str] = field(default_factory=list)
    impact_score: int = 50
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at,
            "tickers": self.tickers,
            "impact_score": self.impact_score,
            "tags": self.tags
        }


# Built-in RSS feed sources
RSS_FEEDS = {
    "ai": [
        {
            "name": "Google AI Blog",
            "url": "https://blog.google/technology/ai/rss/",
            "category": "ai"
        },
        {
            "name": "OpenAI Blog",
            "url": "https://openai.com/blog/rss.xml",
            "category": "ai"
        },
        {
            "name": "TechCrunch AI",
            "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
            "category": "ai"
        },
        {
            "name": "Ars Technica AI",
            "url": "https://arstechnica.com/tag/artificial-intelligence/feed/",
            "category": "ai"
        }
    ],
    "macro": [
        {
            "name": "Fed Reserve News",
            "url": "https://www.federalreserve.gov/feeds/press_all.xml",
            "category": "macro"
        },
        {
            "name": "Reuters Business",
            "url": "https://www.reutersagency.com/feed/?best-sectors=business-finance&post_type=best",
            "category": "macro"
        }
    ],
    "earnings": [
        {
            "name": "SEC EDGAR Filings",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&output=atom",
            "category": "earnings"
        }
    ],
    "general": [
        {
            "name": "Yahoo Finance",
            "url": "https://finance.yahoo.com/news/rssindex",
            "category": "general"
        }
    ]
}


def generate_news_id(url: str, title: str) -> str:
    """Generate a stable ID for a news item."""
    content = f"{url}|{title}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class RSSFetcher:
    """Fetch and parse RSS feeds."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def fetch_feed(
        self,
        url: str,
        source_name: str = "unknown",
        category: str = "general"
    ) -> List[NewsItem]:
        """
        Fetch and parse a single RSS feed.
        
        Args:
            url: RSS feed URL
            source_name: Human-readable source name
            category: Category for items from this feed
        
        Returns:
            List of NewsItem objects.
        """
        try:
            # feedparser handles timeout internally
            feed = feedparser.parse(url)
            
            if feed.bozo and not feed.entries:
                logger.warning(f"Feed error for {source_name}: {feed.bozo_exception}")
                return []
            
            items = []
            for entry in feed.entries:
                try:
                    item = self._parse_entry(entry, source_name, category)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse entry: {e}")
            
            logger.info(f"Fetched {len(items)} items from {source_name}")
            return items
            
        except Exception as e:
            logger.error(f"Failed to fetch feed {source_name}: {e}")
            return []
    
    def _parse_entry(
        self,
        entry: Dict[str, Any],
        source_name: str,
        category: str
    ) -> Optional[NewsItem]:
        """Parse a single feed entry."""
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        
        if not title or not link:
            return None
        
        # Get summary/description
        summary = ""
        if "summary" in entry:
            summary = entry["summary"]
        elif "description" in entry:
            summary = entry["description"]
        
        # Clean up summary (remove HTML)
        import re
        summary = re.sub(r'<[^>]+>', ' ', summary)
        summary = re.sub(r'\s+', ' ', summary).strip()
        summary = summary[:500]  # Limit length
        
        # Get published date
        published = None
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                from time import mktime
                from datetime import datetime, timezone
                published = datetime.fromtimestamp(
                    mktime(entry["published_parsed"]),
                    tz=timezone.utc
                ).isoformat()
            except Exception:
                pass
        elif "published" in entry:
            published = entry["published"]
        
        return NewsItem(
            id=generate_news_id(link, title),
            source=source_name,
            category=category,
            title=title,
            summary=summary,
            url=link,
            published_at=published
        )
    
    def fetch_category(self, category: str) -> List[NewsItem]:
        """
        Fetch all feeds for a category.
        
        Args:
            category: "ai", "macro", "earnings", or "general"
        
        Returns:
            Combined list of NewsItems from all feeds in category.
        """
        feeds = RSS_FEEDS.get(category, [])
        all_items = []
        
        for feed_info in feeds:
            items = self.fetch_feed(
                url=feed_info["url"],
                source_name=feed_info["name"],
                category=feed_info.get("category", category)
            )
            all_items.extend(items)
        
        return all_items
    
    def fetch_all(self) -> Dict[str, List[NewsItem]]:
        """
        Fetch all configured feeds.
        
        Returns:
            Dictionary mapping category to list of NewsItems.
        """
        results = {}
        
        for category in RSS_FEEDS.keys():
            results[category] = self.fetch_category(category)
        
        return results
