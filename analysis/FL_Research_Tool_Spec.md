# FORGOTTEN LANGUAGES RESEARCH TOOL
## Architecture & Implementation Plan
### January 2026

---

## WHAT THIS TOOL SHOULD DO

### Core Capabilities:

1. **SEARCH & DISCOVERY**
   - Full-text search across all FL excerpts
   - Keyword filtering (MilOrb, PSV, DOLYN, Giselian, etc.)
   - Date range filtering
   - Category filtering (Defense, Cassini Diskus, NodeSpaces, etc.)
   - Regex support for pattern matching

2. **COORDINATE ANALYSIS**
   - Interactive map visualization
   - Distance calculations to known facilities
   - Magnetic anomaly overlay
   - Clustering analysis
   - MilOrb coordinate decoding attempts

3. **TEMPORAL CORRELATION**
   - FL post date vs real-world event matching
   - Gap analysis
   - Verification status tracking
   - Predictive pattern identification

4. **NETWORK ANALYSIS**
   - Internal FL cross-references (FL-DDMMYY format)
   - Topic clustering
   - Author/pseudonym tracking
   - Citation network

5. **EXPORT & INTEGRATION**
   - CSV/JSON/GeoJSON exports
   - API for external tools
   - Integration with mapping software
   - Report generation

---

## DATA STRUCTURE

### 1. Excerpts Database (excerpts.json)
```json
{
  "id": "unique_id",
  "url": "full_url",
  "title": "post_title",
  "date": "YYYY-MM-DD",
  "category": "Defense|Cassini Diskus|NodeSpaces|...",
  "excerpt": "English text extracted",
  "keywords": ["MilOrb", "PSV", ...],
  "internal_refs": ["FL-201217", "FL-280417"],
  "external_refs": ["academic citation"],
  "author": "Ayndryl|Direne|...",
  "verified": true|false
}
```

### 2. Coordinates Database (coordinates.json)
```json
{
  "id": "unique_id",
  "lat": 34.5678,
  "lon": -23.4567,
  "format": "decimal|dms|milorb|named",
  "raw": "original string",
  "date": "YYYY-MM-DD",
  "post_url": "source_url",
  "category": "Magnetic Anomaly|Military|...",
  "significance": "description",
  "nearest_facility": "Dugway Proving Ground",
  "facility_distance_km": 7.2,
  "magnetic_anomaly_distance_km": 1599,
  "verified": true|false
}
```

### 3. Temporal Correlations (correlations.json)
```json
{
  "id": "unique_id",
  "fl_date": "YYYY-MM-DD",
  "fl_content": "description",
  "fl_url": "source_url",
  "real_date": "YYYY-MM-DD",
  "real_event": "description",
  "gap_days": 42,
  "verification_method": "wayback|archive|news",
  "verification_url": "proof_url",
  "verified": true|false|"pending"
}
```

---

## PYTHON IMPLEMENTATION

```python
#!/usr/bin/env python3
"""
Forgotten Languages Research Tool
A comprehensive analysis toolkit for FL data
"""

import json
import csv
import re
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import argparse

# ============= DATA MODELS =============

@dataclass
class Excerpt:
    id: str
    url: str
    title: str
    date: str
    category: str
    excerpt: str
    keywords: List[str]
    internal_refs: List[str] = None
    external_refs: List[str] = None
    author: str = None
    verified: bool = False

@dataclass  
class Coordinate:
    id: str
    lat: float
    lon: float
    format: str
    raw: str
    date: str
    post_url: str
    category: str
    significance: str
    nearest_facility: str = None
    facility_distance_km: float = None
    verified: bool = False

@dataclass
class TemporalCorrelation:
    id: str
    fl_date: str
    fl_content: str
    fl_url: str
    real_date: str
    real_event: str
    gap_days: int
    verified: str  # true, false, or "pending"

# ============= CORE DATABASE =============

class FLDatabase:
    def __init__(self, data_dir: str = "./fl_data"):
        self.data_dir = Path(data_dir)
        self.excerpts: List[Excerpt] = []
        self.coordinates: List[Coordinate] = []
        self.correlations: List[TemporalCorrelation] = []
        
    def load_from_csv(self, excerpts_csv: str, coords_csv: str):
        """Load data from CSV files"""
        # Load excerpts
        with open(excerpts_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.excerpts.append(Excerpt(
                    id=str(len(self.excerpts) + 1),
                    url=row.get('URL', ''),
                    title=row.get('Title', ''),
                    date=row.get('Date', ''),
                    category=self._categorize(row.get('Title', '')),
                    excerpt=row.get('Excerpt', ''),
                    keywords=self._extract_keywords(row.get('Excerpt', ''))
                ))
        
        # Load coordinates
        with open(coords_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    self.coordinates.append(Coordinate(
                        id=str(len(self.coordinates) + 1),
                        lat=float(row.get('lat', 0)),
                        lon=float(row.get('lon', 0)),
                        format=row.get('type', 'decimal'),
                        raw=row.get('raw', ''),
                        date=row.get('date', ''),
                        post_url='',
                        category=self._categorize_coord(row.get('title', '')),
                        significance=row.get('title', '')
                    ))
                except:
                    pass
                    
    def _categorize(self, title: str) -> str:
        """Auto-categorize based on title keywords"""
        title_lower = title.lower()
        if any(k in title_lower for k in ['milorb', 'psv', 'defense', 'weapon', 'military']):
            return 'Defense'
        elif 'cassini' in title_lower or 'diskus' in title_lower:
            return 'Cassini Diskus'
        elif 'nodespace' in title_lower or 'golay' in title_lower:
            return 'NodeSpaces'
        elif any(k in title_lower for k in ['dream', 'consciousness', 'xvis']):
            return 'XViS'
        elif any(k in title_lower for k in ['giselian', 'denebian', 'probe']):
            return 'Contact'
        else:
            return 'Other'
    
    def _categorize_coord(self, title: str) -> str:
        """Auto-categorize coordinates"""
        title_lower = title.lower()
        if 'entry event' in title_lower:
            return 'Entry Event'
        elif 'sienna' in title_lower or 'akrij' in title_lower:
            return 'PSV Operation'
        else:
            return 'Location'
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract FL-specific keywords from text"""
        keywords = []
        fl_terms = [
            'MilOrb', 'PSV', 'DOLYN', 'SV17q', 'Giselian', 'Denebian',
            'XViS', 'LyAV', 'Sienna', 'Akrij', 'Presence', 'Tangent',
            'Graphium', 'NodeSpaces', 'UAP', 'USO', 'SAA', 'DENIED'
        ]
        for term in fl_terms:
            if term.lower() in text.lower():
                keywords.append(term)
        return keywords

# ============= SEARCH ENGINE =============

class FLSearch:
    def __init__(self, db: FLDatabase):
        self.db = db
        
    def search_excerpts(self, 
                       query: str = None,
                       category: str = None,
                       keywords: List[str] = None,
                       date_from: str = None,
                       date_to: str = None) -> List[Excerpt]:
        """Search excerpts with multiple filters"""
        results = self.db.excerpts
        
        if query:
            query_lower = query.lower()
            results = [e for e in results if 
                      query_lower in e.title.lower() or 
                      query_lower in e.excerpt.lower()]
        
        if category:
            results = [e for e in results if e.category == category]
            
        if keywords:
            results = [e for e in results if 
                      any(k in e.keywords for k in keywords)]
        
        return results
    
    def search_coordinates(self,
                          category: str = None,
                          near_lat: float = None,
                          near_lon: float = None,
                          radius_km: float = None) -> List[Coordinate]:
        """Search coordinates with spatial filtering"""
        results = self.db.coordinates
        
        if category:
            results = [c for c in results if c.category == category]
            
        if near_lat and near_lon and radius_km:
            results = [c for c in results if 
                      self._haversine(near_lat, near_lon, c.lat, c.lon) <= radius_km]
        
        return results
    
    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km"""
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

# ============= ANALYSIS ENGINE =============

class FLAnalyzer:
    def __init__(self, db: FLDatabase):
        self.db = db
        
    def find_internal_references(self, text: str) -> List[str]:
        """Find FL-DDMMYY format references"""
        pattern = r'FL-\d{6}'
        return re.findall(pattern, text)
    
    def analyze_coordinate_clustering(self) -> Dict:
        """Analyze coordinate clustering patterns"""
        categories = {}
        for coord in self.db.coordinates:
            cat = coord.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((coord.lat, coord.lon))
        
        return {
            'category_counts': {k: len(v) for k, v in categories.items()},
            'total_coordinates': len(self.db.coordinates)
        }
    
    def find_temporal_patterns(self) -> List[Dict]:
        """Identify potential temporal correlations"""
        # This would match FL posts to real-world events
        patterns = []
        # Implementation would cross-reference dates
        return patterns

# ============= EXPORT ENGINE =============

class FLExporter:
    def __init__(self, db: FLDatabase):
        self.db = db
        
    def to_csv(self, output_path: str, data_type: str = 'excerpts'):
        """Export to CSV"""
        if data_type == 'excerpts':
            data = [asdict(e) for e in self.db.excerpts]
        elif data_type == 'coordinates':
            data = [asdict(c) for c in self.db.coordinates]
        else:
            return
            
        if data:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
    
    def to_geojson(self, output_path: str):
        """Export coordinates as GeoJSON"""
        features = []
        for coord in self.db.coordinates:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [coord.lon, coord.lat]
                },
                "properties": {
                    "id": coord.id,
                    "date": coord.date,
                    "category": coord.category,
                    "significance": coord.significance,
                    "raw": coord.raw
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)
    
    def to_json(self, output_path: str):
        """Export full database as JSON"""
        data = {
            "excerpts": [asdict(e) for e in self.db.excerpts],
            "coordinates": [asdict(c) for c in self.db.coordinates],
            "correlations": [asdict(c) for c in self.db.correlations],
            "metadata": {
                "exported": datetime.now().isoformat(),
                "total_excerpts": len(self.db.excerpts),
                "total_coordinates": len(self.db.coordinates)
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

# ============= CLI INTERFACE =============

def main():
    parser = argparse.ArgumentParser(description='FL Research Tool')
    parser.add_argument('command', choices=['search', 'analyze', 'export', 'stats'])
    parser.add_argument('--query', '-q', help='Search query')
    parser.add_argument('--category', '-c', help='Filter by category')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--format', '-f', choices=['csv', 'json', 'geojson'], default='json')
    parser.add_argument('--excerpts-csv', default='fl_all_excerpts.csv')
    parser.add_argument('--coords-csv', default='fl_all_parsed_coordinates.csv')
    
    args = parser.parse_args()
    
    # Initialize database
    db = FLDatabase()
    db.load_from_csv(args.excerpts_csv, args.coords_csv)
    
    if args.command == 'search':
        search = FLSearch(db)
        results = search.search_excerpts(query=args.query, category=args.category)
        for r in results[:10]:  # Show first 10
            print(f"\n[{r.date}] {r.title}")
            print(f"  {r.excerpt[:200]}...")
            
    elif args.command == 'analyze':
        analyzer = FLAnalyzer(db)
        clustering = analyzer.analyze_coordinate_clustering()
        print(json.dumps(clustering, indent=2))
        
    elif args.command == 'export':
        exporter = FLExporter(db)
        output = args.output or f'fl_export.{args.format}'
        if args.format == 'csv':
            exporter.to_csv(output)
        elif args.format == 'geojson':
            exporter.to_geojson(output)
        else:
            exporter.to_json(output)
        print(f"Exported to {output}")
        
    elif args.command == 'stats':
        print(f"Excerpts: {len(db.excerpts)}")
        print(f"Coordinates: {len(db.coordinates)}")
        categories = {}
        for e in db.excerpts:
            categories[e.category] = categories.get(e.category, 0) + 1
        print(f"Categories: {categories}")

if __name__ == '__main__':
    main()
```

---

## DEPLOYMENT OPTIONS

### Option 1: Local Python Script
- Download fl_research_tool.py
- Place CSV files in same directory  
- Run: `python fl_research_tool.py search --query "MilOrb"`

### Option 2: Web Application (Streamlit)
```python
# fl_app.py
import streamlit as st
from fl_research_tool import FLDatabase, FLSearch, FLExporter

st.title("Forgotten Languages Research Tool")

# Load data
db = FLDatabase()
db.load_from_csv('fl_all_excerpts.csv', 'fl_all_parsed_coordinates.csv')
search = FLSearch(db)

# Search interface
query = st.text_input("Search FL database")
category = st.selectbox("Category", ["All", "Defense", "Cassini Diskus", "NodeSpaces"])

if query:
    results = search.search_excerpts(query=query)
    for r in results:
        st.markdown(f"**{r.title}** ({r.date})")
        st.write(r.excerpt)
        st.divider()
```

Run with: `streamlit run fl_app.py`

### Option 3: Hosted Web App
- Deploy to Vercel/Netlify with React frontend
- API backend on Railway/Render
- Database on Supabase/PlanetScale

---

## NEXT STEPS TO BUILD THIS

1. **Clean and consolidate your existing data**
   - Merge all CSVs into unified format
   - Deduplicate entries
   - Add verification flags

2. **Build the Python backend**
   - Implement the code above
   - Add more analysis functions
   - Create API endpoints

3. **Create the web interface**
   - Use the React component as starting point
   - Add interactive map (Leaflet/Mapbox)
   - Implement real-time search

4. **Add advanced features**
   - MilOrb coordinate decoding
   - Automatic Wayback verification
   - News API integration for correlations
   - Citation network visualization

---

## DATA FILES YOU NEED

From your project:
- `fl_all_excerpts.csv` - 250 rows of extracted English text
- `fl_all_parsed_coordinates.csv` - 106 decoded coordinates

Additional recommended:
- `fl_articles_master.json` - Full article metadata (URLs, dates, categories)
- `fl_correlations.json` - Temporal correlation database
- `fl_facilities.json` - Known military/strategic facility locations for matching

---

*Specification created January 2, 2026*
