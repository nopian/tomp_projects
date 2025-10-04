#!/usr/bin/env python3
"""
Generate commit message summary for automated data updates.

This script analyzes the database collection status and generates
a concise commit message summary.
"""
import sys
import os
from pathlib import Path

# Add data_collection to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.append(str(project_root / "data_collection"))

from database import ProjectDatabase


def main() -> None:
    """Generate and print commit message summary."""
    try:
        db = ProjectDatabase()
        status = db.get_collection_status()
        
        # Calculate totals
        total = sum(s.get('records_added', 0) for s in status if s.get('success'))
        sources = [s['source'] for s in status if s.get('success') and s.get('records_added', 0) > 0]
        
        # Generate summary message
        summary = f'Updated {total} projects from {len(sources)} sources'
        print(summary)
        
    except Exception as e:
        print(f"Error generating commit message: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()