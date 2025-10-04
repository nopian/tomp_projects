#!/usr/bin/env python3
"""
Generate GitHub Actions step summary for data collection results.

This script analyzes the database and generates a markdown summary
for GitHub Actions step summary display.
"""
import sys
from pathlib import Path

# Add data_collection to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.append(str(project_root / "data_collection"))

from database import ProjectDatabase


def main() -> None:
    """Generate and print step summary in markdown format."""
    try:
        db = ProjectDatabase()
        status = db.get_collection_status()
        projects = db.get_all_projects()
        
        # Print total projects
        print(f'**Total Projects:** {len(projects)}')
        print('')
        
        # Print collection status
        print('**Collection Status:**')
        for s in status:
            status_emoji = '✅' if s.get('success') else '❌'
            source = s['source'].replace('_', ' ').title()
            records = s.get('records_added', 0)
            print(f'- {status_emoji} {source}: {records} new records')
        
        print('')
        
        # Print projects by source
        print('**Projects by Source:**')
        source_counts = {}
        for p in projects:
            source = p['source']
            source_counts[source] = source_counts.get(source, 0) + 1
        
        for source, count in sorted(source_counts.items()):
            print(f'- {source.replace("_", " ").title()}: {count}')
            
    except Exception as e:
        print(f"Error generating summary: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()