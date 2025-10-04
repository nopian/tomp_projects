"""
Main orchestrator for updating the projects database from all sources.
"""
import logging
import sys
from typing import Dict, Any

from data_collection.database import ProjectDatabase
from data_collection.fetch_planning_council import PlanningCouncilFetcher
from data_collection.fetch_dhec_permits import DHECPermitsFetcher
from data_collection.fetch_water_projects import WaterProjectsFetcher
from data_collection.fetch_stormwater import StormwaterFetcher

logger = logging.getLogger(__name__)

class DatabaseUpdater:
    """Orchestrates data collection from all sources."""
    
    def __init__(self):
        self.db = ProjectDatabase()
        self.fetchers = {
            "planning_council": PlanningCouncilFetcher(),
            "dhec": DHECPermitsFetcher(),
            "water": WaterProjectsFetcher(),
            "stormwater": StormwaterFetcher(),
        }
    
    def update_all_sources(self) -> Dict[str, Any]:
        """
        Update database from all data sources.
        
        Returns:
            Dictionary with collection results
        """
        results = {
            "total_added": 0,
            "sources": {},
            "success": True,
            "errors": []
        }
        
        logger.info("Starting database update from all sources...")
        
        for source_name, fetcher in self.fetchers.items():
            try:
                logger.info(f"Updating {source_name}...")
                added_count = fetcher.fetch_and_store(self.db)
                
                results["sources"][source_name] = {
                    "added": added_count,
                    "success": True,
                    "error": None
                }
                results["total_added"] += added_count
                
                logger.info(f"✓ {source_name}: {added_count} new projects")
                
            except Exception as e:
                error_msg = f"Failed to update {source_name}: {e}"
                logger.error(error_msg)
                
                results["sources"][source_name] = {
                    "added": 0,
                    "success": False,
                    "error": error_msg
                }
                results["errors"].append(error_msg)
                results["success"] = False
        
        logger.info(f"Database update complete. Total new projects: {results['total_added']}")
        
        return results
    
    def update_single_source(self, source_name: str) -> Dict[str, Any]:
        """
        Update database from a single source.
        
        Args:
            source_name: Name of source to update
            
        Returns:
            Dictionary with collection results
        """
        if source_name not in self.fetchers:
            raise ValueError(f"Unknown source: {source_name}. Available: {list(self.fetchers.keys())}")
        
        logger.info(f"Updating single source: {source_name}")
        
        try:
            fetcher = self.fetchers[source_name]
            added_count = fetcher.fetch_and_store(self.db)
            
            result = {
                "source": source_name,
                "added": added_count,
                "success": True,
                "error": None
            }
            
            logger.info(f"✓ {source_name}: {added_count} new projects")
            return result
            
        except Exception as e:
            error_msg = f"Failed to update {source_name}: {e}"
            logger.error(error_msg)
            
            return {
                "source": source_name,
                "added": 0,
                "success": False,
                "error": error_msg
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current database status and collection history.
        
        Returns:
            Dictionary with database status
        """
        collection_status = self.db.get_collection_status()
        all_projects = self.db.get_all_projects()
        
        # Count projects by source
        source_counts = {}
        for project in all_projects:
            source = project["source"]
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "total_projects": len(all_projects),
            "projects_by_source": source_counts,
            "last_collection_runs": collection_status,
            "available_sources": list(self.fetchers.keys())
        }


def main():
    """Run database update with command line interface."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    updater = DatabaseUpdater()
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        source_name = sys.argv[1]
        if source_name == "status":
            status = updater.get_status()
            print(f"Total projects: {status['total_projects']}")
            print("Projects by source:")
            for source, count in status['projects_by_source'].items():
                print(f"  {source}: {count}")
            return
        
        # Update single source
        result = updater.update_single_source(source_name)
        if result["success"]:
            print(f"✓ Added {result['added']} new {source_name} projects")
        else:
            print(f"✗ Failed to update {source_name}: {result['error']}")
            sys.exit(1)
    else:
        # Update all sources
        results = updater.update_all_sources()
        
        print(f"Database update complete!")
        print(f"Total new projects: {results['total_added']}")
        
        for source, result in results["sources"].items():
            status = "✓" if result["success"] else "✗"
            print(f"{status} {source}: {result['added']} new projects")
            if not result["success"]:
                print(f"    Error: {result['error']}")
        
        if not results["success"]:
            print(f"\nSome sources failed. Errors:")
            for error in results["errors"]:
                print(f"  - {error}")
            sys.exit(1)


if __name__ == "__main__":
    main()