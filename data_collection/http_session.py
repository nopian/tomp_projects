"""
Shared HTTP session factory with retries for data fetchers.

Sources like the MPW GIS server intermittently reset connections or
return 5xx from CI runners; retrying with backoff keeps a transient
blip from failing a whole collection run.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Retry configuration
RETRY_ATTEMPTS = 3
BACKOFF_FACTOR = 2  # sleeps ~2s, 4s, 8s between attempts
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


def create_session() -> requests.Session:
    """
    Create a requests session that retries transient failures.

    Retries connection errors, read errors and retryable HTTP status
    codes on GET requests, with exponential backoff.

    Returns:
        Configured requests.Session
    """
    retry = Retry(
        total=RETRY_ATTEMPTS,
        connect=RETRY_ATTEMPTS,
        read=RETRY_ATTEMPTS,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
