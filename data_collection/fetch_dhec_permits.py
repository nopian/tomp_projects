"""
Fetch environmental permits from SC DHEC public notices.
"""
import requests
import logging
from datetime import datetime
from typing import List, Dict, Any

from data_collection.database import ProjectDatabase

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
MILLISECONDS_PER_SECOND = 1000

# User agent for API requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)


class DHECPermitsFetcher:
    """Fetches environmental permits from SC DHEC public notices API."""

    def __init__(self):
        self.url = (
            "https://epermweb.dhec.sc.gov/ncore/ss/publicnoticeslist?"
            "includeMetadataInResponse=false&loadChildren=false&"
            "queryParams=%7B%22filter%22:%5B%7B%7D%5D%7D"
        )
        self.headers = {'User-Agent': USER_AGENT}
        self.source = "dhec"
    
    def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch raw data from DHEC API.
        
        Returns:
            Raw API response data
            
        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = requests.get(
                self.url,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch DHEC data: {e}")
            raise
    
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
                
                # Parse application date
                application_date = None
                if result.get("applicationDate"):
                    try:
                        # DHEC dates are in milliseconds timestamp format
                        timestamp = int(result["applicationDate"])
                        timestamp = timestamp / MILLISECONDS_PER_SECOND
                        application_date = datetime.fromtimestamp(
                            timestamp
                        ).date()
                    except (ValueError, TypeError):
                        pass
                
                # Build project record
                permit_id = result.get('id')
                url = None
                if permit_id:
                    url = (
                        f"https://epermweb.dhec.sc.gov/ncore/external/"
                        f"publicnotice/info/{permit_id}/details"
                    )

                project = {
                    "project_id": str(result.get("id", "")),
                    "name": result.get("permitType", "") or "DHEC Permit",
                    "description": comments or result.get("permitType", ""),
                    "status": result.get("status", ""),
                    "address": result.get("address1", ""),
                    "application_date": application_date or collection_date,
                    "collection_date": collection_date,
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "url": url,
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
        """
        try:
            logger.info("Fetching DHEC permits data...")
            raw_data = self.fetch_data()
            
            logger.info("Parsing DHEC permits...")
            projects = self.parse_projects(raw_data)
            
            # Filter out existing projects
            existing_ids = db.get_existing_project_ids(self.source)
            new_projects = [
                p for p in projects 
                if p["project_id"] not in existing_ids
            ]
            
            logger.info(f"Found {len(new_projects)} new DHEC permits")
            
            # Insert new projects
            added_count = db.insert_projects(new_projects, self.source)
            
            # Log collection run
            db.log_collection_run(self.source, True, added_count)
            
            logger.info(f"Successfully added {added_count} DHEC permits")
            return added_count
            
        except Exception as e:
            error_msg = f"DHEC collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            return 0


def main():
    """Run DHEC permits data collection."""
    logging.basicConfig(level=logging.INFO)
    
    db = ProjectDatabase()
    fetcher = DHECPermitsFetcher()
    
    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new DHEC permits")


if __name__ == "__main__":
    main()