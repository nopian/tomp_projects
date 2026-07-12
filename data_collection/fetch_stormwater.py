"""
Fetch stormwater projects from Mount Pleasant town website with TMS lookup.
"""
import re
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

import requests
import pandas as pd
from bs4 import BeautifulSoup

from data_collection.database import ProjectDatabase
from data_collection.http_session import create_session

logger = logging.getLogger(__name__)

# API Configuration
DEFAULT_TIMEOUT = 30
PARCEL_API_TIMEOUT = 10
COORDINATE_SYSTEM = "4326"

# User agent for requests
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)

# TMS parcel ID format
TMS_REGEX = r"[0-9]{3}-[0-9]{2}-[0-9]{2}-[0-9]{3}"

# Table parsing constants
TABLE_CLASS = "telerik-reTable-2"
TABLE_COLUMNS = ("ProjectName", "Location", "ProjectNumber",
                 "OpenDate", "CloseDate")
NOTICE_BASE_URL = "https://www.tompsc.com"

# Known bad dates on the town website mapped to corrections
DATE_CORRECTIONS = {
    "9/12/222": "9/12/2022",
}


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
        self.session = create_session()
        # Cache TMS lookups within a run (same parcel can appear twice)
        self._coord_cache: Dict[str, Tuple[Optional[float], Optional[float]]] = {}

    @staticmethod
    def _cell_text(cell: Any) -> str:
        """Extract whitespace-normalized text from a table cell."""
        return ' '.join(cell.get_text(' ', strip=True).split())

    def _parse_row(self, row: Any) -> Optional[Dict[str, Any]]:
        """
        Parse one table row into a raw record dict.

        Args:
            row: BeautifulSoup <tr> element

        Returns:
            Record dict with table columns plus URL, or None if the row
            is a header or malformed.
        """
        cells = row.find_all('td')
        if len(cells) < len(TABLE_COLUMNS):
            return None

        values = [self._cell_text(cell) for cell in cells[:len(TABLE_COLUMNS)]]

        # Skip the column-header row and empty rows
        if values[0] == "Project Name" or not any(values):
            return None

        record = dict(zip(TABLE_COLUMNS, values))

        # Each data row links to its notice PDF
        link = row.find('a', href=True)
        url = ""
        if link:
            href = link['href']
            url = href if href.startswith('http') else f"{NOTICE_BASE_URL}{href}"
        record['URL'] = url

        return record

    def fetch_notice_data(self) -> List[Dict[str, Any]]:
        """
        Fetch stormwater construction notices from town website.

        Returns:
            List of project dictionaries from table

        Raises:
            requests.RequestException: If website request fails
            ValueError: If the notice table cannot be found
        """
        response = self.session.get(
            self.notice_url,
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find("table", {"class": TABLE_CLASS})
        if table is None:
            raise ValueError(
                f"Notice table (class={TABLE_CLASS}) not found on "
                f"{self.notice_url}"
            )

        records = []
        for row in table.find_all('tr'):
            record = self._parse_row(row)
            if record:
                records.append(record)

        if not records:
            raise ValueError("No project rows parsed from notice table")

        logger.info(f"Parsed {len(records)} rows from construction notices")
        return records

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

    def _query_parcel_centroid(
        self, tms: str
    ) -> Optional[Tuple[float, float]]:
        """
        Query the parcel API for a TMS ID and return the parcel centroid.

        Args:
            tms: Full TMS parcel ID (with dashes)

        Returns:
            Tuple of (latitude, longitude), or None if lookup failed
        """
        params = {
            "where": f"PARCEL_ID = '{tms.replace('-', '')}'",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": COORDINATE_SYSTEM,
            "resultRecordCount": "1",
            "f": "pjson"
        }

        response = self.session.get(
            self.parcel_api_url,
            params=params,
            headers=self.headers,
            timeout=PARCEL_API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        features = data.get('features') or []
        if not features:
            return None

        # Average the outer-ring vertices for an approximate centroid
        ring = features[0]['geometry']['rings'][0]
        # Drop the closing vertex (duplicate of the first)
        vertices = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
        longitude = sum(v[0] for v in vertices) / len(vertices)
        latitude = sum(v[1] for v in vertices) / len(vertices)
        return (latitude, longitude)

    def lookup_coordinates(
        self, tms_location: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Look up coordinates for a TMS parcel ID.

        Args:
            tms_location: Location string containing TMS parcel ID

        Returns:
            Tuple of (latitude, longitude); (None, None) if lookup fails
            so bogus placeholder points never reach the map.
        """
        tms_matches = self.expand_abbreviated_tms(tms_location)

        if not tms_matches:
            logger.warning(f"No TMS found in location: {tms_location}")
            return (None, None)

        for tms in tms_matches:
            if tms in self._coord_cache:
                return self._coord_cache[tms]
            try:
                coords = self._query_parcel_centroid(tms)
                if coords:
                    self._coord_cache[tms] = coords
                    return coords
            except (requests.RequestException, KeyError, ValueError) as e:
                logger.warning(f"Failed to lookup TMS {tms}: {e}")
                continue

        logger.warning(f"All TMS lookups failed for: {tms_location}")
        return (None, None)

    @staticmethod
    def build_project_id(clean_row: Dict[str, Any]) -> str:
        """
        Build a stable project ID from a cleaned table row.

        Includes the town's project number because multiple notices can
        share a location and open date (e.g. three projects on one
        parcel noticed the same day).

        Args:
            clean_row: Row dict with cleaned column names

        Returns:
            Sanitized project ID string
        """
        loc_part = clean_row.get('Location', '')[:20]
        date_part = clean_row.get('OpenDate', '')
        number_part = clean_row.get('ProjectNumber', '')
        return re.sub(
            r'[^\w\-_]', '_', f"{loc_part}_{date_part}_{number_part}"
        )

    @staticmethod
    def _parse_table_date(value: str) -> Optional[date]:
        """Parse a m/d/yyyy table date, returning None on failure."""
        value = DATE_CORRECTIONS.get(value, value)
        if not value:
            return None
        try:
            return pd.to_datetime(value, format='mixed').date()
        except (ValueError, TypeError):
            return None

    def _derive_status(self, close_date: Optional[date]) -> str:
        """Derive comment-period status from the notice close date."""
        if close_date is None:
            return ""
        if close_date >= datetime.now().date():
            return "Comment Period Open"
        return "Comment Period Closed"

    def parse_projects(
        self,
        raw_data: List[Dict[str, Any]],
        skip_lookup_ids: Optional[set] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse raw table data into standardized project format.

        Args:
            raw_data: List of dictionaries from HTML table
            skip_lookup_ids: Project IDs whose (expensive) TMS coordinate
                lookup should be skipped; their coordinates are returned
                as None and preserved in the database by the upsert.

        Returns:
            List of standardized project dictionaries
        """
        projects = []
        collection_date = datetime.now().date()
        skip_lookup_ids = skip_lookup_ids or set()

        for row in raw_data:
            try:
                # Clean column names
                clean_row = {
                    k.replace(' ', '').replace('\n', ''): v
                    for k, v in row.items()
                }

                application_date = self._parse_table_date(
                    clean_row.get('OpenDate', '')
                )
                close_date = self._parse_table_date(
                    clean_row.get('CloseDate', '')
                )

                location = clean_row.get('Location', '')
                project_id = self.build_project_id(clean_row)

                # Look up coordinates from TMS (new projects only)
                latitude, longitude = (None, None)
                if project_id not in skip_lookup_ids:
                    latitude, longitude = self.lookup_coordinates(location)

                # Build project record
                project = {
                    "project_id": project_id,
                    "name": clean_row.get('ProjectName', ''),
                    "description": (
                        f"Stormwater construction project at {location}"
                    ),
                    "status": self._derive_status(close_date),
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

        Raises:
            Exception: If collection fails (the failed run is logged first)
        """
        try:
            logger.info("Fetching stormwater projects data...")
            raw_data = self.fetch_notice_data()

            logger.info("Parsing stormwater projects...")
            # Skip TMS coordinate lookups for projects that already have
            # coordinates; the upsert preserves them. Projects with failed
            # lookups retry on each run.
            located_ids = db.get_project_ids_with_coordinates(self.source)
            projects = self.parse_projects(
                raw_data, skip_lookup_ids=located_ids
            )

            # Insert new projects and refresh existing ones
            added_count = db.insert_projects(projects, self.source)

            # Log collection run
            db.log_collection_run(self.source, True, added_count)

            logger.info(f"Successfully added {added_count} stormwater projects")
            return added_count

        except Exception as e:
            error_msg = f"Stormwater collection failed: {e}"
            logger.error(error_msg)
            db.log_collection_run(self.source, False, 0, error_msg)
            raise


def main():
    """Run stormwater projects data collection."""
    logging.basicConfig(level=logging.INFO)

    db = ProjectDatabase()
    fetcher = StormwaterFetcher()

    added_count = fetcher.fetch_and_store(db)
    print(f"Added {added_count} new stormwater projects")


if __name__ == "__main__":
    main()
