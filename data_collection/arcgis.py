"""
Shared helpers for querying ArcGIS FeatureServer/MapServer endpoints.
"""
import logging
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)

# Safety cap on pagination loops
MAX_PAGES = 50


def fetch_all_arcgis_pages(
    url: str,
    params: Dict[str, str],
    headers: Dict[str, str],
    page_size: int,
    timeout: int
) -> Dict[str, Any]:
    """
    Fetch all pages of an ArcGIS query, following exceededTransferLimit.

    Args:
        url: ArcGIS layer query endpoint
        params: Base query parameters (must request f=pjson)
        headers: HTTP headers to send
        page_size: Records to request per page
        timeout: Request timeout in seconds

    Returns:
        First page's response dict with `features` from all pages merged

    Raises:
        requests.RequestException: If any page request fails
        ValueError: If a page returns an ArcGIS error payload
    """
    merged: Dict[str, Any] = {}
    offset = 0

    for _ in range(MAX_PAGES):
        page_params = dict(params)
        page_params["resultRecordCount"] = str(page_size)
        page_params["resultOffset"] = str(offset)

        response = requests.get(
            url, params=page_params, headers=headers, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ValueError(f"ArcGIS error from {url}: {data['error']}")

        features = data.get("features", [])
        if not merged:
            merged = data
        else:
            merged["features"].extend(features)

        if not data.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
    else:
        logger.warning(f"Stopped paginating {url} after {MAX_PAGES} pages")

    logger.info(
        f"Fetched {len(merged.get('features', []))} features from {url}"
    )
    return merged
