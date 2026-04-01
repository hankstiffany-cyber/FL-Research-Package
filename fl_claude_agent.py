#!/usr/bin/env python3
"""
FL INTELLIGENT EXTRACTION AGENT (Claude-Powered)
================================================
Uses Claude API for intelligent content extraction from Forgotten Languages.

This agent can:
1. Search FL site for specific topics
2. Extract and interpret mixed-language content
3. Identify key operational details, coordinates, incidents
4. Build a structured knowledge base

Usage:
    python fl_claude_agent.py --topic "MilOrb specifications"
    python fl_claude_agent.py --analyze <url>
    python fl_claude_agent.py --summarize

Requirements:
    pip install anthropic requests beautifulsoup4 --break-system-packages
    
Environment:
    ANTHROPIC_API_KEY=your_api_key
"""

import os
import json
import sqlite3
import argparse
from datetime import datetime

# Try imports
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("Install anthropic: pip install anthropic --break-system-packages")

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = "fl_knowledge.db"
MODEL = "claude-sonnet-4-20250514"  # Use Sonnet for efficiency

# FL extraction prompt template
EXTRACTION_PROMPT = """You are analyzing content from the Forgotten Languages (FL) website, a cryptographic constructed language project. Your task is to extract and structure ALL English content from this mixed-language text.

FL posts typically contain:
1. Constructed language text (ignore this)
2. Embedded English quotes (usually in quotation marks or italics)
3. Technical terminology (SV17q, DOLYN, MilOrb, PSV, XViS, LyAV, Giselian, etc.)
4. Coordinates (GPS, DMS, or encoded formats)
5. Dates and timestamps
6. Vehicle/program names (Sienna, Akrij, Presence, Tangent, Graphium)
7. Event/incident references

CONTENT TO ANALYZE:
{content}

Please extract and return a JSON object with:
{{
    "title": "article title if found",
    "date": "publication date if found",
    "english_excerpts": [
        {{"text": "full English excerpt", "category": "quote|technical|operational|narrative"}}
    ],
    "coordinates": [
        {{"raw": "original format", "decoded": "lat,long if decodable", "location": "place name if identifiable"}}
    ],
    "vehicles_mentioned": ["list of PSV/MilOrb names"],
    "organizations_mentioned": ["SV17q, DOLYN, etc."],
    "incidents_referenced": ["named events"],
    "key_claims": ["main assertions made in the text"],
    "cross_references": ["FL-XXXXXX format references to other posts"]
}}

Extract ALL English content, even partial sentences. Be thorough."""

# ============================================================================
# DATABASE
# ============================================================================

def init_db():
    """Initialize knowledge database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY,
        url TEXT UNIQUE,
        title TEXT,
        date TEXT,
        raw_content TEXT,
        extracted_json TEXT,
        processed_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS excerpts (
        id INTEGER PRIMARY KEY,
        article_id INTEGER,
        text TEXT,
        category TEXT,
        word_count INTEGER,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS coordinates (
        id INTEGER PRIMARY KEY,
        article_id INTEGER,
        raw TEXT,
        latitude REAL,
        longitude REAL,
        location TEXT,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY,
        name TEXT,
        entity_type TEXT,
        first_seen TEXT,
        mention_count INTEGER DEFAULT 1
    )''')
    
    conn.commit()
    conn.close()

# ============================================================================
# CLAUDE INTEGRATION
# ============================================================================

def analyze_with_claude(content, api_key=None):
    """Use Claude to intelligently extract content"""
    if not HAS_ANTHROPIC:
        return None, "anthropic library not installed"
    
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None, "ANTHROPIC_API_KEY not set"
    
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(content=content[:15000])
                }
            ]
        )
        
        # Extract JSON from response
        response_text = message.content[0].text
        
        # Try to parse JSON
        json_match = response_text
        if "```json" in response_text:
            json_match = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_match = response_text.split("```")[1].split("```")[0]
        
        result = json.loads(json_match)
        return result, None
        
    except json.JSONDecodeError as e:
        return {"raw_response": response_text}, f"JSON parse error: {e}"
    except Exception as e:
        return None, str(e)

def fetch_and_analyze(url, api_key=None):
    """Fetch URL and analyze with Claude"""
    if not HAS_REQUESTS:
        return None, "requests library not installed"
    
    # Fetch content
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get main content (FL uses specific structure)
        content = soup.get_text(separator='\n')
        
    except Exception as e:
        return None, f"Fetch error: {e}"
    
    # Analyze with Claude
    result, error = analyze_with_claude(content, api_key)
    
    if error:
        return result, error
    
    # Store in database
    store_analysis(url, content, result)
    
    return result, None

def store_analysis(url, raw_content, analysis):
    """Store analysis results in database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Store article
    c.execute('''INSERT OR REPLACE INTO articles 
               (url, title, date, raw_content, extracted_json, processed_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
             (url, 
              analysis.get('title'),
              analysis.get('date'),
              raw_content[:50000],  # Limit storage
              json.dumps(analysis),
              datetime.now().isoformat()))
    
    article_id = c.lastrowid
    
    # Store excerpts
    for excerpt in analysis.get('english_excerpts', []):
        text = excerpt.get('text', '')
        c.execute('''INSERT INTO excerpts (article_id, text, category, word_count)
                   VALUES (?, ?, ?, ?)''',
                 (article_id, text, excerpt.get('category'), len(text.split())))
    
    # Store coordinates
    for coord in analysis.get('coordinates', []):
        lat, lon = None, None
        if coord.get('decoded'):
            try:
                parts = coord['decoded'].split(',')
                lat, lon = float(parts[0]), float(parts[1])
            except:
                pass
        c.execute('''INSERT INTO coordinates (article_id, raw, latitude, longitude, location)
                   VALUES (?, ?, ?, ?, ?)''',
                 (article_id, coord.get('raw'), lat, lon, coord.get('location')))
    
    # Track entities
    for vehicle in analysis.get('vehicles_mentioned', []):
        track_entity(c, vehicle, 'vehicle')
    for org in analysis.get('organizations_mentioned', []):
        track_entity(c, org, 'organization')
    
    conn.commit()
    conn.close()

def track_entity(cursor, name, entity_type):
    """Track entity mentions"""
    cursor.execute('''INSERT INTO entities (name, entity_type, first_seen)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET mention_count = mention_count + 1''',
                 (name, entity_type, datetime.now().isoformat()))

# ============================================================================
# REPORTING
# ============================================================================

def generate_summary():
    """Generate summary of extracted knowledge"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Stats
    c.execute("SELECT COUNT(*) FROM articles")
    article_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM excerpts")
    excerpt_stats = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM coordinates WHERE latitude IS NOT NULL")
    coord_count = c.fetchone()[0]
    
    c.execute("SELECT name, entity_type, mention_count FROM entities ORDER BY mention_count DESC LIMIT 20")
    top_entities = c.fetchall()
    
    conn.close()
    
    print("\n" + "="*60)
    print("FL KNOWLEDGE BASE SUMMARY")
    print("="*60)
    print(f"\nArticles analyzed: {article_count}")
    print(f"Excerpts extracted: {excerpt_stats[0]}")
    print(f"Total words: {excerpt_stats[1]:,}")
    print(f"Coordinates decoded: {coord_count}")
    print(f"\nTop Entities:")
    for name, etype, count in top_entities:
        print(f"  [{etype:12}] {count:3}x - {name}")

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='FL Intelligent Extraction Agent')
    parser.add_argument('--analyze', help='Analyze single URL with Claude')
    parser.add_argument('--topic', help='Search and analyze topic')
    parser.add_argument('--summarize', action='store_true', help='Show knowledge base summary')
    parser.add_argument('--api-key', help='Anthropic API key')
    parser.add_argument('--init', action='store_true', help='Initialize database')
    
    args = parser.parse_args()
    
    init_db()
    
    if args.init:
        print("Database initialized")
        return
    
    if args.summarize:
        generate_summary()
        return
    
    if args.analyze:
        print(f"Analyzing: {args.analyze}")
        result, error = fetch_and_analyze(args.analyze, args.api_key)
        if error:
            print(f"Error: {error}")
        else:
            print(json.dumps(result, indent=2))
        return
    
    if args.topic:
        print(f"Topic search requires web search integration")
        print(f"Query: site:forgottenlanguages-full.forgottenlanguages.org {args.topic}")
        return
    
    generate_summary()

if __name__ == '__main__':
    main()
