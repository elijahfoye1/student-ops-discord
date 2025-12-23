"""Priority scoring for tasks and events."""

from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class Priority:
    """Priority breakdown for a task."""
    score: int  # 0-100 overall priority
    urgency: int  # 0-100 based on time until due
    impact: int  # 0-100 based on points/type
    risk: int  # 0-100 based on task type
    label: str  # "critical", "high", "medium", "low"
    reasons: List[str]  # Human-readable reasons


# Task type weights for impact scoring
TYPE_WEIGHTS = {
    "exam": 100,
    "midterm": 100,
    "final": 100,
    "project": 85,
    "paper": 80,
    "quiz": 70,
    "problem_set": 65,
    "assignment": 60,
    "lab": 55,
    "discussion": 40,
    "reading": 30,
    "other": 50
}

# Keywords to detect task types from titles
TYPE_KEYWORDS = {
    "exam": ["exam", "midterm", "final"],
    "quiz": ["quiz"],
    "project": ["project", "capstone"],
    "paper": ["paper", "essay", "report", "thesis"],
    "problem_set": ["problem set", "pset", "homework", "hw"],
    "lab": ["lab", "laboratory"],
    "discussion": ["discussion", "forum", "post"],
    "reading": ["reading", "read chapter"]
}


def detect_task_type(title: str, explicit_type: Optional[str] = None) -> str:
    """
    Detect task type from title keywords.
    
    Args:
        title: Task title
        explicit_type: Explicit type from Canvas (e.g., "assignment", "quiz")
    
    Returns:
        Detected task type string.
    """
    title_lower = title.lower()
    
    # Check keywords first (they're more specific)
    for task_type, keywords in TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title_lower:
                return task_type
    
    # Fall back to explicit type if useful
    if explicit_type in TYPE_WEIGHTS:
        return explicit_type
    
    return "other"


def calculate_urgency(hours_until_due: Optional[float]) -> int:
    """
    Calculate urgency score based on hours until due.
    
    Returns 0-100 where 100 is most urgent.
    """
    if hours_until_due is None:
        return 20  # No due date = low urgency
    
    if hours_until_due < 0:
        return 100  # Overdue
    elif hours_until_due <= 6:
        return 100
    elif hours_until_due <= 12:
        return 95
    elif hours_until_due <= 24:
        return 90
    elif hours_until_due <= 48:
        return 75
    elif hours_until_due <= 72:
        return 60
    elif hours_until_due <= 168:  # 1 week
        return 40
    elif hours_until_due <= 336:  # 2 weeks
        return 25
    else:
        return 10


def calculate_impact(
    points_possible: Optional[float],
    task_type: str
) -> int:
    """
    Calculate impact score based on points and type.
    
    Returns 0-100 where 100 is highest impact.
    """
    # Base impact from type
    type_weight = TYPE_WEIGHTS.get(task_type, 50)
    
    # Adjust by points if available
    if points_possible is not None and points_possible > 0:
        if points_possible >= 100:
            points_factor = 1.0
        elif points_possible >= 50:
            points_factor = 0.9
        elif points_possible >= 25:
            points_factor = 0.8
        elif points_possible >= 10:
            points_factor = 0.7
        else:
            points_factor = 0.6
        
        # Blend type weight with points factor
        return int(type_weight * points_factor)
    
    return type_weight


def calculate_priority(
    hours_until_due: Optional[float],
    points_possible: Optional[float] = None,
    task_type: str = "other",
    title: str = ""
) -> Priority:
    """
    Calculate overall priority for a task.
    
    Args:
        hours_until_due: Hours until the task is due (None if no due date)
        points_possible: Points the task is worth (None if unknown)
        task_type: Detected task type
        title: Task title (for additional context)
    
    Returns:
        Priority object with score breakdown.
    """
    # Detect type from title if we have a generic type
    if task_type in ("assignment", "other") and title:
        task_type = detect_task_type(title, task_type)
    
    urgency = calculate_urgency(hours_until_due)
    impact = calculate_impact(points_possible, task_type)
    risk = TYPE_WEIGHTS.get(task_type, 50)
    
    # Weighted combination
    # Urgency is most important, then impact/risk
    score = int(urgency * 0.5 + impact * 0.3 + risk * 0.2)
    
    # Determine label
    if score >= 90:
        label = "critical"
    elif score >= 70:
        label = "high"
    elif score >= 45:
        label = "medium"
    else:
        label = "low"
    
    # Build reasons
    reasons = []
    if hours_until_due is not None:
        if hours_until_due < 0:
            reasons.append("⚠️ Overdue")
        elif hours_until_due <= 24:
            reasons.append(f"⏰ Due in {int(hours_until_due)} hours")
        elif hours_until_due <= 72:
            reasons.append(f"📅 Due in {int(hours_until_due / 24)} days")
    
    if task_type in ("exam", "midterm", "final"):
        reasons.append("📝 Exam/Test")
    elif task_type == "project":
        reasons.append("📊 Major Project")
    
    if points_possible and points_possible >= 50:
        reasons.append(f"💯 Worth {int(points_possible)} points")
    
    return Priority(
        score=min(100, max(0, score)),
        urgency=urgency,
        impact=impact,
        risk=risk,
        label=label,
        reasons=reasons
    )


def sort_by_priority(tasks: List[dict]) -> List[dict]:
    """Sort tasks by priority score (highest first)."""
    def get_priority_score(task: dict) -> int:
        from src.common.time import hours_until
        return calculate_priority(
            hours_until_due=hours_until(task.get("due_at")),
            points_possible=task.get("points_possible"),
            task_type=task.get("type", "other"),
            title=task.get("title", "")
        ).score
    
    return sorted(tasks, key=get_priority_score, reverse=True)
