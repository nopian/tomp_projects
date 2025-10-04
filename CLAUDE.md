## Code Style Guidelines

### General Python Guidelines
- Use Python 3.8+ features
- Follow PEP 8 style guide
- Maximum line length: 88 characters (Black formatter)
- Use type hints for all function parameters and returns
- Docstrings for all classes and functions (Google style)
- Keep functions small and focused (max 50 lines; split into helpers if longer)
- Extract magic numbers into named constants

### Imports
```python
# Standard library imports first
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

# Third-party imports
import requests
import pandas as pd
from bs4 import BeautifulSoup

# Local imports
from data_collection.database import ProjectDatabase
```

### Error Handling
- Always use specific exception types
- Log errors with context
- Provide fallback behavior where appropriate
- Never use bare `except:` clauses

### Example Function Style
```python
def fetch_projects(source: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch development projects from external API.

    Args:
        source: Data source identifier (e.g., 'planning_council')
        timeout: Request timeout in seconds

    Returns:
        List of project dictionaries with standardized fields

    Raises:
        ValueError: If source is invalid
        requests.RequestException: If API request fails
    """
    # Implementation here
    pass
```

## Error Handling Patterns
```python
# Good
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
except requests.RequestException as e:
    logger.error(f"Failed to fetch {url}: {e}")
    return None

# Bad - too broad
try:
    response = requests.get(url)
except:
    pass
```

## Logging Guidelines
- Use structured logging with proper levels
- Include context in log messages
- Log progress for long-running operations
- Don't log sensitive information

```python
import logging

logger = logging.getLogger(__name__)

# Good
logger.info(f"Discovered {len(subdomains)} subdomains for {domain}")
logger.error(f"Failed to parse JavaScript file: {filename}", exc_info=True)

# Bad
print(f"Found subdomains: {subdomains}")  # Use logger instead
```

## Project-Specific Guidelines

### Data Fetcher Pattern
All data fetchers should follow this pattern:
```python
class SomeFetcher:
    def __init__(self):
        self.source = "source_name"
        self.url = "api_endpoint"

    def fetch_data(self) -> Dict[str, Any]:
        """Fetch raw data from API/website."""

    def parse_projects(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse raw data into standardized project format."""

    def fetch_and_store(self, db: ProjectDatabase) -> int:
        """Main entry point: fetch, parse, and store."""
```

### Standardized Project Format
All fetchers must output projects with these fields:
- `project_id`: Unique identifier (str)
- `name`: Project name/title (str)
- `description`: Project details (str)
- `status`: Project status (str)
- `address`: Street address (str)
- `application_date`: Submission date (date object)
- `collection_date`: When scraped (date object)
- `latitude`, `longitude`: Coordinates (float)
- `url`: Link to details (str, optional)
- `raw_data`: Original data (dict)

### Constants
Define constants at module level:
```python
# API configuration
DEFAULT_TIMEOUT = 30
MAX_RESULTS = 200
RETRY_ATTEMPTS = 3

# Mount Pleasant coordinates
DEFAULT_LATITUDE = 32.8648
DEFAULT_LONGITUDE = -79.7870
```

### Path Handling
Use `pathlib.Path` for all file operations:
```python
from pathlib import Path

project_root = Path(__file__).parent.parent
db_path = project_root / "data" / "projects.db"
```

## Remember
- Keep it simple - don't over-engineer
- Start with basic functionality, then enhance
- Document assumptions and decisions
- Test with real-world data sources
- Handle API failures gracefully
- Cache coordinates to avoid repeated API calls
- Filter out residential/private projects where appropriate