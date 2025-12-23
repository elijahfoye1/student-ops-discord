"""Canvas sync and alerts job runner."""

import argparse
import logging
import sys

from src.common.storage import StateStore
from src.common.dedupe import Deduplicator, cleanup_old_events
from src.common.time import hours_until, format_relative, now_utc
from src.common.scoring import calculate_priority
from src.common.discord import (
    get_webhook, build_alert_embed, Embed, EmbedField, COLORS
)
from src.canvas.client import CanvasClient
from src.canvas.sync import sync_all_courses, detect_deadline_changes, update_seen_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Alert thresholds
URGENT_HOURS = 24  # Due within 24 hours
EXAM_HOURS = 72    # Exam/quiz within 72 hours


def run(dry_run: bool = False):
    """
    Run Canvas sync and alert job.
    
    1. Sync courses, assignments, announcements from Canvas
    2. Detect deadline changes
    3. Post alerts for urgent items
    4. Update state
    """
    logger.info("Starting Canvas sync job")
    
    # Initialize
    state = StateStore()
    state.load()
    
    client = CanvasClient()
    if not client.is_configured:
        logger.error("Canvas client not configured, exiting")
        return
    
    # Sync Canvas data
    result = sync_all_courses(client, state)
    
    if result.errors:
        logger.warning(f"Sync completed with {len(result.errors)} errors")
    
    logger.info(f"Synced {len(result.tasks)} tasks from {result.courses_synced} courses")
    
    # Detect deadline changes
    moved_earlier, _ = detect_deadline_changes(result.tasks, state)
    
    # Initialize deduplicator
    dedupe = Deduplicator(state.load())
    
    # Process alerts
    alerts_posted = 0
    
    # Get webhooks
    alerts_webhook = get_webhook("alerts", dry_run=dry_run)
    study_webhook = get_webhook("study_plan", dry_run=dry_run)
    
    # Process each task for alerts
    for task in result.tasks:
        # Skip if no due date
        if not task.get("due_at"):
            continue
        
        # Calculate urgency
        hours = hours_until(task["due_at"])
        if hours is None or hours < 0:
            continue  # Skip overdue or invalid
        
        task_type = task.get("type", "assignment")
        title = task.get("title", "Unknown")
        
        # Check alert conditions
        should_alert = False
        alert_reason = None
        
        # Condition 1: Due within urgent threshold
        if hours <= URGENT_HOURS:
            should_alert = True
            alert_reason = f"Due in {format_relative(task['due_at'])}"
        
        # Condition 2: Exam/quiz within exam threshold
        elif task_type in ("exam", "quiz") and hours <= EXAM_HOURS:
            should_alert = True
            alert_reason = f"📝 Exam/Quiz {format_relative(task['due_at'])}"
        
        # Condition 3: Deadline moved earlier
        elif task in moved_earlier:
            should_alert = True
            alert_reason = "⚠️ Deadline moved earlier!"
        
        if not should_alert:
            continue
        
        # Check deduplication
        # Use due_at in hash so we re-alert if deadline changes
        if not dedupe.check_and_mark(
            "deadline_alert",
            task["id"],
            due_at=task["due_at"]
        ):
            logger.debug(f"Skipping duplicate alert for {title}")
            continue
        
        # Build and post alert
        priority = calculate_priority(
            hours_until_due=hours,
            points_possible=task.get("points_possible"),
            task_type=task_type,
            title=title
        )
        
        embed = build_alert_embed(
            title=f"🚨 {title}",
            description=alert_reason,
            priority=priority.label,
            url=task.get("url"),
            fields=[
                (task["course_name"], format_relative(task["due_at"]), True),
                ("Priority", priority.label.upper(), True)
            ],
            footer=" | ".join(priority.reasons) if priority.reasons else None
        )
        
        if alerts_webhook.post(embeds=[embed]):
            alerts_posted += 1
    
    # Process urgent announcements
    for ann in result.announcements:
        if not ann.get("is_urgent"):
            continue
        
        # Dedupe announcements
        if not dedupe.check_and_mark(
            "announcement_alert",
            ann["id"],
            posted_at=ann.get("posted_at")
        ):
            continue
        
        embed = build_alert_embed(
            title=f"📢 {ann['title']}",
            description=ann.get("message_snippet", "")[:500],
            priority="high",
            url=ann.get("url"),
            fields=[
                (ann["course_name"], ", ".join(ann.get("tags", [])), False)
            ]
        )
        
        if alerts_webhook.post(embeds=[embed]):
            alerts_posted += 1
    
    # Post study plan with top priority tasks
    top_tasks = get_top_priority_tasks(result.tasks, limit=5)
    if top_tasks:
        study_embed = build_study_plan_embed(top_tasks)
        study_webhook.post(embeds=[study_embed])
    
    # Update seen tasks and save state
    update_seen_tasks(result.tasks, state)
    cleanup_old_events(state.load(), max_age_days=30)
    state.update_last_run("canvas")
    state.save()
    
    logger.info(f"Canvas job complete. Posted {alerts_posted} alerts.")


def get_top_priority_tasks(tasks, limit=5):
    """Get top priority tasks for the next 3 days."""
    upcoming = []
    
    for task in tasks:
        if not task.get("due_at"):
            continue
        
        hours = hours_until(task["due_at"])
        if hours is None or hours < 0 or hours > 72:
            continue
        
        priority = calculate_priority(
            hours_until_due=hours,
            points_possible=task.get("points_possible"),
            task_type=task.get("type", "assignment"),
            title=task.get("title", "")
        )
        
        task["_priority"] = priority
        upcoming.append(task)
    
    # Sort by priority score
    upcoming.sort(key=lambda x: x["_priority"].score, reverse=True)
    
    return upcoming[:limit]


def build_study_plan_embed(tasks):
    """Build the study plan embed."""
    lines = []
    
    for i, task in enumerate(tasks, 1):
        priority = task.get("_priority")
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            priority.label if priority else "medium", "⚪"
        )
        
        due_str = format_relative(task.get("due_at"))
        lines.append(f"{emoji} **{i}. {task['title']}**")
        lines.append(f"   {task['course_name']} • {due_str}")
    
    return Embed(
        title="📋 Study Plan",
        description="\n".join(lines) if lines else "No urgent tasks!",
        color=COLORS["blue"]
    )


def main():
    parser = argparse.ArgumentParser(description="Canvas sync and alerts")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of posting to Discord"
    )
    args = parser.parse_args()
    
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
