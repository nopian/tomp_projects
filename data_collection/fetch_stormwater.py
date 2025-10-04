"""
Fetch stormwater projects from Mount Pleasant town website with TMS lookup.
"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Any

import requests
import pandas as pd
from bs4 import BeautifulSoup

from data_collection.database import ProjectDatabase

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
PARCEL_API_TIMEOUT = 10
COORDINATE_SYSTEM = "4326"

# Mount Pleasant center coordinates
DEFAULT_LATITUDE = 32.530988
DEFAULT_LONGITUDE = -79.195347

# User agent for requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)

# TMS parcel ID format
TMS_REGEX = r"[0-9]{3}-[0-9]{2}-[0-9]{2}-[0-9]{3}"

# Table parsing constants
TABLE_CLASS = "telerik-reTable-2"
HEADER_LINKS_TO_SKIP = 6


class StormwaterFetcher:
    """Fetches stormwater projects from MP construction notices."""

    def __init__(self):
        self.notice_url = (
            "https://www.tompsc.com/1405/Construction-Public-Notice"
        )
        self.parcel_api_url = (
            "https://maps.tompsc.com/arcgis/rest/services/"
            "Parcel_Search_New/MPSC_Base_New/MapServer/2/query"
        )
        self.headers = {'User-Agent': USER_AGENT}
        self.source = "stormwater"
        self.default_coords = (DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    
    def fetch_notice_data(self) -> List[Dict[str, Any]]:
        """
        Fetch stormwater construction notices from town website.
        
        Returns:
            List of project dictionaries from table
            
        Raises:
            requests.RequestException: If website request fails
        """
        try:
            response = requests.get(
                self.notice_url,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Parse the table using pandas
            table_html = str(soup.select_one(f".{TABLE_CLASS}"))
            df = pd.read_html(table_html)[0]
            new_header = df.iloc[0]
            df = df[1:]
            df.columns = new_header

            # Extract PDF URLs
            table = soup.find("table", {"class": TABLE_CLASS})
            links = table.findAll('a')

            urls = []
            for link in links[HEADER_LINKS_TO_SKIP:]:
                urls.append(f"https://www.tompsc.com{link['href']}")

            df['URL'] = urls[:len(df)]

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Failed to fetch stormwater notices: {e}")
            raise
    
    def expand_abbreviated_tms(self, tms_location: str) -> List[str]:
        """
        Expand abbreviated TMS notations into full TMS IDs.

        Handles formats like:
        - "537-00-00-085, 084" -> ["537-00-00-085", "537-00-00-084"]
        - "559-13-00-030, -031, -032" -> ["559-13-00-030", "559-13-00-031", ...]

        Args:
            tms_location: Location string with TMS IDs

        Returns:
            List of full TMS IDs
        """
        tms_ids = []

        # First, extract full TMS matches
        full_matches = re.findall(TMS_REGEX, tms_location)

        if full_matches:
            # Use the first match as the base for expansions
            base_tms = full_matches[0]
            tms_ids.extend(full_matches)

            # Look for abbreviated suffixes (e.g., ", 084" or ", -031")
            # Pattern: comma followed by optional dash and 2-3 digits
            abbreviated_pattern = r',\s*-?(\d{2,3})(?=\s|,|$)'
            abbreviated_matches = re.findall(abbreviated_pattern, tms_location)

            if abbreviated_matches:
                # Split base TMS into parts
                base_parts = base_tms.split('-')

                for suffix in abbreviated_matches:
                    # Pad suffix to 3 digits
                    suffix_padded = suffix.zfill(3)
                    # Replace last part with new suffix
                    expanded_tms = '-'.join(base_parts[:-1] + [suffix_padded])
                    if expanded_tms not in tms_ids:
                        tms_ids.append(expanded_tms)

        return tms_ids

    def lookup_coordinates(self, tms_location: str) -> tuple:
        """
        Look up coordinates for a TMS parcel ID.

        Args:
            tms_location: Location string containing TMS parcel ID

        Returns:
            Tuple of (latitude, longitude)
        """
        tms_matches = self.expand_abbreviated_tms(tms_location)

        if not tms_matches:
            logger.warning(f"No TMS found in location: {tms_location}")
            return self.default_coords

        for tms in tms_matches:
            try:
                # Clean TMS format for API
                clean_tms = tms.replace('-', '')

                # Query parcel API
                params = {
                    "where": f"PARCEL_ID = '{clean_tms}'",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": COORDINATE_SYSTEM,
                    "resultRecordCount": "1",
                    "f": "pjson"
                }

                response = requests.get(
                    self.parcel_api_url,
                    params=params,
                    headers=self.headers,
                    timeout=PARCEL_API_TIMEOUT
                )
                response.raise_for_status()

                data = response.json()

                if data.get('features') and len(data['features']) > 0:
                    # Extract coordinates from polygon rings
                    feature = data['features'][0]
                    rings = feature['geometry']['rings'][0][0]
                    longitude, latitude = rings[0], rings[1]
                    return (latitude, longitude)

            except Exception as e:
                logger.warning(f"Failed to lookup TMS {tms}: {e}")
                continue

        logger.warning(f"All TMS lookups failed for: {tms_location}")
        return self.default_coords
    
    def parse_projects(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse raw table data into standardized project format.
        
        Args:
            raw_data: List of dictionaries from HTML table
            
        Returns:
            List of standardized project dictionaries
        """
        projects = []
        collection_date = datetime.now().date()
        
        for row in raw_data:
            try:
                # Clean column names
                clean_row = {
                    k.replace(' ', '').replace('\n', ''): v
                    for k, v in row.items()
                }

                # Parse application date
                application_date = None
                open_date = clean_row.get('OpenDate', '')
                # Fix known bad date
                if open_date == '9/12/222':
                    open_date = '9/12/2022'
                if open_date:
                    try:
                        application_date = pd.to_datetime(
                            open_date,
                            format='mixed'
                        ).date()
                    except (ValueError, TypeError):
                        pass

                # Look up coordinates from TMS
                location = clean_row.get('Location', '')
                latitude, longitude = self.lookup_coordinates(location)

                # Generate project ID from location/date
                loc_part = clean_row.get('Location', '')[:20]
                date_part = clean_row.get('OpenDate', '')
                project_id = f"{loc_part}_{date_part}"
                project_id = re.sub(r'[^\w\-_]', '_', project_id)

                # Build project record
                project = {
                    "project_id": project_id,
                    "name": clean_row.get('ProjectName', ''),
                    "description": (
                        f"Stormwater construction project at {location}"
                    ),
                    "status": clean_row.get('Status', ''),
                    "address": location,
                    "application_date": application_date,
                    "collection_date": collection_date,
                    "latitude": latitude,
                    "longitude": longitude,
                    "url": clean_row.get('URL', ''),
                    "raw_data": clean_row
                }

                projects.append(project)
                
            except Exception as e:
                logger.error(f"Error parsing stormwater project: {e}")
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
            logger.info("Fetching stormwater projects data...")
            raw_data = self.fetch_notice_data()
            
            logger.info("Parsing stormwater projects...")
            projects = self.parse_projects(raw_data)
            
            # Filter out existing projects
            existing_ids = db.get_existing_project_ids(self.source)
            new_projects = [
                p for p in projects 
                if p["project_id"] not in existing_ids
            ]
            
            logger.info(f"Found {len(new_projects)} new stormwater projects")
            
            # Insert new projects
            added_count = db.insert_projects(new_projects, self.source)
            
            # Log collection run
            db.log_collection_run(self.source, True, added_count)
            
            logger.info(f"Successfully added {added_count} stormwater projects")
            return added_count
            
        except Exception as e:
            error_msg = f"Stormwater collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            return 0


def main():
    """Run stormwater projects data collection."""
    logging.basicConfig(level=logging.INFO)
    
    db = ProjectDatabase()
    fetcher = StormwaterFetcher()
    
    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new stormwater projects")


if __name__ == "__main__":
    main()