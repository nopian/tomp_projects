#!/usr/bin/env python3
"""
Simple script to run the Mount Pleasant Development Projects dashboard.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run the dashboard with proper setup."""
    
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("🏗️ Mount Pleasant Development Projects Dashboard")
    print("=" * 50)
    
    # Check if database exists
    db_path = Path("data/projects.db")
    if not db_path.exists():
        print("📊 No database found. Collecting initial data...")
        try:
            result = subprocess.run([
                sys.executable, "data_collection/update_database.py"
            ], check=True, capture_output=True, text=True)
            print("✅ Data collection complete!")
            print(f"   {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Data collection failed: {e}")
            print(f"   Error: {e.stderr}")
            return 1
    else:
        print("📊 Database found. Starting dashboard...")
    
    # Run dashboard
    print("\n🚀 Starting Streamlit dashboard...")
    print("   Dashboard will be available at: http://localhost:8501")
    print("   Press Ctrl+C to stop")
    print("\n" + "=" * 50)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "dashboard/app.py",
            "--server.port", "8501"
        ], check=True)
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped. Goodbye!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Dashboard failed to start: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())