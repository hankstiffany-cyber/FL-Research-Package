"""
FORGOTTEN LANGUAGES RESEARCH INTERFACE
=======================================
A comprehensive web application for exploring and analyzing
the Forgotten Languages database.

Run with: streamlit run fl_app.py

Requirements:
    pip install streamlit pandas plotly folium streamlit-folium
"""

import streamlit as st
import pandas as pd
import json
import math
import html
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="FL Research Interface",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============= CUSTOM CSS =============
def get_theme_css(dark_mode=False):
    if dark_mode:
        return """
        <style>
            :root {
                --bg-primary: #0a0f0d;
                --bg-secondary: #111916;
                --bg-tertiary: #1a2420;
                --text-primary: #e0e6e3;
                --text-secondary: #8b9a93;
                --accent-green: #00ff88;
                --accent-dim: #00b85c;
                --accent-cyan: #00d4ff;
                --warning: #ff6b35;
                --danger: #ff3333;
                --border-color: #2a3f35;
            }
        """
    else:
        return """
        <style>
            :root {
                --bg-primary: #ffffff;
                --bg-secondary: #f8f9fa;
                --bg-tertiary: #f1f3f4;
                --text-primary: #202124;
                --text-secondary: #5f6368;
                --accent-green: #1a73e8;
                --accent-dim: #174ea6;
                --accent-cyan: #1967d2;
                --warning: #ea8600;
                --danger: #d93025;
                --border-color: #dadce0;
            }
        """

# Initial CSS (will be replaced after session state loads)
st.markdown("""
<style>
    /* Clean, readable light theme */
    :root {
        --bg-primary: #ffffff;
        --bg-secondary: #f8f9fa;
        --bg-tertiary: #f1f3f4;
        --text-primary: #202124;
        --text-secondary: #5f6368;
        --accent-green: #1a73e8;
        --accent-dim: #174ea6;
        --accent-cyan: #1967d2;
        --warning: #ea8600;
        --danger: #d93025;
        --border-color: #dadce0;
    }

    /* Use system fonts for best readability */
    .stApp, .stMarkdown, p, span, div, h1, h2, h3 {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif !important;
    }

    /* Main content area */
    .stApp {
        background: var(--bg-primary);
    }

    /* Header styling */
    .main-header {
        color: var(--text-primary);
        font-size: 2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .sub-header {
        color: var(--text-secondary);
        font-size: 1.1rem;
        font-weight: 400;
    }

    /* Stat cards */
    .stat-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
    }

    .stat-value {
        font-size: 2rem;
        font-weight: 600;
        color: var(--accent-green);
        line-height: 1.2;
    }

    .stat-label {
        font-size: 1rem;
        color: var(--text-secondary);
        margin-top: 0.5rem;
    }

    /* Data tables - larger font */
    .dataframe {
        font-size: 1rem !important;
    }

    /* Search results */
    .result-card {
        background: var(--bg-secondary);
        border-left: 4px solid var(--accent-green);
        padding: 1.25rem 1.5rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }

    .result-title {
        color: var(--text-primary);
        font-size: 1.2rem;
        font-weight: 600;
        line-height: 1.5;
    }

    .result-meta {
        color: var(--text-secondary);
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }

    .result-excerpt {
        color: var(--text-secondary);
        font-size: 1.1rem;
        margin-top: 0.75rem;
        line-height: 1.8;
    }

    /* Keywords */
    .keyword-tag {
        display: inline-block;
        background: #e8f0fe;
        color: var(--accent-green);
        padding: 0.3rem 0.8rem;
        border-radius: 16px;
        font-size: 0.95rem;
        margin: 0.25rem;
        font-weight: 500;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: var(--bg-secondary);
    }

    /* Make all text larger and more readable */
    .stMarkdown p {
        font-size: 1.1rem !important;
        line-height: 1.8 !important;
        color: var(--text-primary) !important;
    }

    /* Sidebar text */
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 1rem !important;
    }

    /* Input fields */
    .stTextInput input {
        font-size: 1.1rem !important;
        padding: 0.75rem !important;
    }

    /* Buttons */
    .stButton button {
        font-size: 1rem !important;
        padding: 0.5rem 1rem !important;
    }

    /* Tables */
    .stDataFrame {
        font-size: 1rem !important;
    }

    /* Headers in content */
    h1, h2, h3 {
        color: var(--text-primary) !important;
    }

    /* Links */
    a {
        color: var(--accent-green) !important;
        font-size: 1rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============= DATA LOADING =============
@st.cache_data
def load_data():
    """Load all data files"""
    data = {}
    
    # Try multiple possible paths
    base_paths = [
        Path("data"),
        Path("."),
        Path("FL_Research_Package/data"),
    ]
    
    for base in base_paths:
        if (base / "fl_statistics.json").exists():
            data_path = base
            break
    else:
        st.error("Data files not found. Please ensure data files are in the 'data' folder.")
        return None
    
    # Load statistics
    try:
        with open(data_path / "fl_statistics.json", "r") as f:
            data["stats"] = json.load(f)
    except:
        data["stats"] = {}
    
    # Load articles
    try:
        with open(data_path / "fl_articles_raw.json", "r", encoding="utf-8") as f:
            data["articles"] = json.load(f)
    except:
        data["articles"] = []
    
    # Load excerpts
    try:
        data["excerpts"] = pd.read_csv(data_path / "fl_excerpts_raw.csv", encoding="utf-8")
    except:
        data["excerpts"] = pd.DataFrame()
    
    # Load coordinates
    try:
        data["coordinates"] = pd.read_csv(data_path / "fl_coordinates_complete_decoded.csv", encoding="utf-8")
    except:
        data["coordinates"] = pd.DataFrame()
    
    # Load keyword index
    try:
        with open(data_path / "fl_keyword_index.json", "r", encoding="utf-8") as f:
            data["keywords"] = json.load(f)
    except:
        data["keywords"] = {}

    # Load bibliography (if available)
    try:
        data["bibliography"] = pd.read_csv(data_path / "fl_bibliography.csv", encoding="utf-8")
    except:
        data["bibliography"] = pd.DataFrame()

    # Load citations (if available)
    try:
        data["citations"] = pd.read_csv(data_path / "fl_citations.csv", encoding="utf-8")
    except:
        data["citations"] = pd.DataFrame()

    # Load images (if available)
    try:
        data["images"] = pd.read_csv(data_path / "fl_images.csv", encoding="utf-8")
    except:
        data["images"] = pd.DataFrame()

    return data

# ============= HELPER FUNCTIONS =============
def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def extract_date_from_url(url):
    """Extract date from FL URL pattern"""
    match = re.search(r'/(\d{4})/(\d{2})/', str(url))
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return "Unknown"

FL_KEYWORDS = [
    'MilOrb', 'PSV', 'DOLYN', 'SV17q', 'Giselian', 'Denebian', 'XViS', 
    'LyAV', 'Sienna', 'Akrij', 'Presence', 'Tangent', 'Graphium', 
    'NodeSpaces', 'UAP', 'USO', 'SAA', 'DENIED', 'Cassini', 'MASINT',
    'Corona East', 'Black Prophet', 'Queltron', 'Sol-3', 'NDE', 'dream',
    'consciousness', 'drone', 'kinetic', 'Thule', 'Jan Mayen', 'AUTEC'
]

def find_keywords(text):
    """Find FL keywords in text"""
    found = []
    text_lower = str(text).lower()
    for kw in FL_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found

# ============= MAIN APP =============
def main():
    # Load data
    data = load_data()
    
    if data is None:
        return
    
    # Initialize session state for bookmarks
    if 'bookmarks' not in st.session_state:
        st.session_state.bookmarks = []
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False

    # Sidebar
    with st.sidebar:
        st.markdown("### 📡 NAVIGATION")
        page = st.radio(
            "Select Module",
            ["🏠 Dashboard", "🔍 Full-Text Search", "📍 Coordinates Map", "📊 Analytics", "⏱️ Timeline", "📉 Temporal Patterns", "🕸️ Network Analysis", "🧩 Topic Modeling", "🔤 Language Analysis", "📚 Articles", "📖 Bibliography", "📑 Bibliography Analysis", "🖼️ Images", "📚 Reading Lists", "📈 Topic Evolution", "🔗 Similar Articles", "⭐ Bookmarks"],
            label_visibility="collapsed"
        )

        st.markdown("---")
        st.markdown("### 📊 QUICK STATS")
        stats = data.get("stats", {})
        st.metric("Articles", f"{stats.get('total_articles', 0):,}")
        st.metric("Excerpts", f"{stats.get('total_excerpts', 0):,}")
        st.metric("Coordinates", stats.get('coordinates', {}).get('total', 0))

        st.markdown("---")

        # Dark mode toggle
        dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode)
        if dark_mode != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_mode
            st.rerun()

        st.markdown("---")
        st.markdown(f"""
        <div style='font-size: 0.7rem; color: var(--text-secondary);'>
        Data: 2009-2025<br>
        Source: forgottenlanguages-full<br>
        Bookmarks: {len(st.session_state.bookmarks)}
        </div>
        """, unsafe_allow_html=True)

    # Apply theme CSS based on dark mode
    st.markdown(get_theme_css(st.session_state.dark_mode), unsafe_allow_html=True)

    # Main content
    if page == "🏠 Dashboard":
        render_dashboard(data)
    elif page == "🔍 Full-Text Search":
        render_fulltext_search(data)
    elif page == "📍 Coordinates Map":
        render_coordinates_map(data)
    elif page == "📊 Analytics":
        render_analytics(data)
    elif page == "⏱️ Timeline":
        render_timeline(data)
    elif page == "📉 Temporal Patterns":
        render_temporal_patterns(data)
    elif page == "🕸️ Network Analysis":
        render_network_analysis(data)
    elif page == "🧩 Topic Modeling":
        render_topic_modeling(data)
    elif page == "🔤 Language Analysis":
        render_language_analysis(data)
    elif page == "📚 Articles":
        render_articles(data)
    elif page == "📖 Bibliography":
        render_bibliography(data)
    elif page == "📑 Bibliography Analysis":
        render_bibliography_analysis(data)
    elif page == "🖼️ Images":
        render_images(data)
    elif page == "📚 Reading Lists":
        render_reading_lists(data)
    elif page == "📈 Topic Evolution":
        render_topic_evolution(data)
    elif page == "🔗 Similar Articles":
        render_similar_articles(data)
    elif page == "⭐ Bookmarks":
        render_bookmarks(data)

# ============= DASHBOARD =============
def render_dashboard(data):
    st.markdown('<h1 class="main-header">FORGOTTEN LANGUAGES</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Research Intelligence Database</p>', unsafe_allow_html=True)
    
    stats = data.get("stats", {})
    
    # Top stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_articles', 0):,}</div>
            <div class="stat-label">Articles</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('total_excerpts', 0):,}</div>
            <div class="stat-label">Excerpts</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{stats.get('coordinates', {}).get('total', 0)}</div>
            <div class="stat-label">Coordinates</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        date_range = stats.get('date_range', {})
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">16</div>
            <div class="stat-label">Years of Data</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Two column layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📂 Top Categories")
        labels = stats.get('top_labels', {})
        if labels:
            df_labels = pd.DataFrame([
                {"Category": k, "Articles": v} 
                for k, v in list(labels.items())[:10]
            ])
            fig = px.bar(
                df_labels, 
                x="Articles", 
                y="Category", 
                orientation='h',
                color_discrete_sequence=['#1a73e8']
            )
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#5f6368',
                yaxis={'categoryorder': 'total ascending'},
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0),
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🔑 Top Keywords")
        kw_counts = stats.get('keyword_counts', {})
        if kw_counts:
            df_kw = pd.DataFrame([
                {"Keyword": k, "Occurrences": v}
                for k, v in sorted(kw_counts.items(), key=lambda x: -x[1])[:10]
            ])
            fig = px.bar(
                df_kw,
                x="Occurrences",
                y="Keyword",
                orientation='h',
                color_discrete_sequence=['#1967d2']
            )
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#5f6368',
                yaxis={'categoryorder': 'total ascending'},
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0),
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Key findings
    st.markdown("### 🎯 Key Research Findings")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div style="color: #00ff88; font-size: 1.5rem; font-weight: 700;">p = 0.0017</div>
            <div class="stat-label">Statistical Significance</div>
            <div style="color: #8b9a93; font-size: 0.85rem; margin-top: 0.5rem;">
                Coordinates cluster 1.46× closer to magnetic anomalies than random
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div style="color: #00d4ff; font-size: 1.5rem; font-weight: 700;">7 Years</div>
            <div class="stat-label">MilOrb → Drone Gap</div>
            <div style="color: #8b9a93; font-size: 0.85rem; margin-top: 0.5rem;">
                2017 FL descriptions match 2024 NJ drone characteristics
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div style="color: #ff6b35; font-size: 1.5rem; font-weight: 700;">42 Days</div>
            <div class="stat-label">SAA Prediction Gap</div>
            <div style="color: #8b9a93; font-size: 0.85rem; margin-top: 0.5rem;">
                FL posted SAA coordinate before ESA announcement
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============= SEARCH =============
def render_search(data):
    st.markdown("## 🔍 Search Excerpts")
    st.markdown(f"*Search through {len(data.get('excerpts', []))} extracted English excerpts*")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input("Search query", placeholder="Enter keywords (e.g., MilOrb, Yulara, PSV)")
    
    with col2:
        limit = st.selectbox("Results", [25, 50, 100, 250], index=1)
    
    # Keyword quick filters
    st.markdown("**Quick filters:**")
    quick_keywords = ["MilOrb", "PSV", "Giselian", "XViS", "DOLYN", "SV17q", "drone", "Yulara", "Thule"]
    cols = st.columns(len(quick_keywords))
    for i, kw in enumerate(quick_keywords):
        if cols[i].button(kw, key=f"kw_{kw}"):
            query = kw
    
    if query:
        excerpts_df = data.get("excerpts", pd.DataFrame())
        
        if not excerpts_df.empty:
            # Search
            mask = excerpts_df['text'].str.contains(query, case=False, na=False) | \
                   excerpts_df['title'].str.contains(query, case=False, na=False)
            results = excerpts_df[mask].head(limit)
            
            st.markdown(f"### Found {len(results)} results for '{query}'")
            
            for _, row in results.iterrows():
                date = extract_date_from_url(row.get('url', ''))
                title = row.get('title', 'Untitled')
                text = row.get('text', '')[:500]
                url = row.get('url', '')
                keywords = find_keywords(text)
                
                with st.container():
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-meta">{date}</div>
                        <div class="result-title">{title}</div>
                        <div class="result-excerpt">{text}...</div>
                        <div style="margin-top: 0.5rem;">
                            {''.join([f'<span class="keyword-tag">{kw}</span>' for kw in keywords[:5]])}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if url:
                        st.markdown(f"[View original →]({url})")
                    st.markdown("")

# ============= COORDINATES =============
def render_coordinates(data):
    st.markdown("## 📍 Coordinate Database")
    
    coords_df = data.get("coordinates", pd.DataFrame())
    
    if coords_df.empty:
        st.warning("No coordinate data loaded")
        return
    
    st.markdown(f"*{len(coords_df)} decoded coordinates from Cassini Diskus posts*")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        coord_types = ["All"] + list(coords_df['type'].unique())
        selected_type = st.selectbox("Coordinate Type", coord_types)
    
    with col2:
        search_coord = st.text_input("Search by location/title")
    
    with col3:
        sort_by = st.selectbox("Sort by", ["date", "lat", "lon"])
    
    # Filter data
    filtered = coords_df.copy()
    if selected_type != "All":
        filtered = filtered[filtered['type'] == selected_type]
    if search_coord:
        mask = filtered['title'].str.contains(search_coord, case=False, na=False)
        filtered = filtered[mask]
    
    filtered = filtered.sort_values(sort_by, ascending=False)
    
    # Map
    st.markdown("### 🗺️ Map View")
    
    try:
        fig = px.scatter_geo(
            filtered,
            lat='lat',
            lon='lon',
            hover_name='title',
            hover_data=['date', 'type'],
            color='type',
            projection='natural earth',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(
            geo=dict(
                showland=True,
                landcolor='rgb(20, 30, 25)',
                showocean=True,
                oceancolor='rgb(10, 15, 13)',
                showcoastlines=True,
                coastlinecolor='rgb(0, 100, 68)',
                showframe=False,
                bgcolor='rgba(0,0,0,0)'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#5f6368',
            margin=dict(l=0, r=0, t=0, b=0),
            height=500
        )
        fig.update_traces(marker=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error rendering map: {e}")
    
    # Data table
    st.markdown("### 📋 Coordinate List")
    st.dataframe(
        filtered[['lat', 'lon', 'type', 'date', 'title']].head(100),
        use_container_width=True,
        height=400
    )
    
    # Download
    csv = filtered.to_csv(index=False)
    st.download_button(
        "📥 Download CSV",
        csv,
        "fl_coordinates_filtered.csv",
        "text/csv"
    )

# ============= ANALYTICS =============
def render_analytics(data):
    st.markdown("## 📊 Analytics")
    
    stats = data.get("stats", {})
    
    # Keyword analysis
    st.markdown("### 🔑 Keyword Frequency Analysis")
    
    kw_counts = stats.get('keyword_counts', {})
    if kw_counts:
        df_kw = pd.DataFrame([
            {"Keyword": k, "Count": v, "Category": categorize_keyword(k)}
            for k, v in kw_counts.items()
        ])
        
        fig = px.treemap(
            df_kw,
            path=['Category', 'Keyword'],
            values='Count',
            color='Count',
            color_continuous_scale='Greens'
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#5f6368',
            margin=dict(l=0, r=0, t=30, b=0),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Category distribution
    st.markdown("### 📂 Category Distribution")
    
    labels = stats.get('top_labels', {})
    if labels:
        df_labels = pd.DataFrame([
            {"Category": k, "Count": v}
            for k, v in labels.items()
        ])
        
        fig = px.pie(
            df_labels.head(15),
            values='Count',
            names='Category',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Greens_r
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#5f6368',
            margin=dict(l=0, r=0, t=30, b=0),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Coordinate type breakdown
    st.markdown("### 📍 Coordinate Types")
    
    coord_stats = stats.get('coordinates', {})
    if coord_stats:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total", coord_stats.get('total', 0))
        col2.metric("Decimal GPS", coord_stats.get('decimal_gps', 0))
        col3.metric("DMS Format", coord_stats.get('dms', 0))
        col4.metric("MilOrb Encoded", coord_stats.get('milorb_encoded', 0))

def categorize_keyword(kw):
    """Categorize keywords for treemap"""
    vehicles = ['PSV', 'Sienna', 'Akrij', 'Presence', 'Tangent', 'Graphium', 'MilOrb']
    orgs = ['SV17q', 'SV06n', 'SV09n', 'DOLYN']
    entities = ['Giselian', 'Denebian', 'LyAV']
    tech = ['XViS', 'NodeSpaces', 'Cassini', 'MASINT']
    phenomena = ['UAP', 'UFO', 'USO', 'NDE', 'dream', 'consciousness']
    locations = ['Thule', 'Jan Mayen', 'AUTEC', 'SAA']
    
    if kw in vehicles:
        return "Vehicles"
    elif kw in orgs:
        return "Organizations"
    elif kw in entities:
        return "Entities"
    elif kw in tech:
        return "Technology"
    elif kw in phenomena:
        return "Phenomena"
    elif kw in locations:
        return "Locations"
    else:
        return "Other"

# ============= TIMELINE =============
def render_timeline(data):
    st.markdown("## ⏱️ Temporal Correlation Analysis")
    
    st.markdown("""
    <div style="background: rgba(0, 255, 136, 0.1); border-left: 3px solid #00ff88; padding: 1rem; border-radius: 0 8px 8px 0; margin-bottom: 2rem;">
        <strong>Statistical Finding:</strong> FL coordinate distribution differs significantly from random (p = 0.0017), 
        with coordinates clustering 1.46× closer to magnetic anomalies than expected by chance.
    </div>
    """, unsafe_allow_html=True)
    
    correlations = [
        {
            "fl_date": "December 2017",
            "fl_content": "MilOrb autonomous drones: swarm-capable, mimics UAP, resists 200kW directed energy",
            "real_date": "November 13, 2024",
            "real_event": "NJ drone sightings begin (same day Anduril wins Replicator contract)",
            "gap": "7 years",
            "verified": True,
            "evidence": "4plebs archive October 2019 confirms post existed"
        },
        {
            "fl_date": "September 2, 2025",
            "fl_content": "SAA coordinate posted: 34°50'S 23°55'W (South Atlantic Anomaly center)",
            "real_date": "October 14, 2025",
            "real_event": "ESA announces SAA splitting into two lobes",
            "gap": "42 days",
            "verified": "pending",
            "evidence": "Requires Wayback Machine verification"
        },
        {
            "fl_date": "December 2024",
            "fl_content": "New Jersey kinetic strike test reference",
            "real_date": "December 2024",
            "real_event": "Nordic drone crisis (Copenhagen, Oslo, Munich airports)",
            "gap": "Concurrent",
            "verified": True,
            "evidence": "Events occurred simultaneously"
        },
        {
            "fl_date": "February 9, 2020",
            "fl_content": "PSV Presence positioned at DENIED orbit",
            "real_date": "February 9, 2020",
            "real_event": "Zafar-1 satellite failure at 15:57:25 UT",
            "gap": "Same day",
            "verified": True,
            "evidence": "Date correlation confirmed"
        }
    ]
    
    for corr in correlations:
        verified_class = "verified" if corr["verified"] == True else "pending"
        verified_text = "✓ VERIFIED" if corr["verified"] == True else "⏳ PENDING"
        
        st.markdown(f"""
        <div style="background: #1a2420; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; border: 1px solid rgba(0, 255, 136, 0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <span class="{verified_class}">{verified_text}</span>
                <span style="color: #00d4ff; font-family: 'JetBrains Mono', monospace; font-size: 1.2rem;">Gap: {corr["gap"]}</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                <div>
                    <div style="color: #00ff88; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;">FL Post</div>
                    <div style="color: #e0e6e3; font-weight: 500; margin: 0.5rem 0;">{corr["fl_date"]}</div>
                    <div style="color: #8b9a93; font-size: 0.9rem;">{corr["fl_content"]}</div>
                </div>
                <div>
                    <div style="color: #ff6b35; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;">Real Event</div>
                    <div style="color: #e0e6e3; font-weight: 500; margin: 0.5rem 0;">{corr["real_date"]}</div>
                    <div style="color: #8b9a93; font-size: 0.9rem;">{corr["real_event"]}</div>
                </div>
            </div>
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <span style="color: #666; font-size: 0.8rem;">Evidence: {corr["evidence"]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============= TEMPORAL PATTERNS =============
def render_temporal_patterns(data):
    st.markdown("## 📉 Temporal Pattern Analysis")
    st.markdown("*Detect publication bursts, category trends, keyword spikes, and seasonal patterns*")

    try:
        from fl_temporal_analysis import TemporalAnalysisSuite
    except ImportError:
        st.error("Temporal analysis module not found. Ensure fl_temporal_analysis.py is in the project root.")
        return

    @st.cache_resource
    def get_suite():
        articles = data.get("articles", [])
        keyword_index = data.get("keywords", {})
        coords_df = data.get("coordinates", pd.DataFrame())
        excerpts_df = data.get("excerpts", pd.DataFrame())
        return TemporalAnalysisSuite(articles, excerpts_df, keyword_index, coords_df)

    try:
        suite = get_suite()
    except Exception as e:
        st.error(f"Error initializing temporal analysis: {e}")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Publication Rate",
        "📈 Category Trends",
        "💥 Keyword Bursts",
        "🔄 Seasonal Patterns",
        "📍 Coordinate Timing",
    ])

    # --- Publication Rate ---
    with tab1:
        st.markdown("### Publication Rate Analysis")
        stats = suite.pub_analyzer.get_summary_stats()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Articles", f"{stats['total_articles']:,}")
        col2.metric("Avg/Month", stats['avg_per_month'])
        col3.metric("Peak Month", f"{stats['peak_month']} ({stats['peak_count']})")
        col4.metric("Bursts Detected", stats['num_bursts'])

        st.plotly_chart(suite.pub_analyzer.plot_publication_rate(), use_container_width=True)

        with st.expander("Z-Score Detail"):
            st.plotly_chart(suite.pub_analyzer.plot_bursts(), use_container_width=True)

        with st.expander("Burst & Quiet Period Details"):
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                st.markdown("**Publication Bursts (z > 2.0)**")
                bursts = suite.pub_analyzer.detect_bursts()
                burst_rows = bursts[bursts['is_burst']].sort_values('z_score', ascending=False)
                if not burst_rows.empty:
                    display = burst_rows[['date', 'count', 'z_score']].copy()
                    display['date'] = display['date'].dt.strftime('%Y-%m')
                    display['z_score'] = display['z_score'].round(2)
                    st.dataframe(display, hide_index=True)
                else:
                    st.info("No bursts detected")
            with bcol2:
                st.markdown("**Quiet Periods (z < -1.5)**")
                quiet = suite.pub_analyzer.detect_quiet_periods()
                quiet_rows = quiet[quiet['is_quiet']].sort_values('z_score')
                if not quiet_rows.empty:
                    display = quiet_rows[['date', 'count', 'z_score']].copy()
                    display['date'] = display['date'].dt.strftime('%Y-%m')
                    display['z_score'] = display['z_score'].round(2)
                    st.dataframe(display, hide_index=True)
                else:
                    st.info("No quiet periods detected")

    # --- Category Trends ---
    with tab2:
        st.markdown("### Category Trend Analysis")
        st.markdown("Compares category frequency in the last 12 months vs. historical average")

        trends = suite.cat_analyzer.detect_trending_categories()

        st.plotly_chart(suite.cat_analyzer.plot_trending_vs_declining(), use_container_width=True)

        tcol1, tcol2 = st.columns(2)
        with tcol1:
            st.markdown("**Rising Categories**")
            rising = trends[trends['direction'] == 'rising'][['category', 'trend_ratio', 'recent_avg', 'historical_avg']]
            if not rising.empty:
                st.dataframe(rising, hide_index=True)
            else:
                st.info("No rising categories detected")
        with tcol2:
            st.markdown("**Declining Categories**")
            declining = trends[trends['direction'] == 'declining'][['category', 'trend_ratio', 'recent_avg', 'historical_avg']].head(15)
            if not declining.empty:
                st.dataframe(declining, hide_index=True)
            else:
                st.info("No declining categories detected")

        with st.expander("Category Timeline Comparison"):
            top_cats = trends['category'].head(20).tolist()
            selected = st.multiselect("Select categories to compare", top_cats, default=top_cats[:5])
            if selected:
                st.plotly_chart(suite.cat_analyzer.plot_category_trends(selected), use_container_width=True)

        with st.expander("Co-occurrence Shifts"):
            shifts = suite.cat_analyzer.detect_cooccurrence_shifts()
            if not shifts.empty:
                st.dataframe(shifts.head(20), hide_index=True)

    # --- Keyword Bursts ---
    with tab3:
        st.markdown("### Keyword Burst Detection")

        st.plotly_chart(suite.kw_detector.plot_burst_timeline(), use_container_width=True)

        kcol1, kcol2 = st.columns(2)
        with kcol1:
            st.markdown("**Top Burst Events**")
            all_bursts = suite.kw_detector.detect_all_bursts()
            if not all_bursts.empty:
                display = all_bursts.head(20).copy()
                if 'date' in display.columns:
                    display['date'] = display['date'].apply(
                        lambda d: d.strftime('%Y-%m') if hasattr(d, 'strftime') else str(d)
                    )
                st.dataframe(display, hide_index=True)
        with kcol2:
            st.markdown("**Vanishing Keywords**")
            vanishing = suite.kw_detector.detect_vanishing_keywords()
            if not vanishing.empty:
                display = vanishing.copy()
                display['last_active'] = display['last_active'].dt.strftime('%Y-%m')
                st.dataframe(display, hide_index=True)
            else:
                st.info("No vanishing keywords")

        with st.expander("Single Keyword Deep Dive"):
            kw_list = sorted(suite.kw_detector.keyword_index.keys())
            selected_kw = st.selectbox("Select keyword", kw_list)
            if selected_kw:
                st.plotly_chart(suite.kw_detector.plot_keyword_burst(selected_kw), use_container_width=True)

        with st.expander("Emergent Keywords (last 24 months)"):
            emergent = suite.kw_detector.detect_emergent_keywords()
            em_new = emergent[emergent['is_emergent']]
            if not em_new.empty:
                display = em_new[['keyword', 'first_date', 'total_count']].copy()
                display['first_date'] = display['first_date'].dt.strftime('%Y-%m')
                st.dataframe(display, hide_index=True)
            else:
                st.info("No new keywords in the last 24 months")

    # --- Seasonal Patterns ---
    with tab4:
        st.markdown("### Seasonal Publication Patterns")

        st.plotly_chart(suite.season_analyzer.plot_seasonality(), use_container_width=True)

        with st.expander("Periodicity Detection"):
            st.plotly_chart(suite.season_analyzer.plot_periodicity(), use_container_width=True)
            acorr = suite.season_analyzer.detect_periodicity_autocorrelation()
            if acorr['significant_lags']:
                st.markdown(f"**Significant periodicities at lags:** {acorr['significant_lags'][:10]} months")
                st.markdown(f"**95% confidence band:** +/- {acorr['confidence_band']}")

            fft = suite.season_analyzer.detect_periodicity_fft()
            if 'dominant_periods' in fft and fft['dominant_periods']:
                st.markdown("**Dominant FFT periods:**")
                for p in fft['dominant_periods'][:5]:
                    years = p['period_months'] / 12
                    st.markdown(f"- {p['period_months']} months (~{years:.1f} years), power={p['power']:.0f}")

        with st.expander("Monthly Averages Table"):
            pattern = suite.season_analyzer.get_month_of_year_pattern()
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            pattern['month_name'] = [month_names[int(m)-1] for m in pattern['month']]
            st.dataframe(pattern[['month_name', 'avg_count', 'std_count', 'total_count']], hide_index=True)

    # --- Coordinate Timing ---
    with tab5:
        st.markdown("### Coordinate Temporal Analysis")

        st.plotly_chart(suite.coord_analyzer.plot_coordinate_timeline(), use_container_width=True)

        st.plotly_chart(suite.coord_analyzer.plot_geographic_over_time(), use_container_width=True)

        with st.expander("Temporal Clusters"):
            clusters = suite.coord_analyzer.detect_coordinate_clusters()
            if not clusters.empty:
                display = clusters.copy()
                display['window_end'] = display['window_end'].dt.strftime('%Y-%m')
                st.dataframe(display, hide_index=True)
            else:
                st.info("No coordinate clusters detected")

        with st.expander("Geographic Centroid Shifts"):
            shifts = suite.coord_analyzer.get_geographic_shifts()
            if not shifts.empty:
                st.dataframe(shifts, hide_index=True)
            else:
                st.info("No geographic shift data")

# ============= NETWORK ANALYSIS =============
def render_network_analysis(data):
    st.markdown("## 🕸️ Network Analysis")
    st.markdown("*Discover connections between topics, find hub articles, and map topic communities*")

    try:
        from fl_network_analysis import (ArticleNetworkBuilder, HubDetector, CommunityDetector,
                                         plot_label_network, plot_community_sizes, plot_hub_articles)
    except ImportError:
        st.error("Network analysis module not found. Ensure fl_network_analysis.py is in the project root.")
        return

    articles = data.get("articles", [])
    if not articles:
        st.warning("No article data available.")
        return

    @st.cache_resource
    def build_network():
        builder = ArticleNetworkBuilder(articles)
        nodes, edges = builder.build_label_network()
        hub_det = HubDetector(nodes, edges, articles)
        comm_det = CommunityDetector(nodes, edges, articles)
        communities = comm_det.detect_communities()
        return builder, hub_det, comm_det, nodes, edges, communities

    builder, hub_det, comm_det, nodes, edges, communities = build_network()

    tab1, tab2, tab3 = st.tabs(["🕸️ Label Network", "🎯 Hubs & Bridges", "🏘️ Communities"])

    with tab1:
        st.markdown("### Label Co-occurrence Network")
        st.markdown(f"**{len(nodes)} labels** connected by **{len(edges)} edges**")

        fig = plot_label_network(builder, communities)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Label Statistics"):
            stats = builder.get_label_stats()
            st.dataframe(stats.head(30), hide_index=True)

    with tab2:
        st.markdown("### Hub & Bridge Labels")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Hub Labels** (most connections)")
            hubs = hub_det.find_hub_labels(top_n=20)
            st.dataframe(hubs, hide_index=True)
        with col2:
            st.markdown("**Bridge Labels** (connect different clusters)")
            bridges = hub_det.find_bridge_labels(top_n=15)
            st.dataframe(bridges, hide_index=True)

        with st.expander("Hub Articles (span multiple communities)"):
            hub_arts = hub_det.find_hub_articles(top_n=20)
            st.dataframe(hub_arts, hide_index=True)

        fig = plot_hub_articles(hub_det.find_hub_articles(top_n=20))
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("### Topic Communities")
        summary = comm_det.get_community_summary()
        st.markdown(f"**{len(communities)} communities detected**")

        fig = plot_community_sizes(summary)
        st.plotly_chart(fig, use_container_width=True)

        for _, row in summary.iterrows():
            with st.expander(f"Community {row['community_id']}: {row['top_label']} cluster ({row['article_count']} articles, {row['label_count']} labels)"):
                st.markdown(f"**Labels:** {row['labels']}")

# ============= TOPIC MODELING =============
def render_topic_modeling(data):
    st.markdown("## 🧩 Topic Modeling")
    st.markdown("*Discover hidden thematic clusters in 30,000+ excerpts using NMF*")

    try:
        from fl_topic_modeling import (ExcerptTopicModeler, TopicLabelComparator, TopicTrendAnalyzer,
                                       plot_topic_wordclouds, plot_topic_distribution,
                                       plot_topic_heatmap, plot_topic_trends)
    except ImportError:
        st.error("Topic modeling module not found. Ensure fl_topic_modeling.py is in the project root.")
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        st.error("scikit-learn is required for topic modeling. Install with: pip install scikit-learn")
        return

    articles = data.get("articles", [])
    excerpts_df = data.get("excerpts", pd.DataFrame())
    if excerpts_df.empty:
        st.warning("No excerpt data available.")
        return

    n_topics = st.sidebar.slider("Number of topics", 5, 30, 15, key="n_topics_slider")

    @st.cache_resource
    def fit_model(n):
        modeler = ExcerptTopicModeler(excerpts_df)
        modeler.fit(n_topics=n)
        comparator = TopicLabelComparator(modeler, articles)
        trend_analyzer = TopicTrendAnalyzer(modeler, articles)
        return modeler, comparator, trend_analyzer

    with st.spinner("Fitting topic model (this takes ~10 seconds)..."):
        modeler, comparator, trend_analyzer = fit_model(n_topics)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Discovered Topics", "🔍 Novel Topics", "📈 Topic Trends", "🗺️ Topic-Label Map"])

    with tab1:
        st.markdown("### Discovered Topics")

        fig = plot_topic_wordclouds(modeler)
        st.plotly_chart(fig, use_container_width=True)

        fig2 = plot_topic_distribution(modeler)
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.markdown("### Novel/Hidden Topics")
        st.markdown("*Topics that don't align well with any existing label — these are hidden thematic clusters*")
        novel = comparator.find_novel_topics()
        if not novel.empty:
            for _, row in novel.iterrows():
                st.markdown(f"**Topic {row['topic_id']} [{row['topic_label']}]**: {row['top_words']}")
                st.markdown(f"  Best label match: {row['best_label']} (alignment: {row['alignment_score']:.2f})")
                st.markdown("---")
        else:
            st.info("All topics align with existing labels.")

        with st.expander("Full Topic-Label Comparison"):
            comparison = comparator.compare_topics_to_labels(articles)
            st.dataframe(comparison, hide_index=True)

    with tab3:
        st.markdown("### Topic Trends")
        fig = plot_topic_trends(trend_analyzer)
        st.plotly_chart(fig, use_container_width=True)

        trending = trend_analyzer.get_trending_topics()
        if not trending.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Rising Topics**")
                rising = trending[trending['direction'] == 'rising']
                st.dataframe(rising, hide_index=True)
            with col2:
                st.markdown("**Declining Topics**")
                declining = trending[trending['direction'] == 'declining']
                st.dataframe(declining, hide_index=True)

    with tab4:
        st.markdown("### Topic-Label Alignment Heatmap")
        fig = plot_topic_heatmap(comparator, articles)
        st.plotly_chart(fig, use_container_width=True)

# ============= LANGUAGE ANALYSIS =============
def render_language_analysis(data):
    st.markdown("## 🔤 Language Analysis")
    st.markdown("*Catalog and classify FL constructed languages across 10,000+ articles*")

    try:
        from fl_language_analysis import (LanguageClassifier, LanguageAnalyzer, LanguageFamilyDetector,
                                          LanguageEvolutionTracker, plot_language_timeline,
                                          plot_language_topic_heatmap, plot_language_births,
                                          plot_language_families)
    except ImportError:
        st.error("Language analysis module not found. Ensure fl_language_analysis.py is in the project root.")
        return

    articles = data.get("articles", [])
    if not articles:
        st.warning("No article data available.")
        return

    @st.cache_resource
    def run_language_analysis():
        classifier = LanguageClassifier(articles)
        languages = classifier.get_languages()
        analyzer = LanguageAnalyzer(articles, languages)
        family_det = LanguageFamilyDetector(articles, languages)
        evolution = LanguageEvolutionTracker(articles, languages)
        return classifier, analyzer, family_det, evolution

    classifier, analyzer, family_det, evolution = run_language_analysis()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Language Stats", "👨‍👩‍👧‍👦 Language Families", "📈 Evolution", "🏷️ Classification"])

    with tab1:
        st.markdown("### Language Statistics")
        languages_list = classifier.get_languages()
        topics_list = classifier.get_topics()

        col1, col2, col3 = st.columns(3)
        col1.metric("Languages Identified", len(languages_list))
        col2.metric("Topic Labels", len(topics_list))
        col3.metric("Total Articles", len(articles))

        st.markdown("**Most-used languages:**")
        prolific = analyzer.get_prolific_languages(top_n=30)
        st.dataframe(prolific, hide_index=True)

        fig = plot_language_timeline(analyzer)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### Language Families")
        st.markdown("*Languages grouped by topic similarity*")

        fig = plot_language_families(family_det)
        st.plotly_chart(fig, use_container_width=True)

        summary = family_det.get_family_summary()
        for _, row in summary.iterrows():
            with st.expander(f"Family {row['family_id']}: {row['primary_topics']} ({row['language_count']} languages, {row['article_count']} articles)"):
                st.markdown(f"**Languages:** {row['languages']}")

    with tab3:
        st.markdown("### Language Evolution")
        lifecycle = evolution.get_language_lifecycle()

        col1, col2, col3 = st.columns(3)
        active = lifecycle[lifecycle['status'] == 'active']
        dormant = lifecycle[lifecycle['status'] == 'dormant']
        retired = lifecycle[lifecycle['status'] == 'retired']
        col1.metric("Active", len(active))
        col2.metric("Dormant", len(dormant))
        col3.metric("Retired", len(retired))

        fig = plot_language_births(evolution)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Active Languages"):
            st.dataframe(active.head(30), hide_index=True)
        with st.expander("Dormant Languages"):
            st.dataframe(dormant, hide_index=True)
        with st.expander("Retired Languages"):
            st.dataframe(retired.head(30), hide_index=True)

    with tab4:
        st.markdown("### Label Classification")
        st.markdown("*How labels are classified as language vs topic*")
        classification = classifier.classify_labels()
        st.dataframe(classification, hide_index=True)

        fig = plot_language_topic_heatmap(analyzer)
        st.plotly_chart(fig, use_container_width=True)

# ============= ARTICLES =============
def render_articles(data):
    st.markdown("## 📚 Article Browser")

    articles = data.get("articles", [])
    excerpts_df = data.get("excerpts", pd.DataFrame())

    if not articles:
        st.warning("No article data loaded")
        return

    st.markdown(f"*Browse {len(articles)} FL articles*")

    # Build excerpt lookup for summaries (free - uses existing data)
    excerpt_lookup = {}
    if not excerpts_df.empty and 'url' in excerpts_df.columns:
        for url, group in excerpts_df.groupby('url'):
            # Get first excerpt as summary
            texts = group['text'].dropna().tolist()
            if texts:
                excerpt_lookup[url] = texts[0][:200]

    # Get all labels
    all_labels = set()
    for article in articles:
        all_labels.update(article.get('labels', []))

    col1, col2 = st.columns([2, 1])

    with col1:
        search = st.text_input("Search articles", placeholder="Enter title keywords")

    with col2:
        selected_label = st.selectbox("Filter by category", ["All"] + sorted(list(all_labels)))

    # Filter
    filtered = articles
    if search:
        filtered = [a for a in filtered if search.lower() in a.get('title', '').lower()]
    if selected_label != "All":
        filtered = [a for a in filtered if selected_label in a.get('labels', [])]

    st.markdown(f"### Showing {min(len(filtered), 100)} of {len(filtered)} articles")

    for article in filtered[:100]:
        title = article.get('title', 'Untitled')
        date = article.get('date', 'Unknown')
        labels = article.get('labels', [])
        url = article.get('url', '')
        summary = excerpt_lookup.get(url, '')

        # Escape any HTML in title/summary to prevent rendering issues
        safe_title = html.escape(str(title)[:80])
        safe_summary = html.escape(str(summary)) if summary else ''
        labels_str = ', '.join(labels[:3]) if labels else ''

        # Use st.container with columns for cleaner layout
        with st.container():
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(f"**[{safe_title}{'...' if len(title) > 80 else ''}]({url})**")
                st.caption(f"{date} {'• ' + labels_str if labels_str else ''}")
                if safe_summary:
                    st.markdown(f"<small style='color: gray;'>{safe_summary[:150]}...</small>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"[View →]({url})")

# ============= BIBLIOGRAPHY =============
def render_bibliography(data):
    st.markdown("## 📖 Bibliography & Citations")

    bib_df = data.get("bibliography", pd.DataFrame())
    cite_df = data.get("citations", pd.DataFrame())

    # Show tabs for Bibliography vs Citations
    tab1, tab2 = st.tabs(["📚 Bibliography Entries", "📝 Inline Citations"])

    with tab1:
        if bib_df.empty:
            st.info("""
            **No bibliography data loaded yet.**

            To extract bibliographies from FL articles, run:
            ```bash
            python fl_enhanced_extractor.py --reprocess
            python fl_enhanced_extractor.py --export
            ```
            This will extract academic references from all articles.
            """)
        else:
            st.markdown(f"*{len(bib_df):,} bibliography entries extracted from FL articles*")

            # Filters
            col1, col2 = st.columns([2, 1])
            with col1:
                search_bib = st.text_input("Search bibliography", placeholder="Author, title, or journal...")
            with col2:
                year_filter = st.text_input("Filter by year", placeholder="e.g., 2004")

            # Filter data
            filtered_bib = bib_df.copy()
            if search_bib:
                mask = filtered_bib.apply(lambda row: search_bib.lower() in str(row).lower(), axis=1)
                filtered_bib = filtered_bib[mask]
            if year_filter:
                filtered_bib = filtered_bib[filtered_bib['year'].astype(str).str.contains(year_filter, na=False)]

            st.markdown(f"### Showing {min(len(filtered_bib), 100)} of {len(filtered_bib)} entries")

            # Display entries
            for _, row in filtered_bib.head(100).iterrows():
                author = str(row.get('author', '') or 'Unknown')
                year = str(row.get('year', '') or '')
                title = str(row.get('title', '') or '')
                journal = str(row.get('journal', '') or '')
                article_url = str(row.get('article_url', '') or '')
                article_title = str(row.get('article_title', '') or '')[:60]

                # Build search query for external lookups
                search_parts = []
                if author and author != 'Unknown':
                    search_parts.append(author)
                if title:
                    search_parts.append(title)
                elif year:
                    search_parts.append(year)
                search_query = ' '.join(search_parts)

                # URL encode the search query
                import urllib.parse
                encoded_query = urllib.parse.quote(search_query)
                google_scholar_url = f"https://scholar.google.com/scholar?q={encoded_query}"
                google_books_url = f"https://www.google.com/search?tbm=bks&q={encoded_query}"

                # Build formatted citation string
                cite_parts = []
                if author and author != 'Unknown':
                    cite_parts.append(author)
                if year:
                    cite_parts.append(f"({year})")
                if title:
                    cite_parts.append(f'"{title}"')
                if journal:
                    cite_parts.append(journal)
                formatted_citation = ' '.join(cite_parts)

                # WorldCat search for library copies
                worldcat_url = f"https://www.worldcat.org/search?q={encoded_query}"

                st.markdown(f"""
                <div class="result-card">
                    <div class="result-meta">{year}</div>
                    <div class="result-title">{author}</div>
                    <div class="result-excerpt">{title}</div>
                    <div style="color: var(--accent-cyan); font-size: 0.95rem; margin-top: 0.3rem;">
                        {journal if journal else ''}
                    </div>
                    <div style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-secondary);">
                        From: {article_title}...
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Links row
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    if article_url:
                        st.markdown(f"[View FL article →]({article_url})")
                with col2:
                    st.markdown(f"[Scholar 🎓]({google_scholar_url})")
                with col3:
                    st.markdown(f"[Books 📚]({google_books_url})")
                with col4:
                    st.markdown(f"[WorldCat 🌐]({worldcat_url})")

            # Download buttons
            if not filtered_bib.empty:
                st.markdown("### 📥 Export Bibliography")
                col1, col2, col3 = st.columns(3)

                with col1:
                    csv = filtered_bib.to_csv(index=False)
                    st.download_button(
                        "📥 CSV",
                        csv,
                        "fl_bibliography.csv",
                        "text/csv"
                    )

                with col2:
                    bibtex = generate_bibtex(filtered_bib)
                    st.download_button(
                        "📥 BibTeX",
                        bibtex,
                        "fl_bibliography.bib",
                        "text/plain"
                    )

                with col3:
                    ris = generate_ris(filtered_bib)
                    st.download_button(
                        "📥 RIS (EndNote)",
                        ris,
                        "fl_bibliography.ris",
                        "text/plain"
                    )

            # Statistics
            st.markdown("---")
            st.markdown("### 📊 Bibliography Statistics")

            col1, col2 = st.columns(2)

            with col1:
                if 'year' in bib_df.columns:
                    year_counts = bib_df['year'].dropna().value_counts().sort_index().tail(20)
                    if not year_counts.empty:
                        fig = px.bar(
                            x=year_counts.index.astype(str),
                            y=year_counts.values,
                            labels={'x': 'Year', 'y': 'References'},
                            color_discrete_sequence=['#1a73e8']
                        )
                        fig.update_layout(
                            title="References by Year",
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font_color='#5f6368'
                        )
                        st.plotly_chart(fig, use_container_width=True)

            with col2:
                if 'author' in bib_df.columns:
                    author_counts = bib_df['author'].dropna().value_counts().head(15)
                    if not author_counts.empty:
                        fig = px.bar(
                            x=author_counts.values,
                            y=author_counts.index,
                            orientation='h',
                            labels={'x': 'Count', 'y': 'Author'},
                            color_discrete_sequence=['#1967d2']
                        )
                        fig.update_layout(
                            title="Top Cited Authors",
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font_color='#5f6368',
                            yaxis={'categoryorder': 'total ascending'}
                        )
                        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if cite_df.empty:
            st.info("No inline citation data loaded. Run the enhanced extractor to extract citations.")
        else:
            st.markdown(f"*{len(cite_df):,} inline citations found in FL articles*")

            # Search
            search_cite = st.text_input("Search citations", placeholder="Author or year...")

            filtered_cite = cite_df.copy()
            if search_cite:
                mask = filtered_cite.apply(lambda row: search_cite.lower() in str(row).lower(), axis=1)
                filtered_cite = filtered_cite[mask]

            st.markdown(f"### Showing {min(len(filtered_cite), 50)} of {len(filtered_cite)} citations")

            # Display as cards with links
            for _, row in filtered_cite.head(50).iterrows():
                cite_text = str(row.get('citation_text', '') or '')
                cite_type = str(row.get('type', '') or '')
                author = str(row.get('author', '') or '')
                year = str(row.get('year', '') or '')
                article_title = str(row.get('article_title', '') or '')[:50]
                article_url = str(row.get('article_url', '') or '')

                # Build search query
                search_parts = [p for p in [author, year] if p]
                if search_parts:
                    import urllib.parse
                    encoded = urllib.parse.quote(' '.join(search_parts))
                    scholar_url = f"https://scholar.google.com/scholar?q={encoded}"
                else:
                    scholar_url = None

                st.markdown(f"""
                <div class="result-card">
                    <div class="result-meta">{cite_type} • {year if year else 'Unknown year'}</div>
                    <div class="result-title">{cite_text}</div>
                    <div style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-secondary);">
                        From: {article_title}...
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Links
                link_cols = st.columns([2, 1])
                with link_cols[0]:
                    if article_url:
                        st.markdown(f"[View FL article →]({article_url})")
                with link_cols[1]:
                    if scholar_url:
                        st.markdown(f"[Search Scholar 🎓]({scholar_url})")

            # Download
            if not filtered_cite.empty:
                csv = filtered_cite.to_csv(index=False)
                st.download_button(
                    "📥 Download Citations CSV",
                    csv,
                    "fl_citations_filtered.csv",
                    "text/csv"
                )

# ============= BIBLIOGRAPHY ANALYSIS =============
def render_bibliography_analysis(data):
    st.markdown("## 📑 Bibliography Analysis")
    st.markdown("*Analyze FL's real-world academic sources and citation patterns*")

    try:
        from fl_bibliography_analysis import (BibliographyCleaner, AuthorAnalyzer, SourceAnalyzer,
                                               CitationNetworkAnalyzer, plot_top_authors,
                                               plot_cited_year_distribution, plot_field_distribution,
                                               plot_citation_timeline, plot_author_network)
    except ImportError:
        st.error("Bibliography analysis module not found. Ensure fl_bibliography_analysis.py is in the project root.")
        return

    bib_df = data.get("bibliography", pd.DataFrame())
    cite_df = data.get("citations", pd.DataFrame())
    articles = data.get("articles", [])

    if bib_df.empty:
        st.warning("No bibliography data available. Run `python fl_enhanced_extractor.py --reprocess` to extract bibliographies.")
        return

    @st.cache_resource
    def run_analysis():
        cleaner = BibliographyCleaner()
        clean_bib = cleaner.clean(bib_df)
        noise = cleaner.get_noise_stats()
        author_analyzer = AuthorAnalyzer(clean_bib)
        source_analyzer = SourceAnalyzer(clean_bib)
        citation_analyzer = CitationNetworkAnalyzer(clean_bib, cite_df, articles)
        return clean_bib, noise, author_analyzer, source_analyzer, citation_analyzer

    clean_bib, noise, author_analyzer, source_analyzer, citation_analyzer = run_analysis()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entries", f"{len(bib_df):,}")
    col2.metric("Real References", f"{len(clean_bib):,}")
    col3.metric("Noise Removed", noise.get('total_removed', 0))
    col4.metric("Articles w/ Bibliography", f"{clean_bib['article_id'].nunique()}")

    tab1, tab2, tab3, tab4 = st.tabs(["👤 Authors", "📚 Sources & Fields", "📈 Citation Patterns", "🕸️ Co-citation Network"])

    with tab1:
        st.markdown("### Most-Cited Authors")
        top_authors = author_analyzer.get_most_cited_authors(top_n=30)
        fig = plot_top_authors(top_authors)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Full Author Table"):
            st.dataframe(top_authors, hide_index=True)

        with st.expander("Author Fields"):
            fields = author_analyzer.get_author_fields()
            if not fields.empty:
                st.dataframe(fields.head(30), hide_index=True)

    with tab2:
        st.markdown("### Academic Field Distribution")
        field_dist = source_analyzer.get_field_distribution()
        fig = plot_field_distribution(field_dist)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Publication Year Distribution of Cited Works")
        year_dist = source_analyzer.get_cited_year_distribution()
        fig = plot_cited_year_distribution(year_dist)
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top Journals**")
            journals = source_analyzer.get_top_journals(top_n=20)
            st.dataframe(journals, hide_index=True)
        with col2:
            st.markdown("**Top Publishers**")
            publishers = source_analyzer.get_top_publishers(top_n=20)
            if not publishers.empty:
                st.dataframe(publishers, hide_index=True)

    with tab3:
        st.markdown("### Citation Patterns Over Time")
        timeline = citation_analyzer.get_citation_timeline()
        if not timeline.empty:
            fig = plot_citation_timeline(timeline)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Citation Density by FL Category")
        density = citation_analyzer.get_citation_density_by_category()
        if not density.empty:
            st.dataframe(density.head(20), hide_index=True)

        with st.expander("Most-Cited Works"):
            works = citation_analyzer.get_most_cited_works()
            if not works.empty:
                st.dataframe(works.head(20), hide_index=True)

    with tab4:
        st.markdown("### Author Co-citation Network")
        st.markdown("*Authors connected when cited in the same FL article*")
        cooccurrence = author_analyzer.get_author_cooccurrence(top_n=20)
        if not cooccurrence.empty:
            fig = plot_author_network(cooccurrence)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Co-citation Table"):
                st.dataframe(cooccurrence.head(30), hide_index=True)

        with st.expander("Cross-Article Citations (shared sources)"):
            cross = citation_analyzer.get_cross_article_citations()
            if not cross.empty:
                st.dataframe(cross.head(20), hide_index=True)
            else:
                st.info("No cross-article citations found")

# ============= IMAGES =============
def render_images(data):
    st.markdown("## 🖼️ Image Gallery")

    img_df = data.get("images", pd.DataFrame())

    if img_df.empty:
        st.info("""
        **No image data loaded yet.**

        To extract images from FL articles, run:
        ```bash
        python fl_enhanced_extractor.py --reprocess
        python fl_enhanced_extractor.py --export
        ```

        To download images locally:
        ```bash
        python fl_enhanced_extractor.py --download-images
        ```
        """)
        return

    st.markdown(f"*{len(img_df):,} images extracted from FL articles*")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        search_img = st.text_input("Search by article or alt text", placeholder="Enter keywords...")
    with col2:
        file_types = ["All"] + list(img_df['file_type'].dropna().unique())
        selected_type = st.selectbox("File type", file_types)
    with col3:
        show_headers = st.checkbox("Show header images only", value=False)

    # Filter
    filtered_img = img_df.copy()
    if search_img:
        mask = (filtered_img['article_title'].str.contains(search_img, case=False, na=False) |
                filtered_img['alt_text'].str.contains(search_img, case=False, na=False))
        filtered_img = filtered_img[mask]
    if selected_type != "All":
        filtered_img = filtered_img[filtered_img['file_type'] == selected_type]
    if show_headers:
        filtered_img = filtered_img[filtered_img['is_header'] == 1]

    st.markdown(f"### Showing {min(len(filtered_img), 50)} of {len(filtered_img)} images")

    # Display in grid
    cols = st.columns(3)
    for i, (_, row) in enumerate(filtered_img.head(50).iterrows()):
        with cols[i % 3]:
            image_url = str(row.get('image_url', '') or '')
            alt_text = str(row.get('alt_text', '') or '') or 'FL Image'
            article_title = str(row.get('article_title', '') or 'Unknown')[:50]
            article_url = str(row.get('article_url', '') or '')
            caption = str(row.get('caption', '') or '')

            # Build reverse image search URL
            import urllib.parse
            encoded_img_url = urllib.parse.quote(image_url, safe='')
            google_img_search = f"https://lens.google.com/uploadbyurl?url={encoded_img_url}"
            tineye_search = f"https://tineye.com/search?url={encoded_img_url}"

            st.markdown(f"""
            <div style="background: var(--bg-secondary); border-radius: 8px; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid var(--border-color);">
                <img src="{image_url}" style="width: 100%; border-radius: 4px; max-height: 200px; object-fit: cover;"
                     onerror="this.style.display='none'" alt="{alt_text}">
                <div style="padding: 0.5rem;">
                    <div style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">{article_title}...</div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem;">{alt_text[:60] if alt_text else 'No description'}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Links row for each image
            link_cols = st.columns([2, 1, 1])
            with link_cols[0]:
                if article_url:
                    st.markdown(f"[View article →]({article_url})")
            with link_cols[1]:
                st.markdown(f"[Google Lens 🔍]({google_img_search})")
            with link_cols[2]:
                st.markdown(f"[TinEye 🔎]({tineye_search})")

    # Statistics
    st.markdown("---")
    st.markdown("### 📊 Image Statistics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Images", f"{len(img_df):,}")

    with col2:
        header_count = len(img_df[img_df['is_header'] == 1])
        st.metric("Header Images", f"{header_count:,}")

    with col3:
        if 'file_type' in img_df.columns:
            type_counts = img_df['file_type'].value_counts()
            most_common = type_counts.index[0] if len(type_counts) > 0 else "N/A"
            st.metric("Most Common Type", most_common.upper() if most_common else "N/A")

    # File type breakdown
    if 'file_type' in img_df.columns:
        type_counts = img_df['file_type'].dropna().value_counts()
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            color_discrete_sequence=px.colors.sequential.Greens_r
        )
        fig.update_layout(
            title="Image Types",
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#5f6368'
        )
        st.plotly_chart(fig, use_container_width=True)

    # Download options
    st.markdown("### 📥 Download Options")
    col1, col2 = st.columns(2)

    with col1:
        csv = img_df.to_csv(index=False)
        st.download_button(
            "📥 Download Image List CSV",
            csv,
            "fl_images.csv",
            "text/csv"
        )

    with col2:
        # Generate download script for batch downloading
        if not filtered_img.empty:
            urls = filtered_img['image_url'].dropna().head(100).tolist()
            download_script = """#!/bin/bash
# FL Image Batch Download Script
# Run: chmod +x download_images.sh && ./download_images.sh

mkdir -p fl_images
cd fl_images

"""
            for i, url in enumerate(urls):
                filename = f"fl_image_{i+1}.{url.split('.')[-1][:4] if '.' in url else 'jpg'}"
                download_script += f'curl -L -o "{filename}" "{url}"\n'

            st.download_button(
                "📥 Download Script (bash)",
                download_script,
                "download_images.sh",
                "text/plain",
                help="Shell script to batch download images"
            )

    # PowerShell version for Windows
    st.markdown("**For Windows users:**")
    if not filtered_img.empty:
        urls = filtered_img['image_url'].dropna().head(100).tolist()
        ps_script = """# FL Image Batch Download Script for Windows
# Run in PowerShell: .\\download_images.ps1

New-Item -ItemType Directory -Force -Path fl_images | Out-Null
Set-Location fl_images

"""
        for i, url in enumerate(urls):
            filename = f"fl_image_{i+1}.{url.split('.')[-1][:4] if '.' in url else 'jpg'}"
            ps_script += f'Invoke-WebRequest -Uri "{url}" -OutFile "{filename}"\n'

        st.download_button(
            "📥 Download Script (PowerShell)",
            ps_script,
            "download_images.ps1",
            "text/plain"
        )

# ============= READING LISTS =============
def render_reading_lists(data):
    st.markdown("## 📚 AI Reading Lists")
    st.markdown("*Curated article pathways based on topic importance and connections*")

    # Try to import AI features
    try:
        from fl_ai_features import ReadingListGenerator, TopicTimeline
        has_ai = True
    except ImportError:
        has_ai = False
        st.error("AI features module not found. Ensure fl_ai_features.py is in the same directory.")
        return

    # Initialize generator
    @st.cache_resource
    def get_generator():
        return ReadingListGenerator()

    try:
        generator = get_generator()
    except Exception as e:
        st.error(f"Error loading reading list generator: {e}")
        return

    # Tabs for different list types
    tab1, tab2, tab3 = st.tabs(["🎯 Topic Reading List", "🚀 Starter List", "🔗 Connection Explorer"])

    with tab1:
        st.markdown("### Generate a Topic-Based Reading List")

        col1, col2 = st.columns([3, 1])
        with col1:
            topic = st.text_input("Enter topic or keywords",
                                 placeholder="e.g., MilOrb drones, coordinates, Giselian contact")
        with col2:
            max_articles = st.selectbox("Max articles", [10, 20, 30, 50], index=1)

        # Quick topic buttons
        st.markdown("**Quick topics:**")
        quick_topics = ["MilOrb", "PSV vehicles", "coordinates locations", "Giselian entities",
                       "SV17q organization", "drone technology", "NDE consciousness"]
        cols = st.columns(len(quick_topics))
        for i, t in enumerate(quick_topics):
            if cols[i].button(t, key=f"topic_{t}"):
                topic = t

        if topic:
            with st.spinner("Generating reading list..."):
                reading_list = generator.generate_topic_reading_list(topic, max_articles)

            if reading_list:
                st.markdown(f"### Reading List: {topic}")
                st.markdown(f"*{len(reading_list)} articles found, sorted by importance*")

                for article in reading_list:
                    difficulty_colors = {
                        'beginner': '#00ff88',
                        'intermediate': '#00d4ff',
                        'advanced': '#ff6b35'
                    }
                    diff_color = difficulty_colors.get(article['difficulty'], '#8b9a93')

                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="result-meta">{article['date']}</span>
                            <span style="color: {diff_color}; font-size: 0.75rem; text-transform: uppercase;">
                                {article['difficulty']}
                            </span>
                        </div>
                        <div class="result-title">{article['reading_order']}. {article['title'][:70]}</div>
                        <div class="result-excerpt">{article.get('excerpt_preview', '')[:150]}...</div>
                        <div style="margin-top: 0.5rem;">
                            <span class="keyword-tag">{article['matched_keyword']}</span>
                            <span style="color: #8b9a93; font-size: 0.8rem; margin-left: 1rem;">
                                Importance: {article['importance']:.0f}
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"[Open article →]({article['url']})")
            else:
                st.warning("No articles found for this topic.")

    with tab2:
        st.markdown("### Starter Reading List")
        st.markdown("*The most important articles for new FL researchers*")

        if st.button("Generate Starter List", key="starter_btn"):
            with st.spinner("Generating starter list..."):
                starter_list = generator.generate_starter_reading_list(15)

            if starter_list:
                for article in starter_list:
                    category_colors = {
                        'defense': '#ff6b35',
                        'locations': '#00d4ff',
                        'organizations': '#00ff88',
                        'philosophy': '#9966ff',
                        'general': '#8b9a93'
                    }
                    cat_color = category_colors.get(article.get('category', 'general'), '#8b9a93')

                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="result-meta">{article.get('date', '')}</span>
                            <span style="color: {cat_color}; font-size: 0.75rem; text-transform: uppercase;">
                                {article.get('category', 'general')}
                            </span>
                        </div>
                        <div class="result-title">{article['reading_order']}. {article['title'][:70]}</div>
                        <div style="margin-top: 0.5rem;">
                            <span style="color: #00ff88; font-size: 0.9rem;">
                                Importance Score: {article['importance']:.0f}
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"[Open article →]({article['url']})")

    with tab3:
        st.markdown("### Connection Explorer")
        st.markdown("*Explore articles connected to a starting point*")

        start_url = st.text_input("Enter article URL to explore from",
                                  placeholder="https://forgottenlanguages-full.forgottenlanguages.org/...")

        if start_url:
            with st.spinner("Finding connections..."):
                connections = generator.generate_connection_list(start_url, max_depth=2, max_articles=15)

            if connections:
                st.markdown(f"### Connected Articles ({len(connections)} found)")

                for article in connections:
                    depth_label = ["Starting", "1st degree", "2nd degree"][min(article.get('depth', 0), 2)]

                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="result-meta">{article.get('date', '')}</span>
                            <span style="color: #00d4ff; font-size: 0.75rem;">{depth_label}</span>
                        </div>
                        <div class="result-title">{article['reading_order']}. {article['title'][:70]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"[Open article →]({article['url']})")
            else:
                st.warning("No connections found or invalid URL.")

# ============= TOPIC EVOLUTION =============
def render_topic_evolution(data):
    st.markdown("## 📈 Topic Evolution")
    st.markdown("*Track how keywords and topics evolved over 16 years*")

    try:
        from fl_ai_features import TopicTimeline
        has_ai = True
    except ImportError:
        st.error("AI features module not found.")
        return

    @st.cache_resource
    def get_timeline():
        return TopicTimeline()

    try:
        timeline = get_timeline()
    except Exception as e:
        st.error(f"Error loading timeline: {e}")
        return

    tab1, tab2, tab3 = st.tabs(["📊 Keyword Timeline", "📅 First Occurrences", "🔄 Co-occurrence"])

    with tab1:
        st.markdown("### Keyword Timeline")

        col1, col2 = st.columns([3, 1])
        with col1:
            keyword = st.text_input("Enter keyword to track",
                                   placeholder="e.g., MilOrb, PSV, drone")

        # Quick keyword buttons
        quick_keywords = ["MilOrb", "PSV", "drone", "DOLYN", "SV17q", "Giselian", "NDE", "coordinates"]
        st.markdown("**Quick keywords:**")
        cols = st.columns(len(quick_keywords))
        for i, kw in enumerate(quick_keywords):
            if cols[i].button(kw, key=f"kw_{kw}"):
                keyword = kw

        if keyword:
            timeline_data = timeline.get_keyword_timeline(keyword)

            if timeline_data:
                st.markdown(f"### Timeline for '{keyword}'")

                # Convert to dataframe for plotting
                import pandas as pd
                df = pd.DataFrame(timeline_data, columns=['Date', 'Count'])
                df['Date'] = pd.to_datetime(df['Date'] + '-01')

                fig = px.bar(df, x='Date', y='Count',
                            title=f"'{keyword}' mentions over time",
                            color_discrete_sequence=['#1a73e8'])
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#5f6368',
                    xaxis_title="Date",
                    yaxis_title="Mentions"
                )
                st.plotly_chart(fig, use_container_width=True)

                # Summary stats
                total = sum(c for _, c in timeline_data)
                first_date = timeline_data[0][0] if timeline_data else "N/A"
                peak_date, peak_count = max(timeline_data, key=lambda x: x[1])

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Mentions", total)
                col2.metric("First Appearance", first_date)
                col3.metric("Peak Month", f"{peak_date} ({peak_count})")
            else:
                st.warning(f"No data found for '{keyword}'")

    with tab2:
        st.markdown("### First Occurrences of Key Terms")
        st.markdown("*When did each FL concept first appear?*")

        # Get first occurrences for important terms
        key_terms = ['MilOrb', 'PSV', 'DOLYN', 'SV17q', 'Giselian', 'Denebian',
                    'XViS', 'LyAV', 'drone', 'AUTEC', 'SAA', 'NodeSpaces', 'NDE']

        occurrences = timeline.get_first_occurrences(key_terms)

        if occurrences:
            # Display as timeline
            for keyword, date in occurrences:
                st.markdown(f"""
                <div style="display: flex; align-items: center; margin: 0.5rem 0; padding: 0.5rem;
                           background: rgba(0, 255, 136, 0.1); border-radius: 4px;">
                    <span style="color: #00ff88; font-family: monospace; width: 80px;">{date}</span>
                    <span style="color: #e0e6e3; font-weight: 500;">{keyword}</span>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.markdown("### Keyword Co-occurrence")
        st.markdown("*Find articles where two keywords appear together*")

        col1, col2 = st.columns(2)
        with col1:
            keyword1 = st.text_input("First keyword", placeholder="e.g., MilOrb")
        with col2:
            keyword2 = st.text_input("Second keyword", placeholder="e.g., drone")

        if keyword1 and keyword2:
            cooccurrence = timeline.get_keyword_cooccurrence(keyword1, keyword2)

            if cooccurrence:
                st.markdown(f"### Articles with both '{keyword1}' and '{keyword2}'")
                st.markdown(f"*{len(cooccurrence)} articles found*")

                for article in cooccurrence[:20]:
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-meta">{article['date']}</div>
                        <div class="result-title">{article['title'][:70]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"[Open article →]({article['url']})")
            else:
                st.warning(f"No articles found with both '{keyword1}' and '{keyword2}'")

# ============= FULL-TEXT SEARCH WITH HIGHLIGHTING =============
def render_fulltext_search(data):
    st.markdown("## 🔍 Full-Text Search")
    st.markdown("*Search across all excerpts with highlighted matches*")

    excerpts_df = data.get("excerpts", pd.DataFrame())

    if excerpts_df.empty:
        st.warning("No excerpts data loaded.")
        return

    # Search input
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input("Search excerpts", placeholder="Enter search terms...")
    with col2:
        case_sensitive = st.checkbox("Case sensitive", value=False)

    # Quick search suggestions
    st.markdown("**Quick searches:**")
    quick_searches = ["MilOrb drone", "coordinates location", "SV17q operation",
                     "Giselian contact", "PSV vehicle", "AUTEC base", "NDE experience"]
    cols = st.columns(len(quick_searches))
    for i, term in enumerate(quick_searches):
        if cols[i].button(term, key=f"quick_{term}"):
            search_query = term

    if search_query:
        # Search with highlighting
        def highlight_text(text, query, case_sensitive=False):
            if not case_sensitive:
                pattern = re.compile(re.escape(query), re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(query))

            highlighted = pattern.sub(
                lambda m: f'<mark style="background: #ffeb3b; color: #000; padding: 0 2px;">{m.group()}</mark>',
                str(text)
            )
            return highlighted

        # Filter excerpts
        if case_sensitive:
            mask = excerpts_df['text'].str.contains(search_query, case=True, na=False, regex=False)
        else:
            mask = excerpts_df['text'].str.contains(search_query, case=False, na=False, regex=False)

        results = excerpts_df[mask].copy()

        st.markdown(f"### Found {len(results):,} matches")

        # Display results with highlighting - compact style
        for _, row in results.head(50).iterrows():
            text = str(row.get('text', ''))
            title = str(row.get('title', 'Unknown'))[:70]
            url = str(row.get('url', ''))
            category = str(row.get('category', ''))

            highlighted_text = highlight_text(text[:300], search_query, case_sensitive)

            st.markdown(f"""
            <div style="background: var(--bg-secondary); border-left: 3px solid var(--accent-green);
                        padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0 6px 6px 0;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex: 1;">
                        <a href="{url}" target="_blank" style="color: var(--text-primary); text-decoration: none;
                           font-weight: 500; font-size: 0.9rem;">{title}</a>
                        <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.2rem;">{category}</div>
                        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.4rem; line-height: 1.5;">
                            {highlighted_text}{'...' if len(text) > 300 else ''}
                        </div>
                    </div>
                    <a href="{url}" target="_blank" style="color: var(--accent-green); font-size: 0.75rem;
                       padding: 0.2rem 0.4rem; background: rgba(26,115,232,0.1); border-radius: 4px;
                       text-decoration: none; white-space: nowrap;">View →</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Export results
        if not results.empty:
            csv = results.to_csv(index=False)
            st.download_button(
                "📥 Download Search Results",
                csv,
                f"fl_search_{search_query[:20]}.csv",
                "text/csv"
            )

# ============= INTERACTIVE COORDINATES MAP =============
def render_coordinates_map(data):
    st.markdown("## 📍 Interactive Coordinates Map")
    st.markdown("*Explore geographic locations mentioned in FL articles*")

    coords_df = data.get("coordinates", pd.DataFrame())

    if coords_df.empty:
        st.warning("No coordinate data loaded.")
        return

    # Try to import folium
    try:
        import folium
        from streamlit_folium import st_folium
        has_folium = True
    except ImportError:
        has_folium = False
        st.warning("Install folium for interactive maps: `pip install folium streamlit-folium`")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        coord_types = ["All"] + list(coords_df['type'].dropna().unique()) if 'type' in coords_df.columns else ["All"]
        selected_type = st.selectbox("Coordinate type", coord_types)
    with col2:
        search_loc = st.text_input("Search location", placeholder="Filter by text...")
    with col3:
        show_count = st.slider("Max markers", 10, 500, 100)

    # Filter data
    filtered = coords_df.copy()
    if selected_type != "All" and 'type' in filtered.columns:
        filtered = filtered[filtered['type'] == selected_type]
    if search_loc:
        mask = filtered.apply(lambda r: search_loc.lower() in str(r).lower(), axis=1)
        filtered = filtered[mask]

    st.markdown(f"*Showing {min(len(filtered), show_count)} of {len(filtered)} coordinates*")

    # Normalize column names (handle both lat/lon and latitude/longitude)
    if 'lat' in filtered.columns and 'latitude' not in filtered.columns:
        filtered = filtered.rename(columns={'lat': 'latitude', 'lon': 'longitude'})
    if 'title' in filtered.columns and 'article_title' not in filtered.columns:
        filtered = filtered.rename(columns={'title': 'article_title'})

    if has_folium and not filtered.empty:
        # Create map centered on average coordinates
        if 'latitude' in filtered.columns and 'longitude' in filtered.columns:
            filtered_valid = filtered.dropna(subset=['latitude', 'longitude'])
            if not filtered_valid.empty:
                center_lat = filtered_valid['latitude'].mean()
                center_lon = filtered_valid['longitude'].mean()

                # Create folium map
                m = folium.Map(
                    location=[center_lat, center_lon],
                    zoom_start=3,
                    tiles='CartoDB dark_matter' if st.session_state.get('dark_mode', False) else 'CartoDB positron'
                )

                # Add markers
                for _, row in filtered_valid.head(show_count).iterrows():
                    lat = row['latitude']
                    lon = row['longitude']
                    title = str(row.get('article_title', '') or row.get('title', 'Unknown'))[:40]
                    url = str(row.get('article_url', '') or '')
                    coord_type = str(row.get('type', 'unknown'))

                    # Color by type
                    colors = {
                        'decimal': 'blue',
                        'dms': 'green',
                        'military': 'red',
                        'iso': 'orange'
                    }
                    color = colors.get(coord_type, 'gray')

                    popup_html = f"""
                    <b>{title}</b><br>
                    <i>{coord_type}</i><br>
                    {lat:.4f}, {lon:.4f}<br>
                    <a href="{url}" target="_blank">Open article</a>
                    """

                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=8,
                        color=color,
                        fill=True,
                        fillOpacity=0.7,
                        popup=folium.Popup(popup_html, max_width=300)
                    ).add_to(m)

                # Display map
                st_folium(m, width=None, height=500)
            else:
                st.warning("No valid coordinates to display")
        else:
            st.warning("Coordinate data missing latitude/longitude columns")
    else:
        # Fallback to plotly
        st.markdown("### Map (install folium for interactive features)")
        if 'latitude' in filtered.columns and 'longitude' in filtered.columns:
            fig = px.scatter_geo(
                filtered.head(show_count),
                lat='latitude',
                lon='longitude',
                hover_name='article_title' if 'article_title' in filtered.columns else None,
                color='type' if 'type' in filtered.columns else None,
                projection='natural earth'
            )
            fig.update_layout(
                geo=dict(
                    showland=True,
                    landcolor='rgb(243, 243, 243)' if not st.session_state.get('dark_mode', False) else 'rgb(30, 40, 35)',
                    showocean=True,
                    oceancolor='rgb(204, 229, 255)' if not st.session_state.get('dark_mode', False) else 'rgb(10, 15, 13)'
                ),
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)

    # Coordinates table
    st.markdown("### 📋 Coordinates List")
    st.dataframe(
        filtered[['latitude', 'longitude', 'type', 'article_title']].head(100) if all(c in filtered.columns for c in ['latitude', 'longitude']) else filtered.head(100),
        use_container_width=True,
        height=300
    )

    # Download
    csv = filtered.to_csv(index=False)
    st.download_button("📥 Download Coordinates CSV", csv, "fl_coordinates.csv", "text/csv")

# ============= SIMILAR ARTICLES =============
def render_similar_articles(data):
    st.markdown("## 🔗 Find Similar Articles")
    st.markdown("*Discover related articles based on shared keywords and themes*")

    # Convert articles list to DataFrame if needed
    articles_raw = data.get("articles", [])
    if isinstance(articles_raw, list):
        articles_df = pd.DataFrame(articles_raw) if articles_raw else pd.DataFrame()
    else:
        articles_df = articles_raw

    keywords = data.get("keywords", {})

    if articles_df.empty:
        st.warning("No articles data loaded.")
        return

    # Input: article URL or title search
    search_mode = st.radio("Find article by:", ["Title search", "URL"], horizontal=True)

    target_article = None

    if search_mode == "Title search":
        title_search = st.text_input("Search article title", placeholder="Enter part of the title...")
        if title_search:
            matches = articles_df[articles_df['title'].str.contains(title_search, case=False, na=False)]
            if not matches.empty:
                options = matches['title'].head(10).tolist()
                selected_title = st.selectbox("Select article", options)
                target_article = matches[matches['title'] == selected_title].iloc[0]
    else:
        url_input = st.text_input("Enter article URL", placeholder="https://forgottenlanguages-full...")
        if url_input:
            matches = articles_df[articles_df['url'] == url_input]
            if not matches.empty:
                target_article = matches.iloc[0]
            else:
                st.warning("Article not found in database")

    if target_article is not None:
        # Build excerpt lookup for summaries
        excerpts_df = data.get("excerpts", pd.DataFrame())
        excerpt_lookup = {}
        if not excerpts_df.empty and 'url' in excerpts_df.columns:
            for url, group in excerpts_df.groupby('url'):
                texts = group['text'].dropna().tolist()
                if texts:
                    excerpt_lookup[url] = texts[0][:150]

        st.markdown(f"""
        <div style="background: var(--bg-tertiary); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
            <div style="font-weight: 500; color: var(--text-primary);">{target_article['title'][:70]}...</div>
            <a href="{target_article['url']}" target="_blank" style="font-size: 0.85rem;">View original →</a>
        </div>
        """, unsafe_allow_html=True)

        # Find similar articles based on shared keywords
        target_url = target_article['url']

        # Get keywords for target article
        target_keywords = set()
        for kw, urls in keywords.items():
            if target_url in urls:
                target_keywords.add(kw)

        if target_keywords:
            st.markdown(f"**Keywords:** {', '.join(list(target_keywords)[:10])}")

            # Find articles sharing keywords
            similarity_scores = defaultdict(int)
            for kw in target_keywords:
                for url in keywords.get(kw, []):
                    if url != target_url:
                        similarity_scores[url] += 1

            # Sort by similarity
            similar_urls = sorted(similarity_scores.items(), key=lambda x: -x[1])[:20]

            if similar_urls:
                st.markdown(f"### Found {len(similar_urls)} Similar Articles")

                for url, score in similar_urls:
                    article = articles_df[articles_df['url'] == url]
                    if not article.empty:
                        article = article.iloc[0]
                        title = str(article.get('title', 'Unknown'))[:70]
                        date = str(article.get('date', ''))
                        summary = excerpt_lookup.get(url, '')

                        # Find shared keywords
                        shared = []
                        for kw in target_keywords:
                            if url in keywords.get(kw, []):
                                shared.append(kw)

                        # Compact card style
                        st.markdown(f"""
                        <div style="background: var(--bg-secondary); border-left: 3px solid var(--accent-cyan);
                                    padding: 0.75rem 1rem; margin: 0.4rem 0; border-radius: 0 6px 6px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div style="flex: 1;">
                                    <a href="{url}" target="_blank" style="color: var(--text-primary); text-decoration: none;
                                       font-weight: 500; font-size: 0.9rem;">{title}</a>
                                    <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.2rem;">
                                        {date} • {score} shared: {', '.join(shared[:3])}
                                    </div>
                                    {f'<div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.3rem;">{summary}...</div>' if summary else ''}
                                </div>
                                <a href="{url}" target="_blank" style="color: var(--accent-green); font-size: 0.75rem;
                                   padding: 0.2rem 0.4rem; background: rgba(26,115,232,0.1); border-radius: 4px;
                                   text-decoration: none; white-space: nowrap;">View →</a>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No similar articles found based on shared keywords.")
        else:
            st.info("No keywords found for this article.")

# ============= BOOKMARKS =============
def render_bookmarks(data):
    st.markdown("## ⭐ Your Bookmarks")
    st.markdown("*Saved articles and excerpts for later reference*")

    bookmarks = st.session_state.bookmarks

    if not bookmarks:
        st.info("No bookmarks yet. Use the ⭐ button on articles to save them here.")
        return

    st.markdown(f"*{len(bookmarks)} bookmarked items*")

    # Clear all button
    if st.button("🗑️ Clear All Bookmarks"):
        st.session_state.bookmarks = []
        st.rerun()

    st.markdown("---")

    # Display bookmarks
    for i, bm in enumerate(bookmarks):
        title = bm.get('title', 'Unknown')[:60]
        url = bm.get('url', '')
        excerpt = bm.get('excerpt', '')[:100]

        st.markdown(f"""
        <div class="result-card">
            <div class="result-title">{title}</div>
            <div class="result-excerpt">{excerpt}...</div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            if url:
                st.markdown(f"[Open article →]({url})")
        with col2:
            if st.button("🗑️ Remove", key=f"rm_bm_{i}"):
                st.session_state.bookmarks.pop(i)
                st.rerun()

    # Export bookmarks
    st.markdown("---")
    if bookmarks:
        import json
        bookmarks_json = json.dumps(bookmarks, indent=2)
        st.download_button(
            "📥 Export Bookmarks (JSON)",
            bookmarks_json,
            "fl_bookmarks.json",
            "application/json"
        )

# ============= BIBTEX/RIS EXPORT (add to bibliography section) =============
def generate_bibtex(bib_df):
    """Generate BibTeX format from bibliography dataframe"""
    entries = []
    for i, row in bib_df.iterrows():
        author = str(row.get('author', 'Unknown')).replace('&', 'and')
        year = str(row.get('year', ''))
        title = str(row.get('title', ''))
        journal = str(row.get('journal', ''))

        # Create citation key
        author_key = author.split(',')[0].split()[0] if author else 'unknown'
        cite_key = f"{author_key}{year}_{i}"

        entry = f"""@article{{{cite_key},
    author = {{{author}}},
    title = {{{title}}},
    journal = {{{journal}}},
    year = {{{year}}},
    note = {{Cited in Forgotten Languages}}
}}"""
        entries.append(entry)

    return '\n\n'.join(entries)

def generate_ris(bib_df):
    """Generate RIS format from bibliography dataframe"""
    entries = []
    for _, row in bib_df.iterrows():
        author = str(row.get('author', ''))
        year = str(row.get('year', ''))
        title = str(row.get('title', ''))
        journal = str(row.get('journal', ''))

        entry = f"""TY  - JOUR
AU  - {author}
TI  - {title}
JO  - {journal}
PY  - {year}
N1  - Cited in Forgotten Languages
ER  -"""
        entries.append(entry)

    return '\n\n'.join(entries)

# ============= RUN =============
if __name__ == "__main__":
    main()
