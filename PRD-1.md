Local Development Projects Dashboard
Project Overview
Create a Streamlit dashboard that aggregates and displays upcoming development projects from multiple sources including town planning council, SC DHEC environmental approvals, and stormwater management submissions.
Architecture

Data Collection: GitHub Actions workflow (scheduled daily/weekly)
Data Storage: SQLite database
Frontend: Streamlit dashboard with interactive map and filterable data table

Data Sources
1. Town Planning Council (ArcGIS) - REFERENCE/mtp_projects.py

2. SC DHEC Environmental Approvals (ArcGIS) - REFERENCE/dhec_permits.py

3. Stormwater Projects - REFERENCE/mtp_stormwater.py

4. Mt P Water Projects - REFERENCE/mpw_projects.py