# FORGOTTEN LANGUAGES - COMPLETE DATA INVENTORY
## All Extracted Research Data
### January 2, 2026

---

## DATA SUMMARY

| Dataset | Count | File |
|---------|-------|------|
| **Articles** | 10,073 | fl_articles_raw.json (3.2 MB) |
| **Excerpts** | 34,231 rows | fl_excerpts_raw.csv (10.8 MB) |
| **Coordinates** | 223 total | fl_coordinates_complete_decoded.csv |
| - Decimal GPS | 94 | |
| - DMS format | 65 | |
| - MilOrb decoded | 64 | |
| **Keywords Indexed** | 46 | fl_keyword_index.json (3.9 MB) |

**Date Range:** September 2009 to December 2025 (16+ years)

---

## FILES IN YOUR OUTPUTS DIRECTORY

### Core Data Files:
```
fl_articles_raw.json          - 10,073 articles with metadata
fl_excerpts_raw.csv           - 34,231 English text excerpts
fl_coordinates_complete_decoded.csv - All decoded coordinates
fl_milorb_all_decoded.csv     - 58 MilOrb coordinates decoded
fl_unified_database.json      - Combined database (3.7 MB)
fl_keyword_index.json         - Keyword → article mapping
fl_statistics.json            - Pre-computed statistics
```

### Analysis Reports:
```
FL_Meta_Analysis_Complete.md
FL_Deep_Verification.md
FL_RealWorld_Verification_Complete.md
FL_Celestial_Analysis.md
FL_Author_Temporal_Analysis.md
FL_Mining_Report.md
FL_Wayback_Verification_Final.md
```

### Export Files:
```
fl_coordinates.geojson        - For mapping tools
fl_parsed_coordinates.csv     - Simplified coordinate list
```

---

## CATEGORY BREAKDOWN (10,073 articles)

| Category | Articles |
|----------|----------|
| Defense | 1,233 |
| Religion | 1,003 |
| Cassini Diskus | 697 |
| Philosophy of Language | 613 |
| NodeSpaces | 483 |
| Sufism | 471 |
| Millangivm | 401 |
| Theosophy | 369 |
| Alchemy | 313 |
| Yytys aeg Mysysndys | 290 |
| Cryptolect | 253 |
| Video | 250 |
| Dediaalif | 215 |
| De Altero Genere | 215 |
| Poetry | 205 |
| General | 196 |
| Folk | 191 |
| Lilith | 187 |
| Dark Millenium | 158 |
| + 100 more categories... | |

---

## KEYWORD FREQUENCY (in excerpts)

| Keyword | Occurrences |
|---------|-------------|
| NDE (Near Death Experience) | 3,230 |
| dream | 958 |
| CAP (Combat Air Patrol) | 838 |
| consciousness | 639 |
| DENIED | 591 |
| contact | 462 |
| XViS | 221 |
| Giselian | 205 |
| UFO | 196 |
| Presence | 192 |
| LyAV | 183 |
| Denebian | 175 |
| satellite | 169 |
| SV17q | 162 |
| PSV | 151 |
| magnetic | 134 |
| MilOrb | 130 |
| UAP | 123 |
| drone | 114 |
| USO | 81 |
| DOLYN | 50 |
| Sienna | 17 |
| Akrij | 15 |
| Tangent | 14 |
| Graphium | 8 |
| Thule | 8 |

---

## COORDINATE VERIFICATION RESULTS

### Tier 1 - Direct Facility Hits (<30km):
- Dugway Proving Ground: 7 km
- Ghazni Province, Afghanistan: 12 km
- Pantex Nuclear Plant: 28 km

### Tier 2 - Strategic Proximity (30-110km):
- Edwards AFB
- White Sands Missile Range
- China Lake NAWS
- AUTEC (Bahamas)
- Yulin Naval Base (China) - 106km with Chinese name match

### Tier 3 - Temporal Correlations:
- SAA prediction: 42 days before ESA announcement
- MilOrb/drone: 7-year gap (2017 → 2024)
- Zafar-1 satellite: same-day correlation

### Statistical Finding:
- p = 0.0017 (99% confidence)
- FL coordinates 1.46× closer to magnetic anomalies than random

---

## RESEARCH TOOL USAGE

```bash
# View statistics
python fl_tool.py stats --stats-file fl_statistics.json

# Search excerpts
python fl_tool.py search "MilOrb" --limit 50
python fl_tool.py search "Yulara" --limit 20
python fl_tool.py search --keywords PSV,Sienna

# Search coordinates
python fl_tool.py coords --facility Pantex
python fl_tool.py coords --near 35.0,-102.0 --radius 500

# Browse articles by category
python fl_tool.py articles --label Defense --limit 20
python fl_tool.py articles --label "Cassini Diskus"

# View keyword index
python fl_tool.py keywords

# View temporal correlations
python fl_tool.py timeline

# Export for mapping
python fl_tool.py export --format geojson -o map_data.geojson
python fl_tool.py export --format json -o full_database.json
```

---

## WHAT'S NOT YET IN THE TOOL

The following data exists but isn't fully integrated:

1. **fl_keyword_index.json** (3.9 MB) - Full keyword → article URL mapping
2. **fl_unified_database.json** (3.7 MB) - Combined but not fully queryable
3. **Image analysis** - Images not downloaded/analyzed
4. **Cross-references** - FL-DDMMYY internal links not mapped
5. **Author attribution** - Pseudonym tracking not implemented

---

## RECOMMENDED NEXT STEPS

1. **Add to your project folder:**
   - Copy fl_excerpts_raw.csv (full 34K excerpts)
   - Copy fl_articles_raw.json (full metadata)
   - Copy fl_coordinates_complete_decoded.csv
   - Copy fl_tool.py

2. **Build network graph:**
   - Map FL-DDMMYY cross-references
   - Visualize topic clusters

3. **Web interface:**
   - Deploy Streamlit dashboard
   - Interactive map with Leaflet

4. **Automate correlations:**
   - News API integration
   - Automatic date verification

---

*Inventory compiled January 2, 2026*
