"""Canvas LMS API client."""

import os
import logging
from typing import List, Dict, Any, Optional, Iterator

from src.common.http import HTTPClient

logger = logging.getLogger(__name__)


class CanvasClient:
    """
    Client for the Canvas LMS REST API.
    
    Uses pagination and handles rate limiting via the HTTPClient.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None
    ):
        """
        Initialize Canvas client.
        
        Args:
            base_url: Canvas instance URL (e.g., https://school.instructure.com)
            token: Canvas API access token
        
        Falls back to environment variables if not provided.
        """
        self.base_url = (base_url or os.environ.get("CANVAS_BASE_URL", "")).rstrip("/")
        self.token = token or os.environ.get("CANVAS_TOKEN", "")
        
        if not self.base_url:
            logger.warning("CANVAS_BASE_URL not configured")
        if not self.token:
            logger.warning("CANVAS_TOKEN not configured")
        
        self.http = HTTPClient(
            base_url=f"{self.base_url}/api/v1" if self.base_url else "",
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {}
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        return bool(self.base_url and self.token)
    
    def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 10
    ) -> Iterator[Dict[str, Any]]:
        """
        Iterate through paginated API results.
        
        Yields individual items from each page.
        """
        params = params or {}
        params.setdefault("per_page", 100)
        
        url = endpoint
        page_count = 0
        
        while url and page_count < max_pages:
            try:
                response = self.http.get(url, params=params if page_count == 0 else None)
                data = response.json()
                
                if isinstance(data, list):
                    for item in data:
                        yield item
                else:
                    yield data
                    break
                
                # Check for next page in Link header
                link_header = response.headers.get("Link", "")
                url = self._parse_next_link(link_header)
                page_count += 1
                
            except Exception as e:
                logger.error(f"Pagination error at {url}: {e}")
                break
    
    def _parse_next_link(self, link_header: str) -> Optional[str]:
        """Parse the 'next' URL from a Link header."""
        if not link_header:
            return None
        
        for part in link_header.split(","):
            if 'rel="next"' in part:
                # Extract URL between < and >
                start = part.find("<")
                end = part.find(">")
                if start != -1 and end != -1:
                    return part[start + 1:end]
        return None
    
    def get_courses(
        self,
        enrollment_state: str = "active",
        include: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of courses for the current user.
        
        Args:
            enrollment_state: Filter by enrollment state (active, completed, etc.)
            include: Additional data to include (e.g., ["term", "total_scores"])
        
        Returns:
            List of course dictionaries.
        """
        params = {
            "enrollment_state": enrollment_state
        }
        
        if include:
            params["include[]"] = include
        
        courses = list(self._paginate("/courses", params))
        logger.info(f"Fetched {len(courses)} courses")
        return courses
    
    def get_assignments(
        self,
        course_id: int,
        include: Optional[List[str]] = None,
        order_by: str = "due_at"
    ) -> List[Dict[str, Any]]:
        """
        Get assignments for a course.
        
        Args:
            course_id: Canvas course ID
            include: Additional data (e.g., ["submission", "score_statistics"])
            order_by: Field to order by (due_at, name, position)
        
        Returns:
            List of assignment dictionaries.
        """
        params = {
            "order_by": order_by
        }
        
        if include:
            params["include[]"] = include
        
        try:
            assignments = list(self._paginate(f"/courses/{course_id}/assignments", params))
            logger.info(f"Fetched {len(assignments)} assignments for course {course_id}")
            return assignments
        except Exception as e:
            logger.error(f"Failed to fetch assignments for course {course_id}: {e}")
            return []
    
    def get_announcements(
        self,
        course_id: int,
        only_latest: bool = True,
        max_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get announcements for a course.
        
        Args:
            course_id: Canvas course ID
            only_latest: Only get the most recent announcements
            max_count: Maximum number of announcements to return
        
        Returns:
            List of announcement dictionaries.
        """
        params = {
            "context_codes[]": f"course_{course_id}",
            "per_page": max_count
        }
        
        try:
            announcements = list(self._paginate("/announcements", params, max_pages=1))
            logger.info(f"Fetched {len(announcements)} announcements for course {course_id}")
            return announcements
        except Exception as e:
            logger.error(f"Failed to fetch announcements for course {course_id}: {e}")
            return []
    
    def get_upcoming_events(self, days: int = 14) -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events.
        
        Args:
            days: Number of days ahead to look
        
        Returns:
            List of calendar event dictionaries.
        """
        from datetime import datetime, timedelta, timezone
        
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=days)
        
        params = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "type": "assignment"
        }
        
        try:
            events = list(self._paginate("/calendar_events", params))
            logger.info(f"Fetched {len(events)} upcoming events")
            return events
        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return []
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get the current user's profile (for testing auth)."""
        try:
            return self.http.get_json("/users/self/profile")
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return {}
