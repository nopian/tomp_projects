"""
Fetch development projects from Town Planning Council ArcGIS service.
"""
import requests
import logging
from datetime import datetime
from typing import List, Dict, Any

from data_collection.database import ProjectDatabase

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
MAX_RESULT_COUNT = 100
COORDINATE_SYSTEM = "4326"

# User agent for API requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)


class PlanningCouncilFetcher:
    """Fetches data from Mount Pleasant Planning Council ArcGIS service."""

    def __init__(self):
        self.url = (
            "https://services8.arcgis.com/lzpM6epdQtzxVX5J/ArcGIS/rest/services/"
            "QobYc/FeatureServer/0/query"
        )
        self.params = {
            "where": "f5 IS NOT NULL",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": COORDINATE_SYSTEM,
            "resultRecordCount": str(MAX_RESULT_COUNT),
            "f": "pjson"
        }
        self.headers = {'User-Agent': USER_AGENT}
        self.source = "planning_council"
    
    def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch raw data from Planning Council API.
        
        Returns:
            Raw API response data
            
        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = requests.get(
                self.url,
                params=self.params,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch planning council data: {e}")
            raise
    
    def parse_projects(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse raw API data into standardized project format.
        
        Args:
            data: Raw API response data
            
        Returns:
            List of standardized project dictionaries
        """
        if "features" not in data or "fields" not in data:
            logger.warning("Invalid data structure from planning council API")
            return []
        
        # Build field mapping from API metadata
        field_dict = {}
        for field in data["fields"]:
            field_dict[field['name']] = field["alias"]
        
        projects = []
        collection_date = datetime.now().date()
        
        for feature in data["features"]:
            try:
                attributes = feature.get("attributes", {})
                geometry = feature.get("geometry", {})
                
                # Skip null entries (f5 is the case number/ID)
                if not attributes.get("f5"):
                    continue
                
                # Extract coordinates
                latitude = geometry.get("y")
                longitude = geometry.get("x")
                
                # Build project record with correct field mapping
                project = {
                    "project_id": str(attributes.get("objectId", "")),  # Use objectId as unique identifier
                    "name": attributes.get("f5", ""),  # Project name/case number like "V-06-25" or "Queens Court Revisions"
                    "description": f"{attributes.get('f7', '')} - {attributes.get('f9', '')}".strip(" -"),  # Group + Description
                    "status": "Active",  # All planning council items are active requests
                    "address": attributes.get("f1", ""),  # Street address
                    "application_date": collection_date,  # Use collection date since no app date available
                    "collection_date": collection_date,
                    "latitude": latitude,
                    "longitude": longitude,
                    "url": attributes.get("f10"),  # Agenda URL
                    "raw_data": {
                        "attributes": attributes,
                        "geometry": geometry,
                        "field_mapping": field_dict
                    }
                }
                
                projects.append(project)
                
            except Exception as e:
                logger.error(f"Error parsing planning council project: {e}")
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
            logger.info("Fetching planning council data...")
            raw_data = self.fetch_data()
            
            logger.info("Parsing planning council projects...")
            projects = self.parse_projects(raw_data)
            
            # Filter out existing projects
            existing_ids = db.get_existing_project_ids(self.source)
            new_projects = [
                p for p in projects 
                if p["project_id"] not in existing_ids
            ]
            
            logger.info(f"Found {len(new_projects)} new planning council projects")
            
            # Insert new projects
            added_count = db.insert_projects(new_projects, self.source)
            
            # Log collection run
            db.log_collection_run(self.source, True, added_count)
            
            logger.info(f"Successfully added {added_count} planning council projects")
            return added_count
            
        except Exception as e:
            error_msg = f"Planning council collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            return 0


def main():
    """Run planning council data collection."""
    logging.basicConfig(level=logging.INFO)
    
    db = ProjectDatabase()
    fetcher = PlanningCouncilFetcher()
    
    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new planning council projects")


if __name__ == "__main__":
    main()