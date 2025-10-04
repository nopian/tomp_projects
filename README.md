# Mount Pleasant Development Projects Dashboard

A Streamlit dashboard that aggregates and displays development projects in Mount Pleasant, SC from multiple data sources.

## Features

- **Interactive Map**: Projects displayed on a map with color-coded markers by data source
- **Data Filtering**: Filter by source, date range, status, and search terms
- **Real-time Updates**: Automated daily data collection via GitHub Actions
- **Multiple Sources**: Aggregates data from:
  - Town Planning Council (ArcGIS)
  - SC DHEC Environmental Permits
  - Stormwater Projects
  - Mount Pleasant Water Projects
  - Charleston New Construction (bonus)

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
2. Updates the SQLite database
3. Commits changes back to the repository
4. Provides a summary of the collection run

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
│   └── projects.db          # SQLite database
├── .github/workflows/
│   └── update_data.yml      # GitHub Actions workflow
├── REFERENCE/               # Original reference scripts
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
- **Updates**: New projects added when discovered

### DHEC Permits
- **Source**: SC DHEC Environmental Permits API
- **Data**: Environmental approvals for Mount Pleasant
- **Filtering**: Excludes private residences

### Stormwater Projects
- **Source**: Mount Pleasant construction notices website
- **Data**: Stormwater management projects
- **Coordinates**: Looked up via TMS parcel ID

### Water Projects
- **Source**: Mount Pleasant Water ArcGIS
- **Data**: Water infrastructure projects
- **Filtering**: Excludes residential projects

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
- **Sources with real application dates**: Water Projects, Stormwater (use actual submission dates)
- **Sources without application dates**: Planning Council, DHEC (use collection date as fallback)

This ensures all projects appear in date range filters while maintaining accuracy where real dates exist.

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