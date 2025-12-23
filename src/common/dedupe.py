"""Event deduplication using stable hashing."""

import hashlib
import logging
from typing import Dict, Any, Optional

from src.common.time import now_utc

logger = logging.getLogger(__name__)


def hash_event(
    event_type: str,
    event_id: str,
    **extra_keys
) -> str:
    """
    Generate a stable hash for an event.
    
    Args:
        event_type: Type of event (e.g., "deadline_alert", "announcement")
        event_id: Primary identifier (e.g., task_id, announcement_id)
        **extra_keys: Additional keys to include in hash (e.g., due_at)
    
    Returns:
        A hex digest hash string.
    """
    # Sort extra keys for consistent ordering
    parts = [event_type, event_id]
    for key in sorted(extra_keys.keys()):
        value = extra_keys[key]
        if value is not None:
            parts.append(f"{key}={value}")
    
    hash_input = "|".join(parts)
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def already_sent(
    state: Dict[str, Any],
    event_hash: str
) -> bool:
    """
    Check if an event has already been sent.
    
    Args:
        state: The loaded state dictionary
        event_hash: Hash from hash_event()
    
    Returns:
        True if the event was already sent.
    """
    sent_events = state.get("sent_events", {})
    return event_hash in sent_events


def mark_sent(
    state: Dict[str, Any],
    event_hash: str
) -> None:
    """
    Mark an event as sent.
    
    Args:
        state: The loaded state dictionary
        event_hash: Hash from hash_event()
    """
    if "sent_events" not in state:
        state["sent_events"] = {}
    
    state["sent_events"][event_hash] = now_utc().isoformat()
    logger.debug(f"Marked event as sent: {event_hash}")


def cleanup_old_events(
    state: Dict[str, Any],
    max_age_days: int = 30
) -> int:
    """
    Remove events older than max_age_days.
    
    Returns the number of events removed.
    """
    from src.common.time import parse_iso
    from datetime import timedelta
    
    sent_events = state.get("sent_events", {})
    if not sent_events:
        return 0
    
    now = now_utc()
    cutoff = now - timedelta(days=max_age_days)
    
    to_remove = []
    for event_hash, sent_at in sent_events.items():
        sent_dt = parse_iso(sent_at)
        if sent_dt and sent_dt < cutoff:
            to_remove.append(event_hash)
    
    for event_hash in to_remove:
        del sent_events[event_hash]
    
    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old events")
    
    return len(to_remove)


class Deduplicator:
    """
    Convenience wrapper for deduplication operations.
    """
    
    def __init__(self, state: Dict[str, Any]):
        self.state = state
    
    def check_and_mark(
        self,
        event_type: str,
        event_id: str,
        **extra_keys
    ) -> bool:
        """
        Check if event is new, and if so, mark it as sent.
        
        Returns:
            True if the event is new (should be sent).
            False if already sent (should be skipped).
        """
        event_hash = hash_event(event_type, event_id, **extra_keys)
        
        if already_sent(self.state, event_hash):
            logger.debug(f"Skipping duplicate event: {event_type}/{event_id}")
            return False
        
        mark_sent(self.state, event_hash)
        return True
    
    def is_new(
        self,
        event_type: str,
        event_id: str,
        **extra_keys
    ) -> bool:
        """Check if an event is new without marking it."""
        event_hash = hash_event(event_type, event_id, **extra_keys)
        return not already_sent(self.state, event_hash)
    
    def mark(
        self,
        event_type: str,
        event_id: str,
        **extra_keys
    ) -> None:
        """Mark an event as sent."""
        event_hash = hash_event(event_type, event_id, **extra_keys)
        mark_sent(self.state, event_hash)
