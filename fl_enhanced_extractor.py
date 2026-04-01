#!/usr/bin/env python3
"""
FL ENHANCED EXTRACTOR
======================
Extracts bibliographies, citations, images, and enhanced metadata from FL articles.

Features:
    - Bibliography/reference extraction (academic citation patterns)
    - Image URL extraction with metadata
    - Citation pattern detection (inline and reference list)
    - Can re-process existing URLs to add new data
    - Exports to JSON and CSV formats

Usage:
    python fl_enhanced_extractor.py --url <url>           # Process single URL
    python fl_enhanced_extractor.py --batch urls.txt     # Process URL list
    python fl_enhanced_extractor.py --reprocess          # Re-extract from all known URLs
    python fl_enhanced_extractor.py --status             # Show database status
    python fl_enhanced_extractor.py --export             # Export all data

Requirements:
    pip install requests beautifulsoup4
"""

import sqlite3
import re
import json
import csv
import argparse
import time
import hashlib
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("=" * 60)
    print("MISSING DEPENDENCIES - Run:")
    print("  pip install requests beautifulsoup4")
    print("=" * 60)

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = "fl_enhanced.db"
DATA_DIR = Path("data")
IMAGES_DIR = Path("images")
DELAY = 1.5  # seconds between requests

# FL terminology for context tagging
FL_TERMS = [
    'SV17q', 'SV06n', 'SV09n', 'DOLYN', 'MilOrb', 'PSV', 'XViS', 'LyAV',
    'Giselian', 'MASINT', 'UAP', 'USO', 'Queltron', 'NodeSpaces',
    'Cassini', 'NDE', 'Denebian', 'DENIED', 'Akrij', 'Sienna', 'Presence',
    'Tangent', 'Graphium', 'Corona East', 'Black Prophet', 'AUTEC',
    'Yulara', 'Thule', 'Jan Mayen', 'SAA', 'transmedium'
]

# ============================================================================
# DATABASE SCHEMA
# ============================================================================

def init_database():
    """Create enhanced database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Articles table (enhanced)
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        post_date TEXT,
        labels TEXT,
        excerpt_count INTEGER DEFAULT 0,
        citation_count INTEGER DEFAULT 0,
        image_count INTEGER DEFAULT 0,
        bibliography_count INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        has_coordinates INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        added_at TEXT,
        processed_at TEXT,
        enhanced_at TEXT
    )''')

    # Excerpts table (existing)
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

    # NEW: Citations table (inline citations found in text)
    c.execute('''CREATE TABLE IF NOT EXISTS citations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        citation_text TEXT,
        citation_hash TEXT UNIQUE,
        citation_type TEXT,
        author TEXT,
        year TEXT,
        title TEXT,
        source TEXT,
        position INTEGER,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')

    # NEW: Bibliography table (reference list entries)
    c.execute('''CREATE TABLE IF NOT EXISTS bibliography (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        entry_text TEXT,
        entry_hash TEXT UNIQUE,
        author TEXT,
        year TEXT,
        title TEXT,
        journal TEXT,
        volume TEXT,
        pages TEXT,
        publisher TEXT,
        url TEXT,
        doi TEXT,
        position INTEGER,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')

    # NEW: Images table
    c.execute('''CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        image_url TEXT,
        image_hash TEXT UNIQUE,
        alt_text TEXT,
        caption TEXT,
        width INTEGER,
        height INTEGER,
        file_type TEXT,
        is_header INTEGER DEFAULT 0,
        is_downloaded INTEGER DEFAULT 0,
        local_path TEXT,
        position INTEGER,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )''')

    # Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_citations_article ON citations(article_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_bibliography_article ON bibliography(article_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_images_article ON images(article_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)')

    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")

def get_db():
    return sqlite3.connect(DB_PATH)

# ============================================================================
# CITATION EXTRACTION
# ============================================================================

# Patterns for academic citations
CITATION_PATTERNS = [
    # Author (Year) - e.g., "Smith (2004)" or "Smith et al. (2004)"
    (r'([A-Z][a-zé]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][a-zé]+)?)\s*\((\d{4}[a-z]?)\)', 'author_year'),

    # (Author Year) - e.g., "(Smith 2004)" or "(Smith & Jones 2004)"
    (r'\(([A-Z][a-zé]+(?:\s+(?:et\s+al\.?|&|and)\s+[A-Z][a-zé]+)?)\s+(\d{4}[a-z]?)\)', 'parenthetical'),

    # (Author, Year) - e.g., "(Smith, 2004)"
    (r'\(([A-Z][a-zé]+(?:\s+(?:et\s+al\.?|&|and)\s+[A-Z][a-zé]+)?),\s*(\d{4}[a-z]?)\)', 'parenthetical_comma'),

    # Year in brackets after quote - e.g., "quote" (2004)
    (r'[""]\s*\((\d{4})\)', 'year_after_quote'),
]

# Patterns for bibliography entries
BIBLIOGRAPHY_PATTERNS = [
    # Standard: Author (Year) Title...
    r'^([A-Z][^(]+)\((\d{4}[a-z]?)\)[,.]?\s*["""]?([^""",]+)',

    # Author, Initial. (Year). Title.
    r'^([A-Z][a-zé]+,\s+[A-Z]\.(?:\s*[A-Z]\.)*)\s*\((\d{4})\)[.,]?\s*(.+?)(?:\.|$)',

    # Journal format: "Title," Journal Vol(Issue)
    r'["""]([^"""]+)["""],?\s+([A-Za-z\s]+)\s+(\d+)(?:\s*\((\d+)\))?(?::\s*(\d+[-–]\d+))?',

    # With "in" for book chapters
    r'^([A-Z][^(]+)\((\d{4})\)[,.]?\s*["""]?([^"""]+)["""]?,?\s+in\s+(.+)',
]

def extract_citations(text):
    """Extract inline citations from text"""
    citations = []
    seen_hashes = set()

    for pattern, cite_type in CITATION_PATTERNS:
        for match in re.finditer(pattern, text):
            full_match = match.group(0)
            cite_hash = hashlib.md5(full_match.encode()).hexdigest()[:16]

            if cite_hash in seen_hashes:
                continue
            seen_hashes.add(cite_hash)

            citation = {
                'text': full_match,
                'hash': cite_hash,
                'type': cite_type,
                'author': match.group(1) if match.lastindex >= 1 else None,
                'year': match.group(2) if match.lastindex >= 2 else None,
                'position': match.start()
            }
            citations.append(citation)

    return citations

def extract_bibliography(text, soup=None):
    """Extract bibliography/reference list entries"""
    entries = []
    seen_hashes = set()

    # Look for reference section markers
    ref_markers = [
        'references', 'bibliography', 'works cited', 'sources',
        'literature', 'citations', 'notes'
    ]

    # Try to find reference section in text
    text_lower = text.lower()
    ref_start = -1

    for marker in ref_markers:
        idx = text_lower.rfind(marker)  # Find last occurrence
        if idx > ref_start:
            ref_start = idx

    # If we found a reference section, focus on that area
    if ref_start > 0:
        ref_text = text[ref_start:]
    else:
        ref_text = text

    # Split into potential entries (by newline or double space)
    lines = re.split(r'\n\s*\n|\n(?=[A-Z][a-z]+,?\s+[A-Z]\.)', ref_text)

    for i, line in enumerate(lines):
        line = line.strip()
        if len(line) < 20:
            continue

        # Check if it looks like a bibliography entry
        # Must start with author name pattern or have year in parentheses
        if not (re.match(r'^[A-Z][a-zé]+', line) or re.search(r'\(\d{4}\)', line)):
            continue

        # Must have a year
        year_match = re.search(r'\((\d{4}[a-z]?)\)', line)
        if not year_match:
            continue

        entry_hash = hashlib.md5(line.encode()).hexdigest()[:16]
        if entry_hash in seen_hashes:
            continue
        seen_hashes.add(entry_hash)

        # Parse the entry
        entry = parse_bibliography_entry(line)
        entry['hash'] = entry_hash
        entry['position'] = i
        entries.append(entry)

    return entries

def parse_bibliography_entry(text):
    """Parse a bibliography entry into components"""
    entry = {
        'text': text[:500],  # Limit length
        'author': None,
        'year': None,
        'title': None,
        'journal': None,
        'volume': None,
        'pages': None,
        'publisher': None,
        'url': None,
        'doi': None
    }

    # Extract year
    year_match = re.search(r'\((\d{4}[a-z]?)\)', text)
    if year_match:
        entry['year'] = year_match.group(1)

    # Extract author (before the year)
    if year_match:
        author_part = text[:year_match.start()].strip().rstrip(',.')
        entry['author'] = author_part[:200] if author_part else None

    # Extract title (in quotes or after year)
    title_match = re.search(r'["""]([^"""]+)["""]', text)
    if title_match:
        entry['title'] = title_match.group(1)[:300]
    elif year_match:
        after_year = text[year_match.end():].strip().lstrip('.,: ')
        # Title is usually first sentence after year
        title_end = after_year.find('.')
        if title_end > 0:
            entry['title'] = after_year[:title_end][:300]

    # Extract journal
    journal_patterns = [
        r'(?:in|In)\s+([A-Z][^,]+),',
        r',\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\d+',
        r'Journal of ([^,]+)',
    ]
    for pattern in journal_patterns:
        match = re.search(pattern, text)
        if match:
            entry['journal'] = match.group(1)[:200]
            break

    # Extract volume/pages
    vol_match = re.search(r'(\d+)\s*[:(]\s*(\d+[-–]\d+)', text)
    if vol_match:
        entry['volume'] = vol_match.group(1)
        entry['pages'] = vol_match.group(2)
    else:
        pages_match = re.search(r'pp?\.?\s*(\d+[-–]\d+)', text)
        if pages_match:
            entry['pages'] = pages_match.group(1)

    # Extract DOI
    doi_match = re.search(r'(10\.\d{4,}/[^\s]+)', text)
    if doi_match:
        entry['doi'] = doi_match.group(1)

    # Extract URL
    url_match = re.search(r'(https?://[^\s]+)', text)
    if url_match:
        entry['url'] = url_match.group(1)

    return entry

# ============================================================================
# IMAGE EXTRACTION
# ============================================================================

def extract_images(soup, base_url):
    """Extract images from HTML"""
    images = []
    seen_hashes = set()

    # Find all img tags
    for i, img in enumerate(soup.find_all('img')):
        src = img.get('src', '')
        if not src:
            continue

        # Resolve relative URLs
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = urljoin(base_url, src)
        elif not src.startswith('http'):
            src = urljoin(base_url, src)

        # Skip tiny tracking pixels and icons
        width = img.get('width', '')
        height = img.get('height', '')
        if width and height:
            try:
                if int(width) < 50 or int(height) < 50:
                    continue
            except:
                pass

        # Skip common non-content images
        skip_patterns = ['favicon', 'icon', 'button', 'logo', 'avatar', 'emoji',
                        'widget', 'badge', 'banner-ad', 'advertisement']
        if any(p in src.lower() for p in skip_patterns):
            continue

        img_hash = hashlib.md5(src.encode()).hexdigest()[:16]
        if img_hash in seen_hashes:
            continue
        seen_hashes.add(img_hash)

        # Get alt text and try to find caption
        alt_text = img.get('alt', '')
        caption = None

        # Look for figcaption or nearby text
        parent = img.parent
        if parent:
            figcaption = parent.find('figcaption')
            if figcaption:
                caption = figcaption.get_text(strip=True)[:500]
            else:
                # Check for text immediately after image
                next_sib = img.find_next_sibling()
                if next_sib and next_sib.name in ['span', 'div', 'p', 'em', 'i']:
                    potential_caption = next_sib.get_text(strip=True)
                    if len(potential_caption) < 200:
                        caption = potential_caption

        # Determine if this is a header image
        is_header = 'header' in src.lower() or i == 0

        # Determine file type
        file_type = None
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            if ext in src.lower():
                file_type = ext.replace('.', '')
                break

        image = {
            'url': src,
            'hash': img_hash,
            'alt_text': alt_text[:500] if alt_text else None,
            'caption': caption,
            'width': int(width) if width and width.isdigit() else None,
            'height': int(height) if height and height.isdigit() else None,
            'file_type': file_type,
            'is_header': 1 if is_header else 0,
            'position': i
        }
        images.append(image)

    return images

# ============================================================================
# MAIN EXTRACTION
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

    # Pattern 1: Quoted text
    for match in re.findall(r'["""]([^"""]{25,500})["""]', text, re.DOTALL):
        add_excerpt(match, 'quote')

    # Pattern 2: Text in italics
    for match in re.findall(r'\*([^*]{30,500})\*', text):
        add_excerpt(match, 'emphasis')

    # Pattern 3: Sentences containing FL terminology
    fl_pattern = '|'.join(re.escape(term) for term in FL_TERMS)
    for match in re.findall(rf'([A-Z][^.!?]*(?:{fl_pattern})[^.!?]*[.!?])', text):
        if len(match) < 400:
            add_excerpt(match, 'technical')

    # Pattern 4: English sentences
    for sentence in re.findall(r'([A-Z][a-z][^.!?]{40,250}[.!?])', text):
        ascii_ratio = sum(1 for c in sentence if ord(c) < 128) / len(sentence)
        if ascii_ratio > 0.95:
            add_excerpt(sentence, 'narrative')

    return excerpts

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

def process_url(url, verbose=True, extract_new_only=False):
    """Fetch and process a single URL with enhanced extraction"""
    if verbose:
        try:
            print(f"\nProcessing: {url}")
        except UnicodeEncodeError:
            print(f"\nProcessing: {url[:50]}...")

    conn = get_db()
    c = conn.cursor()

    # Check existing status
    c.execute("SELECT id, status, enhanced_at FROM articles WHERE url = ?", (url,))
    existing = c.fetchone()

    if existing:
        article_id = existing[0]
        if extract_new_only and existing[2]:  # Already enhanced
            if verbose:
                print("  Already enhanced, skipping")
            conn.close()
            return {'excerpts': 0, 'citations': 0, 'bibliography': 0, 'images': 0}

    # Fetch HTML
    html, error = fetch_url(url)
    if error:
        if verbose:
            print(f"  Error: {error}")
        conn.close()
        return {'excerpts': 0, 'citations': 0, 'bibliography': 0, 'images': 0}

    soup = BeautifulSoup(html, 'html.parser')

    # Extract metadata
    title = "Untitled"
    title_tag = soup.find('h3', class_='post-title') or soup.find('title')
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = re.sub(r'^Forgotten Languages Full:\s*', '', title)[:200]

    # Date from URL
    date_match = re.search(r'/(\d{4})/(\d{2})/', url)
    post_date = f"{date_match.group(1)}-{date_match.group(2)}" if date_match else None

    # Labels
    labels = [a.get_text(strip=True) for a in soup.find_all('a', rel='tag')]
    labels_str = json.dumps(labels)

    # Get main content
    post_body = soup.find('div', class_='post-body')
    if post_body:
        content = post_body.get_text(separator='\n')
    else:
        content = soup.get_text(separator='\n')

    if verbose:
        try:
            print(f"  Title: {title[:50]}...")
        except UnicodeEncodeError:
            print(f"  Title: [contains special characters]")

    # Extract all components
    excerpts = extract_english(content)
    citations = extract_citations(content)
    bibliography = extract_bibliography(content, soup)
    images = extract_images(soup, url)

    # Check for coordinates
    has_coords = 1 if re.search(r'[-+]?\d{1,3}\.\d{3,}', content) else 0

    if verbose:
        try:
            print(f"  Excerpts: {len(excerpts)}, Citations: {len(citations)}, "
                  f"Bibliography: {len(bibliography)}, Images: {len(images)}")
        except UnicodeEncodeError:
            pass  # Skip if encoding fails

    # Store/update article
    now = datetime.now().isoformat()

    if existing:
        c.execute("""UPDATE articles SET
                    title=?, post_date=?, labels=?,
                    excerpt_count=?, citation_count=?, image_count=?, bibliography_count=?,
                    has_coordinates=?, status='done', processed_at=?, enhanced_at=?
                    WHERE id=?""",
                  (title, post_date, labels_str, len(excerpts), len(citations),
                   len(images), len(bibliography), has_coords, now, now, article_id))
    else:
        c.execute("""INSERT INTO articles
                    (url, title, post_date, labels, excerpt_count, citation_count,
                     image_count, bibliography_count, has_coordinates, status, added_at, processed_at, enhanced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'done', ?, ?, ?)""",
                  (url, title, post_date, labels_str, len(excerpts), len(citations),
                   len(images), len(bibliography), has_coords, now, now, now))
        article_id = c.lastrowid

    # Store excerpts
    for i, exc in enumerate(excerpts):
        try:
            c.execute("""INSERT OR IGNORE INTO excerpts
                        (article_id, text, text_hash, word_count, category, position)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (article_id, exc['text'], exc['hash'], exc['words'], exc['category'], i))
        except:
            pass

    # Store citations
    for cite in citations:
        try:
            c.execute("""INSERT OR IGNORE INTO citations
                        (article_id, citation_text, citation_hash, citation_type,
                         author, year, position)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (article_id, cite['text'], cite['hash'], cite['type'],
                      cite.get('author'), cite.get('year'), cite['position']))
        except:
            pass

    # Store bibliography
    for bib in bibliography:
        try:
            c.execute("""INSERT OR IGNORE INTO bibliography
                        (article_id, entry_text, entry_hash, author, year, title,
                         journal, volume, pages, publisher, url, doi, position)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (article_id, bib['text'], bib['hash'], bib.get('author'),
                      bib.get('year'), bib.get('title'), bib.get('journal'),
                      bib.get('volume'), bib.get('pages'), bib.get('publisher'),
                      bib.get('url'), bib.get('doi'), bib['position']))
        except:
            pass

    # Store images
    for img in images:
        try:
            c.execute("""INSERT OR IGNORE INTO images
                        (article_id, image_url, image_hash, alt_text, caption,
                         width, height, file_type, is_header, position)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (article_id, img['url'], img['hash'], img.get('alt_text'),
                      img.get('caption'), img.get('width'), img.get('height'),
                      img.get('file_type'), img['is_header'], img['position']))
        except:
            pass

    conn.commit()
    conn.close()

    return {
        'excerpts': len(excerpts),
        'citations': len(citations),
        'bibliography': len(bibliography),
        'images': len(images)
    }

# ============================================================================
# BATCH PROCESSING
# ============================================================================

def process_batch(url_file, delay=1.5, verbose=True):
    """Process URLs from file"""
    with open(url_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    print(f"Processing {len(urls)} URLs...")

    totals = {'excerpts': 0, 'citations': 0, 'bibliography': 0, 'images': 0}

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}]", end="")
        result = process_url(url, verbose=verbose)

        for key in totals:
            totals[key] += result[key]

        if delay > 0 and i < len(urls):
            time.sleep(delay)

    print(f"\n{'='*60}")
    print(f"COMPLETE:")
    print(f"  Excerpts: {totals['excerpts']}")
    print(f"  Citations: {totals['citations']}")
    print(f"  Bibliography: {totals['bibliography']}")
    print(f"  Images: {totals['images']}")

    return totals

def reprocess_all(delay=1.5, verbose=True):
    """Re-process all known URLs to extract new data"""
    # First try to load URLs from existing data files
    urls = set()

    # From existing articles JSON
    articles_file = DATA_DIR / "fl_articles_raw.json"
    if articles_file.exists():
        with open(articles_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)
            for article in articles:
                if 'url' in article:
                    urls.add(article['url'])

    # From all_urls.txt
    urls_file = Path("all_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            for line in f:
                if line.strip():
                    urls.add(line.strip())

    # From existing database
    if Path(DB_PATH).exists():
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT url FROM articles")
        for row in c.fetchall():
            urls.add(row[0])
        conn.close()

    if not urls:
        print("No URLs found to reprocess")
        return

    print(f"Reprocessing {len(urls)} URLs for enhanced extraction...")

    totals = {'excerpts': 0, 'citations': 0, 'bibliography': 0, 'images': 0}

    for i, url in enumerate(sorted(urls), 1):
        print(f"\n[{i}/{len(urls)}]", end="")
        result = process_url(url, verbose=verbose, extract_new_only=False)

        for key in totals:
            totals[key] += result[key]

        if delay > 0 and i < len(urls):
            time.sleep(delay)

        # Save progress every 100 URLs
        if i % 100 == 0:
            print(f"\n  [Progress saved at {i} URLs]")

    print(f"\n{'='*60}")
    print(f"REPROCESSING COMPLETE:")
    for key, val in totals.items():
        print(f"  {key}: {val}")

# ============================================================================
# REPORTING & EXPORT
# ============================================================================

def show_status():
    """Display database statistics"""
    if not Path(DB_PATH).exists():
        print("Database not found. Run --init first.")
        return

    conn = get_db()
    c = conn.cursor()

    print("\n" + "="*60)
    print("FL ENHANCED DATABASE STATUS")
    print("="*60)

    # Article counts
    c.execute("SELECT COUNT(*) FROM articles")
    print(f"\nArticles: {c.fetchone()[0]}")

    c.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
    for status, count in c.fetchall():
        print(f"  - {status}: {count}")

    # Excerpts
    c.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM excerpts")
    exc_count, word_count = c.fetchone()
    print(f"\nExcerpts: {exc_count:,} ({word_count:,} words)")

    # Citations
    c.execute("SELECT COUNT(*) FROM citations")
    print(f"Citations: {c.fetchone()[0]:,}")

    c.execute("SELECT citation_type, COUNT(*) FROM citations GROUP BY citation_type")
    for cite_type, count in c.fetchall():
        print(f"  - {cite_type}: {count}")

    # Bibliography
    c.execute("SELECT COUNT(*) FROM bibliography")
    print(f"\nBibliography entries: {c.fetchone()[0]:,}")

    # Top cited authors
    c.execute("""SELECT author, COUNT(*) as cnt FROM bibliography
                 WHERE author IS NOT NULL
                 GROUP BY author ORDER BY cnt DESC LIMIT 10""")
    top_authors = c.fetchall()
    if top_authors:
        print("\nTop bibliography authors:")
        for author, cnt in top_authors:
            print(f"  [{cnt:3}] {author[:50]}")

    # Images
    c.execute("SELECT COUNT(*) FROM images")
    print(f"\nImages: {c.fetchone()[0]:,}")

    c.execute("SELECT file_type, COUNT(*) FROM images WHERE file_type IS NOT NULL GROUP BY file_type")
    for ftype, count in c.fetchall():
        print(f"  - {ftype}: {count}")

    conn.close()

def export_data(output_dir="data"):
    """Export all data to JSON and CSV files"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    conn = get_db()
    c = conn.cursor()

    # Export citations
    c.execute("""SELECT a.url, a.title, c.citation_text, c.citation_type, c.author, c.year
                 FROM citations c
                 JOIN articles a ON c.article_id = a.id
                 ORDER BY a.id, c.position""")
    citations = c.fetchall()

    with open(output_path / "fl_citations.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['url', 'article_title', 'citation_text', 'type', 'author', 'year'])
        writer.writerows(citations)
    print(f"Exported {len(citations)} citations to fl_citations.csv")

    # Export bibliography
    c.execute("""SELECT a.url, a.title, b.entry_text, b.author, b.year, b.title,
                        b.journal, b.volume, b.pages, b.doi
                 FROM bibliography b
                 JOIN articles a ON b.article_id = a.id
                 ORDER BY a.id, b.position""")
    bibs = c.fetchall()

    with open(output_path / "fl_bibliography.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['article_url', 'article_title', 'entry_text', 'author', 'year',
                        'title', 'journal', 'volume', 'pages', 'doi'])
        writer.writerows(bibs)
    print(f"Exported {len(bibs)} bibliography entries to fl_bibliography.csv")

    # Export images
    c.execute("""SELECT a.url, a.title, i.image_url, i.alt_text, i.caption,
                        i.file_type, i.is_header
                 FROM images i
                 JOIN articles a ON i.article_id = a.id
                 ORDER BY a.id, i.position""")
    imgs = c.fetchall()

    with open(output_path / "fl_images.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['article_url', 'article_title', 'image_url', 'alt_text',
                        'caption', 'file_type', 'is_header'])
        writer.writerows(imgs)
    print(f"Exported {len(imgs)} images to fl_images.csv")

    # Export combined JSON
    c.execute("SELECT * FROM articles")
    articles = []
    cols = [desc[0] for desc in c.description]
    for row in c.fetchall():
        article = dict(zip(cols, row))
        article_id = article['id']

        # Get citations for this article
        c.execute("SELECT citation_text, citation_type, author, year FROM citations WHERE article_id=?",
                  (article_id,))
        article['citations'] = [{'text': r[0], 'type': r[1], 'author': r[2], 'year': r[3]}
                               for r in c.fetchall()]

        # Get bibliography for this article
        c.execute("SELECT entry_text, author, year, title, journal FROM bibliography WHERE article_id=?",
                  (article_id,))
        article['bibliography'] = [{'text': r[0], 'author': r[1], 'year': r[2],
                                   'title': r[3], 'journal': r[4]} for r in c.fetchall()]

        # Get images for this article
        c.execute("SELECT image_url, alt_text, caption, file_type FROM images WHERE article_id=?",
                  (article_id,))
        article['images'] = [{'url': r[0], 'alt': r[1], 'caption': r[2], 'type': r[3]}
                            for r in c.fetchall()]

        articles.append(article)

    with open(output_path / "fl_enhanced_articles.json", 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(articles)} enhanced articles to fl_enhanced_articles.json")

    conn.close()

def download_images(output_dir="images", limit=None, delay=0.5):
    """Download all images to local directory"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    conn = get_db()
    c = conn.cursor()

    c.execute("""SELECT id, image_url, file_type FROM images
                 WHERE is_downloaded = 0
                 ORDER BY id""")
    images = c.fetchall()

    if limit:
        images = images[:limit]

    print(f"Downloading {len(images)} images...")

    downloaded = 0
    for i, (img_id, url, file_type) in enumerate(images, 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Generate filename
            ext = file_type or 'jpg'
            filename = f"fl_img_{img_id}.{ext}"
            filepath = output_path / filename

            with open(filepath, 'wb') as f:
                f.write(response.content)

            # Update database
            c.execute("UPDATE images SET is_downloaded=1, local_path=? WHERE id=?",
                     (str(filepath), img_id))
            conn.commit()

            downloaded += 1
            if i % 10 == 0:
                print(f"  Downloaded {i}/{len(images)}")

            time.sleep(delay)

        except Exception as e:
            print(f"  Error downloading {url}: {e}")

    conn.close()
    print(f"\nDownloaded {downloaded} images to {output_dir}/")

# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='FL Enhanced Extractor - Extract citations, bibliography, and images',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--url', metavar='URL', help='Process single URL')
    parser.add_argument('--batch', metavar='FILE', help='Process URLs from file')
    parser.add_argument('--reprocess', action='store_true',
                       help='Re-extract all known URLs with enhanced extraction')
    parser.add_argument('--status', action='store_true', help='Show database statistics')
    parser.add_argument('--export', action='store_true', help='Export all data to CSV/JSON')
    parser.add_argument('--download-images', action='store_true', help='Download all images locally')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between requests (seconds)')
    parser.add_argument('--quiet', action='store_true', help='Reduce output verbosity')

    args = parser.parse_args()

    if not HAS_DEPS:
        return

    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    # Initialize or ensure DB exists
    if args.init or not Path(DB_PATH).exists():
        init_database()
        if args.init:
            return

    if args.status:
        show_status()
        return

    if args.export:
        export_data()
        return

    if args.download_images:
        download_images(delay=args.delay)
        return

    if args.url:
        result = process_url(args.url, verbose=not args.quiet)
        print(f"\nResult: {result}")
        return

    if args.batch:
        process_batch(args.batch, delay=args.delay, verbose=not args.quiet)
        return

    if args.reprocess:
        reprocess_all(delay=args.delay, verbose=not args.quiet)
        return

    # Default: show status
    show_status()

if __name__ == '__main__':
    main()
