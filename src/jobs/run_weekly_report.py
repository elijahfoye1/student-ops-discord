"""Weekly report job runner (optional)."""

import argparse
import logging
from datetime import datetime, timedelta

from src.common.storage import StateStore
from src.common.time import now_utc, now_local
from src.common.discord import get_webhook, Embed, EmbedField, COLORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False):
    """
    Run weekly summary report.
    
    Aggregates the week's activity and posts a summary.
    """
    logger.info("Starting weekly report job")
    
    # Initialize
    state = StateStore()
    data = state.load()
    
    # Calculate stats from state
    sent_events = data.get("sent_events", {})
    seen_tasks = data.get("seen_tasks", {})
    
    # Count events from the past week
    week_ago = (now_utc() - timedelta(days=7)).isoformat()
    
    alerts_sent = 0
    news_posted = 0
    
    for event_hash, sent_at in sent_events.items():
        if sent_at >= week_ago:
            # Approximate categorization based on hash patterns
            alerts_sent += 1
    
    # Count active tasks
    active_tasks = 0
    completed_tasks = 0
    
    for task_id, info in seen_tasks.items():
        if info.get("last_seen", "") >= week_ago:
            active_tasks += 1
    
    # Build embed
    embed = Embed(
        title="📊 Weekly Summary Report",
        description=f"Activity summary for the week ending {now_local().strftime('%B %d, %Y')}",
        color=COLORS["blue"],
        fields=[
            EmbedField(
                name="📌 Events Tracked",
                value=f"{len(sent_events)} total events processed",
                inline=True
            ),
            EmbedField(
                name="📚 Tasks Monitored",
                value=f"{active_tasks} active tasks",
                inline=True
            ),
            EmbedField(
                name="🔔 Alerts This Week",
                value=str(alerts_sent),
                inline=True
            )
        ],
        footer="Keep up the great work! 🎯"
    )
    
    # Post
    webhook = get_webhook("daily_brief", dry_run=dry_run)  # Reuse daily brief channel
    webhook.post(embeds=[embed])
    
    # Update state
    state.update_last_run("weekly_report")
    state.save()
    
    logger.info("Weekly report posted")


def main():
    parser = argparse.ArgumentParser(description="Weekly summary report")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of posting to Discord"
    )
    args = parser.parse_args()
    
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
