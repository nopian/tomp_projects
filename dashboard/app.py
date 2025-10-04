"""
Streamlit dashboard for Mount Pleasant development projects.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Configuration constants
CACHE_TTL_SECONDS = 300
MAP_DEFAULT_LAT = 32.8648
MAP_DEFAULT_LON = -79.7870
MAP_DEFAULT_ZOOM = 12
MAP_HEIGHT = 700
MAP_POPUP_MAX_WIDTH = 300
DESCRIPTION_TRUNCATE_LENGTH = 100
RECENT_PROJECTS_COUNT = 5

# Color mapping for data sources
SOURCE_COLORS = {
    'planning_council': 'blue',
    'dhec': 'green',
    'stormwater': 'orange',
    'water': 'purple',
    'charleston': 'red'
}

# Page configuration
st.set_page_config(
    page_title="Mount Pleasant Development Projects",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_data() -> Tuple[pd.DataFrame, List[Dict]]:
    """Load project data from SQLite database."""
    # Use the same database path logic as the collection scripts
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "projects.db"
    
    if not db_path.exists():
        return pd.DataFrame(), {}
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Load projects
            projects_df = pd.read_sql_query("""
                SELECT * FROM projects 
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                ORDER BY application_date DESC, created_at DESC
            """, conn)
            
            # Load collection status
            status_df = pd.read_sql_query("""
                SELECT source, 
                       MAX(run_date) as last_run,
                       success,
                       records_added,
                       error_message
                FROM collection_runs 
                GROUP BY source
                ORDER BY last_run DESC
            """, conn)
            
        collection_status = status_df.to_dict('records')
        
        # Convert dates
        if not projects_df.empty:
            projects_df['application_date'] = pd.to_datetime(projects_df['application_date'], errors='coerce')
            projects_df['collection_date'] = pd.to_datetime(projects_df['collection_date'], errors='coerce')
            # Keep date objects for display but datetime for sorting
            projects_df['application_date_display'] = projects_df['application_date'].dt.date
            projects_df['collection_date_display'] = projects_df['collection_date'].dt.date
            
        return projects_df, collection_status
        
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), {}

def create_popup_content(project: pd.Series) -> str:
    """
    Create HTML popup content for a project marker.

    Args:
        project: Project data series

    Returns:
        HTML string for popup
    """
    app_date = project.get(
        'application_date_display',
        project.get('application_date', 'N/A')
    )

    desc = project['description'] or ''
    truncated_desc = desc[:DESCRIPTION_TRUNCATE_LENGTH]
    if len(desc) > DESCRIPTION_TRUNCATE_LENGTH:
        truncated_desc += '...'

    popup_content = f"""
    <b>{project['name'] or 'Unnamed Project'}</b><br>
    <b>Source:</b> {project['source'].replace('_', ' ').title()}<br>
    <b>Address:</b> {project['address'] or 'N/A'}<br>
    <b>Status:</b> {project['status'] or 'N/A'}<br>
    <b>Application Date:</b> {app_date or 'N/A'}<br>
    <b>Description:</b> {truncated_desc}
    """

    if project['url']:
        popup_content += (
            f"<br><a href='{project['url']}' "
            f"target='_blank'>View Details</a>"
        )

    return popup_content


def add_map_legend(map_obj: folium.Map) -> None:
    """
    Add legend to Folium map.

    Args:
        map_obj: Folium map to add legend to
    """
    legend_html = '''
    <div style="position: fixed;
                bottom: 50px; left: 50px; width: 200px; height: 120px;
                background-color: white; border:2px solid grey;
                z-index:9999; font-size:14px; padding: 10px">
    <b>Data Sources</b><br>
    <i class="fa fa-map-marker" style="color:blue"></i> Planning Council<br>
    <i class="fa fa-map-marker" style="color:green"></i> DHEC Permits<br>
    <i class="fa fa-map-marker" style="color:orange"></i> Stormwater<br>
    <i class="fa fa-map-marker" style="color:purple"></i> Water Projects<br>
    <i class="fa fa-map-marker" style="color:red"></i> Charleston
    </div>
    '''
    map_obj.get_root().html.add_child(folium.Element(legend_html))


def create_map(df: pd.DataFrame) -> folium.Map:
    """
    Create Folium map with project markers.

    Args:
        df: DataFrame containing project data

    Returns:
        Folium map object
    """
    if df.empty:
        # Center on Mount Pleasant if no data
        m = folium.Map(
            location=[MAP_DEFAULT_LAT, MAP_DEFAULT_LON],
            zoom_start=MAP_DEFAULT_ZOOM
        )
        return m

    # Center map on data centroid
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=MAP_DEFAULT_ZOOM
    )

    # Add markers for each project
    for _, project in df.iterrows():
        color = SOURCE_COLORS.get(project['source'], 'gray')
        popup_content = create_popup_content(project)

        folium.Marker(
            location=[project['latitude'], project['longitude']],
            popup=folium.Popup(popup_content, max_width=MAP_POPUP_MAX_WIDTH),
            tooltip=project['name'] or 'Unnamed Project',
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(m)

    add_map_legend(m)
    return m

def render_custom_css() -> None:
    """Render custom CSS for dashboard styling."""
    st.markdown("""
    <style>
    /* Map container styling - ensure it fills the space */
    .element-container iframe {
        width: 100% !important;
        height: 700px !important;
        display: block;
    }

    /* Remove extra padding/margin around iframe */
    .element-container:has(iframe) {
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Reduce top padding */
    .stApp > div:first-child > div:first-child > div:first-child {
        padding-top: 0rem;
    }

    /* Add consistent spacing between sections */
    .stSubheader {
        margin-top: 2rem !important;
        margin-bottom: 1rem !important;
    }

    /* First subheader after title should have less top margin */
    h1 + .stSubheader {
        margin-top: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_header() -> None:
    """Render dashboard header and info section."""
    st.title("🏗️ Mount Pleasant Development Projects")
    st.markdown(
        "Real-time dashboard aggregating development projects "
        "from multiple sources"
    )

    with st.expander("ℹ️ Data Source Information"):
        st.markdown("""
        **Application Dates:**
        - **Water Projects & Stormwater**: Use actual project dates
        - **Planning Council & DHEC**: Use collection date as fallback

        **Data Sources:**
        - **Planning Council**: Zoning appeals and design reviews
        - **Water Projects**: Infrastructure development projects
        - **Stormwater**: Construction notices and permits
        - **DHEC**: Environmental permits and approvals
        """)


def apply_filters(
    df: pd.DataFrame,
    selected_source: str,
    date_range: Optional[Tuple],
    selected_status: str,
    search_term: str
) -> pd.DataFrame:
    """
    Apply user-selected filters to dataframe.

    Args:
        df: Full project dataframe
        selected_source: Selected source filter
        date_range: Selected date range tuple
        selected_status: Selected status filter
        search_term: Search string

    Returns:
        Filtered dataframe
    """
    filtered_df = df.copy()

    if selected_source != 'All':
        filtered_df = filtered_df[filtered_df['source'] == selected_source]

    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        start_datetime = pd.to_datetime(start_date)
        end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1)
        filtered_df = filtered_df[
            (filtered_df['application_date'].notna()) &
            (filtered_df['application_date'] >= start_datetime) &
            (filtered_df['application_date'] < end_datetime)
        ]

    if selected_status != 'All':
        filtered_df = filtered_df[filtered_df['status'] == selected_status]

    if search_term:
        search_mask = (
            filtered_df['name'].str.contains(
                search_term, case=False, na=False
            ) |
            filtered_df['address'].str.contains(
                search_term, case=False, na=False
            ) |
            filtered_df['description'].str.contains(
                search_term, case=False, na=False
            )
        )
        filtered_df = filtered_df[search_mask]

    return filtered_df


def render_project_summaries(df: pd.DataFrame) -> None:
    """
    Render project summary sections (by source and recently added).

    Args:
        df: Filtered project dataframe
    """
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Projects by Source")
        if not df.empty:
            source_counts = df['source'].value_counts()
            for source, count in source_counts.items():
                display_name = source.replace('_', ' ').title()
                st.write(f"• **{display_name}**: {count}")
        else:
            st.info("No projects match the current filters.")

    with col2:
        st.subheader("🕒 Recently Added")
        if not df.empty:
            recent = df.nlargest(RECENT_PROJECTS_COUNT, 'collection_date')
            for _, project in recent.iterrows():
                name = project['name'] or 'Unnamed'
                source = project['source'].replace('_', ' ').title()
                st.write(f"• **{name}** ({source})")
        else:
            st.info("No projects match the current filters.")


def render_project_table(df: pd.DataFrame) -> None:
    """
    Render project details table with export functionality.

    Args:
        df: Filtered project dataframe
    """
    st.subheader("📋 Project Details")

    if not df.empty:
        # Prepare display dataframe
        display_df = df[[
            'source', 'name', 'address', 'status',
            'application_date_display', 'description', 'url'
        ]].copy()

        display_df['source'] = display_df['source'].str.replace(
            '_', ' '
        ).str.title()
        display_df.columns = [
            'Source', 'Name', 'Address', 'Status',
            'Application Date', 'Description', 'URL'
        ]

        # Truncate long descriptions for table display
        def truncate_desc(x):
            if pd.notna(x) and len(str(x)) > DESCRIPTION_TRUNCATE_LENGTH:
                return str(x)[:DESCRIPTION_TRUNCATE_LENGTH] + '...'
            return str(x) if pd.notna(x) else ''

        display_df['Description'] = display_df['Description'].apply(
            truncate_desc
        )
        display_df['URL'] = display_df['URL'].fillna('')

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn(
                    "URL",
                    help="Click to view project details"
                )
            }
        )

        # Export functionality
        col1, col2 = st.columns([1, 1])
        with col1:
            csv = df.to_csv(index=False)
            filename = (
                f"mount_pleasant_projects_"
                f"{datetime.now().strftime('%Y%m%d')}.csv"
            )
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=filename,
                mime="text/csv"
            )

        with col2:
            if st.button("🔄 Refresh Data"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info(
            "No projects match the current filters. "
            "Try adjusting your search criteria."
        )


def render_collection_status(collection_status: List[Dict]) -> None:
    """
    Render data collection status table.

    Args:
        collection_status: List of collection run status dictionaries
    """
    st.subheader("🔄 Data Collection Status")

    if collection_status:
        status_df = pd.DataFrame(collection_status)
        status_df['last_run'] = pd.to_datetime(
            status_df['last_run']
        ).dt.strftime('%Y-%m-%d %H:%M')
        status_df['source'] = status_df['source'].str.replace(
            '_', ' '
        ).str.title()
        status_df['status'] = status_df['success'].apply(
            lambda x: '✅ Success' if x else '❌ Failed'
        )

        display_status = status_df[[
            'source', 'last_run', 'status', 'records_added'
        ]].copy()
        display_status.columns = [
            'Source', 'Last Run', 'Status', 'Records Added'
        ]

        st.dataframe(
            display_status,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No collection status available.")


def render_summary_metrics(df: pd.DataFrame) -> None:
    """
    Render summary metrics in columns.

    Args:
        df: Filtered project dataframe
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Projects", len(df))

    with col2:
        if not df.empty:
            st.metric("Data Sources", len(df['source'].unique()))
        else:
            st.metric("Data Sources", 0)

    with col3:
        if not df.empty:
            latest_date = df['application_date'].max().strftime('%Y-%m-%d')
            st.metric("Latest Project", latest_date)
        else:
            st.metric("Latest Project", "N/A")

    with col4:
        if not df.empty:
            source_counts = df['source'].value_counts()
            top_source = source_counts.index[0].replace('_', ' ').title()
            count = source_counts.iloc[0]
            st.metric("Top Source", f"{top_source} ({count})")
        else:
            st.metric("Top Source", "N/A")


def render_sidebar_filters(df: pd.DataFrame) -> Tuple:
    """
    Render sidebar filter controls.

    Args:
        df: Project dataframe

    Returns:
        Tuple of (selected_source, date_range, selected_status, search_term)
    """
    st.sidebar.header("Filters")

    # Source filter
    sources = ['All'] + sorted(df['source'].unique().tolist())
    selected_source = st.sidebar.selectbox("Data Source", sources)

    # Date filter
    valid_dates = df['application_date'].dropna()
    date_range = None
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()

        if min_date and max_date:
            date_range = st.sidebar.date_input(
                "Application Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                help="For sources without dates, collection date is used"
            )

    # Status filter
    statuses = ['All'] + [
        s for s in sorted(df['status'].dropna().unique().tolist()) if s
    ]
    selected_status = st.sidebar.selectbox("Project Status", statuses)

    # Search filter
    search_term = st.sidebar.text_input(
        "Search projects",
        placeholder="Enter name, address, or description..."
    )

    return selected_source, date_range, selected_status, search_term


def main():
    """Main dashboard application."""
    render_custom_css()
    render_header()

    # Load data
    df, collection_status = load_data()

    if df.empty:
        st.warning(
            "No project data available. "
            "Run the data collection scripts to populate the database."
        )
        return
    
    # Sidebar filters
    filters = render_sidebar_filters(df)
    selected_source, date_range, selected_status, search_term = filters

    # Apply filters
    filtered_df = apply_filters(
        df, selected_source, date_range, selected_status, search_term
    )

    # Summary metrics at top
    render_summary_metrics(filtered_df)

    st.divider()

    # Large map taking full width
    st.subheader("📍 Project Map")

    if not filtered_df.empty:
        map_obj = create_map(filtered_df)
        st_folium(
            map_obj,
            use_container_width=True,
            height=MAP_HEIGHT
        )
    else:
        st.info("No projects match the current filters.")

    st.divider()

    # Summary details below map
    render_project_summaries(filtered_df)

    st.divider()

    # Data table
    render_project_table(filtered_df)

    st.divider()

    # Data source status
    render_collection_status(collection_status)

if __name__ == "__main__":
    main()