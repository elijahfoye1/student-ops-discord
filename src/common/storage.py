"""State storage with atomic writes."""

import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default state directory
STATE_DIR = Path("state")
STATE_FILE = STATE_DIR / "state.json"


def get_default_state() -> Dict[str, Any]:
    """Return the default state structure."""
    return {
        "last_run": {
            "canvas": None,
            "daily_brief": None,
            "news": None,
            "weekly_report": None
        },
        "seen_tasks": {},
        "sent_events": {},
        "last_announcements_seen": {},
        "last_news_seen": {}
    }


class StateStore:
    """State storage with atomic writes and default initialization."""
    
    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or STATE_FILE
        self._state: Optional[Dict[str, Any]] = None
    
    def _ensure_dir(self) -> None:
        """Ensure the state directory exists."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """
        Load state from disk.
        
        Returns default state if file doesn't exist.
        """
        if self._state is not None:
            return self._state
        
        if not self.state_file.exists():
            logger.info(f"State file not found, using defaults: {self.state_file}")
            self._state = get_default_state()
            return self._state
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                self._state = json.load(f)
            logger.info(f"Loaded state from {self.state_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state, using defaults: {e}")
            self._state = get_default_state()
        
        # Merge with defaults to handle schema changes
        default = get_default_state()
        for key, value in default.items():
            if key not in self._state:
                self._state[key] = value
        
        return self._state
    
    def save(self) -> None:
        """
        Save state to disk atomically.
        
        Uses a temp file + rename to prevent corruption.
        """
        if self._state is None:
            logger.warning("No state to save")
            return
        
        self._ensure_dir()
        
        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(
            dir=self.state_file.parent,
            prefix=".state_",
            suffix=".json"
        )
        
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
            
            # Atomic rename
            os.replace(temp_path, self.state_file)
            logger.info(f"Saved state to {self.state_file}")
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        state = self.load()
        return state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in state (does not save automatically)."""
        state = self.load()
        state[key] = value
    
    def update_last_run(self, job_name: str) -> None:
        """Update the last run timestamp for a job."""
        from src.common.time import now_utc
        state = self.load()
        state["last_run"][job_name] = now_utc().isoformat()
    
    def get_seen_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a previously seen task."""
        state = self.load()
        return state.get("seen_tasks", {}).get(task_id)
    
    def update_seen_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """Update info for a seen task."""
        state = self.load()
        if "seen_tasks" not in state:
            state["seen_tasks"] = {}
        state["seen_tasks"][task_id] = task_info
