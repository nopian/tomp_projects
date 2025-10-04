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
        Insert or update projects in database.
        
        Args:
            projects: List of project dictionaries
            source: Data source identifier
            
        Returns:
            Number of records added
        """
        added_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            for project in projects:
                try:
                    # Convert raw data to JSON string
                    raw_data = json.dumps(project.get('raw_data', {}))
                    
                    # Insert or ignore (prevents duplicates)
                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO projects (
                            source, project_id, name, description, status,
                            application_date, collection_date, latitude, longitude,
                            address, url, raw_data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    
                    if cursor.rowcount > 0:
                        added_count += 1
                        
                except Exception as e:
                    logger.error(f"Error inserting project {project.get('project_id', 'unknown')}: {e}")
                    continue
        
        return added_count
    
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