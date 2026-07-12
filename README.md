# Mount Pleasant Development Projects Dashboard

A Streamlit dashboard that aggregates and displays development projects in Mount Pleasant, SC from multiple data sources.

## Features

- **Interactive Map**: Projects displayed on a map with color-coded markers by data source
- **Data Filtering**: Filter by source, date range, status, and search terms
- **Real-time Updates**: Automated daily data collection via GitHub Actions
- **Multiple Sources**: Aggregates data from:
  - Town Planning Council (ArcGIS)
  - SC DES Environmental Permits (formerly DHEC)
  - Stormwater Projects
  - Mount Pleasant Water Projects
- **GeoJSON Export**: `data/projects.geojson` regenerated on every
  collection run for easy integration with external maps

## Quick Start

### Prerequisites

- Python 3.8+
- Git

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd tomp
```

2. Install dependencies:
```bash
# Data collection dependencies
pip install -r requirements.txt

# Dashboard dependencies (additional)
pip install -r requirements-dashboard.txt
```

3. Initialize the database:
```bash
cd data_collection
python update_database.py
```

4. Run the dashboard:
```bash
# Easy way - automated setup
python run_dashboard.py

# Or manual way
streamlit run dashboard/app.py
```

The dashboard will be available at `http://localhost:8501`

## Data Collection

### Manual Collection

Run all data sources:
```bash
cd data_collection
python update_database.py
```

Run a single source:
```bash
cd data_collection
python update_database.py planning_council
python update_database.py dhec
python update_database.py stormwater
python update_database.py water
```

Check status:
```bash
cd data_collection
python update_database.py status
```

### Automated Collection

GitHub Actions automatically runs data collection daily at 6 AM UTC. The workflow:
1. Fetches data from all sources
2. Updates the SQLite database (new rows inserted, existing rows refreshed)
3. Regenerates `data/projects.geojson`
4. Commits changes back to the repository
5. Provides a summary of the collection run

### GeoJSON Export

For integrating the data into another map, use the GeoJSON export:
```bash
python scripts/export_geojson.py
```
This writes `data/projects.geojson` with one Point feature per project
that has coordinates. Feature properties carry the standardized fields
(`source`, `project_id`, `name`, `description`, `status`, `address`,
`application_date`, `collection_date`, `url`, `updated_at`).

### Data Repairs

`scripts/repair_data.py` is an idempotent repair pass for historical
rows (rebuilds DHEC-era records from raw data, clears old placeholder
coordinates). Run it manually if needed:
```bash
python scripts/repair_data.py
```

## Project Structure

```
project/
├── data_collection/           # Data collection scripts
│   ├── __init__.py
│   ├── database.py           # Database utilities
│   ├── fetch_planning_council.py
│   ├── fetch_dhec_permits.py
│   ├── fetch_stormwater.py
│   ├── fetch_water_projects.py
│   └── update_database.py    # Main orchestrator
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── data/
│   ├── projects.db          # SQLite database
│   └── projects.geojson     # GeoJSON export for map integration
├── scripts/
│   ├── export_geojson.py    # Regenerate data/projects.geojson
│   ├── repair_data.py       # Idempotent historical data repairs
│   ├── generate_summary.py  # GitHub Actions step summary
│   └── generate_commit_message.py
├── .github/workflows/
│   └── update_data.yml      # GitHub Actions workflow
├── requirements.txt         # Data collection dependencies
├── requirements-dashboard.txt # Dashboard dependencies
└── .env.example            # Environment variables template
```

## Database Schema

The system uses SQLite with two main tables:

### Projects Table
- `source`: Data source identifier
- `project_id`: Original ID from source
- `name`: Project name/title  
- `description`: Project details
- `status`: Project status
- `application_date`: When project was submitted
- `latitude`, `longitude`: Coordinates
- `address`: Street address
- `url`: Link to documents/details
- `raw_data`: JSON of original data

### Collection Runs Table
- Tracks data collection history
- Records success/failure status
- Logs error messages

## Data Sources

### Planning Council
- **Source**: Mount Pleasant Planning Council ArcGIS
- **Data**: Development projects with planning approvals
- **Status**: `Active` while on the agenda feed; automatically marked
  `Archived` once an item leaves the feed (decided or withdrawn)

### DHEC/DES Permits
- **Source**: SC DES public notices API (`epermitting.des.sc.gov`;
  DHEC's environmental programs moved to DES in 2024)
- **Data**: Environmental permit public notices for Mount Pleasant
- **Filtering**: Excludes private residences

### Stormwater Projects
- **Source**: Mount Pleasant construction notices website
- **Data**: Stormwater management projects (NOI public notices)
- **Coordinates**: Parcel centroid looked up via TMS parcel ID; left
  empty when the parcel no longer exists (e.g. replatted) or the
  location is a right-of-way
- **Status**: `Comment Period Open`/`Comment Period Closed`, derived
  from the notice close date

### Water Projects
- **Source**: Mount Pleasant Water ArcGIS
- **Data**: Water infrastructure projects
- **Filtering**: Excludes residential projects (RSAN* project IDs)

## Development

### Adding New Data Sources

1. Create a new fetcher class in `data_collection/fetch_<source>.py`
2. Implement the required methods:
   - `fetch_data()`: Get raw data from API/website
   - `parse_projects()`: Convert to standardized format
   - `fetch_and_store()`: Main entry point
3. Add to `update_database.py` fetchers dictionary
4. Update dashboard filters if needed

### Standardized Project Format

All data sources must convert their data to this format:
```python
{
    "project_id": "unique_id",
    "name": "Project Name",
    "description": "Project description",
    "status": "Active/Pending/Complete",
    "address": "Street address",
    "application_date": date_object,  # Use collection_date if no app date available
    "collection_date": date_object,
    "latitude": float,
    "longitude": float,
    "url": "link_to_details",
    "raw_data": original_data_dict
}
```

### Date Handling

**Application Date Logic:**
- **Sources with real dates**: Water Projects (GIS record creation),
  Stormwater (notice open date), DHEC/DES (notice start date)
- **Sources without application dates**: Planning Council (uses the
  date the item was first collected)

### Update Semantics

Collection runs upsert: new `(source, project_id)` pairs are inserted,
existing rows have their name/description/status/address/coordinates/
url/raw_data refreshed so status changes at the source are captured.
Original application and collection dates are preserved, and
coordinates are never overwritten with NULL.

## Troubleshooting

### Database Issues
- Check if `data/projects.db` exists
- Run `python update_database.py status` to check collection history
- Delete database file to reset (data will be re-collected)

### Data Collection Failures
- Check network connectivity
- Verify API endpoints are still active
- Review error logs in collection_runs table

### Dashboard Issues
- Ensure all dashboard dependencies are installed
- Check if database contains projects with coordinates
- Clear Streamlit cache with browser refresh

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test data collection and dashboard
5. Submit a pull request

## License

This project is for educational and civic purposes. Please respect the terms of service of the data sources.