"""
Fetch water infrastructure projects from Mount Pleasant Water ArcGIS service.
"""
import requests
import logging
from datetime import datetime
from typing import List, Dict, Any

from data_collection.database import ProjectDatabase

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
MAX_RESULT_COUNT = 200
COORDINATE_SYSTEM = "4326"
MILLISECONDS_PER_SECOND = 1000

# User agent for API requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)


class WaterProjectsFetcher:
    """Fetches water infrastructure projects from MP Water ArcGIS service."""

    def __init__(self):
        self.url = (
            "https://gis.mpwonline.com/arcgis/rest/services/"
            "DeveloperProjects/FeatureServer/2/query"
        )
        self.params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": COORDINATE_SYSTEM,
            "returnCentroid": "true",
            "resultRecordCount": str(MAX_RESULT_COUNT),
            "f": "pjson"
        }
        self.headers = {'User-Agent': USER_AGENT}
        self.source = "water"
    
    def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch raw data from Mount Pleasant Water API.
        
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
            logger.error(f"Failed to fetch water projects data: {e}")
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
            logger.warning("Invalid data structure from water projects API")
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
                centroid = feature.get("centroid", {})
                
                project_id = attributes.get("PROJ_ID", "")
                
                # Skip residential projects
                if project_id.startswith('RSAN'):
                    continue
                
                # Extract coordinates from centroid
                latitude = centroid.get("y")
                longitude = centroid.get("x")
                
                # Parse project dates if available (timestamps in ms)
                application_date = None
                if attributes.get("created_date"):
                    try:
                        timestamp = int(attributes["created_date"])
                        timestamp = timestamp / MILLISECONDS_PER_SECOND
                        application_date = datetime.fromtimestamp(
                            timestamp
                        ).date()
                    except (ValueError, TypeError):
                        pass
                
                # Build project record with correct field names
                status_parts = [
                    attributes.get('STATUS', ''),
                    attributes.get('PHASE', '')
                ]
                status = " - ".join(filter(None, status_parts))

                project = {
                    "project_id": str(project_id),
                    "name": attributes.get("PROJECTNAME", ""),
                    "description": attributes.get("WebsiteDesc", ""),
                    "status": status,
                    "address": attributes.get("PROJ_ADDR", ""),
                    "application_date": application_date or collection_date,
                    "collection_date": collection_date,
                    "latitude": latitude,
                    "longitude": longitude,
                    "url": attributes.get("PIPES_LINK"),
                    "raw_data": {
                        "attributes": attributes,
                        "centroid": centroid,
                        "field_mapping": field_dict
                    }
                }
                
                projects.append(project)
                
            except Exception as e:
                logger.error(f"Error parsing water project: {e}")
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
            logger.info("Fetching water projects data...")
            raw_data = self.fetch_data()
            
            logger.info("Parsing water projects...")
            projects = self.parse_projects(raw_data)
            
            # Filter out existing projects
            existing_ids = db.get_existing_project_ids(self.source)
            new_projects = [
                p for p in projects 
                if p["project_id"] not in existing_ids
            ]
            
            logger.info(f"Found {len(new_projects)} new water projects")
            
            # Insert new projects
            added_count = db.insert_projects(new_projects, self.source)
            
            # Log collection run
            db.log_collection_run(self.source, True, added_count)
            
            logger.info(f"Successfully added {added_count} water projects")
            return added_count
            
        except Exception as e:
            error_msg = f"Water projects collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            return 0


def main():
    """Run water projects data collection."""
    logging.basicConfig(level=logging.INFO)
    
    db = ProjectDatabase()
    fetcher = WaterProjectsFetcher()
    
    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new water projects")


if __name__ == "__main__":
    main()