"""Study tracking data storage and streak calculation."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Default storage path
DATA_DIR = Path(os.getenv("BOT_DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "study_data.json"


def get_default_data() -> Dict[str, Any]:
    """Return default data structure."""
    return {
        "classes": [],
        "sessions": [],
        "streak": {
            "current": 0,
            "best": 0,
            "last_study_date": None
        }
    }


class StudyTracker:
    """Track study sessions and calculate streaks."""
    
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or DATA_FILE
        self._data: Optional[Dict[str, Any]] = None
    
    def _ensure_dir(self) -> None:
        """Ensure data directory exists."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """Load data from disk."""
        if self._data is not None:
            return self._data
        
        if not self.data_file.exists():
            logger.info(f"Data file not found, using defaults: {self.data_file}")
            self._data = get_default_data()
            return self._data
        
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"Loaded data from {self.data_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load data, using defaults: {e}")
            self._data = get_default_data()
        
        # Merge with defaults
        default = get_default_data()
        for key, value in default.items():
            if key not in self._data:
                self._data[key] = value
        
        return self._data
    
    def save(self) -> None:
        """Save data to disk."""
        if self._data is None:
            return
        
        self._ensure_dir()
        
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        logger.info(f"Saved data to {self.data_file}")
    
    # ========== Classes ==========
    
    def get_classes(self) -> List[str]:
        """Get list of classes."""
        return self.load().get("classes", [])
    
    def add_class(self, class_name: str) -> bool:
        """Add a class. Returns True if added, False if already exists."""
        data = self.load()
        class_name = class_name.upper().strip()
        
        if class_name in data["classes"]:
            return False
        
        data["classes"].append(class_name)
        data["classes"].sort()
        self.save()
        return True
    
    def remove_class(self, class_name: str) -> bool:
        """Remove a class. Returns True if removed, False if not found."""
        data = self.load()
        class_name = class_name.upper().strip()
        
        if class_name not in data["classes"]:
            return False
        
        data["classes"].remove(class_name)
        self.save()
        return True
    
    # ========== Sessions ==========
    
    def log_session(self, class_name: str, minutes: int) -> Dict[str, Any]:
        """
        Log a study session.
        
        Returns session info including updated streak.
        """
        data = self.load()
        class_name = class_name.upper().strip()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Auto-add class if not exists
        if class_name and class_name not in data["classes"]:
            data["classes"].append(class_name)
            data["classes"].sort()
        
        # Create session
        session = {
            "date": today,
            "class": class_name,
            "minutes": minutes,
            "timestamp": datetime.now().isoformat()
        }
        data["sessions"].append(session)
        
        # Update streak
        streak_info = self._update_streak(today)
        
        self.save()
        
        return {
            "session": session,
            "streak": streak_info
        }
    
    def _update_streak(self, today: str) -> Dict[str, Any]:
        """Update streak based on new session."""
        data = self.load()
        streak = data["streak"]
        
        last_date = streak.get("last_study_date")
        
        if last_date is None:
            # First ever session
            streak["current"] = 1
            streak["best"] = 1
        elif last_date == today:
            # Already studied today, no change
            pass
        else:
            # Check if yesterday
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_date == yesterday:
                # Streak continues
                streak["current"] += 1
                streak["best"] = max(streak["best"], streak["current"])
            else:
                # Streak broken, start new
                streak["current"] = 1
        
        streak["last_study_date"] = today
        
        return streak
    
    def get_streak(self) -> Dict[str, Any]:
        """Get current streak info, updating if needed."""
        data = self.load()
        streak = data["streak"]
        
        # Check if streak is still valid
        last_date = streak.get("last_study_date")
        if last_date:
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            if last_date != today and last_date != yesterday:
                # Streak is broken
                streak["current"] = 0
                self.save()
        
        return streak
    
    # ========== Stats ==========
    
    def get_week_stats(self) -> Dict[str, Any]:
        """Get this week's study stats by class."""
        data = self.load()
        sessions = data.get("sessions", [])
        
        # Get dates for this week (last 7 days)
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        week_ago_str = week_ago.strftime("%Y-%m-%d")
        
        # Filter to this week
        week_sessions = [
            s for s in sessions 
            if s.get("date", "") >= week_ago_str
        ]
        
        # Aggregate by class
        by_class = {}
        total_minutes = 0
        total_sessions = 0
        
        for session in week_sessions:
            cls = session.get("class", "General")
            mins = session.get("minutes", 0)
            
            if cls not in by_class:
                by_class[cls] = {"minutes": 0, "sessions": 0}
            
            by_class[cls]["minutes"] += mins
            by_class[cls]["sessions"] += 1
            total_minutes += mins
            total_sessions += 1
        
        # Days studied
        days_studied = len(set(s.get("date") for s in week_sessions))
        
        return {
            "by_class": by_class,
            "total_minutes": total_minutes,
            "total_sessions": total_sessions,
            "days_studied": days_studied,
            "avg_per_day": total_minutes / 7 if total_minutes > 0 else 0
        }
    
    def get_neglected_classes(self, days: int = 7) -> List[str]:
        """Get classes not studied in the last N days."""
        data = self.load()
        classes = data.get("classes", [])
        sessions = data.get("sessions", [])
        
        if not classes:
            return []
        
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Find classes studied recently
        recent_classes = set()
        for session in sessions:
            if session.get("date", "") >= cutoff:
                recent_classes.add(session.get("class", ""))
        
        # Find neglected classes
        neglected = [cls for cls in classes if cls not in recent_classes]
        
        return neglected
    
    def get_today_summary(self) -> Dict[str, Any]:
        """Get today's study summary."""
        data = self.load()
        sessions = data.get("sessions", [])
        today = datetime.now().strftime("%Y-%m-%d")
        
        today_sessions = [s for s in sessions if s.get("date") == today]
        
        total_minutes = sum(s.get("minutes", 0) for s in today_sessions)
        classes_studied = list(set(s.get("class", "") for s in today_sessions))
        
        return {
            "total_minutes": total_minutes,
            "session_count": len(today_sessions),
            "classes": classes_studied
        }
