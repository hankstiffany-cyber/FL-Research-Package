#!/usr/bin/env python3
"""
FL Incremental Update
Discovers and extracts only NEW articles since the last extraction.
Merges results into existing data files.
"""

import sys
import io
import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
import os
from datetime import datetime

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = "https://forgottenlanguages-full.forgottenlanguages.org"
DATA_DIR = "data"
DELAY = 1.5

# Labels to crawl for new articles
LABELS = [
    "Defense", "Cassini Diskus", "NodeSpaces", "MilOrb", "DOLYN",
    "SV17q", "MASINT", "USO", "transmedium", "South Atlantic Anomaly",
    "Religion", "Philosophy of Language", "Queltron", "XViS", "PSV",
]

INDEX_PAGES = [
    "/p/blog-page_22.html",
    "/p/blog-page_19.html",
    "/p/fl-sitemap.html",
    "/p/books-2022-2024.html",
]


class FLIncrementalUpdater:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })
        self.existing_urls = set()
        self.new_urls = set()
        self.new_articles = []
        self.new_excerpts = []
        self.failed = []

    def fetch(self, url):
        try:
            time.sleep(DELAY)
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  ERROR fetching {url}: {e}")
            self.failed.append(url)
            return None

    def load_existing_urls(self):
        """Load all known URLs from existing data."""
        # From all_urls.txt
        if os.path.exists("all_urls.txt"):
            with open("all_urls.txt") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.existing_urls.add(line)

        # From articles JSON
        articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
        if os.path.exists(articles_path):
            with open(articles_path, encoding="utf-8") as f:
                articles = json.load(f)
                for a in articles:
                    self.existing_urls.add(a["url"])

        # From new_urls.txt (these are known but may not be extracted yet)
        if os.path.exists("new_urls.txt"):
            with open("new_urls.txt") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.new_urls.add(line)

        print(f"Loaded {len(self.existing_urls)} existing URLs")
        print(f"Loaded {len(self.new_urls)} URLs from new_urls.txt")

    def extract_post_urls(self, html):
        """Extract FL post URLs from HTML content."""
        return set(re.findall(
            r'https://forgottenlanguages-full[^"\'<>\s]+/\d{4}/\d{2}/[^"\'<>\s]+\.html',
            html
        ))

    def discover_from_label(self, label, max_pages=60):
        """Crawl /search/label/<label> pages for new URLs."""
        found = set()
        label_slug = label.replace(" ", "%20")
        next_url = f"{BASE_URL}/search/label/{label_slug}?max-results=20"
        pages = 0

        while next_url and pages < max_pages:
            pages += 1
            print(f"  Label '{label}' page {pages}")
            html = self.fetch(next_url)
            if not html:
                break

            page_urls = self.extract_post_urls(html)
            found.update(page_urls)

            # Check if any URLs on this page are new
            new_on_page = page_urls - self.existing_urls
            if not new_on_page and pages > 2:
                # All URLs on this page are known - stop crawling deeper
                print(f"    No new URLs found, stopping label crawl")
                break

            soup = BeautifulSoup(html, "html.parser")
            older = soup.find("a", class_="blog-pager-older-link")
            next_url = older["href"] if (older and older.get("href")) else None

        return found

    def discover_from_archives(self, start_year=2025, start_month=12):
        """Crawl monthly archives from a start date to present."""
        found = set()
        now = datetime.now()
        year, month = start_year, start_month

        while (year < now.year) or (year == now.year and month <= now.month):
            archive_url = f"{BASE_URL}/{year}/{month:02d}/"
            print(f"  Archive {year}/{month:02d}")
            html = self.fetch(archive_url)
            if html:
                page_urls = self.extract_post_urls(html)
                found.update(page_urls)
                new_count = len(page_urls - self.existing_urls)
                print(f"    Found {len(page_urls)} URLs ({new_count} new)")

            month += 1
            if month > 12:
                month = 1
                year += 1

        return found

    def discover_from_index_pages(self):
        """Check index/sitemap pages for any new URLs."""
        found = set()
        for idx_page in INDEX_PAGES:
            url = BASE_URL + idx_page
            print(f"  Index page: {idx_page}")
            html = self.fetch(url)
            if html:
                page_urls = self.extract_post_urls(html)
                found.update(page_urls)

        return found

    def discover_from_homepage(self):
        """Check the homepage and recent posts feed."""
        found = set()
        print("  Homepage")
        html = self.fetch(BASE_URL)
        if html:
            found.update(self.extract_post_urls(html))

        # Blogger feeds (recent posts)
        feed_url = f"{BASE_URL}/feeds/posts/default?max-results=50&alt=json"
        print("  Atom feed (recent 50)")
        html = self.fetch(feed_url)
        if html:
            found.update(self.extract_post_urls(html))

        return found

    def discover_new_urls(self):
        """Run all discovery methods and find URLs not in existing data."""
        print("=" * 60)
        print("PHASE 1: DISCOVERING NEW URLs")
        print("=" * 60)

        all_discovered = set()

        # 1. Homepage and feed
        print("\n[1/4] Checking homepage and feed...")
        all_discovered.update(self.discover_from_homepage())

        # 2. Monthly archives (Dec 2025 through present)
        print("\n[2/4] Crawling monthly archives (Dec 2025 - present)...")
        all_discovered.update(self.discover_from_archives(2025, 12))

        # 3. Label pages (stop early when no new URLs found)
        print("\n[3/4] Crawling label pages...")
        for label in LABELS:
            print(f"  Crawling label: {label}")
            all_discovered.update(self.discover_from_label(label, max_pages=10))

        # 4. Index pages
        print("\n[4/4] Checking index pages...")
        all_discovered.update(self.discover_from_index_pages())

        # Filter to only truly new URLs
        self.new_urls.update(all_discovered - self.existing_urls)

        print(f"\nTotal discovered: {len(all_discovered)}")
        print(f"New URLs found: {len(self.new_urls)}")

        if self.new_urls:
            print("\nNew articles:")
            for url in sorted(self.new_urls):
                print(f"  {url}")

        return self.new_urls

    def is_english(self, text):
        eng_words = {
            'the', 'is', 'are', 'was', 'were', 'be', 'have', 'has', 'had', 'do',
            'does', 'will', 'would', 'could', 'should', 'a', 'an', 'and', 'or',
            'but', 'if', 'when', 'at', 'by', 'for', 'with', 'about', 'to', 'from',
            'in', 'on', 'that', 'this', 'we', 'they', 'you', 'it', 'not', 'no',
            'can', 'all', 'been', 'being', 'more',
        }
        words = set(text.lower().split())
        matches = len(words & eng_words)
        return matches >= 3 and matches / max(len(words), 1) > 0.12

    def extract_english(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('div', class_='post-body')
        if not body:
            return []

        text = body.get_text(separator=' ', strip=True)
        excerpts = []

        for quote in re.findall(r'"([^"]{25,})"', text):
            if self.is_english(quote):
                excerpts.append({'type': 'quote', 'text': quote.strip()})

        for sent in re.split(r'[.!?]+', text):
            sent = sent.strip()
            if len(sent) > 60 and self.is_english(sent):
                if not any(sent in e['text'] or e['text'] in sent for e in excerpts):
                    excerpts.append({'type': 'sentence', 'text': sent})

        return excerpts

    def extract_metadata(self, html, url):
        soup = BeautifulSoup(html, 'html.parser')

        title_el = soup.find('h3', class_='post-title') or soup.find('title')
        title = title_el.get_text(strip=True) if title_el else "Unknown"

        date_match = re.search(r'/(\d{4})/(\d{2})/', url)
        date = f"{date_match.group(1)}-{date_match.group(2)}" if date_match else None

        labels = [a.get_text(strip=True) for a in soup.find_all('a', rel='tag')]

        text = soup.get_text()
        coords = []
        coords.extend(re.findall(r'[-+]?\d{1,3}\.\d{3,},\s*[-+]?\d{1,3}\.\d{3,}', text))
        coords.extend(re.findall(r'\d{1,3}[°]\d{1,2}[\'\"]\d{1,2}[.\d]*[\"\'"]?[NSEW]', text))
        coords.extend(re.findall(r'[+-]\d{3}[+-]\d{3}', text))

        return {
            'url': url,
            'title': title,
            'date': date,
            'labels': labels,
            'coordinates': list(set(coords)),
        }

    def extract_new_articles(self):
        """Extract content from all new URLs."""
        if not self.new_urls:
            print("\nNo new articles to extract.")
            return

        print("\n" + "=" * 60)
        print(f"PHASE 2: EXTRACTING {len(self.new_urls)} NEW ARTICLES")
        print("=" * 60)

        url_list = sorted(self.new_urls)
        for i, url in enumerate(url_list, 1):
            print(f"[{i}/{len(url_list)}] {url.split('/')[-1]}")
            html = self.fetch(url)
            if not html:
                continue

            meta = self.extract_metadata(html, url)
            eng = self.extract_english(html)

            meta['excerpt_count'] = len(eng)
            self.new_articles.append(meta)

            for j, e in enumerate(eng):
                e['url'] = url
                e['title'] = meta['title']
                e['position'] = j + 1
                self.new_excerpts.append(e)

            print(f"  Title: {meta['title']}")
            print(f"  Labels: {meta['labels']}")
            print(f"  Excerpts: {len(eng)}")

    def merge_into_existing(self):
        """Merge new data into existing data files."""
        if not self.new_articles:
            print("\nNo new articles to merge.")
            return

        print("\n" + "=" * 60)
        print("PHASE 3: MERGING INTO EXISTING DATA")
        print("=" * 60)

        # 1. Merge into fl_articles_raw.json
        articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
        existing_articles = []
        if os.path.exists(articles_path):
            with open(articles_path, encoding="utf-8") as f:
                existing_articles = json.load(f)

        existing_article_urls = {a['url'] for a in existing_articles}
        added_articles = 0
        for article in self.new_articles:
            if article['url'] not in existing_article_urls:
                existing_articles.append(article)
                added_articles += 1

        # Sort by date then URL
        existing_articles.sort(key=lambda a: (a.get('date', ''), a.get('url', '')))

        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump(existing_articles, f, indent=2, ensure_ascii=False)
        print(f"  Articles: added {added_articles} (total: {len(existing_articles)})")

        # 2. Merge into fl_excerpts_raw.csv
        excerpts_path = os.path.join(DATA_DIR, "fl_excerpts_raw.csv")
        existing_excerpt_keys = set()
        existing_rows = []

        if os.path.exists(excerpts_path):
            with open(excerpts_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_rows.append(row)
                    existing_excerpt_keys.add((row.get('url', ''), row.get('text', '')))

        added_excerpts = 0
        for exc in self.new_excerpts:
            key = (exc.get('url', ''), exc.get('text', ''))
            if key not in existing_excerpt_keys:
                existing_rows.append(exc)
                added_excerpts += 1

        fieldnames = ['url', 'title', 'type', 'text', 'position']
        with open(excerpts_path, "w", newline='', encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            w.writeheader()
            w.writerows(existing_rows)
        print(f"  Excerpts: added {added_excerpts} (total: {len(existing_rows)})")

        # 3. Update all_urls.txt
        all_urls = set(self.existing_urls)
        all_urls.update(url for a in self.new_articles for url in [a['url']])
        with open("all_urls.txt", "w") as f:
            for url in sorted(all_urls):
                f.write(url + "\n")
        print(f"  all_urls.txt: {len(all_urls)} total URLs")

        # 4. Update new_urls.txt (clear processed URLs)
        remaining_new = self.new_urls - {a['url'] for a in self.new_articles}
        with open("new_urls.txt", "w") as f:
            for url in sorted(remaining_new):
                f.write(url + "\n")
        if remaining_new:
            print(f"  new_urls.txt: {len(remaining_new)} URLs remaining (failed to extract)")
        else:
            print(f"  new_urls.txt: cleared (all processed)")

        # 5. Update keyword index
        keyword_path = os.path.join(DATA_DIR, "fl_keyword_index.json")
        if os.path.exists(keyword_path):
            with open(keyword_path, encoding="utf-8") as f:
                keyword_index = json.load(f)

            for article in self.new_articles:
                for label in article.get('labels', []):
                    label_lower = label.lower()
                    if label_lower not in keyword_index:
                        keyword_index[label_lower] = []
                    if article['url'] not in keyword_index[label_lower]:
                        keyword_index[label_lower].append(article['url'])

            with open(keyword_path, "w", encoding="utf-8") as f:
                json.dump(keyword_index, f, indent=2, ensure_ascii=False)
            print(f"  Keyword index: updated")

    def run(self):
        print("=" * 60)
        print("FL INCREMENTAL UPDATE")
        print(f"Started: {datetime.now()}")
        print("=" * 60)

        self.load_existing_urls()
        self.discover_new_urls()
        self.extract_new_articles()
        self.merge_into_existing()

        print("\n" + "=" * 60)
        print("UPDATE COMPLETE")
        print("=" * 60)
        print(f"New URLs discovered: {len(self.new_urls)}")
        print(f"Articles extracted:  {len(self.new_articles)}")
        print(f"Excerpts extracted:  {len(self.new_excerpts)}")
        print(f"Failed fetches:      {len(self.failed)}")

        if self.failed:
            print(f"\nFailed URLs:")
            for url in self.failed:
                print(f"  {url}")

        return {
            'new_urls': len(self.new_urls),
            'articles': len(self.new_articles),
            'excerpts': len(self.new_excerpts),
            'failed': len(self.failed),
        }


if __name__ == "__main__":
    updater = FLIncrementalUpdater()
    updater.run()
