# FL RESEARCH WEB APP
## Setup & Installation Guide

---

## QUICK START (Windows)

1. **Make sure you have Python 3.8+ installed**
   - Download from: https://python.org
   - During install, check "Add Python to PATH"

2. **Open Command Prompt in your FL_Research_Package folder**
   ```
   cd C:\FL_Research\fl_extractor\FL_Research_Package
   ```

3. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Run the app**
   ```
   streamlit run fl_app.py
   ```
   
   Or just double-click: `run_app.bat`

5. **Open in browser**
   - The app will automatically open at: http://localhost:8501

---

## FOLDER STRUCTURE

Your folder should look like this:
```
FL_Research_Package/
├── data/
│   ├── fl_articles_raw.json      (10,073 articles)
│   ├── fl_excerpts_raw.csv       (34,231 excerpts)
│   ├── fl_coordinates_complete_decoded.csv
│   ├── fl_keyword_index.json
│   ├── fl_statistics.json
│   └── fl_coordinates.geojson
├── analysis/
│   └── (18 research reports)
├── tools/
│   └── fl_tool.py
├── fl_app.py                     ← Main web app
├── requirements.txt
├── run_app.bat                   ← Double-click to run
└── README.md
```

---

## FEATURES

### 🏠 Dashboard
- Overview statistics
- Category distribution charts
- Keyword frequency analysis
- Key research findings

### 🔍 Search Excerpts
- Full-text search across 34,231 excerpts
- Quick keyword filters (MilOrb, PSV, Giselian, etc.)
- Clickable links to original FL posts

### 📍 Coordinates
- Interactive world map
- Filter by coordinate type
- Distance calculations to known facilities
- Export filtered results

### 📊 Analytics
- Keyword treemap visualization
- Category pie charts
- Statistical breakdowns

### ⏱️ Timeline
- Temporal correlation analysis
- Verified vs pending predictions
- Evidence documentation

### 📚 Articles
- Browse all 10,073 articles
- Filter by category/label
- Search by title

---

## TROUBLESHOOTING

### "streamlit is not recognized"
```
pip install streamlit
```

### "No module named pandas"
```
pip install pandas plotly
```

### "Data files not found"
Make sure the `data/` folder contains:
- fl_statistics.json
- fl_articles_raw.json
- fl_excerpts_raw.csv
- fl_coordinates_complete_decoded.csv

### App won't start
Try:
```
python -m streamlit run fl_app.py
```

---

## COMMAND LINE TOOL

You can also use the command-line tool:

```bash
# Statistics
python tools/fl_tool.py stats --stats-file data/fl_statistics.json

# Search
python tools/fl_tool.py search "MilOrb" --excerpts data/fl_excerpts_raw.csv

# Coordinates
python tools/fl_tool.py coords --facility Pantex --coordinates data/fl_coordinates_complete_decoded.csv

# Articles
python tools/fl_tool.py articles --label Defense --articles-file data/fl_articles_raw.json
```

---

## SUPPORT

Data source: forgottenlanguages-full.forgottenlanguages.org
Database: 10,073 articles, 34,231 excerpts, 223 coordinates
Date range: September 2009 - December 2025
