#!/usr/bin/env python3
"""
FL EXTRACTION AGENT - STANDALONE VERSION
=========================================
Run this on your local machine to extract content from Forgotten Languages.

SETUP:
    pip install requests beautifulsoup4
    python fl_local_agent.py --init
    python fl_local_agent.py --url "https://forgottenlanguages-full.forgottenlanguages.org/..."

FULL USAGE:
    --init              Initialize database
    --url URL           Process single URL
    --batch FILE        Process URLs from file (one per line)
    --pending           Process all pending URLs in queue
    --status            Show database statistics
    --export FILE.csv   Export all excerpts to CSV
    --search TERM       Search existing excerpts
"""

import sqlite3
import re
import csv
import argparse
import time
import hashlib
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("="*60)
    print("MISSING DEPENDENCIES - Run:")
    print("  pip install requests beautifulsoup4")
    print("="*60)

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = "fl_database.db"

# FL terminology for pattern matching
FL_TERMS = [
    'SV17q', 'SV06n', 'SV09n', 'DOLYN', 'MilOrb', 'PSV', 'XViS', 'LyAV',
    'Giselian', 'MASINT', 'UAP', 'USO', 'USP', 'CTC', 'Queltron', 'NodeSpaces',
    'Cassini', 'DART', 'NDE', 'ETI', 'Denebian', 'DENIED', 'FL-', 'Akrij',
    'Sienna', 'Presence', 'Tangent', 'Graphium', 'Corona East', 'Black Prophet',
    'CAFB', 'HUT', 'AUTEC', 'Yulara', 'Atacama', 'Thule', 'Jan Mayen'
]

# ============================================================================
# DATABASE
# ============================================================================

def init_database():
    """Create database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        post_date TEXT,
        status TEXT DEFAULT 'pending',
        excerpt_count INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        added_at TEXT,
        processed_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS excerpts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        text TEXT,
        text_hash TEXT UNIQUE,
        word_count INTEGER,
        category TEXT,
        position INTEGER,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_excerpts_hash ON excerpts(text_hash)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")

def get_db():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

# ============================================================================
# EXTRACTION ENGINE
# ============================================================================

def extract_english(text):
    """Extract English content from FL mixed-language text"""
    excerpts = []
    seen_hashes = set()
    
    def add_excerpt(content, category):
        clean = content.strip().replace('\n', ' ')
        clean = re.sub(r'\s+', ' ', clean)
        
        if len(clean) < 30:
            return
        
        # Check ASCII ratio (filters FL constructed language)
        ascii_ratio = sum(1 for c in clean if ord(c) < 128) / len(clean)
        if ascii_ratio < 0.80:
            return
        
        words = len(clean.split())
        if words < 6:
            return
        
        text_hash = hashlib.md5(clean.encode()).hexdigest()[:16]
        if text_hash in seen_hashes:
            return
        
        seen_hashes.add(text_hash)
        excerpts.append({
            'text': clean,
            'hash': text_hash,
            'words': words,
            'category': category
        })
    
    # Pattern 1: Quoted text (highest confidence)
    for match in re.findall(r'"([^"]{25,500})"', text, re.DOTALL):
        add_excerpt(match, 'quote')
    
    # Pattern 2: Text in italics
    for match in re.findall(r'\*([^*]{30,500})\*', text):
        add_excerpt(match, 'emphasis')
    
    # Pattern 3: Sentences containing FL terminology
    fl_pattern = '|'.join(re.escape(term) for term in FL_TERMS)
    for match in re.findall(rf'([A-Z][^.!?]*(?:{fl_pattern})[^.!?]*[.!?])', text):
        if len(match) < 300:  # Avoid huge matches
            add_excerpt(match, 'technical')
    
    # Pattern 4: English sentences (longer, high ASCII)
    for sentence in re.findall(r'([A-Z][a-z][^.!?]{40,200}[.!?])', text):
        ascii_ratio = sum(1 for c in sentence if ord(c) < 128) / len(sentence)
        if ascii_ratio > 0.95:
            add_excerpt(sentence, 'narrative')
    
    return excerpts

def extract_metadata(html):
    """Extract title and date from page"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Title
    title = "Untitled"
    title_tag = soup.find('h3', class_='post-title') or soup.find('title')
    if title_tag:
        title = title_tag.get_text().strip()
        title = re.sub(r'^Forgotten Languages Full:\s*', '', title)
        title = title[:200]
    
    # Date
    date = None
    date_tag = soup.find('h2', class_='date-header')
    if date_tag:
        date = date_tag.get_text().strip()
    
    # Main content
    content = ""
    post_body = soup.find('div', class_='post-body')
    if post_body:
        content = post_body.get_text(separator='\n')
    else:
        content = soup.get_text(separator='\n')
    
    return title, date, content

# ============================================================================
# URL PROCESSING
# ============================================================================

def fetch_url(url, timeout=30):
    """Fetch URL with error handling"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text, None
    except Exception as e:
        return None, str(e)

def process_url(url, verbose=True):
    """Fetch and process a single URL"""
    if verbose:
        print(f"\nProcessing: {url}")
    
    # Check if already processed
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, status FROM articles WHERE url = ?", (url,))
    existing = c.fetchone()
    
    if existing and existing[1] == 'done':
        if verbose:
            print("  Already processed, skipping")
        conn.close()
        return 0, 0
    
    # Fetch
    html, error = fetch_url(url)
    if error:
        if verbose:
            print(f"  Error: {error}")
        conn.close()
        return 0, 0
    
    # Extract
    title, date, content = extract_metadata(html)
    excerpts = extract_english(content)
    
    if verbose:
        print(f"  Title: {title[:50]}...")
        print(f"  Found: {len(excerpts)} excerpts")
    
    # Store article
    if existing:
        article_id = existing[0]
        c.execute("UPDATE articles SET title=?, post_date=?, status='done', processed_at=? WHERE id=?",
                  (title, date, datetime.now().isoformat(), article_id))
    else:
        c.execute("""INSERT INTO articles (url, title, post_date, status, added_at, processed_at)
                   VALUES (?, ?, ?, 'done', ?, ?)""",
                  (url, title, date, datetime.now().isoformat(), datetime.now().isoformat()))
        article_id = c.lastrowid
    
    # Store excerpts
    total_words = 0
    excerpt_count = 0
    
    for i, exc in enumerate(excerpts):
        try:
            c.execute("""INSERT OR IGNORE INTO excerpts 
                       (article_id, text, text_hash, word_count, category, position)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                     (article_id, exc['text'], exc['hash'], exc['words'], exc['category'], i))
            if c.rowcount > 0:
                excerpt_count += 1
                total_words += exc['words']
        except sqlite3.IntegrityError:
            pass  # Duplicate
    
    # Update counts
    c.execute("UPDATE articles SET excerpt_count=?, word_count=? WHERE id=?",
              (excerpt_count, total_words, article_id))
    
    conn.commit()
    conn.close()
    
    return excerpt_count, total_words

def add_to_queue(url):
    """Add URL to processing queue"""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""INSERT OR IGNORE INTO articles (url, status, added_at)
                   VALUES (?, 'pending', ?)""", (url, datetime.now().isoformat()))
        conn.commit()
        added = c.rowcount > 0
    except:
        added = False
    conn.close()
    return added

def process_pending(delay=1.0):
    """Process all pending URLs"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT url FROM articles WHERE status = 'pending'")
    pending = [row[0] for row in c.fetchall()]
    conn.close()
    
    if not pending:
        print("No pending URLs")
        return
    
    print(f"Processing {len(pending)} URLs...")
    
    total_excerpts = 0
    total_words = 0
    
    for i, url in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}]", end="")
        exc, words = process_url(url)
        total_excerpts += exc
        total_words += words
        
        if delay > 0 and i < len(pending):
            time.sleep(delay)
    
    print(f"\n{'='*60}")
    print(f"COMPLETE: {total_excerpts} excerpts, {total_words:,} words")

# ============================================================================
# REPORTING
# ============================================================================

def show_status():
    """Display database statistics"""
    conn = get_db()
    c = conn.cursor()
    
    # Article counts
    c.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
    status_counts = dict(c.fetchall())
    
    # Excerpt totals
    c.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM excerpts")
    exc_count, word_count = c.fetchone()
    
    # Top articles
    c.execute("""SELECT title, excerpt_count, word_count 
               FROM articles WHERE excerpt_count > 0
               ORDER BY excerpt_count DESC LIMIT 10""")
    top_articles = c.fetchall()
    
    # Category breakdown
    c.execute("SELECT category, COUNT(*), SUM(word_count) FROM excerpts GROUP BY category")
    categories = c.fetchall()
    
    conn.close()
    
    print("\n" + "="*60)
    print("FL DATABASE STATUS")
    print("="*60)
    
    print("\n📊 ARTICLES:")
    for status, count in status_counts.items():
        print(f"   {status}: {count}")
    
    print(f"\n📝 EXCERPTS: {exc_count:,}")
    print(f"📖 WORDS: {word_count:,}")
    
    print("\n📁 BY CATEGORY:")
    for cat, count, words in categories:
        print(f"   {cat or 'unknown'}: {count} excerpts ({words:,} words)")
    
    print("\n🏆 TOP ARTICLES:")
    for title, exc, words in top_articles:
        t = (title or "Untitled")[:45]
        print(f"   [{exc:2}] {words:4}w - {t}")

def export_csv(output_path):
    """Export excerpts to CSV"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT a.url, a.title, a.post_date, e.text, e.word_count, e.category
               FROM excerpts e
               JOIN articles a ON e.article_id = a.id
               ORDER BY a.id, e.position""")
    rows = c.fetchall()
    conn.close()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['URL', 'Title', 'Date', 'Excerpt', 'Words', 'Category'])
        writer.writerows(rows)
    
    print(f"Exported {len(rows)} excerpts to {output_path}")

def search_excerpts(term):
    """Search excerpts for term"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT a.title, e.text FROM excerpts e
               JOIN articles a ON e.article_id = a.id
               WHERE e.text LIKE ?
               ORDER BY e.word_count DESC LIMIT 20""",
             (f'%{term}%',))
    results = c.fetchall()
    conn.close()
    
    print(f"\n🔍 Search results for '{term}': {len(results)} found\n")
    for title, text in results:
        t = (title or "Untitled")[:40]
        txt = text[:100] + "..." if len(text) > 100 else text
        print(f"[{t}]")
        print(f"  {txt}\n")

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='FL Extraction Agent - Extract English from Forgotten Languages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fl_local_agent.py --init
  python fl_local_agent.py --url "https://forgottenlanguages-full.forgottenlanguages.org/2017/12/axis-from-lightning-bugs-to-milorbs.html"
  python fl_local_agent.py --batch urls.txt
  python fl_local_agent.py --status
  python fl_local_agent.py --export output.csv
  python fl_local_agent.py --search "MilOrb"
        """)
    
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--url', metavar='URL', help='Process single URL')
    parser.add_argument('--batch', metavar='FILE', help='Process URLs from file')
    parser.add_argument('--pending', action='store_true', help='Process pending queue')
    parser.add_argument('--status', action='store_true', help='Show statistics')
    parser.add_argument('--export', metavar='FILE', help='Export to CSV')
    parser.add_argument('--search', metavar='TERM', help='Search excerpts')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
    
    args = parser.parse_args()
    
    if not HAS_DEPS:
        return
    
    # Ensure DB exists
    if not Path(DB_PATH).exists() or args.init:
        init_database()
        if args.init:
            return
    
    if args.status:
        show_status()
        return
    
    if args.export:
        export_csv(args.export)
        return
    
    if args.search:
        search_excerpts(args.search)
        return
    
    if args.url:
        exc, words = process_url(args.url)
        print(f"\nResult: {exc} excerpts, {words} words")
        return
    
    if args.batch:
        with open(args.batch, 'r') as f:
            urls = [line.strip() for line in f 
                   if line.strip() and not line.startswith('#')]
        
        print(f"Adding {len(urls)} URLs to queue...")
        for url in urls:
            add_to_queue(url)
        
        process_pending(delay=args.delay)
        return
    
    if args.pending:
        process_pending(delay=args.delay)
        return
    
    # Default: show status
    show_status()

if __name__ == '__main__':
    main()
