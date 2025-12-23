"""Normalize Canvas data into consistent Task/Announcement objects."""

import re
import logging
from typing import Dict, Any, Optional, List
from html import unescape

logger = logging.getLogger(__name__)


# Keywords for detecting task types
EXAM_KEYWORDS = ["exam", "midterm", "final", "test"]
QUIZ_KEYWORDS = ["quiz"]
PROJECT_KEYWORDS = ["project", "capstone", "portfolio"]
PAPER_KEYWORDS = ["paper", "essay", "report", "thesis", "writing"]
LAB_KEYWORDS = ["lab", "laboratory", "experiment"]
DISCUSSION_KEYWORDS = ["discussion", "forum", "reply", "respond"]

# Keywords for urgent announcements
URGENT_KEYWORDS = [
    "required", "mandatory", "must", "urgent", "important",
    "exam", "midterm", "final", "quiz", "test",
    "deadline", "due date", "changed", "moved", "extended",
    "cancelled", "canceled", "postponed", "rescheduled"
]


def detect_task_type(title: str, submission_types: Optional[List[str]] = None) -> str:
    """
    Detect the type of task from its title and submission types.
    
    Returns: assignment, quiz, exam, project, paper, lab, discussion, other
    """
    title_lower = title.lower()
    
    # Check for specific types based on keywords
    if any(kw in title_lower for kw in EXAM_KEYWORDS):
        return "exam"
    if any(kw in title_lower for kw in QUIZ_KEYWORDS):
        return "quiz"
    if any(kw in title_lower for kw in PROJECT_KEYWORDS):
        return "project"
    if any(kw in title_lower for kw in PAPER_KEYWORDS):
        return "paper"
    if any(kw in title_lower for kw in LAB_KEYWORDS):
        return "lab"
    if any(kw in title_lower for kw in DISCUSSION_KEYWORDS):
        return "discussion"
    
    # Check submission types from Canvas
    if submission_types:
        if "online_quiz" in submission_types:
            return "quiz"
        if "discussion_topic" in submission_types:
            return "discussion"
    
    return "assignment"


def extract_tags(title: str, task_type: str, points: Optional[float] = None) -> List[str]:
    """Extract relevant tags from task metadata."""
    tags = []
    
    # Type-based tags
    if task_type in ("exam", "quiz"):
        tags.append("exam")
    if task_type == "project":
        tags.append("project")
    
    # Impact tags
    if points is not None:
        if points >= 100:
            tags.append("high_impact")
        elif points >= 50:
            tags.append("medium_impact")
    
    # Keyword-based tags
    title_lower = title.lower()
    if "final" in title_lower:
        tags.append("final")
    if "midterm" in title_lower:
        tags.append("midterm")
    if "group" in title_lower or "team" in title_lower:
        tags.append("group_work")
    
    return tags


def normalize_assignment(
    assignment: Dict[str, Any],
    course_id: int,
    course_name: str
) -> Optional[Dict[str, Any]]:
    """
    Normalize a Canvas assignment into a Task dictionary.
    
    Args:
        assignment: Raw Canvas assignment data
        course_id: Canvas course ID
        course_name: Human-readable course name
    
    Returns:
        Normalized Task dictionary, or None if invalid.
    """
    assignment_id = assignment.get("id")
    if not assignment_id:
        return None
    
    title = assignment.get("name", "Untitled Assignment")
    due_at = assignment.get("due_at")  # May be None
    points = assignment.get("points_possible")
    submission_types = assignment.get("submission_types", [])
    
    # Detect type and tags
    task_type = detect_task_type(title, submission_types)
    tags = extract_tags(title, task_type, points)
    
    # Build URL
    html_url = assignment.get("html_url", "")
    
    # Check workflow state
    workflow_state = assignment.get("workflow_state", "")
    is_published = workflow_state == "published"
    
    # Skip unpublished assignments
    if not is_published:
        logger.debug(f"Skipping unpublished assignment: {title}")
        return None
    
    return {
        "id": f"canvas:{course_id}:{assignment_id}",
        "course_name": course_name,
        "course_id": course_id,
        "title": title,
        "type": task_type,
        "due_at": due_at,
        "points_possible": points,
        "url": html_url,
        "updated_at": assignment.get("updated_at"),
        "workflow_state": workflow_state,
        "is_published": is_published,
        "has_submission": bool(assignment.get("submission", {}).get("submitted_at")),
        "tags": tags
    }


def extract_announcement_tags(title: str, message: str) -> List[str]:
    """Extract tags from announcement content."""
    tags = []
    combined = (title + " " + message).lower()
    
    # Check for urgent content
    urgent_found = []
    for keyword in URGENT_KEYWORDS:
        if keyword in combined:
            urgent_found.append(keyword)
    
    if any(kw in combined for kw in ["exam", "midterm", "final", "quiz"]):
        tags.append("exam")
    if any(kw in combined for kw in ["deadline", "due date", "changed", "moved"]):
        tags.append("deadline_change")
    if any(kw in combined for kw in ["required", "mandatory", "must"]):
        tags.append("required_action")
    if any(kw in combined for kw in ["cancelled", "canceled", "postponed"]):
        tags.append("schedule_change")
    
    return tags


def strip_html(html: str) -> str:
    """Remove HTML tags and unescape entities."""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', html)
    # Unescape HTML entities
    clean = unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def normalize_announcement(
    announcement: Dict[str, Any],
    course_id: int,
    course_name: str
) -> Optional[Dict[str, Any]]:
    """
    Normalize a Canvas announcement.
    
    Args:
        announcement: Raw Canvas announcement data
        course_id: Canvas course ID
        course_name: Human-readable course name
    
    Returns:
        Normalized Announcement dictionary, or None if invalid.
    """
    ann_id = announcement.get("id")
    if not ann_id:
        return None
    
    title = announcement.get("title", "Untitled Announcement")
    message = announcement.get("message", "")
    posted_at = announcement.get("posted_at")
    
    # Clean up message for snippet
    message_clean = strip_html(message)
    message_snippet = message_clean[:300] + "..." if len(message_clean) > 300 else message_clean
    
    # Extract tags
    tags = extract_announcement_tags(title, message_clean)
    
    # Determine if urgent
    is_urgent = len(tags) > 0
    
    return {
        "id": f"canvas:announcement:{ann_id}",
        "course_id": course_id,
        "course_name": course_name,
        "title": title,
        "message_snippet": message_snippet,
        "posted_at": posted_at,
        "url": announcement.get("html_url", ""),
        "tags": tags,
        "is_urgent": is_urgent
    }
