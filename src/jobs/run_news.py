"""News polling and posting job runner."""

import argparse
import logging

from src.common.storage import StateStore
from src.common.dedupe import Deduplicator, cleanup_old_events
from src.common.discord import (
    get_webhook, build_news_embed, Embed, EmbedField, COLORS
)
from src.news.sources import RSSFetcher
from src.news.filters import filter_news, categorize_item, load_watchlists
from src.news.earnings import EarningsTracker
from src.news.macro import MacroTracker
from src.news.analyst_prompts import (
    format_analyst_message, format_valuation_message, get_classroom_bridge
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False):
    """
    Run news polling and posting job.
    
    1. Fetch news from RSS sources
    2. Filter by watchlist and keywords
    3. Post to appropriate channels
    4. Post analyst prompts for high-impact items
    """
    logger.info("Starting news job")
    
    # Initialize
    state = StateStore()
    state.load()
    dedupe = Deduplicator(state.load())
    
    # Load watchlists
    watchlists = load_watchlists()
    
    # Get webhooks
    webhooks = {
        "ai": get_webhook("ai", dry_run=dry_run),
        "earnings": get_webhook("earnings", dry_run=dry_run),
        "macro": get_webhook("macro", dry_run=dry_run),
        "market_alerts": get_webhook("market_alerts", dry_run=dry_run),
        "analyst": get_webhook("analyst", dry_run=dry_run),
        "valuation": get_webhook("valuation", dry_run=dry_run),
        "bridge": get_webhook("bridge", dry_run=dry_run)
    }
    
    posted_count = 0
    
    # Fetch and process general news
    fetcher = RSSFetcher()
    all_items = []
    
    for category in ["ai", "macro", "general"]:
        items = fetcher.fetch_category(category)
        # Convert NewsItem objects to dicts
        for item in items:
            if hasattr(item, "to_dict"):
                all_items.append(item.to_dict())
            else:
                all_items.append(item)
    
    logger.info(f"Fetched {len(all_items)} total items")
    
    # Filter items
    filtered = filter_news(all_items, watchlists)
    logger.info(f"Filtered to {len(filtered)} relevant items")
    
    # Process each filtered item
    for item in filtered:
        item_id = item.get("id", "")
        if not item_id:
            continue
        
        # Dedupe
        if not dedupe.check_and_mark("news", item_id):
            logger.debug(f"Skipping duplicate: {item.get('title', '')[:50]}")
            continue
        
        # Determine channel
        channel = categorize_item(item)
        webhook = webhooks.get(channel)
        
        if not webhook:
            continue
        
        # Build and post news embed
        embed = build_news_embed(
            title=item.get("title", "News"),
            summary=item.get("summary", "")[:400],
            category=item.get("category", "general"),
            url=item.get("url", ""),
            why_it_matters=get_why_it_matters(item)
        )
        
        if webhook.post(embeds=[embed]):
            posted_count += 1
            
            # Post analyst prompt for high-impact items
            if item.get("impact_score", 0) >= 60:
                post_analyst_prompt(item, webhooks, dedupe)
    
    # Also process earnings specifically
    process_earnings(watchlists, webhooks, dedupe, dry_run)
    
    # Process macro news
    process_macro(webhooks, dedupe, dry_run)
    
    # Cleanup and save
    cleanup_old_events(state.load(), max_age_days=30)
    state.update_last_run("news")
    state.save()
    
    logger.info(f"News job complete. Posted {posted_count} items.")


def get_why_it_matters(item):
    """Generate 'why it matters' context."""
    category = item.get("category", "")
    tickers = item.get("tickers", [])
    
    if category == "earnings" and tickers:
        return f"Earnings for {', '.join(tickers)} may impact portfolio positions."
    elif category == "ai":
        return "AI developments can affect tech valuations and competitive dynamics."
    elif category == "macro":
        return "Macro data influences Fed policy and market discount rates."
    
    if tickers:
        return f"Relevant to: {', '.join(tickers)}"
    
    return None


def post_analyst_prompt(item, webhooks, dedupe):
    """Post analyst prompt and valuation lens for high-impact items."""
    item_id = item.get("id", "")
    
    # Check if we already posted analyst prompt for this item
    if not dedupe.is_new("analyst_prompt", item_id):
        return
    
    dedupe.mark("analyst_prompt", item_id)
    
    # Post analyst prompt
    analyst_webhook = webhooks.get("analyst")
    if analyst_webhook and analyst_webhook.is_configured:
        prompt_text = format_analyst_message(item)
        
        title = item.get("title", "Event")[:100]
        category = item.get("category", "general")
        
        embed = Embed(
            title=f"🧠 If I Were An Analyst: {title}",
            description=prompt_text,
            color=COLORS["purple"]
        )
        
        analyst_webhook.post(embeds=[embed])
    
    # Post valuation lens
    valuation_webhook = webhooks.get("valuation")
    if valuation_webhook and valuation_webhook.is_configured:
        valuation_text = format_valuation_message(item)
        
        embed = Embed(
            title="📊 Valuation Lens",
            description=valuation_text,
            color=COLORS["blue"]
        )
        
        valuation_webhook.post(embeds=[embed])
    
    # Post classroom bridge (optional)
    bridge_webhook = webhooks.get("bridge")
    if bridge_webhook and bridge_webhook.is_configured:
        bridge = get_classroom_bridge(
            item.get("macro_event_type", ""),
            item.get("category", "general")
        )
        
        embed = Embed(
            title="📚 Classroom Bridge",
            description=bridge["description"],
            color=COLORS["gray"],
            fields=[
                EmbedField(
                    name="Related Concepts",
                    value=", ".join(bridge["concepts"]),
                    inline=False
                )
            ]
        )
        
        bridge_webhook.post(embeds=[embed])


def process_earnings(watchlists, webhooks, dedupe, dry_run):
    """Process earnings-specific news."""
    tracker = EarningsTracker(watchlists.get("tickers", []))
    earnings_items = tracker.fetch_earnings_news()
    
    logger.info(f"Found {len(earnings_items)} earnings items")
    
    for item in earnings_items:
        item_id = item.get("id", "")
        if not dedupe.check_and_mark("earnings", item_id):
            continue
        
        webhook = webhooks.get("earnings")
        if not webhook:
            continue
        
        summary = tracker.create_earnings_summary(item)
        
        embed = Embed(
            title=f"💰 {item.get('title', 'Earnings')[:100]}",
            description=summary,
            color=COLORS["green"],
            url=item.get("url", "")
        )
        
        webhook.post(embeds=[embed])
        
        # Post analyst prompt for earnings
        if item.get("tickers"):
            post_analyst_prompt(item, webhooks, dedupe)


def process_macro(webhooks, dedupe, dry_run):
    """Process macro-specific news."""
    tracker = MacroTracker()
    macro_items = tracker.fetch_macro_news()
    
    logger.info(f"Found {len(macro_items)} macro items")
    
    for item in macro_items:
        item_id = item.get("id", "")
        if not dedupe.check_and_mark("macro", item_id):
            continue
        
        webhook = webhooks.get("macro")
        if not webhook:
            continue
        
        summary = tracker.create_macro_summary(item)
        why = tracker.get_why_it_matters(item)
        
        embed = Embed(
            title=f"{item.get('macro_emoji', '📊')} {item.get('title', 'Macro')[:100]}",
            description=f"{summary}\n\n**Why it matters:** {why}",
            color=COLORS["orange"],
            url=item.get("url", "")
        )
        
        webhook.post(embeds=[embed])
        
        # Post analyst prompt for high-importance macro
        if item.get("importance") == "high":
            post_analyst_prompt(item, webhooks, dedupe)


def main():
    parser = argparse.ArgumentParser(description="News polling and posting")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of posting to Discord"
    )
    args = parser.parse_args()
    
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
