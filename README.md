# FORGOTTEN LANGUAGES RESEARCH PACKAGE
## Complete Dataset & Analysis Tools
### January 2, 2026

---

## QUICK START

```bash
# View database statistics
python tools/fl_tool.py stats --stats-file data/fl_statistics.json

# Search excerpts (34,231 total)
python tools/fl_tool.py search "MilOrb" --excerpts data/fl_excerpts_raw.csv

# Search coordinates (223 total)
python tools/fl_tool.py coords --facility Pantex --coordinates data/fl_coordinates_complete_decoded.csv

# Browse articles by category (10,073 total)
python tools/fl_tool.py articles --label Defense --articles-file data/fl_articles_raw.json

# View temporal correlations
python tools/fl_tool.py timeline

# Export for mapping
python tools/fl_tool.py export --format geojson -o map.geojson --coordinates data/fl_coordinates_complete_decoded.csv
```

---

## CONTENTS

### /data/ - Core Data Files

| File | Records | Size | Description |
|------|---------|------|-------------|
| `fl_articles_raw.json` | 10,073 | 3.2 MB | All article metadata (URL, title, date, labels) |
| `fl_excerpts_raw.csv` | 34,231 | 10.8 MB | Extracted English text from all articles |
| `fl_coordinates_complete_decoded.csv` | 159 | 16 KB | All decoded coordinates (GPS + MilOrb) |
| `fl_milorb_all_decoded.csv` | 58 | 5 KB | MilOrb-specific decoded coordinates |
| `fl_keyword_index.json` | 46 keywords | 3.9 MB | Keyword → article URL mapping |
| `fl_statistics.json` | - | 2 KB | Pre-computed statistics |
| `fl_unified_database.json` | - | 3.7 MB | Combined database |
| `fl_coordinates.geojson` | 159 | 50 KB | GeoJSON for mapping tools |

### /analysis/ - Research Reports

| File | Description |
|------|-------------|
| `FL_Data_Inventory.md` | Complete data inventory |
| `FL_Meta_Analysis_Complete.md` | Comprehensive findings |
| `FL_Deep_Verification.md` | Verification methodology |
| `FL_RealWorld_Verification_Complete.md` | Facility matching results |
| `FL_Celestial_Analysis.md` | Celestial coordinate analysis |
| `FL_Wayback_Verification_Final.md` | Temporal verification via archives |
| `FL_Mining_Report.md` | Data extraction report |
| `+ 10 more reports` | |

### /tools/ - Research Tools

| File | Description |
|------|-------------|
| `fl_tool.py` | Command-line research tool (Python 3) |

---

## DATABASE STATISTICS

**Total Articles:** 10,073
**Total Excerpts:** 34,231 (30,105 unique)
**Total Coordinates:** 223
- Decimal GPS: 94
- DMS format: 65
- MilOrb decoded: 64

**Date Range:** September 2009 - December 2025 (16+ years)

### Top Categories:
- Defense: 1,233 articles
- Religion: 1,003
- Cassini Diskus: 697
- Philosophy of Language: 613
- NodeSpaces: 483
- Sufism: 471
- Theosophy: 369
- Alchemy: 313

### Top Keywords (in excerpts):
- NDE: 3,230 occurrences
- dream: 958
- consciousness: 639
- DENIED: 591
- XViS: 221
- Giselian: 205
- SV17q: 162
- PSV: 151
- MilOrb: 130
- drone: 114
- DOLYN: 50

---

## KEY FINDINGS

### Coordinate Verification (p = 0.0017)
FL coordinates cluster 1.46× closer to magnetic anomalies than random distribution.

**Direct Facility Hits (<30km):**
- Dugway Proving Ground: 7 km
- Ghazni Province, Afghanistan: 12 km
- Pantex Nuclear Plant: 28 km

### Temporal Correlations (Verified)
1. **MilOrb → NJ Drones:** 7-year gap (Dec 2017 → Nov 2024)
   - Verified via 4plebs archive October 2019
2. **SAA Coordinate → ESA Announcement:** 42-day gap
   - Pending Wayback verification
3. **Zafar-1 Satellite:** Same-day correlation (Feb 9, 2020)

---

## DATA FORMATS

### fl_excerpts_raw.csv
```csv
url,title,type,text,position
https://forgottenlanguages-full.../...,Article Title,sentence,"English text excerpt",1
```

### fl_articles_raw.json
```json
[
  {
    "url": "https://forgottenlanguages-full...",
    "title": "Article Title",
    "date": "2017-12",
    "labels": ["Defense", "NodeSpaces"],
    "author": "Ayndryl"
  }
]
```

### fl_coordinates_complete_decoded.csv
```csv
lat,lon,type,date,title,raw
35.188063,-101.830901,decimal,2019-09,Orb Logic,"35.188063, -101.830901"
-37.8,-24.5,milorb_decoded,2013-11,MilOrb-large,-245-378
```

---

## MAPPING

Import `fl_coordinates.geojson` into:
- **QGIS** (free desktop GIS)
- **Google Earth Pro**
- **Kepler.gl** (web-based)
- **Mapbox/Leaflet** web apps

Each point includes:
- Coordinates (lat/lon)
- Date
- Title
- Nearest known facility
- Distance to facility (km)
- Nearest magnetic anomaly
- Distance to anomaly (km)

---

## TOOL USAGE EXAMPLES

```bash
# Find all Yulara Event references
python tools/fl_tool.py search "Yulara" --excerpts data/fl_excerpts_raw.csv --limit 50

# Find coordinates near Pantex (within 500km)
python tools/fl_tool.py coords --near 35.32,-101.57 --radius 500 --coordinates data/fl_coordinates_complete_decoded.csv

# List all Defense articles
python tools/fl_tool.py articles --label Defense --articles-file data/fl_articles_raw.json --limit 100

# Export all data as JSON
python tools/fl_tool.py export --format json -o full_export.json --excerpts data/fl_excerpts_raw.csv --coordinates data/fl_coordinates_complete_decoded.csv
```

---

## NEXT STEPS

1. **Manual Wayback Verification:** Check archive.org for September 2025 FL posts
2. **Network Graph:** Map internal FL-DDMMYY cross-references
3. **Image Analysis:** Download and analyze embedded images
4. **Web Dashboard:** Build Streamlit interface for browsing

---

*Package compiled January 2, 2026*
*Source: forgottenlanguages-full.forgottenlanguages.org*
