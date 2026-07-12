"""
Database utilities for Mount Pleasant development projects.
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ProjectDatabase:
    """SQLite database manager for development projects."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            # Use absolute path relative to project root
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "projects.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    project_id TEXT,
                    name TEXT,
                    description TEXT,
                    status TEXT,
                    application_date DATE,
                    collection_date DATE,
                    latitude REAL,
                    longitude REAL,
                    address TEXT,
                    url TEXT,
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, project_id)
                );
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN,
                    records_added INTEGER,
                    error_message TEXT
                );
            """)
            
            # Create indexes for better query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_source ON projects(source);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_coords ON projects(latitude, longitude);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_date ON projects(application_date);")
    
    def insert_projects(self, projects: List[Dict[str, Any]], source: str) -> int:
        """
        Insert new projects and refresh existing ones.

        New (source, project_id) pairs are inserted. Existing ones get
        their mutable fields (name, description, status, address,
        coordinates, url, raw_data) refreshed so status changes at the
        source are captured. Original application/collection dates are
        preserved, and coordinates are never overwritten with NULL.

        Args:
            projects: List of project dictionaries
            source: Data source identifier

        Returns:
            Number of new records added (updates not counted)
        """
        existing_ids = self.get_existing_project_ids(source)
        added_count = 0

        with sqlite3.connect(self.db_path) as conn:
            for project in projects:
                try:
                    # Convert raw data to JSON string
                    raw_data = json.dumps(project.get('raw_data', {}))

                    conn.execute("""
                        INSERT INTO projects (
                            source, project_id, name, description, status,
                            application_date, collection_date, latitude, longitude,
                            address, url, raw_data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source, project_id) DO UPDATE SET
                            name = excluded.name,
                            description = excluded.description,
                            status = excluded.status,
                            address = excluded.address,
                            latitude = COALESCE(excluded.latitude, latitude),
                            longitude = COALESCE(excluded.longitude, longitude),
                            url = excluded.url,
                            raw_data = excluded.raw_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        source,
                        project.get('project_id'),
                        project.get('name'),
                        project.get('description'),
                        project.get('status'),
                        project.get('application_date'),
                        project.get('collection_date', datetime.now().date()),
                        project.get('latitude'),
                        project.get('longitude'),
                        project.get('address'),
                        project.get('url'),
                        raw_data
                    ))

                    if project.get('project_id') not in existing_ids:
                        added_count += 1
                        existing_ids.add(project.get('project_id'))

                except Exception as e:
                    logger.error(f"Error inserting project {project.get('project_id', 'unknown')}: {e}")
                    continue

        return added_count

    def mark_inactive_projects(
        self,
        source: str,
        active_ids: List[str],
        inactive_status: str = "Archived"
    ) -> int:
        """
        Mark projects no longer present at the source as inactive.

        Useful for sources that only publish currently-active items
        (e.g. planning council agendas), where disappearing from the
        feed means the item was decided or withdrawn.

        Args:
            source: Data source identifier
            active_ids: Project IDs currently present at the source
            inactive_status: Status to assign to missing projects

        Returns:
            Number of projects marked inactive
        """
        if not active_ids:
            logger.warning(
                f"No active IDs supplied for {source}; skipping archive pass"
            )
            return 0

        placeholders = ",".join("?" for _ in active_ids)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                UPDATE projects
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE source = ?
                  AND status != ?
                  AND project_id NOT IN ({placeholders})
            """, [inactive_status, source, inactive_status, *active_ids])
            return cursor.rowcount
    
    def log_collection_run(self, source: str, success: bool, records_added: int, error_message: str = None) -> None:
        """
        Log a data collection run.
        
        Args:
            source: Data source identifier
            success: Whether collection succeeded
            records_added: Number of records added
            error_message: Error message if failed
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO collection_runs (source, success, records_added, error_message)
                VALUES (?, ?, ?, ?)
            """, (source, success, records_added, error_message))
    
    def get_all_projects(self) -> List[Dict[str, Any]]:
        """
        Get all projects from database.
        
        Returns:
            List of project dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM projects 
                ORDER BY application_date DESC, created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_projects_by_source(self, source: str) -> List[Dict[str, Any]]:
        """
        Get projects from a specific source.
        
        Args:
            source: Data source identifier
            
        Returns:
            List of project dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM projects 
                WHERE source = ?
                ORDER BY application_date DESC, created_at DESC
            """, (source,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_existing_project_ids(self, source: str) -> set:
        """
        Get set of existing project IDs for a source.
        
        Args:
            source: Data source identifier
            
        Returns:
            Set of existing project IDs
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT project_id FROM projects 
                WHERE source = ? AND project_id IS NOT NULL
            """, (source,))
            return {row[0] for row in cursor.fetchall()}
    
    def get_project_ids_with_coordinates(self, source: str) -> set:
        """
        Get project IDs for a source that already have coordinates.

        Args:
            source: Data source identifier

        Returns:
            Set of project IDs with non-null coordinates
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT project_id FROM projects
                WHERE source = ? AND project_id IS NOT NULL
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
            """, (source,))
            return {row[0] for row in cursor.fetchall()}

    def get_collection_status(self) -> List[Dict[str, Any]]:
        """
        Get latest collection run status for each source.
        
        Returns:
            List of collection status dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT source, 
                       MAX(run_date) as last_run,
                       success,
                       records_added,
                       error_message
                FROM collection_runs 
                GROUP BY source
                ORDER BY last_run DESC
            """)
            return [dict(row) for row in cursor.fetchall()]