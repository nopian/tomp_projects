#!/usr/bin/env python3
"""
Export the projects database to GeoJSON for map integration.

Writes data/projects.geojson containing every project with coordinates
as a Point feature. Properties carry the standardized project fields
(raw_data is omitted to keep the file lean). Features are sorted by
source and project_id so the file diffs cleanly in git.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_collection.database import ProjectDatabase

logger = logging.getLogger(__name__)

OUTPUT_PATH = project_root / "data" / "projects.geojson"

# Standardized fields exposed as GeoJSON properties
PROPERTY_FIELDS = (
    "source", "project_id", "name", "description", "status",
    "address", "application_date", "collection_date", "url", "updated_at"
)


def project_to_feature(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a project row to a GeoJSON Point feature.

    Args:
        project: Project dictionary from the database

    Returns:
        GeoJSON feature dictionary
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [project["longitude"], project["latitude"]],
        },
        "properties": {
            field: project.get(field) for field in PROPERTY_FIELDS
        },
    }


def export_geojson(db: ProjectDatabase, output_path: Path) -> int:
    """
    Export all mappable projects to a GeoJSON file.

    Args:
        db: Database instance
        output_path: Destination file path

    Returns:
        Number of features written
    """
    projects = db.get_all_projects()
    mappable = [
        p for p in projects
        if p.get("latitude") is not None and p.get("longitude") is not None
    ]
    skipped = len(projects) - len(mappable)
    if skipped:
        logger.info(f"Skipping {skipped} projects without coordinates")

    mappable.sort(key=lambda p: (p["source"], str(p["project_id"])))

    collection = {
        "type": "FeatureCollection",
        "features": [project_to_feature(p) for p in mappable],
    }

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=1, ensure_ascii=False)
        f.write("\n")

    logger.info(f"Wrote {len(mappable)} features to {output_path}")
    return len(mappable)


def main() -> None:
    """Run the GeoJSON export."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db = ProjectDatabase()
    count = export_geojson(db, OUTPUT_PATH)
    print(f"Exported {count} projects to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
