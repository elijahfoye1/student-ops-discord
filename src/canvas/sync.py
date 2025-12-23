"""Canvas data synchronization."""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from src.canvas.client import CanvasClient
from src.canvas.normalize import normalize_assignment, normalize_announcement
from src.common.storage import StateStore

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    tasks: List[Dict[str, Any]]
    announcements: List[Dict[str, Any]]
    courses_synced: int
    errors: List[str]


def sync_all_courses(
    client: CanvasClient,
    state: StateStore
) -> SyncResult:
    """
    Synchronize data from all active courses.
    
    Fetches assignments and announcements, normalizes them,
    and tracks changes against previous state.
    
    Args:
        client: Configured CanvasClient
        state: StateStore for tracking seen items
    
    Returns:
        SyncResult with all tasks and announcements.
    """
    all_tasks = []
    all_announcements = []
    errors = []
    courses_synced = 0
    
    if not client.is_configured:
        logger.error("Canvas client not configured")
        return SyncResult(
            tasks=[],
            announcements=[],
            courses_synced=0,
            errors=["Canvas client not configured"]
        )
    
    # Get active courses
    try:
        courses = client.get_courses(enrollment_state="active")
    except Exception as e:
        logger.error(f"Failed to fetch courses: {e}")
        return SyncResult(
            tasks=[],
            announcements=[],
            courses_synced=0,
            errors=[f"Failed to fetch courses: {e}"]
        )
    
    logger.info(f"Syncing {len(courses)} courses")
    
    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name", "Unknown Course")
        
        if not course_id:
            continue
        
        try:
            # Sync assignments
            tasks = sync_course_assignments(client, course_id, course_name)
            all_tasks.extend(tasks)
            
            # Sync announcements
            announcements = sync_course_announcements(client, course_id, course_name)
            all_announcements.extend(announcements)
            
            courses_synced += 1
            
        except Exception as e:
            error_msg = f"Error syncing course {course_name}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            # Continue with other courses - don't let one failure stop everything
    
    logger.info(
        f"Sync complete: {len(all_tasks)} tasks, "
        f"{len(all_announcements)} announcements from {courses_synced} courses"
    )
    
    return SyncResult(
        tasks=all_tasks,
        announcements=all_announcements,
        courses_synced=courses_synced,
        errors=errors
    )


def sync_course_assignments(
    client: CanvasClient,
    course_id: int,
    course_name: str
) -> List[Dict[str, Any]]:
    """
    Fetch and normalize assignments for a single course.
    
    Args:
        client: CanvasClient
        course_id: Canvas course ID
        course_name: Human-readable course name
    
    Returns:
        List of normalized Task dictionaries.
    """
    logger.debug(f"Fetching assignments for {course_name} (ID: {course_id})")
    
    assignments = client.get_assignments(
        course_id,
        include=["submission"],
        order_by="due_at"
    )
    
    tasks = []
    for assignment in assignments:
        try:
            task = normalize_assignment(assignment, course_id, course_name)
            if task:
                tasks.append(task)
        except Exception as e:
            logger.warning(f"Failed to normalize assignment: {e}")
    
    return tasks


def sync_course_announcements(
    client: CanvasClient,
    course_id: int,
    course_name: str
) -> List[Dict[str, Any]]:
    """
    Fetch and normalize announcements for a single course.
    
    Args:
        client: CanvasClient
        course_id: Canvas course ID
        course_name: Human-readable course name
    
    Returns:
        List of normalized Announcement dictionaries.
    """
    logger.debug(f"Fetching announcements for {course_name} (ID: {course_id})")
    
    raw_announcements = client.get_announcements(course_id, max_count=10)
    
    announcements = []
    for ann in raw_announcements:
        try:
            normalized = normalize_announcement(ann, course_id, course_name)
            if normalized:
                announcements.append(normalized)
        except Exception as e:
            logger.warning(f"Failed to normalize announcement: {e}")
    
    return announcements


def detect_deadline_changes(
    current_tasks: List[Dict[str, Any]],
    state: StateStore
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Detect tasks with deadline changes.
    
    Args:
        current_tasks: Current list of tasks
        state: StateStore with previously seen tasks
    
    Returns:
        Tuple of (moved_earlier, moved_later) task lists.
    """
    from src.common.time import parse_iso
    
    moved_earlier = []
    moved_later = []
    
    seen_tasks = state.get("seen_tasks", {})
    
    for task in current_tasks:
        task_id = task.get("id")
        if not task_id or not task.get("due_at"):
            continue
        
        previous = seen_tasks.get(task_id)
        if not previous or not previous.get("due_at"):
            continue
        
        current_due = parse_iso(task["due_at"])
        previous_due = parse_iso(previous["due_at"])
        
        if not current_due or not previous_due:
            continue
        
        if current_due < previous_due:
            task["_deadline_change"] = "earlier"
            task["_previous_due"] = previous["due_at"]
            moved_earlier.append(task)
        elif current_due > previous_due:
            task["_deadline_change"] = "later"
            task["_previous_due"] = previous["due_at"]
            moved_later.append(task)
    
    if moved_earlier:
        logger.info(f"Detected {len(moved_earlier)} tasks with earlier deadlines")
    
    return moved_earlier, moved_later


def update_seen_tasks(tasks: List[Dict[str, Any]], state: StateStore) -> None:
    """Update the seen_tasks in state with current task info."""
    from src.common.time import now_utc
    
    seen = state.load().get("seen_tasks", {})
    now = now_utc().isoformat()
    
    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        
        seen[task_id] = {
            "due_at": task.get("due_at"),
            "updated_at": task.get("updated_at"),
            "last_seen": now,
            "title": task.get("title", "")[:100]  # Keep snippet for debugging
        }
    
    state.set("seen_tasks", seen)
