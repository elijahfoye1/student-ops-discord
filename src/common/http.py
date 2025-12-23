"""HTTP client with exponential backoff retries."""

import time
import logging
from typing import Optional, Dict, Any

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


class HTTPClient:
    """HTTP client with automatic retries and exponential backoff."""
    
    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)
    
    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """Make an HTTP request with retries."""
        url = f"{self.base_url}{endpoint}" if self.base_url else endpoint
        kwargs.setdefault("timeout", self.timeout)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (Timeout, ConnectionError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            except requests.HTTPError as e:
                # Don't retry client errors (4xx), only server errors (5xx)
                if e.response is not None and 400 <= e.response.status_code < 500:
                    raise
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Server error (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            except RequestException as e:
                last_exception = e
                logger.error(f"Request failed: {e}")
                raise
        
        raise last_exception
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a GET request."""
        return self._request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a POST request."""
        return self._request("POST", endpoint, **kwargs)
    
    def get_json(self, endpoint: str, **kwargs) -> Any:
        """Make a GET request and return JSON."""
        response = self.get(endpoint, **kwargs)
        return response.json()
    
    def post_json(self, endpoint: str, json_data: Dict[str, Any], **kwargs) -> Any:
        """Make a POST request with JSON body and return JSON."""
        response = self.post(endpoint, json=json_data, **kwargs)
        try:
            return response.json()
        except ValueError:
            return None
