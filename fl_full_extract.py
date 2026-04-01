#!/usr/bin/env python3
"""
Forgotten Languages Full Extractor
Run in Claude Code for complete FL extraction
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
import os
from datetime import datetime

BASE_URL = "https://forgottenlanguages-full.forgottenlanguages.org"
OUTPUT_DIR = "fl_extracted"
DELAY = 1.5  # seconds between requests

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Index pages containing article links
INDEX_PAGES = [
    "/p/blog-page_22.html",
    "/p/blog-page_19.html",
    "/p/books-by-title-2008-2019.html",
    "/p/fl-sitemap.html",
    "/p/books-2022-2024.html",
    "/p/books-2021.html",
]

# Priority search terms (kept for prioritization in ordering later)
PRIORITY_TOPICS = [
    "DP-2147", "Denebian", "Giselian", "MilOrb", "DOLYN", "LyAV",
    "Cassini Diskus", "NodeSpaces", "XViS", "Queltron", "PSV",
    "South Atlantic Anomaly", "Year 3100", "SV17q", "beacon",
    "Defense", "MASINT", "USO", "transmedium"
]

# Labels to crawl via /search/label/ (safer than /search?q=)
LABELS = [
    "Defense",
    "Cassini Diskus",
    "NodeSpaces",
    "MilOrb",
    "DOLYN",
    "SV17q",
    "MASINT",
    "USO",
    "transmedium",
    "South Atlantic Anomaly",
]

class FLExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })
        self.urls = set()
        self.articles = []
        self.excerpts = []
        self.failed = []

    def fetch(self, url):
        try:
            time.sleep(DELAY)
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  ERROR: {e}")
            self.failed.append(url)
            return None

    def discover_from_label(self, label, max_pages=60):
        """
        Crawl /search/label/<label> pages, following 'Older Posts' pagination.
        Returns a set of post URLs discovered.
        """
        found_all = set()
        label_slug = label.replace(" ", "%20")
        next_url = f"{BASE_URL}/search/label/{label_slug}?max-results=20"
        pages = 0

        while next_url and pages < max_pages:
            pages += 1
            print(f"  Label crawl ({label}) page {pages}: {next_url[-60:]}")
            html = self.fetch(next_url)
            if not html:
                break

            # Extract post URLs from this page (same regex as everywhere else)
            found = set(re.findall(
                r'https://forgottenlanguages-full[^"\'<>\s]+/\d{4}/\d{2}/[^"\'<>\s]+\.html',
                html
            ))
            found_all.update(found)

            # Find the "Older Posts" link for pagination (Blogger)
            soup = BeautifulSoup(html, "html.parser")
            older = soup.find("a", class_="blog-pager-older-link")
            next_url = older["href"] if (older and older.get("href")) else None

        return found_all

    def discover_urls(self):
        print("=" * 60)
        print("PHASE 1: DISCOVERING URLs")
        print("=" * 60)

        # From index pages
        for idx_page in INDEX_PAGES:
            url = BASE_URL + idx_page
            print(f"Scanning: {idx_page}")
            html = self.fetch(url)
            if html:
                found = set(re.findall(r'https://forgottenlanguages-full[^"\'<>\s]+/\d{4}/\d{2}/[^"\'<>\s]+\.html', html))
                print(f"  Found: {len(found)} URLs")
                self.urls.update(found)

        # From label pages (safer than /search?q=)
        for label in LABELS:
            print(f"Crawling label: {label}")
            found = self.discover_from_label(label, max_pages=60)
            print(f"  Found: {len(found)} URLs")
            self.urls.update(found)

        # From monthly archives (2020-2025)
        for year in range(2020, 2026):
            for month in range(1, 13):
                archive_url = f"{BASE_URL}/{year}/{month:02d}/"
                print(f"Archive: {year}/{month:02d}")
                html = self.fetch(archive_url)
                if html:
                    found = set(re.findall(r'https://forgottenlanguages-full[^"\'<>\s]+/\d{4}/\d{2}/[^"\'<>\s]+\.html', html))
                    print(f"  Found: {len(found)} URLs")
                    self.urls.update(found)

        print(f"\nTOTAL UNIQUE URLs: {len(self.urls)}")

        # Save URL list
        with open(f"{OUTPUT_DIR}/all_urls.txt", "w") as f:
            for u in sorted(self.urls):
                f.write(u + "\n")

    def is_english(self, text):
        eng_words = {'the','is','are','was','were','be','have','has','had','do','does',
                     'will','would','could','should','a','an','and','or','but','if','when',
                     'at','by','for','with','about','to','from','in','on','that','this',
                     'we','they','you','it','not','no','can','all','been','being','more'}
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

        # Quoted text
        for quote in re.findall(r'"([^"]{25,})"', text):
            if self.is_english(quote):
                excerpts.append({'type': 'quote', 'text': quote.strip()})

        # English sentences
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

        # Date from URL
        date_match = re.search(r'/(\d{4})/(\d{2})/', url)
        date = f"{date_match.group(1)}-{date_match.group(2)}" if date_match else None

        # Labels
        labels = [a.get_text(strip=True) for a in soup.find_all('a', rel='tag')]

        # Coordinates
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
            'coordinates': list(set(coords))
        }

    def process_articles(self):
        print("\n" + "=" * 60)
        print("PHASE 2: EXTRACTING CONTENT")
        print("=" * 60)

        url_list = sorted(self.urls)
        total = len(url_list)

        for i, url in enumerate(url_list, 1):
            print(f"[{i}/{total}] {url[-50:]}")
            html = self.fetch(url)
            if not html:
                continue

            meta = self.extract_metadata(html, url)
            eng = self.extract_english(html)

            meta['excerpt_count'] = len(eng)
            self.articles.append(meta)

            for j, e in enumerate(eng):
                e['url'] = url
                e['title'] = meta['title']
                e['position'] = j + 1
                self.excerpts.append(e)

            # Save progress every 100
            if i % 100 == 0:
                self.save()
                print(f"  [Saved progress: {len(self.articles)} articles, {len(self.excerpts)} excerpts]")

        self.save()

    def save(self):
        with open(f"{OUTPUT_DIR}/articles.json", "w") as f:
            json.dump(self.articles, f, indent=2)

        with open(f"{OUTPUT_DIR}/excerpts.csv", "w", newline='', encoding='utf-8') as f:
            if self.excerpts:
                w = csv.DictWriter(f, fieldnames=['url', 'title', 'type', 'text', 'position'])
                w.writeheader()
                w.writerows(self.excerpts)

        with open(f"{OUTPUT_DIR}/failed.txt", "w") as f:
            for u in self.failed:
                f.write(u + "\n")

    def run(self):
        print("=" * 60)
        print("FORGOTTEN LANGUAGES FULL EXTRACTION")
        print(f"Started: {datetime.now()}")
        print("=" * 60)

        self.discover_urls()
        self.process_articles()

        print("\n" + "=" * 60)
        print("COMPLETE")
        print("=" * 60)
        print(f"URLs discovered: {len(self.urls)}")
        print(f"Articles processed: {len(self.articles)}")
        print(f"Excerpts extracted: {len(self.excerpts)}")
        print(f"Failed fetches: {len(self.failed)}")
        print(f"\nOutput in: {OUTPUT_DIR}/")
        print(f"  - all_urls.txt")
        print(f"  - articles.json")
        print(f"  - excerpts.csv")
        print(f"  - failed.txt")

if __name__ == "__main__":
    FLExtractor().run()
