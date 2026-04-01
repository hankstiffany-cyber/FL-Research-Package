#!/usr/bin/env python3
"""
Forgotten Languages Research Tool v2.0
======================================
A comprehensive analysis toolkit for FL research data.
Now using FULL extracted dataset (34,231 excerpts, 10,073 articles, 223 coordinates)

Usage:
    python fl_tool.py search "MilOrb"
    python fl_tool.py search --keywords PSV,Sienna --limit 50
    python fl_tool.py coords --near 35.0,-102.0 --radius 500
    python fl_tool.py coords --facility Pantex
    python fl_tool.py export --format geojson
    python fl_tool.py stats
    python fl_tool.py timeline
    python fl_tool.py articles --label Defense
"""

import csv
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import argparse

# Default paths - use full extracted data
DEFAULT_EXCERPTS = 'fl_excerpts_raw.csv'
DEFAULT_COORDS = 'fl_coordinates_complete_decoded.csv'
DEFAULT_ARTICLES = 'fl_articles_raw.json'
DEFAULT_STATS = 'fl_statistics.json'
DEFAULT_KEYWORDS = 'fl_keyword_index.json'

# ============= CONFIGURATION =============

FL_KEYWORDS = [
    'MilOrb', 'PSV', 'DOLYN', 'SV17q', 'Giselian', 'Denebian', 'XViS', 
    'LyAV', 'Sienna', 'Akrij', 'Presence', 'Tangent', 'Graphium', 
    'NodeSpaces', 'UAP', 'USO', 'SAA', 'DENIED', 'Cassini', 'MASINT',
    'Corona East', 'Black Prophet', 'Queltron', 'Sol-3'
]

MAGNETIC_ANOMALIES = [
    {'name': 'South Atlantic Anomaly', 'lat': -30, 'lon': -40, 'radius': 3000},
    {'name': 'SAA African Lobe', 'lat': -25, 'lon': 15, 'radius': 1500},
    {'name': 'Kursk Magnetic Anomaly', 'lat': 51.7, 'lon': 36.2, 'radius': 300},
    {'name': 'Bangui Anomaly', 'lat': 6, 'lon': 18, 'radius': 1000},
    {'name': 'Bermuda Triangle', 'lat': 25, 'lon': -71, 'radius': 800},
]

KNOWN_FACILITIES = [
    {'name': 'Dugway Proving Ground', 'lat': 40.18, 'lon': -112.93, 'type': 'Military'},
    {'name': 'Pantex Plant', 'lat': 35.32, 'lon': -101.57, 'type': 'Nuclear'},
    {'name': 'AUTEC', 'lat': 24.75, 'lon': -77.75, 'type': 'Naval'},
    {'name': 'White Sands', 'lat': 32.38, 'lon': -106.48, 'type': 'Military'},
    {'name': 'China Lake', 'lat': 35.69, 'lon': -117.69, 'type': 'Military'},
    {'name': 'Edwards AFB', 'lat': 34.91, 'lon': -117.88, 'type': 'Military'},
    {'name': 'Thule Air Base', 'lat': 76.53, 'lon': -68.70, 'type': 'Military'},
    {'name': 'Yulin Naval Base', 'lat': 18.22, 'lon': 109.56, 'type': 'Naval'},
]

# ============= UTILITY FUNCTIONS =============

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def extract_keywords(text: str) -> List[str]:
    """Extract FL-specific keywords from text"""
    found = []
    text_lower = text.lower()
    for kw in FL_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found

def find_fl_references(text: str) -> List[str]:
    """Find FL-DDMMYY format internal references"""
    pattern = r'FL-\d{6}'
    return re.findall(pattern, text)

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats"""
    formats = ['%Y-%m-%d', '%Y-%m', '%b %d, %Y', '%b %Y', '%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return None

# ============= DATA LOADING =============

def load_excerpts(csv_path: str) -> List[Dict]:
    """Load excerpts from CSV - handles both old and new format"""
    excerpts = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # New format: url,title,type,text,position
                # Old format: URL,Title,Date,Excerpt,Word Count
                text = row.get('text') or row.get('Excerpt', '')
                title = row.get('title') or row.get('Title', '')
                url = row.get('url') or row.get('URL', '')
                
                # Extract date from URL if not in row
                date = row.get('Date', '')
                if not date and url:
                    match = re.search(r'/(\d{4})/(\d{2})/', url)
                    if match:
                        date = f"{match.group(1)}-{match.group(2)}"
                
                excerpt = {
                    'id': i + 1,
                    'url': url,
                    'title': title,
                    'date': date,
                    'excerpt': text,
                    'word_count': len(text.split()) if text else 0,
                    'keywords': extract_keywords(text),
                    'fl_refs': find_fl_references(text),
                    'position': row.get('position', 1)
                }
                excerpts.append(excerpt)
    except FileNotFoundError:
        print(f"Warning: {csv_path} not found")
    return excerpts

def load_articles(json_path: str) -> List[Dict]:
    """Load articles metadata from JSON"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {json_path} not found")
        return []

def load_statistics(json_path: str) -> Dict:
    """Load pre-computed statistics"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_keyword_index(json_path: str) -> Dict:
    """Load keyword index"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_coordinates(csv_path: str) -> List[Dict]:
    """Load coordinates from CSV"""
    coords = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    lat = float(row.get('lat', 0))
                    lon = float(row.get('lon', 0))
                    
                    # Find nearest facility
                    nearest = None
                    nearest_dist = float('inf')
                    for fac in KNOWN_FACILITIES:
                        dist = haversine(lat, lon, fac['lat'], fac['lon'])
                        if dist < nearest_dist:
                            nearest_dist = dist
                            nearest = fac['name']
                    
                    # Find nearest magnetic anomaly
                    nearest_anomaly = None
                    anomaly_dist = float('inf')
                    for anom in MAGNETIC_ANOMALIES:
                        dist = haversine(lat, lon, anom['lat'], anom['lon'])
                        if dist < anomaly_dist:
                            anomaly_dist = dist
                            nearest_anomaly = anom['name']
                    
                    coord = {
                        'id': i + 1,
                        'lat': lat,
                        'lon': lon,
                        'type': row.get('type', 'decimal'),
                        'date': row.get('date', ''),
                        'title': row.get('title', ''),
                        'raw': row.get('raw', ''),
                        'nearest_facility': nearest,
                        'facility_distance_km': round(nearest_dist, 1),
                        'nearest_anomaly': nearest_anomaly,
                        'anomaly_distance_km': round(anomaly_dist, 1)
                    }
                    coords.append(coord)
                except (ValueError, TypeError):
                    continue
    except FileNotFoundError:
        print(f"Warning: {csv_path} not found")
    return coords

# ============= SEARCH FUNCTIONS =============

def search_excerpts(excerpts: List[Dict], 
                   query: str = None,
                   keywords: List[str] = None,
                   min_words: int = None) -> List[Dict]:
    """Search excerpts with filters"""
    results = excerpts
    
    if query:
        q = query.lower()
        results = [e for e in results if 
                  q in e['title'].lower() or 
                  q in e['excerpt'].lower()]
    
    if keywords:
        results = [e for e in results if 
                  any(k in e['keywords'] for k in keywords)]
    
    if min_words:
        results = [e for e in results if e['word_count'] >= min_words]
    
    return results

def search_coordinates(coords: List[Dict],
                      near: Tuple[float, float] = None,
                      radius_km: float = None,
                      facility: str = None) -> List[Dict]:
    """Search coordinates with spatial filters"""
    results = coords
    
    if near and radius_km:
        lat, lon = near
        results = [c for c in results if 
                  haversine(lat, lon, c['lat'], c['lon']) <= radius_km]
    
    if facility:
        f = facility.lower()
        results = [c for c in results if 
                  f in c['nearest_facility'].lower()]
    
    return results

# ============= ANALYSIS FUNCTIONS =============

def analyze_keywords(excerpts: List[Dict]) -> Dict[str, int]:
    """Count keyword frequencies"""
    counts = defaultdict(int)
    for e in excerpts:
        for kw in e['keywords']:
            counts[kw] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))

def analyze_clustering(coords: List[Dict]) -> Dict:
    """Analyze coordinate clustering"""
    # Count by nearest facility
    by_facility = defaultdict(list)
    for c in coords:
        by_facility[c['nearest_facility']].append(c)
    
    # Find close pairs
    close_pairs = []
    for i, c1 in enumerate(coords):
        for c2 in coords[i+1:]:
            dist = haversine(c1['lat'], c1['lon'], c2['lat'], c2['lon'])
            if dist < 50:  # Within 50km
                close_pairs.append({
                    'coord1': c1['title'],
                    'coord2': c2['title'],
                    'distance_km': round(dist, 1)
                })
    
    return {
        'total': len(coords),
        'by_facility': {k: len(v) for k, v in by_facility.items()},
        'close_pairs': close_pairs[:10]  # Top 10
    }

def calculate_statistics(excerpts: List[Dict], coords: List[Dict]) -> Dict:
    """Calculate overall statistics"""
    # Keyword analysis
    keywords = analyze_keywords(excerpts)
    
    # Coordinate analysis
    avg_facility_dist = sum(c['facility_distance_km'] for c in coords) / len(coords) if coords else 0
    avg_anomaly_dist = sum(c['anomaly_distance_km'] for c in coords) / len(coords) if coords else 0
    
    # Within anomaly zones
    in_anomaly = sum(1 for c in coords if c['anomaly_distance_km'] < 1000)
    
    # Date range
    dates = [parse_date(e['date']) for e in excerpts if parse_date(e['date'])]
    
    return {
        'total_excerpts': len(excerpts),
        'total_coordinates': len(coords),
        'total_words': sum(e['word_count'] for e in excerpts),
        'top_keywords': dict(list(keywords.items())[:10]),
        'avg_facility_distance_km': round(avg_facility_dist, 1),
        'avg_anomaly_distance_km': round(avg_anomaly_dist, 1),
        'coords_near_anomaly': in_anomaly,
        'anomaly_percentage': round(100 * in_anomaly / len(coords), 1) if coords else 0,
        'date_range': {
            'earliest': min(dates).strftime('%Y-%m-%d') if dates else None,
            'latest': max(dates).strftime('%Y-%m-%d') if dates else None
        }
    }

# ============= EXPORT FUNCTIONS =============

def export_geojson(coords: List[Dict], output_path: str):
    """Export coordinates as GeoJSON"""
    features = []
    for c in coords:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [c['lon'], c['lat']]
            },
            "properties": {
                "id": c['id'],
                "date": c['date'],
                "title": c['title'],
                "nearest_facility": c['nearest_facility'],
                "facility_distance_km": c['facility_distance_km'],
                "nearest_anomaly": c['nearest_anomaly'],
                "anomaly_distance_km": c['anomaly_distance_km']
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    print(f"Exported {len(features)} coordinates to {output_path}")

def export_json(excerpts: List[Dict], coords: List[Dict], output_path: str):
    """Export all data as JSON"""
    data = {
        "metadata": {
            "exported": datetime.now().isoformat(),
            "tool_version": "1.0",
            "total_excerpts": len(excerpts),
            "total_coordinates": len(coords)
        },
        "excerpts": excerpts,
        "coordinates": coords,
        "known_facilities": KNOWN_FACILITIES,
        "magnetic_anomalies": MAGNETIC_ANOMALIES
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Exported full database to {output_path}")

def export_csv(data: List[Dict], output_path: str):
    """Export data as CSV"""
    if not data:
        print("No data to export")
        return
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"Exported {len(data)} rows to {output_path}")

# ============= TIMELINE ANALYSIS =============

TEMPORAL_CORRELATIONS = [
    {
        'fl_date': '2017-12',
        'fl_content': 'MilOrb autonomous drones, swarm-capable, mimics UAP, resists directed energy',
        'real_date': '2024-11-13',
        'real_event': 'NJ drone sightings begin (same day Anduril wins Replicator contract)',
        'gap_days': 2539,
        'verified': True,
        'verification': '4plebs archive October 2019 confirms post existed'
    },
    {
        'fl_date': '2025-09-02',
        'fl_content': 'SAA coordinate 34°50\'S 23°55\'W posted',
        'real_date': '2025-10-14',
        'real_event': 'ESA announces SAA splitting into two lobes',
        'gap_days': 42,
        'verified': 'pending',
        'verification': 'Requires Wayback Machine manual verification'
    },
    {
        'fl_date': '2024-12',
        'fl_content': 'New Jersey kinetic strike test reference',
        'real_date': '2024-12',
        'real_event': 'Nordic drone crisis (Copenhagen, Oslo, Munich airports)',
        'gap_days': 0,
        'verified': True,
        'verification': 'Concurrent events'
    },
    {
        'fl_date': '2020-02-09',
        'fl_content': 'PSV Presence positioned at DENIED orbit',
        'real_date': '2020-02-09',
        'real_event': 'Zafar-1 satellite failure at 15:57:25 UT',
        'gap_days': 0,
        'verified': True,
        'verification': 'Same day correlation'
    }
]

def show_timeline():
    """Display temporal correlations"""
    print("\n" + "="*70)
    print("TEMPORAL CORRELATION ANALYSIS")
    print("="*70)
    
    for corr in TEMPORAL_CORRELATIONS:
        status = "✓ VERIFIED" if corr['verified'] == True else "⏳ PENDING"
        print(f"\n[{status}]")
        print(f"FL Date:    {corr['fl_date']}")
        print(f"FL Content: {corr['fl_content'][:60]}...")
        print(f"Real Date:  {corr['real_date']}")
        print(f"Real Event: {corr['real_event']}")
        print(f"Gap:        {corr['gap_days']} days")
        print(f"Evidence:   {corr['verification']}")
    
    print("\n" + "-"*70)
    verified = sum(1 for c in TEMPORAL_CORRELATIONS if c['verified'] == True)
    print(f"Total correlations: {len(TEMPORAL_CORRELATIONS)}")
    print(f"Verified: {verified}")
    print(f"Pending: {len(TEMPORAL_CORRELATIONS) - verified}")

# ============= CLI INTERFACE =============

def main():
    parser = argparse.ArgumentParser(
        description='Forgotten Languages Research Tool v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fl_tool.py search "MilOrb"
  python fl_tool.py search --keywords PSV,Sienna --limit 50
  python fl_tool.py coords --near 35.0,-102.0 --radius 500
  python fl_tool.py coords --facility Pantex
  python fl_tool.py articles --label Defense --limit 20
  python fl_tool.py export --format geojson -o fl_coords.geojson
  python fl_tool.py stats
  python fl_tool.py timeline
  
Full dataset: 10,073 articles, 34,231 excerpts, 223 coordinates
        """
    )
    
    parser.add_argument('command', 
                       choices=['search', 'coords', 'articles', 'export', 'stats', 'timeline', 'keywords'],
                       help='Command to execute')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--keywords', '-k', help='Comma-separated keywords')
    parser.add_argument('--near', help='Lat,lon for proximity search')
    parser.add_argument('--radius', type=float, default=100, help='Radius in km')
    parser.add_argument('--facility', help='Filter by nearest facility')
    parser.add_argument('--label', help='Filter articles by label/category')
    parser.add_argument('--format', '-f', choices=['json', 'geojson', 'csv'], default='json')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--excerpts', default=DEFAULT_EXCERPTS, help='Excerpts CSV path')
    parser.add_argument('--coordinates', default=DEFAULT_COORDS, help='Coordinates CSV path')
    parser.add_argument('--articles-file', default=DEFAULT_ARTICLES, help='Articles JSON path')
    parser.add_argument('--stats-file', default=DEFAULT_STATS, help='Statistics JSON path')
    parser.add_argument('--limit', '-n', type=int, default=20, help='Limit results')
    
    args = parser.parse_args()
    
    # Load data
    excerpts = load_excerpts(args.excerpts)
    coords = load_coordinates(args.coordinates)
    
    print(f"Loaded: {len(excerpts)} excerpts, {len(coords)} coordinates")
    
    # Execute command
    if args.command == 'search':
        keywords = args.keywords.split(',') if args.keywords else None
        results = search_excerpts(excerpts, query=args.query, keywords=keywords)
        
        print(f"\nFound {len(results)} results\n")
        for r in results[:args.limit]:
            print(f"[{r['date']}] {r['title']}")
            print(f"  Keywords: {', '.join(r['keywords']) or 'none'}")
            excerpt = r['excerpt'][:200] + "..." if len(r['excerpt']) > 200 else r['excerpt']
            print(f"  {excerpt}")
            print()
    
    elif args.command == 'coords':
        near = None
        if args.near:
            lat, lon = map(float, args.near.split(','))
            near = (lat, lon)
        
        results = search_coordinates(coords, near=near, radius_km=args.radius, facility=args.facility)
        
        print(f"\nFound {len(results)} coordinates\n")
        for c in results[:args.limit]:
            print(f"[{c['date']}] {c['lat']:.4f}, {c['lon']:.4f}")
            print(f"  {c['title']}")
            print(f"  Nearest: {c['nearest_facility']} ({c['facility_distance_km']} km)")
            print(f"  Anomaly: {c['nearest_anomaly']} ({c['anomaly_distance_km']} km)")
            print()
    
    elif args.command == 'articles':
        articles = load_articles(args.articles_file)
        if args.label:
            articles = [a for a in articles if args.label.lower() in str(a.get('labels', [])).lower()]
        if args.query:
            q = args.query.lower()
            articles = [a for a in articles if q in a.get('title', '').lower()]
        
        print(f"\nFound {len(articles)} articles\n")
        for a in articles[:args.limit]:
            print(f"[{a.get('date', 'unknown')}] {a.get('title', 'Untitled')}")
            print(f"  Labels: {', '.join(a.get('labels', []))}")
            print(f"  URL: {a.get('url', '')}")
            print()
    
    elif args.command == 'keywords':
        kw_index = load_keyword_index(args.stats_file.replace('statistics', 'keyword_index'))
        stats = load_statistics(args.stats_file)
        
        print("\n" + "="*50)
        print("KEYWORD INDEX")
        print("="*50)
        if 'keyword_counts' in stats:
            for kw, count in sorted(stats['keyword_counts'].items(), key=lambda x: -x[1]):
                print(f"  {kw}: {count}")
        else:
            for kw in sorted(kw_index.keys()):
                print(f"  {kw}: {len(kw_index[kw])} articles")
    
    elif args.command == 'export':
        output = args.output or f'fl_export.{args.format}'
        
        if args.format == 'geojson':
            export_geojson(coords, output)
        elif args.format == 'json':
            export_json(excerpts, coords, output)
        elif args.format == 'csv':
            export_csv(coords, output)
    
    elif args.command == 'stats':
        # Try to load pre-computed stats first
        stats = load_statistics(args.stats_file)
        
        if stats:
            print("\n" + "="*50)
            print("FORGOTTEN LANGUAGES DATABASE STATISTICS")
            print("="*50)
            print(f"\nArticles:     {stats.get('total_articles', 'N/A')}")
            print(f"Excerpts:     {stats.get('total_excerpts', 'N/A')}")
            print(f"Coordinates:  {stats.get('coordinates', {}).get('total', 'N/A')}")
            print(f"  - Decimal GPS: {stats.get('coordinates', {}).get('decimal_gps', 'N/A')}")
            print(f"  - DMS format:  {stats.get('coordinates', {}).get('dms', 'N/A')}")
            print(f"  - MilOrb encoded: {stats.get('coordinates', {}).get('milorb_encoded', 'N/A')}")
            print(f"\nDate range:   {stats.get('date_range', {}).get('start', 'N/A')} to {stats.get('date_range', {}).get('end', 'N/A')}")
            print(f"\nTop categories:")
            for label, count in list(stats.get('top_labels', {}).items())[:15]:
                print(f"  {label}: {count}")
            print(f"\nTop keywords:")
            for kw, count in sorted(stats.get('keyword_counts', {}).items(), key=lambda x: -x[1])[:15]:
                print(f"  {kw}: {count}")
        else:
            # Fall back to computing stats
            stats = calculate_statistics(excerpts, coords)
            print("\n" + "="*50)
            print("FORGOTTEN LANGUAGES DATABASE STATISTICS")
            print("="*50)
            print(f"\nExcerpts:     {stats['total_excerpts']}")
            print(f"Coordinates:  {stats['total_coordinates']}")
            print(f"Total words:  {stats['total_words']}")
    
    elif args.command == 'timeline':
        show_timeline()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
