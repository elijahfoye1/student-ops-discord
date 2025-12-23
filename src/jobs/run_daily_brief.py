"""Daily brief job runner."""

import argparse
import logging

from src.common.storage import StateStore
from src.common.time import hours_until, is_today, is_tomorrow, is_this_week, format_datetime
from src.common.scoring import calculate_priority, sort_by_priority
from src.common.discord import get_webhook, Embed, EmbedField, COLORS
from src.canvas.client import CanvasClient
from src.canvas.sync import sync_all_courses

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False):
    """
    Run daily brief job.
    
    Compiles tasks into Today/Tomorrow/This Week sections
    and posts to the daily-brief channel.
    """
    logger.info("Starting daily brief job")
    
    # Initialize
    state = StateStore()
    state.load()
    
    client = CanvasClient()
    if not client.is_configured:
        logger.error("Canvas client not configured, exiting")
        return
    
    # Sync latest data
    result = sync_all_courses(client, state)
    logger.info(f"Synced {len(result.tasks)} tasks")
    
    # Categorize tasks
    today_tasks = []
    tomorrow_tasks = []
    week_tasks = []
    
    for task in result.tasks:
        if not task.get("due_at"):
            continue
        
        # Skip if already submitted (if we have that info)
        if task.get("has_submission"):
            continue
        
        if is_today(task["due_at"]):
            today_tasks.append(task)
        elif is_tomorrow(task["due_at"]):
            tomorrow_tasks.append(task)
        elif is_this_week(task["due_at"]):
            week_tasks.append(task)
    
    # Sort by priority
    today_tasks = sort_by_priority(today_tasks)
    tomorrow_tasks = sort_by_priority(tomorrow_tasks)
    week_tasks = sort_by_priority(week_tasks)
    
    # Build embed
    embed = build_daily_brief_embed(today_tasks, tomorrow_tasks, week_tasks)
    
    # Post
    webhook = get_webhook("daily_brief", dry_run=dry_run)
    webhook.post(embeds=[embed])
    
    # Update state
    state.update_last_run("daily_brief")
    state.save()
    
    logger.info("Daily brief posted")


def build_daily_brief_embed(today, tomorrow, week):
    """Build the comprehensive daily brief embed."""
    fields = []
    
    # Today section
    if today:
        today_lines = []
        for task in today[:5]:
            hours = hours_until(task.get("due_at"))
            time_str = f"({int(hours)}h)" if hours else ""
            emoji = get_type_emoji(task.get("type", "assignment"))
            today_lines.append(f"{emoji} {task['title']} {time_str}")
        
        fields.append(EmbedField(
            name=f"📅 Today ({len(today)} due)",
            value="\n".join(today_lines) or "Nothing due!",
            inline=False
        ))
    else:
        fields.append(EmbedField(
            name="📅 Today",
            value="✅ Nothing due today!",
            inline=False
        ))
    
    # Tomorrow section
    if tomorrow:
        tomorrow_lines = []
        for task in tomorrow[:5]:
            emoji = get_type_emoji(task.get("type", "assignment"))
            tomorrow_lines.append(f"{emoji} {task['title']}")
        
        fields.append(EmbedField(
            name=f"📆 Tomorrow ({len(tomorrow)} due)",
            value="\n".join(tomorrow_lines),
            inline=False
        ))
    
    # This week section
    if week:
        week_lines = []
        for task in week[:5]:
            emoji = get_type_emoji(task.get("type", "assignment"))
            due = format_datetime(task.get("due_at"), include_time=False)
            week_lines.append(f"{emoji} {task['title']} - {due}")
        
        fields.append(EmbedField(
            name=f"🗓️ This Week ({len(week)} due)",
            value="\n".join(week_lines),
            inline=False
        ))
    
    # Calculate total
    total = len(today) + len(tomorrow) + len(week)
    
    # Determine color based on urgency
    if any(task.get("type") in ("exam", "quiz") for task in today):
        color = COLORS["red"]
    elif len(today) >= 3:
        color = COLORS["orange"]
    elif len(today) >= 1:
        color = COLORS["yellow"]
    else:
        color = COLORS["green"]
    
    return Embed(
        title="📚 Daily Academic Brief",
        description=f"You have **{total} tasks** coming up this week.",
        color=color,
        fields=fields,
        footer="Stay focused and good luck! 💪"
    )


def get_type_emoji(task_type):
    """Get emoji for task type."""
    return {
        "exam": "📝",
        "quiz": "❓",
        "project": "📊",
        "paper": "📄",
        "lab": "🔬",
        "discussion": "💬",
        "assignment": "📋",
        "reading": "📖"
    }.get(task_type, "📋")


def main():
    parser = argparse.ArgumentParser(description="Daily academic brief")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of posting to Discord"
    )
    args = parser.parse_args()
    
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
