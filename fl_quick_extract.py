import requests
from bs4 import BeautifulSoup
import time
import re
import json

BASE = "https://forgottenlanguages-full.forgottenlanguages.org"
TOPICS = ["DP-2147", "Denebian probe", "Giselian", "MilOrb", "DOLYN", "LyAV"]

results = []
for topic in TOPICS:
    print(f"Searching: {topic}")
    r = requests.get(f"{BASE}/search?q={topic.replace(' ', '+')}", timeout=30)
    urls = set(re.findall(r'https://forgottenlanguages-full[^"\'>\s]+/\d{4}/\d{2}/[^"\'>\s]+\.html', r.text))
    print(f"  Found {len(urls)} URLs")
    for url in list(urls)[:3]:  # First 3 per topic as test
        time.sleep(1)
        print(f"  Fetching: {url}")
        page = requests.get(url, timeout=30)
        soup = BeautifulSoup(page.text, 'html.parser')
        title = soup.find('h3', class_='post-title')
        title = title.get_text(strip=True) if title else "Unknown"
        results.append({"topic": topic, "url": url, "title": title})

print(f"\n=== EXTRACTED {len(results)} ARTICLES ===")
for r in results:
    print(f"{r['topic']}: {r['title']}")

with open("fl_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved to fl_test_results.json")
