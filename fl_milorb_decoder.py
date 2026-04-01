#!/usr/bin/env python3
"""
FL MilOrb Coordinate Decoder
=============================
Applies three validated decoding formulas to MilOrb/MilDSP coordinate codes
found in FL articles. Also detects celestial coordinates.

Formulas (independently verified):
  MilOrb-Small (|v1| <= 90):  lat = 21 + v1,  lon = v2 / 4
  MilOrb-Large (|v1| > 90):   lat = v2 / 10,  lon = v1 / 10
  MilDSP:                     lat = -0.0197*v1 + 37.61,  lon = 1.1247*v2 - 93.96
  Celestial (MilDSP fallback): RA = v1 as HHMM,  Dec = v2 / 10

Usage:
  python fl_milorb_decoder.py --scan              # Scan corpus for new MilOrb patterns
  python fl_milorb_decoder.py --decode "+017+105"  # Decode a single code
  python fl_milorb_decoder.py --report             # Generate full report
"""

import sqlite3
import re
import csv
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = Path("fl_enhanced.db")
EXISTING_MILORB_CSV = Path("data/fl_milorb_all_decoded.csv")
EXISTING_COORDS_CSV = Path("data/fl_coordinates_complete_decoded.csv")
OUTPUT_DIR = Path("data")

# ============================================================================
# VALIDATED DECODING FORMULAS
# ============================================================================

def decode_milorb_small(v1, v2):
    """
    MilOrb-Small: |v1| <= 90
    Verified 23/25 (92%) — confirmed via Yulin Naval Base Chinese title match
    """
    lat = 21 + v1
    lon = v2 / 4
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon, "MilOrb-small"
    return None


def decode_milorb_large(v1, v2):
    """
    MilOrb-Large: |v1| > 90
    Verified 30/30 (100%) — confirmed via Mauritania GPS cross-reference
    Key insight: v1 encodes LONGITUDE, v2 encodes LATITUDE (reversed)
    """
    lat = v2 / 10
    lon = v1 / 10
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon, "MilOrb-large"
    return None


def decode_mildsp(v1, v2):
    """
    MilDSP (Military Deep Space Platform)
    Verified 5/9 (56%) for Earth coords — confirmed via Texas Panhandle, Turkmenistan
    Falls back to celestial interpretation when lon is out of range
    """
    lat = -0.0197 * v1 + 37.61
    lon = 1.1247 * v2 - 93.96
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon, "MilDSP"
    return None


def decode_celestial(v1, v2):
    """
    Celestial coordinates — MilDSP codes where Earth lon is out of range
    Verified via Andromeda Galaxy proximity (9 deg separation)
    RA = v1 parsed as HHMM, Dec = v2 / 10
    """
    # Parse v1 as HHMM format
    abs_v1 = abs(v1)
    if abs_v1 < 100:
        ra_hours = 0
        ra_minutes = abs_v1
    else:
        ra_hours = abs_v1 // 100
        ra_minutes = abs_v1 % 100

    if ra_hours > 24 or ra_minutes > 59:
        return None

    ra_decimal = ra_hours + ra_minutes / 60.0
    dec = v2 / 10

    if -90 <= dec <= 90:
        return ra_decimal, dec, "Celestial"
    return None


def classify_and_decode(code_str, source_context=""):
    """
    Parse a MilOrb code string and apply the correct formula.

    Returns dict with keys: code, v1, v2, lat, lon, method, is_celestial
    or None if unparseable.

    Decision tree (from validated research):
      1. If source says "MilDSP": try MilDSP Earth first, then celestial
      2. If |v1| <= 90: MilOrb-small
      3. If |v1| > 90: MilOrb-large
    """
    v1, v2 = parse_milorb_code(code_str)
    if v1 is None:
        return None

    result = {
        "code": code_str.strip(),
        "v1": v1,
        "v2": v2,
        "is_celestial": False,
    }

    is_mildsp_tagged = bool(re.search(r'MilDSP', source_context, re.IGNORECASE))

    # If explicitly tagged MilDSP, use that formula (or fall back to celestial)
    if is_mildsp_tagged:
        mildsp = decode_mildsp(v1, v2)
        if mildsp:
            result["lat"], result["lon"], result["method"] = mildsp
            return result
        # MilDSP with out-of-range lon -> celestial
        celestial = decode_celestial(v1, v2)
        if celestial:
            result["lat"], result["lon"], result["method"] = celestial
            result["is_celestial"] = True
            return result
        return None

    # Standard classification by v1 magnitude
    mildsp = decode_mildsp(v1, v2)

    if abs(v1) <= 90:
        # Primary: MilOrb-small
        decoded = decode_milorb_small(v1, v2)
        if decoded:
            result["lat"], result["lon"], result["method"] = decoded
            return result
    else:
        # Primary: MilOrb-large
        decoded = decode_milorb_large(v1, v2)
        if decoded:
            result["lat"], result["lon"], result["method"] = decoded
            return result

    # Fallback: MilDSP Earth
    if mildsp:
        result["lat"], result["lon"], result["method"] = mildsp
        return result

    # Last resort: celestial
    celestial = decode_celestial(v1, v2)
    if celestial:
        result["lat"], result["lon"], result["method"] = celestial
        result["is_celestial"] = True
        return result

    return None


# ============================================================================
# PATTERN EXTRACTION
# ============================================================================

# MilOrb code format: +NNN+NNN, -NNN-NNN, +NNN-NNN, etc.
MILORB_PATTERN = re.compile(r'([+-]\d{2,3})([+-]\d{2,3})')

# Broader pattern that catches codes mentioned in titles/text
MILORB_TITLE_PATTERN = re.compile(
    r'(?:MilOrb|MilDSP|MilOrb-?\w*)\s*[:\-]?\s*([+-]\d{2,3}[+-]\d{2,3})',
    re.IGNORECASE
)

# Cassini Diskus coordinate format (standalone in text)
CASSINI_COORD_PATTERN = re.compile(
    r'(?<![.\d])([+-]\d{2,3})([+-]\d{2,3})(?![.\d])'
)


def parse_milorb_code(code_str):
    """Parse a MilOrb code string like '+017+105' into (v1, v2) integers."""
    code_str = code_str.strip()
    match = MILORB_PATTERN.search(code_str)
    if not match:
        return None, None
    try:
        v1 = int(match.group(1))
        v2 = int(match.group(2))
        return v1, v2
    except ValueError:
        return None, None


def is_likely_false_positive(code_str, context=""):
    """
    Filter out patterns that match MilOrb format but are actually
    dates, page numbers, bibliography references, or identifiers.
    """
    v1, v2 = parse_milorb_code(code_str)
    if v1 is None:
        return True

    # Small negative values that look like date fragments (-11-03 = Nov 3)
    if abs(v1) <= 31 and abs(v2) <= 31 and v1 < 0 and v2 < 0:
        # Exception: if the context explicitly says MilOrb/MilDSP
        if not re.search(r'MilOrb|MilDSP|Cassini Diskus', context, re.IGNORECASE):
            return True

    # Check if code is embedded in a larger identifier (DASYS-2075-05-25, MeKG-6-30-15, FM-34-67)
    # These produce codes like -05-25, -30-15, -34-67
    surrounding_pattern = re.compile(
        r'[A-Za-z0-9]' + re.escape(code_str) + r'|'
        + re.escape(code_str) + r'[A-Za-z/]'
    )
    if surrounding_pattern.search(context):
        # It's embedded in a larger token — likely not a standalone MilOrb code
        if not re.search(r'MilOrb|MilDSP', context, re.IGNORECASE):
            return True

    # Very small codes (2-digit both) without MilOrb context are usually noise
    if abs(v1) < 20 and abs(v2) < 20:
        if not re.search(r'MilOrb|MilDSP|Cassini Diskus|\+\d{2,3}[+-]\d{2,3}', context, re.IGNORECASE):
            return True

    return False


def extract_milorb_codes(text):
    """
    Find all MilOrb-format codes in text.
    Returns list of (code_string, context_snippet) tuples.
    Filters out likely false positives (dates, page numbers, etc.)
    """
    codes = set()

    for match in MILORB_PATTERN.finditer(text):
        code = match.group(0)
        v1, v2 = int(match.group(1)), int(match.group(2))

        if abs(v1) > 999 or abs(v2) > 999:
            continue

        # Get surrounding context for false-positive filtering
        start = max(0, match.start() - 40)
        end = min(len(text), match.end() + 40)
        context = text[start:end]

        if not is_likely_false_positive(code, context):
            codes.add(code)

    return sorted(codes)


# ============================================================================
# GEOGRAPHIC UTILITIES
# ============================================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two points."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def classify_region(lat, lon):
    """Classify a coordinate into a geographic region."""
    if lat > 66:
        return "Arctic"
    if lat < -60:
        return "Antarctic"
    if 30 <= lat <= 60 and 20 <= lon <= 90:
        return "Central Asia"
    if 15 <= lat <= 45 and -130 <= lon <= -65:
        return "North America"
    if -10 <= lat <= 35 and -20 <= lon <= 55:
        return "Africa/Middle East"
    if -40 <= lat <= -10 and 10 <= lon <= 65:
        return "Southern Africa"
    if 20 <= lat <= 55 and 90 <= lon <= 145:
        return "East Asia"
    if -15 <= lat <= 15 and -80 <= lon <= -35:
        return "South America"
    if 35 <= lat <= 70 and -10 <= lon <= 40:
        return "Europe"
    return "Ocean/Other"


KNOWN_FACILITIES = [
    ("Dugway Proving Ground", 40.17, -112.94),
    ("Pantex Plant", 35.32, -101.57),
    ("White Sands", 32.38, -106.48),
    ("Edwards AFB", 34.91, -117.88),
    ("China Lake NAWS", 35.69, -117.69),
    ("Yulin Naval Base", 18.22, 109.56),
    ("Ghazni", 33.55, 68.42),
    ("Dushanbe", 38.56, 68.77),
    ("Mecca", 21.43, 39.83),
]

SAA_CENTER = (-30.0, -40.0)  # South Atlantic Anomaly approximate center

MAGNETIC_ANOMALIES = [
    ("South Atlantic Anomaly", -30.0, -40.0),
    ("SAA African Lobe", -25.0, 18.0),
    ("Bangui Anomaly", 5.0, 18.0),
    ("Kursk Magnetic Anomaly", 51.7, 37.5),
    ("Bermuda Triangle", 25.0, -71.0),
]


def find_nearest_facility(lat, lon):
    """Find nearest known facility and distance."""
    best = None
    best_dist = float("inf")
    for name, flat, flon in KNOWN_FACILITIES:
        d = haversine_km(lat, lon, flat, flon)
        if d < best_dist:
            best_dist = d
            best = name
    return best, best_dist


def find_nearest_anomaly(lat, lon):
    """Find nearest magnetic anomaly and distance."""
    best = None
    best_dist = float("inf")
    for name, alat, alon in MAGNETIC_ANOMALIES:
        d = haversine_km(lat, lon, alat, alon)
        if d < best_dist:
            best_dist = d
            best = name
    return best, best_dist


# ============================================================================
# DATABASE SCANNING
# ============================================================================

def load_existing_codes():
    """Load already-decoded MilOrb codes from CSV."""
    codes = set()
    if EXISTING_MILORB_CSV.exists():
        with open(EXISTING_MILORB_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                codes.add(row["code"].strip())
    return codes


def scan_corpus():
    """
    Scan all articles in fl_enhanced.db for MilOrb patterns.
    Returns list of dicts: {code, article_id, url, title, post_date, context}
    """
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return []

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    findings = []

    # Scan article titles
    c.execute("SELECT id, url, title, post_date FROM articles")
    articles = c.fetchall()
    print(f"Scanning {len(articles)} article titles...")

    for art in articles:
        title = art["title"] or ""
        codes = extract_milorb_codes(title)
        for code in codes:
            findings.append({
                "code": code,
                "article_id": art["id"],
                "url": art["url"],
                "title": title,
                "post_date": art["post_date"],
                "context": "title",
            })

    # Scan excerpts
    c.execute("""
        SELECT e.article_id, e.text, a.url, a.title, a.post_date
        FROM excerpts e
        JOIN articles a ON e.article_id = a.id
    """)
    print(f"Scanning excerpts...")

    batch_count = 0
    while True:
        rows = c.fetchmany(5000)
        if not rows:
            break
        batch_count += len(rows)
        for row in rows:
            text = row["text"] or ""
            codes = extract_milorb_codes(text)
            for code in codes:
                findings.append({
                    "code": code,
                    "article_id": row["article_id"],
                    "url": row["url"],
                    "title": row["title"],
                    "post_date": row["post_date"],
                    "context": text[:200],
                })
        if batch_count % 50000 == 0:
            print(f"  Processed {batch_count} excerpts...")

    print(f"  Total excerpts scanned: {batch_count}")
    conn.close()

    # Deduplicate by (code, url)
    seen = set()
    unique = []
    for f in findings:
        key = (f["code"], f["url"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_scan_results(findings, existing_codes):
    """
    Decode all found MilOrb codes, separating new from already-known.
    Returns (new_results, known_results) — lists of decoded dicts.
    """
    new_results = []
    known_results = []

    for f in findings:
        source_ctx = f.get("title", "") + " " + f.get("context", "")
        decoded = classify_and_decode(f["code"], source_context=source_ctx)
        if not decoded:
            continue

        result = {**f, **decoded}

        # Add geographic context for Earth coordinates
        if not decoded.get("is_celestial"):
            result["region"] = classify_region(decoded["lat"], decoded["lon"])
            facility, dist = find_nearest_facility(decoded["lat"], decoded["lon"])
            result["nearest_facility"] = facility
            result["facility_distance_km"] = round(dist, 1)
            anomaly, adist = find_nearest_anomaly(decoded["lat"], decoded["lon"])
            result["nearest_anomaly"] = anomaly
            result["anomaly_distance_km"] = round(adist, 1)

        if f["code"] in existing_codes:
            known_results.append(result)
        else:
            new_results.append(result)

    return new_results, known_results


def validate_new_coordinates(new_results, existing_coords):
    """
    Check if new decoded coordinates cluster near existing known coordinates.
    Adds validation info to each result.
    """
    for result in new_results:
        if result.get("is_celestial"):
            result["validation"] = "celestial-no-earth-validation"
            continue

        lat, lon = result["lat"], result["lon"]
        min_dist = float("inf")
        nearest_known = None

        for ec in existing_coords:
            d = haversine_km(lat, lon, ec["lat"], ec["lon"])
            if d < min_dist:
                min_dist = d
                nearest_known = ec

        result["nearest_known_km"] = round(min_dist, 1)
        if nearest_known:
            result["nearest_known_code"] = nearest_known.get("raw", "")

        if min_dist < 50:
            result["validation"] = "STRONG-near-known-coord"
        elif min_dist < 200:
            result["validation"] = "moderate-proximity"
        elif result.get("facility_distance_km", 9999) < 100:
            result["validation"] = "near-facility"
        else:
            result["validation"] = "unvalidated"

    return new_results


def load_existing_coordinates():
    """Load existing coordinate database for cross-validation."""
    coords = []
    if EXISTING_COORDS_CSV.exists():
        with open(EXISTING_COORDS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    coords.append({
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "type": row.get("type", ""),
                        "raw": row.get("raw", ""),
                    })
                except (ValueError, KeyError):
                    continue
    return coords


# ============================================================================
# REPORTING
# ============================================================================

def print_report(new_results, known_results, findings):
    """Print a summary report to stdout."""
    sys.stdout.reconfigure(encoding="utf-8")

    total_codes_found = len(set(f["code"] for f in findings))
    new_codes = set(r["code"] for r in new_results)
    known_codes = set(r["code"] for r in known_results)

    print("\n" + "=" * 70)
    print("FL MilOrb CORPUS SCAN REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 70)

    print(f"\nMilOrb patterns found in corpus: {total_codes_found} unique codes")
    print(f"  Already decoded: {len(known_codes)}")
    print(f"  NEW (not in existing database): {len(new_codes)}")

    if new_results:
        # Earth coordinates
        earth = [r for r in new_results if not r.get("is_celestial")]
        celestial = [r for r in new_results if r.get("is_celestial")]

        print(f"\n--- NEW EARTH COORDINATES ({len(earth)}) ---")
        for r in sorted(earth, key=lambda x: x.get("facility_distance_km", 9999)):
            print(f"\n  Code: {r['code']}")
            print(f"  Decoded: {r['lat']:.2f}, {r['lon']:.2f} ({r['method']})")
            print(f"  Region: {r.get('region', '?')}")
            print(f"  Nearest facility: {r.get('nearest_facility', '?')} ({r.get('facility_distance_km', '?')} km)")
            print(f"  Nearest anomaly: {r.get('nearest_anomaly', '?')} ({r.get('anomaly_distance_km', '?')} km)")
            print(f"  Validation: {r.get('validation', '?')}")
            print(f"  Source: {r.get('post_date', '?')} - {(r.get('title') or '?')[:60]}")
            print(f"  URL: {r.get('url', '?')}")

        if celestial:
            print(f"\n--- NEW CELESTIAL COORDINATES ({len(celestial)}) ---")
            for r in celestial:
                print(f"\n  Code: {r['code']}")
                print(f"  RA: {r['lat']:.2f}h, Dec: {r['lon']:.1f} deg")
                print(f"  Source: {r.get('post_date', '?')} - {(r.get('title') or '?')[:60]}")

    # Regional breakdown of all decoded (new + known)
    all_earth = [r for r in new_results + known_results if not r.get("is_celestial")]
    if all_earth:
        print(f"\n--- REGIONAL DISTRIBUTION (all {len(all_earth)} Earth coords) ---")
        regions = {}
        for r in all_earth:
            reg = r.get("region", "Unknown")
            regions[reg] = regions.get(reg, 0) + 1
        for reg, count in sorted(regions.items(), key=lambda x: -x[1]):
            print(f"  {reg}: {count}")

    # Facility proximity summary
    close_facilities = [r for r in all_earth if r.get("facility_distance_km", 9999) < 200]
    if close_facilities:
        print(f"\n--- COORDINATES NEAR KNOWN FACILITIES (<200km) ---")
        for r in sorted(close_facilities, key=lambda x: x["facility_distance_km"]):
            new_tag = " [NEW]" if r["code"] in new_codes else ""
            print(f"  {r['code']} -> {r['nearest_facility']} ({r['facility_distance_km']} km){new_tag}")

    print("\n" + "=" * 70)


def export_results(new_results, known_results):
    """Export decoded coordinates to CSV files."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    # Export new coordinates
    if new_results:
        earth = [r for r in new_results if not r.get("is_celestial")]
        if earth:
            outfile = OUTPUT_DIR / f"fl_milorb_new_decoded_{timestamp}.csv"
            with open(outfile, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "code", "lat", "lon", "method", "region", "post_date",
                    "nearest_facility", "facility_distance_km",
                    "nearest_anomaly", "anomaly_distance_km",
                    "validation", "nearest_known_km", "title", "url"
                ])
                for r in earth:
                    writer.writerow([
                        r["code"], round(r["lat"], 4), round(r["lon"], 4),
                        r["method"], r.get("region", ""),
                        r.get("post_date", ""),
                        r.get("nearest_facility", ""),
                        r.get("facility_distance_km", ""),
                        r.get("nearest_anomaly", ""),
                        r.get("anomaly_distance_km", ""),
                        r.get("validation", ""),
                        r.get("nearest_known_km", ""),
                        (r.get("title") or "")[:100],
                        r.get("url", ""),
                    ])
            print(f"\nExported {len(earth)} new Earth coordinates to {outfile}")

        celestial = [r for r in new_results if r.get("is_celestial")]
        if celestial:
            outfile = OUTPUT_DIR / f"fl_milorb_new_celestial_{timestamp}.csv"
            with open(outfile, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["code", "ra_hours", "dec_degrees", "method", "post_date", "title", "url"])
                for r in celestial:
                    writer.writerow([
                        r["code"], round(r["lat"], 4), round(r["lon"], 1),
                        r["method"], r.get("post_date", ""),
                        (r.get("title") or "")[:100], r.get("url", ""),
                    ])
            print(f"Exported {len(celestial)} new celestial coordinates to {outfile}")

    # Export combined updated database
    all_results = new_results + known_results
    all_earth = [r for r in all_results if not r.get("is_celestial")]
    if all_earth:
        outfile = OUTPUT_DIR / f"fl_milorb_all_decoded_updated_{timestamp}.csv"
        with open(outfile, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "code", "lat", "lon", "date", "method", "region", "title",
                "nearest_facility", "facility_distance_km",
                "nearest_anomaly", "anomaly_distance_km", "url"
            ])
            for r in sorted(all_earth, key=lambda x: x.get("post_date", "")):
                writer.writerow([
                    r["code"], round(r["lat"], 4), round(r["lon"], 4),
                    r.get("post_date", ""),
                    r["method"], r.get("region", ""),
                    (r.get("title") or "")[:100],
                    r.get("nearest_facility", ""),
                    r.get("facility_distance_km", ""),
                    r.get("nearest_anomaly", ""),
                    r.get("anomaly_distance_km", ""),
                    r.get("url", ""),
                ])
        print(f"Exported {len(all_earth)} total coordinates to {outfile}")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FL MilOrb Coordinate Decoder — validated formulas only",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scan", action="store_true",
                        help="Scan full corpus for MilOrb patterns and decode")
    parser.add_argument("--decode", metavar="CODE",
                        help="Decode a single MilOrb code (e.g. '+017+105')")
    parser.add_argument("--report", action="store_true",
                        help="Generate full report with validation")
    parser.add_argument("--export", action="store_true",
                        help="Export results to CSV")

    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.decode:
        result = classify_and_decode(args.decode)
        if result:
            print(f"Code: {result['code']}")
            print(f"v1={result['v1']}, v2={result['v2']}")
            if result.get("is_celestial"):
                print(f"Type: CELESTIAL")
                print(f"RA: {result['lat']:.2f} hours")
                print(f"Dec: {result['lon']:.1f} degrees")
            else:
                print(f"Method: {result['method']}")
                print(f"Lat: {result['lat']:.4f}")
                print(f"Lon: {result['lon']:.4f}")
                region = classify_region(result["lat"], result["lon"])
                print(f"Region: {region}")
                facility, dist = find_nearest_facility(result["lat"], result["lon"])
                print(f"Nearest facility: {facility} ({dist:.1f} km)")
                anomaly, adist = find_nearest_anomaly(result["lat"], result["lon"])
                print(f"Nearest anomaly: {anomaly} ({adist:.1f} km)")
        else:
            print(f"Could not decode: {args.decode}")
        return

    if args.scan or args.report or args.export:
        # Load existing data
        existing_codes = load_existing_codes()
        existing_coords = load_existing_coordinates()
        print(f"Loaded {len(existing_codes)} existing MilOrb codes")
        print(f"Loaded {len(existing_coords)} existing coordinates for validation")

        # Scan corpus
        findings = scan_corpus()
        print(f"\nFound {len(findings)} MilOrb occurrences in corpus")

        # Decode
        new_results, known_results = process_scan_results(findings, existing_codes)

        # Validate new against existing
        new_results = validate_new_coordinates(new_results, existing_coords)

        if args.report or args.scan:
            print_report(new_results, known_results, findings)

        if args.export:
            export_results(new_results, known_results)

        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
