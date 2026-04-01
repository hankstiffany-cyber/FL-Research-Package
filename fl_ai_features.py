#!/usr/bin/env python3
"""
FL AI FEATURES MODULE
======================
Smart research features for the Forgotten Languages database.

Features:
    1. Reading List Generator - Curated article pathways by topic
    2. Semantic Search - Embedding-based similarity search
    3. Network Graph - Article connection mapping
    4. Topic Timeline - Keyword evolution tracking
    5. Article Importance Scoring - Rank articles by research value

Usage:
    # Generate embeddings (one-time setup)
    python fl_ai_features.py --build-embeddings

    # Generate a reading list
    python fl_ai_features.py --reading-list "MilOrb drones"

    # Find similar articles
    python fl_ai_features.py --similar "https://..."

    # Build network graph
    python fl_ai_features.py --network

Requirements:
    pip install sentence-transformers numpy scikit-learn
"""

import json
import csv
import re
import pickle
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import math

# Optional imports - graceful degradation
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")
CACHE_DIR = Path("cache")
EMBEDDINGS_FILE = CACHE_DIR / "fl_embeddings.pkl"
NETWORK_FILE = CACHE_DIR / "fl_network.json"
IMPORTANCE_FILE = CACHE_DIR / "fl_importance.json"

# FL-specific keywords for importance scoring
FL_PRIORITY_TERMS = {
    'high': ['MilOrb', 'PSV', 'DOLYN', 'SV17q', 'Giselian', 'coordinates', 'DENIED',
             'drone', 'kinetic', 'transmedium', 'SAA', 'AUTEC', 'Cassini Diskus'],
    'medium': ['XViS', 'LyAV', 'Denebian', 'NodeSpaces', 'Presence', 'UAP', 'USO',
               'Sienna', 'Akrij', 'Tangent', 'Graphium', 'NDE', 'consciousness'],
    'low': ['dream', 'contact', 'satellite', 'magnetic', 'anomaly', 'disclosure']
}

# Topic categories for reading lists
TOPIC_CATEGORIES = {
    'defense': ['MilOrb', 'drone', 'kinetic', 'DOLYN', 'Defense', 'MASINT', 'directed energy'],
    'vehicles': ['PSV', 'Sienna', 'Akrij', 'Presence', 'Tangent', 'Graphium', 'transmedium'],
    'entities': ['Giselian', 'Denebian', 'LyAV', 'XViS', 'contact'],
    'locations': ['Cassini Diskus', 'coordinates', 'AUTEC', 'Thule', 'Jan Mayen', 'SAA', 'Yulara'],
    'organizations': ['SV17q', 'SV06n', 'SV09n', 'DENIED', 'NodeSpaces'],
    'phenomena': ['NDE', 'consciousness', 'dream', 'UAP', 'USO', 'anomaly']
}

# ============================================================================
# DATA LOADING
# ============================================================================

def load_articles():
    """Load article metadata"""
    articles_file = DATA_DIR / "fl_articles_raw.json"
    if articles_file.exists():
        with open(articles_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_excerpts():
    """Load excerpts as list of dicts"""
    excerpts_file = DATA_DIR / "fl_excerpts_raw.csv"
    if not excerpts_file.exists():
        return []

    excerpts = []
    with open(excerpts_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            excerpts.append(row)
    return excerpts

def load_keyword_index():
    """Load keyword to article mapping"""
    index_file = DATA_DIR / "fl_keyword_index.json"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_statistics():
    """Load pre-computed statistics"""
    stats_file = DATA_DIR / "fl_statistics.json"
    if stats_file.exists():
        with open(stats_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# ============================================================================
# 1. READING LIST GENERATOR
# ============================================================================

class ReadingListGenerator:
    """Generate curated reading lists based on topics and importance"""

    def __init__(self):
        self.articles = load_articles()
        self.excerpts = load_excerpts()
        self.keyword_index = load_keyword_index()

        # Build article lookup
        self.article_by_url = {a['url']: a for a in self.articles}

        # Build excerpt lookup by URL
        self.excerpts_by_url = defaultdict(list)
        for exc in self.excerpts:
            self.excerpts_by_url[exc.get('url', '')].append(exc)

        # Compute importance scores after excerpts_by_url is built
        self.importance_scores = self._load_or_compute_importance()

    def _load_or_compute_importance(self):
        """Load cached importance scores or compute them"""
        if IMPORTANCE_FILE.exists():
            with open(IMPORTANCE_FILE, 'r') as f:
                return json.load(f)
        return self._compute_importance_scores()

    def _compute_importance_scores(self):
        """Compute importance score for each article"""
        scores = {}

        for article in self.articles:
            url = article.get('url', '')
            score = 0

            # Score based on labels
            labels = article.get('labels', [])
            for label in labels:
                if label in ['Defense', 'Cassini Diskus', 'NodeSpaces']:
                    score += 10
                elif label in ['DOLYN', 'MilOrb']:
                    score += 15

            # Score based on excerpt content
            article_excerpts = self.excerpts_by_url.get(url, [])
            for exc in article_excerpts:
                text = exc.get('text', '').lower()

                for term in FL_PRIORITY_TERMS['high']:
                    if term.lower() in text:
                        score += 5
                for term in FL_PRIORITY_TERMS['medium']:
                    if term.lower() in text:
                        score += 2
                for term in FL_PRIORITY_TERMS['low']:
                    if term.lower() in text:
                        score += 1

            # Score based on excerpt count (more content = more important)
            score += min(len(article_excerpts) * 0.5, 10)

            # Score based on coordinates
            if article.get('coordinates'):
                score += 15

            scores[url] = score

        # Cache the scores
        CACHE_DIR.mkdir(exist_ok=True)
        with open(IMPORTANCE_FILE, 'w') as f:
            json.dump(scores, f)

        return scores

    def generate_topic_reading_list(self, topic, max_articles=20, difficulty='all'):
        """
        Generate a reading list for a specific topic.

        Args:
            topic: Topic name or keywords
            max_articles: Maximum articles to include
            difficulty: 'beginner', 'intermediate', 'advanced', or 'all'

        Returns:
            List of articles with reading order and descriptions
        """
        topic_lower = topic.lower()

        # Find relevant category
        category_keywords = []
        for cat, keywords in TOPIC_CATEGORIES.items():
            if topic_lower in cat or any(k.lower() in topic_lower for k in keywords):
                category_keywords.extend(keywords)

        # If no category match, use the topic as keyword
        if not category_keywords:
            category_keywords = [topic]

        # Find articles matching these keywords
        matching_articles = []
        seen_urls = set()

        # Search keyword index
        for keyword in category_keywords:
            if keyword in self.keyword_index:
                for entry in self.keyword_index[keyword]:
                    url = entry.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        article = self.article_by_url.get(url, {})
                        if article:
                            matching_articles.append({
                                'url': url,
                                'title': article.get('title', 'Untitled'),
                                'date': article.get('date', ''),
                                'labels': article.get('labels', []),
                                'importance': self.importance_scores.get(url, 0),
                                'matched_keyword': keyword,
                                'excerpt_preview': entry.get('text', '')[:200]
                            })

        # Also search excerpts directly
        for exc in self.excerpts:
            text = exc.get('text', '').lower()
            url = exc.get('url', '')

            if url in seen_urls:
                continue

            for keyword in category_keywords:
                if keyword.lower() in text:
                    seen_urls.add(url)
                    article = self.article_by_url.get(url, {})
                    if article:
                        matching_articles.append({
                            'url': url,
                            'title': article.get('title', exc.get('title', 'Untitled')),
                            'date': article.get('date', ''),
                            'labels': article.get('labels', []),
                            'importance': self.importance_scores.get(url, 0),
                            'matched_keyword': keyword,
                            'excerpt_preview': exc.get('text', '')[:200]
                        })
                    break

        # Sort by importance
        matching_articles.sort(key=lambda x: x['importance'], reverse=True)

        # Assign difficulty levels based on position
        total = len(matching_articles)
        for i, article in enumerate(matching_articles):
            if i < total * 0.2:
                article['difficulty'] = 'beginner'
                article['reading_order'] = i + 1
            elif i < total * 0.6:
                article['difficulty'] = 'intermediate'
                article['reading_order'] = i + 1
            else:
                article['difficulty'] = 'advanced'
                article['reading_order'] = i + 1

        # Filter by difficulty if specified
        if difficulty != 'all':
            matching_articles = [a for a in matching_articles if a['difficulty'] == difficulty]

        return matching_articles[:max_articles]

    def generate_starter_reading_list(self, max_articles=15):
        """Generate a 'start here' reading list for new researchers"""

        # Get top articles by importance across all categories
        all_articles = []

        for article in self.articles:
            url = article.get('url', '')
            importance = self.importance_scores.get(url, 0)

            if importance > 10:  # Only include significant articles
                all_articles.append({
                    'url': url,
                    'title': article.get('title', 'Untitled'),
                    'date': article.get('date', ''),
                    'labels': article.get('labels', []),
                    'importance': importance,
                    'category': self._categorize_article(article)
                })

        # Sort by importance
        all_articles.sort(key=lambda x: x['importance'], reverse=True)

        # Ensure diversity - pick from different categories
        selected = []
        categories_seen = set()

        for article in all_articles:
            cat = article['category']
            if cat not in categories_seen or len(selected) < 5:
                selected.append(article)
                categories_seen.add(cat)
                article['reading_order'] = len(selected)

            if len(selected) >= max_articles:
                break

        return selected

    def _categorize_article(self, article):
        """Determine primary category for an article"""
        labels = article.get('labels', [])

        if 'Defense' in labels or 'MilOrb' in str(labels):
            return 'defense'
        elif 'Cassini Diskus' in labels:
            return 'locations'
        elif 'NodeSpaces' in labels:
            return 'organizations'
        elif any(l in labels for l in ['Religion', 'Theosophy', 'Sufism']):
            return 'philosophy'
        else:
            return 'general'

    def generate_connection_list(self, start_url, max_depth=2, max_articles=20):
        """
        Generate a reading list based on connections from a starting article.
        Follows keyword connections to related articles.
        """
        visited = set()
        reading_list = []
        queue = [(start_url, 0)]  # (url, depth)

        while queue and len(reading_list) < max_articles:
            url, depth = queue.pop(0)

            if url in visited or depth > max_depth:
                continue

            visited.add(url)
            article = self.article_by_url.get(url)

            if not article:
                continue

            # Add to reading list
            reading_list.append({
                'url': url,
                'title': article.get('title', 'Untitled'),
                'date': article.get('date', ''),
                'labels': article.get('labels', []),
                'importance': self.importance_scores.get(url, 0),
                'depth': depth,
                'reading_order': len(reading_list) + 1
            })

            # Find connected articles through shared keywords
            article_excerpts = self.excerpts_by_url.get(url, [])
            found_keywords = set()

            for exc in article_excerpts:
                text = exc.get('text', '')
                for keyword in self.keyword_index.keys():
                    if keyword.lower() in text.lower():
                        found_keywords.add(keyword)

            # Add connected articles to queue
            for keyword in found_keywords:
                for entry in self.keyword_index.get(keyword, [])[:3]:  # Limit per keyword
                    connected_url = entry.get('url', '')
                    if connected_url and connected_url not in visited:
                        queue.append((connected_url, depth + 1))

        return reading_list

# ============================================================================
# 2. SEMANTIC SEARCH
# ============================================================================

class SemanticSearch:
    """Embedding-based semantic search for finding similar content"""

    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.embeddings = None
        self.excerpt_data = None

        if HAS_EMBEDDINGS:
            self._load_or_build_embeddings()

    def _load_or_build_embeddings(self):
        """Load cached embeddings or build them"""
        if EMBEDDINGS_FILE.exists():
            print("Loading cached embeddings...")
            with open(EMBEDDINGS_FILE, 'rb') as f:
                cache = pickle.load(f)
                self.embeddings = cache['embeddings']
                self.excerpt_data = cache['excerpt_data']
            print(f"Loaded {len(self.excerpt_data)} embeddings")
        else:
            print("No embeddings cache found. Run --build-embeddings first.")

    def build_embeddings(self, batch_size=100, max_excerpts=None):
        """Build embeddings for all excerpts"""
        if not HAS_EMBEDDINGS:
            print("sentence-transformers not installed. Run: pip install sentence-transformers")
            return

        print(f"Loading model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)

        excerpts = load_excerpts()
        if max_excerpts:
            excerpts = excerpts[:max_excerpts]

        print(f"Building embeddings for {len(excerpts)} excerpts...")

        # Prepare texts
        texts = []
        excerpt_data = []

        for exc in excerpts:
            text = exc.get('text', '')
            if len(text) > 20:  # Skip very short excerpts
                texts.append(text[:512])  # Limit length for efficiency
                excerpt_data.append({
                    'url': exc.get('url', ''),
                    'title': exc.get('title', ''),
                    'text': text[:500]
                })

        # Build embeddings in batches
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = self.model.encode(batch, show_progress_bar=True)
            all_embeddings.extend(batch_embeddings)
            print(f"Processed {min(i+batch_size, len(texts))}/{len(texts)}")

        self.embeddings = np.array(all_embeddings)
        self.excerpt_data = excerpt_data

        # Cache embeddings
        CACHE_DIR.mkdir(exist_ok=True)
        with open(EMBEDDINGS_FILE, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'excerpt_data': self.excerpt_data
            }, f)

        print(f"Saved embeddings to {EMBEDDINGS_FILE}")

    def search(self, query, top_k=20):
        """Search for excerpts similar to query"""
        if not HAS_EMBEDDINGS or self.embeddings is None:
            return []

        if self.model is None:
            self.model = SentenceTransformer(self.model_name)

        # Encode query
        query_embedding = self.model.encode([query])[0]

        # Compute similarities
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]

        # Get top results
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'url': self.excerpt_data[idx]['url'],
                'title': self.excerpt_data[idx]['title'],
                'text': self.excerpt_data[idx]['text'],
                'similarity': float(similarities[idx])
            })

        return results

    def find_similar_to_url(self, url, top_k=10):
        """Find articles similar to a given URL"""
        if self.excerpt_data is None:
            return []

        # Find excerpts from this URL
        target_indices = [i for i, e in enumerate(self.excerpt_data) if e['url'] == url]

        if not target_indices:
            return []

        # Average embeddings for this article
        target_embedding = np.mean(self.embeddings[target_indices], axis=0)

        # Compute similarities
        similarities = cosine_similarity([target_embedding], self.embeddings)[0]

        # Get top results (excluding same article)
        seen_urls = {url}
        results = []

        for idx in np.argsort(similarities)[::-1]:
            article_url = self.excerpt_data[idx]['url']
            if article_url not in seen_urls:
                seen_urls.add(article_url)
                results.append({
                    'url': article_url,
                    'title': self.excerpt_data[idx]['title'],
                    'text': self.excerpt_data[idx]['text'],
                    'similarity': float(similarities[idx])
                })

                if len(results) >= top_k:
                    break

        return results

# ============================================================================
# 3. NETWORK GRAPH
# ============================================================================

class NetworkGraph:
    """Build and analyze article connection networks"""

    def __init__(self):
        self.articles = load_articles()
        self.excerpts = load_excerpts()
        self.keyword_index = load_keyword_index()

        # Build URL to article mapping
        self.article_by_url = {a['url']: a for a in self.articles}

        # Build excerpt lookup
        self.excerpts_by_url = defaultdict(list)
        for exc in self.excerpts:
            self.excerpts_by_url[exc.get('url', '')].append(exc)

    def build_keyword_network(self, min_shared_keywords=2):
        """
        Build network based on shared keywords between articles.
        Returns nodes and edges for visualization.
        """
        # Build keyword -> articles mapping
        keyword_articles = defaultdict(set)
        article_keywords = defaultdict(set)

        for keyword, entries in self.keyword_index.items():
            for entry in entries:
                url = entry.get('url', '')
                if url:
                    keyword_articles[keyword].add(url)
                    article_keywords[url].add(keyword)

        # Build edges based on shared keywords
        edges = []
        edge_weights = defaultdict(int)

        urls = list(article_keywords.keys())
        for i, url1 in enumerate(urls):
            for url2 in urls[i+1:]:
                shared = article_keywords[url1] & article_keywords[url2]
                if len(shared) >= min_shared_keywords:
                    edge_key = tuple(sorted([url1, url2]))
                    edge_weights[edge_key] = len(shared)

        # Build nodes
        nodes = []
        for url, keywords in article_keywords.items():
            article = self.article_by_url.get(url, {})
            nodes.append({
                'id': url,
                'title': article.get('title', 'Unknown')[:50],
                'date': article.get('date', ''),
                'labels': article.get('labels', []),
                'keyword_count': len(keywords),
                'top_keywords': list(keywords)[:5]
            })

        # Build edges list
        edges = [
            {'source': e[0], 'target': e[1], 'weight': w}
            for e, w in edge_weights.items()
        ]

        return {'nodes': nodes, 'edges': edges}

    def build_citation_network(self):
        """
        Build network based on FL internal citations (FL-DDMMYY pattern).
        """
        # Pattern for FL internal references
        fl_ref_pattern = r'FL[-_]?(\d{6}|\d{2}[-/]\d{2}[-/]\d{2})'

        edges = []
        nodes_with_refs = set()

        for url, excerpts in self.excerpts_by_url.items():
            for exc in excerpts:
                text = exc.get('text', '')
                refs = re.findall(fl_ref_pattern, text, re.IGNORECASE)

                for ref in refs:
                    nodes_with_refs.add(url)
                    edges.append({
                        'source': url,
                        'target_ref': ref,
                        'context': text[:100]
                    })

        return {
            'nodes': list(nodes_with_refs),
            'edges': edges,
            'total_references': len(edges)
        }

    def get_article_connections(self, url, max_connections=20):
        """Get articles connected to a specific URL"""
        network = self.build_keyword_network(min_shared_keywords=1)

        # Find edges involving this URL
        connections = []
        for edge in network['edges']:
            if edge['source'] == url:
                other = edge['target']
            elif edge['target'] == url:
                other = edge['source']
            else:
                continue

            article = self.article_by_url.get(other, {})
            connections.append({
                'url': other,
                'title': article.get('title', 'Unknown'),
                'shared_keywords': edge['weight']
            })

        # Sort by connection strength
        connections.sort(key=lambda x: x['shared_keywords'], reverse=True)
        return connections[:max_connections]

    def save_network(self, output_file=None):
        """Save network to JSON for visualization"""
        if output_file is None:
            output_file = NETWORK_FILE

        network = self.build_keyword_network()

        CACHE_DIR.mkdir(exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(network, f, indent=2)

        print(f"Saved network: {len(network['nodes'])} nodes, {len(network['edges'])} edges")
        return network

# ============================================================================
# 4. TOPIC TIMELINE
# ============================================================================

class TopicTimeline:
    """Track keyword/topic evolution over time"""

    def __init__(self):
        self.articles = load_articles()
        self.excerpts = load_excerpts()
        self.keyword_index = load_keyword_index()
        self.stats = load_statistics()

    def get_keyword_timeline(self, keyword):
        """Get monthly occurrence counts for a keyword"""
        timeline = defaultdict(int)

        if keyword in self.keyword_index:
            for entry in self.keyword_index[keyword]:
                url = entry.get('url', '')
                # Extract date from URL
                match = re.search(r'/(\d{4})/(\d{2})/', url)
                if match:
                    date_key = f"{match.group(1)}-{match.group(2)}"
                    timeline[date_key] += 1

        # Sort by date
        sorted_timeline = sorted(timeline.items())
        return sorted_timeline

    def get_category_timeline(self, category):
        """Get monthly article counts for a category/label"""
        timeline = defaultdict(int)

        for article in self.articles:
            labels = article.get('labels', [])
            if category in labels:
                date = article.get('date', '')
                if date:
                    timeline[date] += 1

        return sorted(timeline.items())

    def get_first_occurrences(self, keywords=None):
        """Find when each keyword first appeared"""
        if keywords is None:
            keywords = list(self.keyword_index.keys())

        first_occurrences = {}

        for keyword in keywords:
            if keyword in self.keyword_index:
                entries = self.keyword_index[keyword]
                dates = []

                for entry in entries:
                    url = entry.get('url', '')
                    match = re.search(r'/(\d{4})/(\d{2})/', url)
                    if match:
                        dates.append(f"{match.group(1)}-{match.group(2)}")

                if dates:
                    first_occurrences[keyword] = min(dates)

        # Sort by date
        return sorted(first_occurrences.items(), key=lambda x: x[1])

    def get_keyword_cooccurrence(self, keyword1, keyword2):
        """Find articles where both keywords appear"""
        urls1 = set(e.get('url') for e in self.keyword_index.get(keyword1, []))
        urls2 = set(e.get('url') for e in self.keyword_index.get(keyword2, []))

        shared = urls1 & urls2

        results = []
        for url in shared:
            match = re.search(r'/(\d{4})/(\d{2})/', url)
            date = f"{match.group(1)}-{match.group(2)}" if match else ''

            for article in self.articles:
                if article.get('url') == url:
                    results.append({
                        'url': url,
                        'title': article.get('title', 'Unknown'),
                        'date': date
                    })
                    break

        return sorted(results, key=lambda x: x['date'])

    def get_trending_keywords(self, time_window_months=6):
        """Find keywords with increasing frequency recently"""
        # This is a simplified version - could be enhanced with proper trend detection
        keyword_counts = self.stats.get('keyword_counts', {})

        # Sort by count
        trending = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        return trending[:20]

# ============================================================================
# 5. IMPORTANCE SCORING
# ============================================================================

def compute_article_importance(articles, excerpts, keyword_index):
    """
    Compute importance scores for all articles.

    Factors:
    - High-priority keyword mentions
    - Number of excerpts (content richness)
    - Coordinate data presence
    - Category importance
    - Citation count (if available)
    """
    scores = {}

    # Build excerpt lookup
    excerpts_by_url = defaultdict(list)
    for exc in excerpts:
        excerpts_by_url[exc.get('url', '')].append(exc)

    for article in articles:
        url = article.get('url', '')
        score = 0

        # Category score
        labels = article.get('labels', [])
        if 'Defense' in labels:
            score += 15
        if 'Cassini Diskus' in labels:
            score += 12
        if 'NodeSpaces' in labels:
            score += 10

        # Keyword score
        article_excerpts = excerpts_by_url.get(url, [])
        for exc in article_excerpts:
            text = exc.get('text', '').lower()

            for term in FL_PRIORITY_TERMS['high']:
                if term.lower() in text:
                    score += 5
            for term in FL_PRIORITY_TERMS['medium']:
                if term.lower() in text:
                    score += 2

        # Content richness
        score += min(len(article_excerpts), 20)

        # Coordinates bonus
        if article.get('coordinates'):
            score += 20

        scores[url] = score

    return scores

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='FL AI Features')
    parser.add_argument('--build-embeddings', action='store_true',
                       help='Build semantic search embeddings (one-time)')
    parser.add_argument('--reading-list', metavar='TOPIC',
                       help='Generate reading list for topic')
    parser.add_argument('--starter-list', action='store_true',
                       help='Generate starter reading list')
    parser.add_argument('--similar', metavar='URL',
                       help='Find articles similar to URL')
    parser.add_argument('--search', metavar='QUERY',
                       help='Semantic search for query')
    parser.add_argument('--network', action='store_true',
                       help='Build and save network graph')
    parser.add_argument('--timeline', metavar='KEYWORD',
                       help='Show keyword timeline')
    parser.add_argument('--first-occurrences', action='store_true',
                       help='Show when keywords first appeared')
    parser.add_argument('--limit', type=int, default=20,
                       help='Limit results')

    args = parser.parse_args()

    if args.build_embeddings:
        search = SemanticSearch()
        search.build_embeddings()
        return

    if args.reading_list:
        generator = ReadingListGenerator()
        reading_list = generator.generate_topic_reading_list(args.reading_list, args.limit)

        print(f"\n📚 Reading List: {args.reading_list}")
        print("=" * 60)
        for article in reading_list:
            print(f"\n{article['reading_order']}. [{article['difficulty'].upper()}] {article['title'][:60]}")
            print(f"   Date: {article['date']} | Importance: {article['importance']:.0f}")
            print(f"   Keywords: {article['matched_keyword']}")
            print(f"   URL: {article['url']}")
        return

    if args.starter_list:
        generator = ReadingListGenerator()
        reading_list = generator.generate_starter_reading_list(args.limit)

        print("\n📚 Starter Reading List for FL Research")
        print("=" * 60)
        for article in reading_list:
            print(f"\n{article['reading_order']}. {article['title'][:60]}")
            print(f"   Category: {article['category']} | Importance: {article['importance']:.0f}")
            print(f"   URL: {article['url']}")
        return

    if args.search:
        search = SemanticSearch()
        results = search.search(args.search, args.limit)

        print(f"\n🔍 Semantic Search: '{args.search}'")
        print("=" * 60)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['similarity']:.3f}] {r['title'][:50]}")
            print(f"   {r['text'][:100]}...")
        return

    if args.similar:
        search = SemanticSearch()
        results = search.find_similar_to_url(args.similar, args.limit)

        print(f"\n🔗 Articles Similar To: {args.similar[:50]}...")
        print("=" * 60)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['similarity']:.3f}] {r['title'][:50]}")
        return

    if args.network:
        graph = NetworkGraph()
        network = graph.save_network()
        print(f"Network saved to {NETWORK_FILE}")
        return

    if args.timeline:
        timeline = TopicTimeline()
        data = timeline.get_keyword_timeline(args.timeline)

        print(f"\n📈 Timeline for '{args.timeline}'")
        print("=" * 60)
        for date, count in data[-24:]:  # Last 24 months
            bar = "█" * min(count, 50)
            print(f"{date}: {bar} ({count})")
        return

    if args.first_occurrences:
        timeline = TopicTimeline()
        occurrences = timeline.get_first_occurrences(list(FL_PRIORITY_TERMS['high']))

        print("\n📅 First Occurrences of Key Terms")
        print("=" * 60)
        for keyword, date in occurrences:
            print(f"{date}: {keyword}")
        return

    # Default: show available commands
    print("FL AI Features - Available Commands:")
    print("  --build-embeddings    Build semantic search index")
    print("  --reading-list TOPIC  Generate reading list")
    print("  --starter-list        Generate starter reading list")
    print("  --search QUERY        Semantic search")
    print("  --similar URL         Find similar articles")
    print("  --network             Build network graph")
    print("  --timeline KEYWORD    Show keyword timeline")
    print("  --first-occurrences   Show when terms first appeared")

if __name__ == '__main__':
    main()
