#!/usr/bin/env python3
"""
One-time (idempotent) repair of historical data quality issues.

Fixes applied:
1. DHEC rows: rebuild name, description, status, url and application
   date from stored raw_data. The old parser read fields the API never
   populated, so every row was named "DHEC Permit" with a dead
   epermweb.dhec.sc.gov URL and a collection-date fallback date.
2. Stormwater rows stored with the old placeholder coordinates
   (32.530988, -79.195347 — a point in the Atlantic Ocean): re-look-up
   real coordinates from the TMS parcel ID, or NULL them out.
3. Stormwater project IDs: migrate from the old location+date scheme
   (which collapsed distinct projects noticed on the same parcel and
   day) to the location+date+project-number scheme. IDs are
   recomputed from stored raw_data.

Safe to re-run; rows already repaired are simply rewritten with the
same values.
"""
import json
import logging
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_collection.database import ProjectDatabase
from data_collection.fetch_dhec_permits import DHECPermitsFetcher
from data_collection.fetch_stormwater import StormwaterFetcher

logger = logging.getLogger(__name__)

# Old placeholder coordinates (offshore point, never a real location)
OLD_DEFAULT_LATITUDE = 32.530988
OLD_DEFAULT_LONGITUDE = -79.195347
COORD_TOLERANCE = 1e-6


def repair_dhec_rows(db: ProjectDatabase) -> int:
    """
    Rebuild DHEC project fields from stored raw_data.

    Args:
        db: Database instance

    Returns:
        Number of rows updated
    """
    fetcher = DHECPermitsFetcher()
    updated = 0

    with sqlite3.connect(db.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, raw_data FROM projects WHERE source = 'dhec'"
        ).fetchall()

        for row in rows:
            try:
                raw = json.loads(row["raw_data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Row {row['id']}: unparseable raw_data")
                continue

            name = (
                raw.get("siteName")
                or raw.get("programAreaDescription")
                or "DES Public Notice"
            )
            comments = raw.get("comments") or ""
            program_area = raw.get("programAreaDescription") or ""
            description = " — ".join(
                part for part in (program_area, comments) if part
            )
            status = raw.get("publicNotificationTypeDescription") or ""
            url = fetcher._build_notice_url(raw)
            notice_date = fetcher._parse_notice_date(raw)

            conn.execute("""
                UPDATE projects
                SET name = ?, description = ?, status = ?, url = ?,
                    application_date = COALESCE(?, application_date),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (name, description, status, url, notice_date, row["id"]))
            updated += 1

    logger.info(f"Repaired {updated} DHEC rows")
    return updated


def repair_stormwater_coords(db: ProjectDatabase) -> int:
    """
    Replace old placeholder ocean coordinates on stormwater rows.

    Args:
        db: Database instance

    Returns:
        Number of rows updated
    """
    fetcher = StormwaterFetcher()
    updated = 0

    with sqlite3.connect(db.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, address FROM projects
            WHERE source = 'stormwater'
              AND ABS(latitude - ?) < ? AND ABS(longitude - ?) < ?
        """, (OLD_DEFAULT_LATITUDE, COORD_TOLERANCE,
              OLD_DEFAULT_LONGITUDE, COORD_TOLERANCE)).fetchall()

        logger.info(f"Found {len(rows)} stormwater rows with placeholder "
                    "coordinates")

        for row in rows:
            latitude, longitude = fetcher.lookup_coordinates(
                row["address"] or ""
            )
            conn.execute("""
                UPDATE projects
                SET latitude = ?, longitude = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (latitude, longitude, row["id"]))
            updated += 1
            outcome = "located" if latitude else "cleared"
            logger.info(f"Row {row['id']} ({row['address']}): {outcome}")

    logger.info(f"Repaired {updated} stormwater rows")
    return updated


def migrate_stormwater_ids(db: ProjectDatabase) -> int:
    """
    Migrate stormwater project IDs to include the project number.

    Args:
        db: Database instance

    Returns:
        Number of rows migrated
    """
    fetcher = StormwaterFetcher()
    migrated = 0

    with sqlite3.connect(db.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, project_id, raw_data FROM projects
            WHERE source = 'stormwater'
        """).fetchall()

        for row in rows:
            try:
                raw = json.loads(row["raw_data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Row {row['id']}: unparseable raw_data")
                continue

            new_id = fetcher.build_project_id(raw)
            if new_id == row["project_id"]:
                continue

            try:
                conn.execute("""
                    UPDATE projects
                    SET project_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_id, row["id"]))
                migrated += 1
            except sqlite3.IntegrityError:
                # Another row already carries the new ID: this row is a
                # duplicate of the same notice, so drop it.
                logger.info(f"Row {row['id']} duplicates {new_id}; deleting")
                conn.execute(
                    "DELETE FROM projects WHERE id = ?", (row["id"],)
                )

    logger.info(f"Migrated {migrated} stormwater project IDs")
    return migrated


def main() -> None:
    """Run all data repairs."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db = ProjectDatabase()
    dhec_count = repair_dhec_rows(db)
    stormwater_count = repair_stormwater_coords(db)
    migrated_count = migrate_stormwater_ids(db)

    print(f"Repaired {dhec_count} DHEC rows, "
          f"{stormwater_count} stormwater coordinate rows; "
          f"migrated {migrated_count} stormwater IDs")


if __name__ == "__main__":
    main()
