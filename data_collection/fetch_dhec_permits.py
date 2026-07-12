"""
Fetch environmental permits from SC DES (formerly DHEC) public notices.

SC DHEC's environmental programs moved to the SC Department of
Environmental Services (DES) in 2024; the old epermweb.dhec.sc.gov
endpoint now redirects to epermitting.des.sc.gov.
"""
import requests
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from data_collection.database import ProjectDatabase
from data_collection.http_session import create_session

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
MILLISECONDS_PER_SECOND = 1000
ISO_DATE_LENGTH = 10  # 'YYYY-MM-DD' prefix of ISO timestamps

# User agent for API requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)

# The retired DHEC domain redirects here (with an expired certificate,
# so browsers never reach the redirect); rewrite URLs proactively
OLD_DOMAIN_PREFIX = "https://epermweb.dhec.sc.gov/"
NEW_DOMAIN_PREFIX = "https://epermitting.des.sc.gov/ext/"


class DHECPermitsFetcher:
    """Fetches environmental permits from SC DES public notices API."""

    def __init__(self):
        self.url = (
            "https://epermitting.des.sc.gov/ext/ncore/ss/publicnoticeslist?"
            "includeMetadataInResponse=false&loadChildren=false&"
            "queryParams=%7B%22filter%22:%5B%7B%7D%5D%7D"
        )
        self.headers = {'User-Agent': USER_AGENT}
        self.source = "dhec"
        self.session = create_session()
    
    def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch raw data from DHEC API.
        
        Returns:
            Raw API response data
            
        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = self.session.get(
                self.url,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch DHEC data: {e}")
            raise
    
    def _parse_notice_date(self, result: Dict[str, Any]) -> Optional[date]:
        """
        Parse the public notice date from an API record.

        Prefers the ISO `startDate` (notice start); falls back to the
        legacy `applicationDate` millisecond timestamp if present.

        Args:
            result: Single record from the API response

        Returns:
            Parsed date, or None if no usable date found
        """
        start_date = result.get("startDate")
        if start_date:
            try:
                return date.fromisoformat(str(start_date)[:ISO_DATE_LENGTH])
            except ValueError:
                pass

        if result.get("applicationDate"):
            try:
                timestamp = int(result["applicationDate"])
                timestamp = timestamp / MILLISECONDS_PER_SECOND
                return datetime.fromtimestamp(timestamp).date()
            except (ValueError, TypeError):
                pass

        return None

    def _build_notice_url(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Build the public-facing URL for a notice record.

        Args:
            result: Single record from the API response

        Returns:
            URL string, or None if no identifier available
        """
        site_url = result.get("siteProfileUrl")
        if site_url:
            return site_url.replace(OLD_DOMAIN_PREFIX, NEW_DOMAIN_PREFIX)

        permit_id = result.get("id")
        if permit_id:
            return (
                f"https://epermitting.des.sc.gov/ext/ncore/external/"
                f"publicnotice/info/{permit_id}/details"
            )
        return None

    def parse_projects(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse raw API data into standardized project format.

        Args:
            data: Raw API response data

        Returns:
            List of standardized project dictionaries
        """
        if "queryResults" not in data:
            logger.warning("Invalid data structure from DHEC API")
            return []

        projects = []
        collection_date = datetime.now().date()

        for result in data["queryResults"]:
            try:
                # Filter for Mount Pleasant projects only
                city = result.get("city", "")
                if not city or "pleasant" not in city.lower():
                    continue

                # Skip private residences
                comments = result.get("comments", "")
                if comments.startswith("PRIVATE"):
                    continue

                application_date = self._parse_notice_date(result)

                name = (
                    result.get("siteName")
                    or result.get("programAreaDescription")
                    or "DES Public Notice"
                )
                status = result.get("publicNotificationTypeDescription", "")
                program_area = result.get("programAreaDescription", "")
                description = " — ".join(
                    part for part in (program_area, comments) if part
                )

                project = {
                    "project_id": str(result.get("id", "")),
                    "name": name,
                    "description": description,
                    "status": status,
                    "address": result.get("address1", ""),
                    "application_date": application_date or collection_date,
                    "collection_date": collection_date,
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "url": self._build_notice_url(result),
                    "raw_data": result
                }

                projects.append(project)

            except Exception as e:
                logger.error(f"Error parsing DHEC permit: {e}")
                continue

        return projects
    
    def fetch_and_store(self, db: ProjectDatabase) -> int:
        """
        Fetch data and store in database.
        
        Args:
            db: Database instance
            
        Returns:
            Number of new projects added

        Raises:
            Exception: If collection fails (the failed run is logged first)
        """
        try:
            logger.info("Fetching DHEC permits data...")
            raw_data = self.fetch_data()
            
            logger.info("Parsing DHEC permits...")
            projects = self.parse_projects(raw_data)

            # Insert new permits and refresh existing ones
            added_count = db.insert_projects(projects, self.source)
            
            # Log collection run
            db.log_collection_run(self.source, True, added_count)
            
            logger.info(f"Successfully added {added_count} DHEC permits")
            return added_count
            
        except Exception as e:
            error_msg = f"DHEC collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            raise


def main():
    """Run DHEC permits data collection."""
    logging.basicConfig(level=logging.INFO)
    
    db = ProjectDatabase()
    fetcher = DHECPermitsFetcher()
    
    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new DHEC permits")


if __name__ == "__main__":
    main()