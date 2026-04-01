#!/usr/bin/env python3
"""
FL AUTONOMOUS EXTRACTION AGENT
==============================
A self-contained agent for extracting English content from Forgotten Languages.

Usage:
    python fl_agent.py --search "DOLYN signatures"     # Search and extract
    python fl_agent.py --url <url>                     # Extract single URL
    python fl_agent.py --batch urls.txt               # Process URL list
    python fl_agent.py --status                        # Show database status
    python fl_agent.py --export                        # Export to CSV

Requirements:
    pip install requests beautifulsoup4 --break-system-packages
"""

import sqlite3
import re
import json
import argparse
import time
from datetime import datetime
from pathlib import Path

# Try to import optional dependencies
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Note: Install requests and beautifulsoup4 for web fetching")

# ============================================================================
# DATABASE SETUP
# ============================================================================

DB_PATH = "fl_excerpts.db"

def init_database():
    """Initialize SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS fl_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        url_hash TEXT,
        title TEXT,
        post_date TEXT,
        labels TEXT,
        extraction_status TEXT DEFAULT 'pending',
        excerpt_count INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        source TEXT DEFAULT 'agent',
        added_at TEXT,
        extracted_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS fl_excerpts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        excerpt_text TEXT,
        excerpt_hash TEXT,
        word_count INTEGER,
        position INTEGER,
        extracted_at TEXT,
        FOREIGN KEY (article_id) REFERENCES fl_articles(id),
        UNIQUE(excerpt_hash)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS agent_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        action TEXT,
        details TEXT
    )''')
    
    conn.commit()
    conn.close()

def log_action(action, details=""):
    """Log agent action to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO agent_log (timestamp, action, details) VALUES (?, ?, ?)",
              (datetime.now().isoformat(), action, details))
    conn.commit()
    conn.close()

# ============================================================================
# EXTRACTION LOGIC
# ============================================================================

# FL-specific terminology for pattern matching
FL_TERMS = [
    'SV17q', 'SV06n', 'SV09n', 'DOLYN', 'MilOrb', 'PSV', 'XViS', 'LyAV',
    'Giselian', 'MASINT', 'UAP', 'USO', 'USP', 'CTC', 'Queltron', 'NodeSpaces',
    'Cassini', 'DART', 'NDE', 'ETI', 'Denebian', 'DENIED', 'FL-', 'Akrij',
    'Sienna', 'Presence', 'Tangent', 'Graphium', 'Corona East', 'Black Prophet'
]

def extract_english(text):
    """
    Extract English sentences from FL mixed-language content.
    Returns list of (text, word_count) tuples.
    """
    excerpts = []
    seen = set()
    
    # Pattern 1: Quoted text (highest quality)
    for match in re.findall(r'"([^"]{25,})"', text, re.DOTALL):
        clean = match.strip().replace('\n', ' ').replace('  ', ' ')
        if _is_valid_excerpt(clean, seen):
            seen.add(clean)
            excerpts.append((clean, len(clean.split())))
    
    # Pattern 2: Italicized text (*text*)
    for match in re.findall(r'\*([^*]{30,})\*', text, re.DOTALL):
        clean = match.strip().replace('\n', ' ').replace('  ', ' ')
        if _is_valid_excerpt(clean, seen, min_words=8):
            seen.add(clean)
            excerpts.append((clean, len(clean.split())))
    
    # Pattern 3: Sentences with FL terminology
    fl_pattern = '|'.join(re.escape(term) for term in FL_TERMS)
    for match in re.findall(rf'([A-Z][^.!?]*(?:{fl_pattern})[^.!?]*[.!?])', text):
        clean = match.strip().replace('\n', ' ').replace('  ', ' ')
        if _is_valid_excerpt(clean, seen, min_words=10, min_ascii=0.90):
            seen.add(clean)
            excerpts.append((clean, len(clean.split())))
    
    return excerpts

def _is_valid_excerpt(text, seen, min_words=6, min_len=30, min_ascii=0.80):
    """Check if text is a valid English excerpt"""
    if len(text) < min_len or text in seen:
        return False
    
    # ASCII ratio check (filters out FL constructed language)
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
    if ascii_ratio < min_ascii:
        return False
    
    # Word count check
    words = len(text.split())
    if words < min_words:
        return False
    
    return True

def extract_metadata(html_content):
    """Extract title and date from FL page"""
    title = "Untitled"
    date = None
    
    # Title patterns
    title_match = re.search(r'### \[([^\]]+)\]', html_content)
    if title_match:
        title = title_match.group(1).strip()[:200]
    else:
        title_match = re.search(r'Forgotten Languages Full:\s*(.+?)(?:\n|$)', html_content)
        if title_match:
            title = title_match.group(1).strip()[:200]
    
    # Date pattern
    date_match = re.search(r'## ([A-Z][a-z]+ \d+, \d{4})', html_content)
    if date_match:
        date = date_match.group(1)
    
    return title, date

# ============================================================================
# WEB FETCHING (requires requests)
# ============================================================================

def fetch_url(url, timeout=30):
    """Fetch URL content"""
    if not HAS_REQUESTS:
        return None, "requests library not installed"
    
    try:
        headers = {
            'User-Agent': 'FL-Research-Agent/1.0'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text, None
    except Exception as e:
        return None, str(e)

def search_fl_site(query, max_results=10):
    """
    Search FL site using Google site: operator.
    Note: This is a simplified version - for production use Google Custom Search API.
    """
    # This would need API access - returning placeholder
    print(f"Search functionality requires external API integration")
    print(f"Query: site:forgottenlanguages-full.forgottenlanguages.org {query}")
    return []

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def add_url(url):
    """Add URL to processing queue"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    url_hash = str(hash(url) & 0xFFFFFFFF)
    try:
        c.execute('''INSERT OR IGNORE INTO fl_articles 
                   (url, url_hash, extraction_status, added_at)
                   VALUES (?, ?, 'pending', ?)''',
                 (url, url_hash, datetime.now().isoformat()))
        conn.commit()
        added = c.rowcount > 0
    except Exception as e:
        added = False
        print(f"Error adding URL: {e}")
    
    conn.close()
    return added

def process_url(url):
    """Fetch and process a single URL"""
    print(f"Processing: {url}")
    
    # Fetch content
    content, error = fetch_url(url)
    if error:
        print(f"  Error fetching: {error}")
        return 0, 0
    
    # Extract metadata
    title, date = extract_metadata(content)
    print(f"  Title: {title}")
    
    # Extract English excerpts
    excerpts = extract_english(content)
    print(f"  Found {len(excerpts)} excerpts")
    
    # Store in database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get or create article
    c.execute("SELECT id FROM fl_articles WHERE url = ?", (url,))
    result = c.fetchone()
    
    if result:
        article_id = result[0]
    else:
        url_hash = str(hash(url) & 0xFFFFFFFF)
        c.execute('''INSERT INTO fl_articles (url, url_hash, added_at)
                   VALUES (?, ?, ?)''',
                 (url, url_hash, datetime.now().isoformat()))
        article_id = c.lastrowid
    
    # Store excerpts
    excerpt_count = 0
    total_words = 0
    
    for i, (text, word_count) in enumerate(excerpts):
        excerpt_hash = str(hash(text) & 0xFFFFFFFF)
        try:
            c.execute('''INSERT OR IGNORE INTO fl_excerpts
                       (article_id, excerpt_text, excerpt_hash, 
                        word_count, position, extracted_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                     (article_id, text, excerpt_hash, word_count, i,
                      datetime.now().isoformat()))
            if c.rowcount > 0:
                excerpt_count += 1
                total_words += word_count
        except:
            pass
    
    # Update article
    c.execute('''UPDATE fl_articles SET 
                extraction_status = 'extracted',
                title = ?,
                post_date = ?,
                excerpt_count = ?,
                word_count = ?,
                extracted_at = ?
                WHERE id = ?''',
             (title, date, excerpt_count, total_words, 
              datetime.now().isoformat(), article_id))
    
    conn.commit()
    conn.close()
    
    log_action("extract", f"{url} -> {excerpt_count} excerpts, {total_words} words")
    return excerpt_count, total_words

def process_pending():
    """Process all pending URLs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url FROM fl_articles WHERE extraction_status = 'pending'")
    pending = [row[0] for row in c.fetchall()]
    conn.close()
    
    print(f"Processing {len(pending)} pending URLs...")
    
    total_excerpts = 0
    total_words = 0
    
    for i, url in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}]")
        excerpts, words = process_url(url)
        total_excerpts += excerpts
        total_words += words
        time.sleep(1)  # Rate limiting
    
    print(f"\n{'='*60}")
    print(f"Completed: {total_excerpts} excerpts, {total_words} words")
    return total_excerpts, total_words

def show_status():
    """Display database status"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT extraction_status, COUNT(*) FROM fl_articles GROUP BY extraction_status")
    status = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM fl_excerpts")
    total = c.fetchone()
    
    c.execute("""SELECT title, excerpt_count, word_count 
               FROM fl_articles 
               WHERE excerpt_count > 0 
               ORDER BY excerpt_count DESC LIMIT 10""")
    top = c.fetchall()
    
    conn.close()
    
    print("\n" + "="*60)
    print("FL AGENT DATABASE STATUS")
    print("="*60)
    print(f"\nArticles:")
    for s, count in status.items():
        print(f"  {s}: {count}")
    print(f"\nExcerpts: {total[0]}")
    print(f"Words: {total[1]:,}")
    print(f"\nTop Articles:")
    for title, excerpts, words in top:
        title_short = (title or "Untitled")[:45]
        print(f"  [{excerpts:2}] {words:4}w - {title_short}")

def export_csv(output_path="fl_excerpts_export.csv"):
    """Export excerpts to CSV"""
    import csv
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT a.url, a.title, a.post_date, e.excerpt_text, e.word_count
        FROM fl_excerpts e
        JOIN fl_articles a ON e.article_id = a.id
        ORDER BY a.id, e.position
    """)
    rows = c.fetchall()
    conn.close()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['URL', 'Title', 'Date', 'Excerpt', 'Word Count'])
        writer.writerows(rows)
    
    print(f"Exported {len(rows)} excerpts to {output_path}")
    return len(rows)

# ============================================================================
# MANUAL EXCERPT ADDITION
# ============================================================================

def add_manual_excerpt(title, excerpt_text, url=None):
    """Add manually extracted excerpt"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create or get article
    if url:
        c.execute("SELECT id FROM fl_articles WHERE url = ?", (url,))
    else:
        url = f"manual-{hash(title) & 0xFFFFFFFF}"
        c.execute("SELECT id FROM fl_articles WHERE url = ?", (url,))
    
    result = c.fetchone()
    if result:
        article_id = result[0]
    else:
        c.execute('''INSERT INTO fl_articles (url, url_hash, title, extraction_status, added_at)
                   VALUES (?, ?, ?, 'manual', ?)''',
                 (url, str(hash(url) & 0xFFFFFFFF), title, datetime.now().isoformat()))
        article_id = c.lastrowid
    
    # Add excerpt
    word_count = len(excerpt_text.split())
    excerpt_hash = str(hash(excerpt_text) & 0xFFFFFFFF)
    
    c.execute('''INSERT OR IGNORE INTO fl_excerpts
               (article_id, excerpt_text, excerpt_hash, word_count, position, extracted_at)
               VALUES (?, ?, ?, ?, 0, ?)''',
             (article_id, excerpt_text, excerpt_hash, word_count, datetime.now().isoformat()))
    
    # Update article counts
    c.execute("""UPDATE fl_articles SET 
                excerpt_count = (SELECT COUNT(*) FROM fl_excerpts WHERE article_id = ?),
                word_count = (SELECT COALESCE(SUM(word_count), 0) FROM fl_excerpts WHERE article_id = ?)
                WHERE id = ?""", (article_id, article_id, article_id))
    
    conn.commit()
    conn.close()
    
    return article_id

# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='FL Autonomous Extraction Agent')
    parser.add_argument('--url', help='Process single URL')
    parser.add_argument('--batch', help='Process URLs from file')
    parser.add_argument('--search', help='Search FL site (requires API)')
    parser.add_argument('--pending', action='store_true', help='Process all pending URLs')
    parser.add_argument('--status', action='store_true', help='Show database status')
    parser.add_argument('--export', help='Export to CSV file')
    parser.add_argument('--init', action='store_true', help='Initialize database')
    
    args = parser.parse_args()
    
    # Always ensure database exists
    init_database()
    
    if args.init:
        print("Database initialized")
        return
    
    if args.status:
        show_status()
        return
    
    if args.export:
        export_csv(args.export)
        return
    
    if args.url:
        excerpts, words = process_url(args.url)
        print(f"Extracted: {excerpts} excerpts, {words} words")
        return
    
    if args.batch:
        with open(args.batch, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        for url in urls:
            add_url(url)
        print(f"Added {len(urls)} URLs to queue")
        process_pending()
        return
    
    if args.pending:
        process_pending()
        return
    
    if args.search:
        search_fl_site(args.search)
        return
    
    # Default: show status
    show_status()

if __name__ == '__main__':
    main()
