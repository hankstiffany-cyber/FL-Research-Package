#!/usr/bin/env python3
"""
FL Topic Modeling
Discovers hidden thematic clusters in FL excerpts using TF-IDF + NMF
(Non-negative Matrix Factorization), compares them to author-assigned labels,
and tracks topic trends over time.
"""

import sys
import io
import argparse
import json
import re
import os
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import NMF
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DATA_DIR = "data"

# FL-specific noise words: common FL language fragments and non-meaningful tokens
FL_STOP_WORDS = {
    "fl", "forgotten", "languages", "forgottenlanguages", "org", "html", "http",
    "https", "www", "com", "full", "blogspot",
    # Common FL constructed-language fragments
    "ael", "aen", "aer", "dei", "der", "ede", "eil", "eln", "ene", "ere",
    "nei", "ner", "nde", "nei", "sel", "sen", "ser",
    # Short meaningless tokens
    "al", "el", "en", "es", "et", "de", "di", "du", "da", "le", "la", "li",
    "lo", "na", "ne", "ni", "no", "nu", "re", "se", "si", "te", "ti", "un",
    # Common but uninformative
    "also", "would", "could", "one", "two", "three", "may", "use", "used",
    "using", "new", "like", "way", "see", "first", "well", "even", "much",
    "many", "make", "made", "must", "need", "say", "said", "know", "known",
    "just", "get", "got", "take", "taken", "give", "given", "come", "came",
    "going", "goes", "thing", "things", "still", "however", "therefore",
    "thus", "hence", "since", "though", "although", "yet", "per", "via",
    "within", "without", "upon", "already", "another", "rather", "whether",
    "every", "each", "either", "neither", "certain", "several", "various",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _extract_date_from_url(url):
    """Extract YYYY-MM from a FL article URL."""
    m = re.search(r'/(\d{4})/(\d{2})/', url)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _clean_text(text):
    """Basic text cleaning for topic modeling."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove non-alpha characters (keep spaces)
    text = re.sub(r'[^a-z\s]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def load_data():
    """Load articles and excerpts from data directory."""
    articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
    excerpts_path = os.path.join(DATA_DIR, "fl_excerpts_raw.csv")

    with open(articles_path, encoding='utf-8') as f:
        articles = json.load(f)

    excerpts_df = pd.read_csv(excerpts_path, encoding='utf-8') if os.path.exists(excerpts_path) else pd.DataFrame()

    return articles, excerpts_df


# ---------------------------------------------------------------------------
# 1. ExcerptTopicModeler
# ---------------------------------------------------------------------------

class ExcerptTopicModeler:
    """Discovers topics from FL excerpts using TF-IDF + NMF."""

    def __init__(self, excerpts_df):
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for topic modeling. Install with: pip install scikit-learn")
        self.excerpts_df = excerpts_df.copy()
        self.vectorizer = None
        self.nmf_model = None
        self.tfidf_matrix = None
        self.doc_topic_matrix = None
        self.n_topics = None
        self.feature_names = None
        self._fitted = False

    def fit(self, n_topics=15):
        """Fit TF-IDF + NMF model on excerpt texts."""
        self.n_topics = n_topics

        # Clean texts
        texts = self.excerpts_df['text'].apply(_clean_text)
        # Drop empty texts
        valid_mask = texts.str.len() > 10
        texts = texts[valid_mask]
        self.excerpts_df = self.excerpts_df[valid_mask].reset_index(drop=True)
        texts = texts.reset_index(drop=True)

        # Build combined stop word list: sklearn English + FL-specific
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        combined_stops = list(ENGLISH_STOP_WORDS | FL_STOP_WORDS)

        # TF-IDF vectorization
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            min_df=5,
            max_df=0.85,
            stop_words=combined_stops,
            token_pattern=r'\b[a-z]{3,}\b',  # Words with 3+ chars only
            ngram_range=(1, 1),
        )

        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        self.feature_names = self.vectorizer.get_feature_names_out()

        # NMF decomposition
        self.nmf_model = NMF(
            n_components=n_topics,
            random_state=42,
            max_iter=300,
            init='nndsvda',
        )
        self.doc_topic_matrix = self.nmf_model.fit_transform(self.tfidf_matrix)
        self._fitted = True

        return self

    def get_topics(self, n_words=10):
        """Get list of topics with top words and weights."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        topics = []
        for topic_idx, topic_vec in enumerate(self.nmf_model.components_):
            top_indices = topic_vec.argsort()[-n_words:][::-1]
            top_words = []
            for i in top_indices:
                top_words.append({
                    'word': self.feature_names[i],
                    'weight': float(topic_vec[i]),
                })
            topics.append({
                'topic_id': topic_idx,
                'top_words': top_words,
            })
        return topics

    def get_topic_labels(self):
        """Generate auto-labels from top 3 words of each topic."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        labels = {}
        for topic_idx, topic_vec in enumerate(self.nmf_model.components_):
            top3 = topic_vec.argsort()[-3:][::-1]
            label = "-".join(self.feature_names[i] for i in top3)
            labels[topic_idx] = label
        return labels

    def get_excerpt_topics(self, top_n=3):
        """Get dominant topics for each excerpt."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Use cached result if available
        cache_key = f"_excerpt_topics_{top_n}"
        if hasattr(self, cache_key):
            return getattr(self, cache_key)

        labels = self.get_topic_labels()

        # Vectorized dominant topic extraction
        dominant_topics = self.doc_topic_matrix.argmax(axis=1)
        topic_scores = self.doc_topic_matrix.max(axis=1)

        result = pd.DataFrame({
            'url': self.excerpts_df['url'].values,
            'title': self.excerpts_df['title'].values,
            'text_preview': self.excerpts_df['text'].astype(str).str[:100].values,
            'dominant_topic': dominant_topics,
            'topic_label': [labels[t] for t in dominant_topics],
            'topic_score': np.round(topic_scores, 4),
        })

        setattr(self, cache_key, result)
        return result

    def get_topic_article_mapping(self):
        """Map topics to their constituent articles."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        excerpt_topics = self.get_excerpt_topics(top_n=1)
        labels = self.get_topic_labels()

        result = []
        for topic_id in range(self.n_topics):
            mask = excerpt_topics['dominant_topic'] == topic_id
            urls = excerpt_topics.loc[mask, 'url'].unique().tolist()
            result.append({
                'topic_id': topic_id,
                'topic_label': labels[topic_id],
                'article_urls': urls,
                'article_count': len(urls),
            })

        return pd.DataFrame(result)


# ---------------------------------------------------------------------------
# 2. TopicLabelComparator
# ---------------------------------------------------------------------------

class TopicLabelComparator:
    """Compares discovered NMF topics with author-assigned article labels."""

    def __init__(self, modeler):
        """
        Args:
            modeler: A fitted ExcerptTopicModeler instance.
        """
        if not modeler._fitted:
            raise RuntimeError("ExcerptTopicModeler must be fitted first.")
        self.modeler = modeler

    def compare_topics_to_labels(self, articles):
        """
        Compare NMF topics to author-assigned labels.

        Returns DataFrame with: topic_id, topic_label, most_aligned_labels,
        alignment_score, is_novel.
        """
        # Build article URL -> labels mapping
        url_to_labels = {}
        for art in articles:
            url_to_labels[art['url']] = [lbl.lower().strip() for lbl in art.get('labels', [])]

        # Get all unique labels
        all_labels = set()
        for labels in url_to_labels.values():
            all_labels.update(labels)
        all_labels = sorted(all_labels)

        topic_mapping = self.modeler.get_topic_article_mapping()
        topic_labels_auto = self.modeler.get_topic_labels()

        results = []
        for _, row in topic_mapping.iterrows():
            topic_id = row['topic_id']
            urls = row['article_urls']

            # Count label occurrences for articles in this topic
            label_counts = Counter()
            total_with_labels = 0
            for url in urls:
                article_labels = url_to_labels.get(url, [])
                if article_labels:
                    total_with_labels += 1
                    for lbl in article_labels:
                        label_counts[lbl] += 1

            # Compute alignment scores
            aligned = []
            if total_with_labels > 0:
                for lbl, count in label_counts.most_common(5):
                    score = round(count / total_with_labels, 2)
                    aligned.append({'label': lbl, 'score': score})

            best_score = aligned[0]['score'] if aligned else 0.0
            is_novel = best_score < 0.30

            results.append({
                'topic_id': topic_id,
                'topic_label': topic_labels_auto[topic_id],
                'most_aligned_labels': aligned,
                'alignment_score': best_score,
                'is_novel': is_novel,
            })

        return pd.DataFrame(results)

    def find_novel_topics(self, articles):
        """Find topics that don't align well with any existing label."""
        comparison = self.compare_topics_to_labels(articles)
        return comparison[comparison['is_novel']].sort_values('alignment_score')

    def find_mislabeled_articles(self, articles, disagreement_threshold=0.5):
        """
        Find articles where the NMF topic strongly disagrees with assigned labels.

        An article is 'mislabeled' when its NMF dominant topic has low alignment
        with the article's actual labels.
        """
        url_to_labels = {}
        for art in articles:
            url_to_labels[art['url']] = [lbl.lower().strip() for lbl in art.get('labels', [])]

        comparison = self.compare_topics_to_labels(articles)
        # Build topic_id -> aligned labels set
        topic_aligned = {}
        for _, row in comparison.iterrows():
            aligned_labels = set()
            for entry in row['most_aligned_labels']:
                if entry['score'] >= 0.3:
                    aligned_labels.add(entry['label'])
            topic_aligned[row['topic_id']] = aligned_labels

        excerpt_topics = self.modeler.get_excerpt_topics(top_n=1)

        mislabeled = []
        seen_urls = set()
        for _, row in excerpt_topics.iterrows():
            url = row['url']
            if url in seen_urls:
                continue
            seen_urls.add(url)

            topic_id = row['dominant_topic']
            score = row['topic_score']
            if score < disagreement_threshold:
                continue  # Weak topic assignment, skip

            article_labels = set(url_to_labels.get(url, []))
            aligned = topic_aligned.get(topic_id, set())

            if article_labels and not article_labels.intersection(aligned):
                mislabeled.append({
                    'url': url,
                    'title': row['title'],
                    'assigned_labels': list(article_labels),
                    'nmf_topic': row['topic_label'],
                    'nmf_topic_id': topic_id,
                    'topic_score': score,
                })

        return pd.DataFrame(mislabeled) if mislabeled else pd.DataFrame(
            columns=['url', 'title', 'assigned_labels', 'nmf_topic', 'nmf_topic_id', 'topic_score']
        )


# ---------------------------------------------------------------------------
# 3. TopicTrendAnalyzer
# ---------------------------------------------------------------------------

class TopicTrendAnalyzer:
    """Track NMF topics over time using article publication dates."""

    def __init__(self, modeler):
        if not modeler._fitted:
            raise RuntimeError("ExcerptTopicModeler must be fitted first.")
        self.modeler = modeler
        self._excerpt_topics = None

    def _get_excerpt_topics_with_dates(self):
        """Get excerpt topics with dates extracted from URLs."""
        if self._excerpt_topics is not None:
            return self._excerpt_topics

        et = self.modeler.get_excerpt_topics(top_n=1)
        et['date_str'] = et['url'].apply(_extract_date_from_url)
        et = et.dropna(subset=['date_str'])
        et['date'] = pd.to_datetime(et['date_str'] + '-01', format='%Y-%m-%d', errors='coerce')
        et = et.dropna(subset=['date'])
        self._excerpt_topics = et
        return et

    def get_topic_timeline(self, topic_id):
        """Get monthly article count for a specific topic."""
        et = self._get_excerpt_topics_with_dates()
        topic_data = et[et['dominant_topic'] == topic_id]

        # Count unique articles per month
        monthly = topic_data.groupby('date')['url'].nunique().reset_index(name='count')
        monthly = monthly.sort_values('date')
        return monthly

    def get_all_topic_timelines(self):
        """Get timelines for all topics."""
        labels = self.modeler.get_topic_labels()
        timelines = {}
        for topic_id in range(self.modeler.n_topics):
            tl = self.get_topic_timeline(topic_id)
            timelines[topic_id] = tl
        return timelines

    def get_trending_topics(self, recent_months=12):
        """Find topics that are gaining traction in recent months."""
        et = self._get_excerpt_topics_with_dates()
        if et.empty:
            return pd.DataFrame(columns=['topic_id', 'topic_label', 'recent_count',
                                         'historical_avg', 'trend_ratio', 'direction'])

        max_date = et['date'].max()
        cutoff = max_date - pd.DateOffset(months=recent_months)
        labels = self.modeler.get_topic_labels()

        trends = []
        for topic_id in range(self.modeler.n_topics):
            topic_data = et[et['dominant_topic'] == topic_id]
            recent = topic_data[topic_data['date'] >= cutoff]
            historical = topic_data[topic_data['date'] < cutoff]

            recent_count = recent['url'].nunique()

            # Calculate monthly average for historical period
            if not historical.empty:
                hist_months = max(1, (cutoff - historical['date'].min()).days / 30)
                hist_avg = historical['url'].nunique() / hist_months * recent_months
            else:
                hist_avg = 0.1  # Avoid division by zero

            ratio = round(recent_count / max(hist_avg, 0.1), 2)

            if ratio > 1.3:
                direction = 'rising'
            elif ratio < 0.7:
                direction = 'declining'
            else:
                direction = 'stable'

            trends.append({
                'topic_id': topic_id,
                'topic_label': labels[topic_id],
                'recent_count': recent_count,
                'historical_avg': round(hist_avg, 1),
                'trend_ratio': ratio,
                'direction': direction,
            })

        df = pd.DataFrame(trends)
        return df.sort_values('trend_ratio', ascending=False)


# ---------------------------------------------------------------------------
# 4. Plotly Visualizations
# ---------------------------------------------------------------------------

def plot_topic_wordclouds(modeler, n_words=10):
    """Horizontal bar charts showing top words per topic (subplots)."""
    topics = modeler.get_topics(n_words=n_words)
    labels = modeler.get_topic_labels()
    n = len(topics)
    cols = 3
    rows = (n + cols - 1) // cols

    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=[f"Topic {t['topic_id']}: {labels[t['topic_id']]}" for t in topics],
        horizontal_spacing=0.12,
        vertical_spacing=0.08,
    )

    for idx, topic in enumerate(topics):
        r = idx // cols + 1
        c = idx % cols + 1
        words = [w['word'] for w in reversed(topic['top_words'])]
        weights = [w['weight'] for w in reversed(topic['top_words'])]

        fig.add_trace(
            go.Bar(x=weights, y=words, orientation='h', marker_color='steelblue',
                   showlegend=False),
            row=r, col=c,
        )

    fig.update_layout(
        title_text="Topic Top Words (TF-IDF + NMF)",
        height=300 * rows,
        width=1200,
    )
    return fig


def plot_topic_distribution(modeler):
    """Bar chart of article count per topic."""
    mapping = modeler.get_topic_article_mapping()
    labels = modeler.get_topic_labels()

    mapping = mapping.sort_values('article_count', ascending=True)
    display_labels = [f"T{row['topic_id']}: {labels[row['topic_id']]}" for _, row in mapping.iterrows()]

    fig = go.Figure(go.Bar(
        x=mapping['article_count'].values,
        y=display_labels,
        orientation='h',
        marker_color='teal',
    ))
    fig.update_layout(
        title="Articles per Topic",
        xaxis_title="Number of Articles",
        yaxis_title="Topic",
        height=max(400, len(mapping) * 35),
        width=900,
    )
    return fig


def plot_topic_heatmap(comparator, articles):
    """Heatmap of topics vs labels showing alignment scores."""
    comparison = comparator.compare_topics_to_labels(articles)
    topic_labels_auto = comparator.modeler.get_topic_labels()

    # Collect all labels that appear
    all_aligned_labels = set()
    for _, row in comparison.iterrows():
        for entry in row['most_aligned_labels']:
            all_aligned_labels.add(entry['label'])

    # Take top labels by frequency
    label_freq = Counter()
    for _, row in comparison.iterrows():
        for entry in row['most_aligned_labels']:
            label_freq[entry['label']] += entry['score']
    top_labels = [lbl for lbl, _ in label_freq.most_common(20)]

    # Build matrix
    n_topics = len(comparison)
    matrix = []
    y_labels = []
    for _, row in comparison.iterrows():
        tid = row['topic_id']
        y_labels.append(f"T{tid}: {topic_labels_auto[tid]}")
        scores_map = {e['label']: e['score'] for e in row['most_aligned_labels']}
        matrix.append([scores_map.get(lbl, 0.0) for lbl in top_labels])

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=[lbl.title() for lbl in top_labels],
        y=y_labels,
        colorscale='YlOrRd',
        text=[[f"{v:.2f}" for v in row] for row in matrix],
        texttemplate="%{text}",
        hovertemplate="Topic: %{y}<br>Label: %{x}<br>Score: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Topic-Label Alignment Heatmap",
        xaxis_title="Author-Assigned Labels",
        yaxis_title="Discovered Topics",
        height=max(500, n_topics * 40),
        width=1000,
        xaxis_tickangle=45,
    )
    return fig


def plot_topic_trends(trend_analyzer):
    """Line chart of topic frequency over time."""
    timelines = trend_analyzer.get_all_topic_timelines()
    labels = trend_analyzer.modeler.get_topic_labels()

    fig = go.Figure()
    for topic_id, tl in timelines.items():
        if tl.empty:
            continue
        fig.add_trace(go.Scatter(
            x=tl['date'], y=tl['count'],
            mode='lines',
            name=f"T{topic_id}: {labels[topic_id]}",
            line=dict(width=1.5),
        ))

    fig.update_layout(
        title="Topic Trends Over Time",
        xaxis_title="Date",
        yaxis_title="Articles per Month",
        height=600,
        width=1100,
        legend=dict(font=dict(size=9)),
    )
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="FL Topic Modeling (TF-IDF + NMF)")
    parser.add_argument('--fit', action='store_true', help='Run topic modeling')
    parser.add_argument('--topics', action='store_true', help='Show discovered topics')
    parser.add_argument('--compare', action='store_true', help='Compare topics to author labels')
    parser.add_argument('--novel', action='store_true', help='Show novel/hidden topics')
    parser.add_argument('--trends', action='store_true', help='Show topic timelines')
    parser.add_argument('--mislabeled', action='store_true', help='Show potentially mislabeled articles')
    parser.add_argument('--full-report', action='store_true', help='Full analysis report')
    parser.add_argument('--n-topics', type=int, default=15, help='Number of topics (default: 15)')
    parser.add_argument('--n-words', type=int, default=10, help='Words per topic (default: 10)')
    parser.add_argument('--recent-months', type=int, default=12, help='Recent months for trend analysis')
    args = parser.parse_args()

    # Default to full report if nothing specified
    if not any([args.fit, args.topics, args.compare, args.novel, args.trends,
                args.mislabeled, args.full_report]):
        args.full_report = True

    print("Loading data...")
    articles, excerpts_df = load_data()
    print(f"  {len(articles)} articles, {len(excerpts_df)} excerpts")

    # Always fit the model
    print(f"\nFitting NMF topic model ({args.n_topics} topics)...")
    modeler = ExcerptTopicModeler(excerpts_df)
    modeler.fit(n_topics=args.n_topics)
    print(f"  Model fitted on {len(modeler.excerpts_df)} excerpts")

    labels_auto = modeler.get_topic_labels()

    if args.full_report or args.fit or args.topics:
        topics = modeler.get_topics(n_words=args.n_words)
        print(f"\nTOPIC MODELING RESULTS ({args.n_topics} topics from {len(modeler.excerpts_df):,} excerpts)")
        print("=" * 60)

        comparator = TopicLabelComparator(modeler)
        comparison = comparator.compare_topics_to_labels(articles)

        for _, cmp_row in comparison.iterrows():
            tid = cmp_row['topic_id']
            topic = topics[tid]
            words_str = ", ".join(w['word'] for w in topic['top_words'])
            print(f"\nTopic {tid} [{labels_auto[tid]}]: {words_str}")

            aligned = cmp_row['most_aligned_labels']
            if aligned:
                aligned_str = ", ".join(f"{e['label'].title()} ({e['score']:.2f})" for e in aligned[:3])
                print(f"  Aligned labels: {aligned_str}")
            else:
                print("  Aligned labels: (none)")

            mapping = modeler.get_topic_article_mapping()
            count = mapping.loc[mapping['topic_id'] == tid, 'article_count'].values[0]
            print(f"  Articles: {count:,}")

    if args.full_report or args.compare:
        comparator = TopicLabelComparator(modeler)
        comparison = comparator.compare_topics_to_labels(articles)
        if not (args.full_report and args.topics):
            # Only print if not already printed above
            if args.compare and not args.full_report:
                print(f"\nTOPIC-LABEL COMPARISON")
                print("=" * 60)
                for _, row in comparison.iterrows():
                    tid = row['topic_id']
                    aligned = row['most_aligned_labels']
                    aligned_str = ", ".join(f"{e['label'].title()} ({e['score']:.2f})" for e in aligned[:3]) if aligned else "(none)"
                    novel_flag = " ** NOVEL **" if row['is_novel'] else ""
                    print(f"  Topic {tid} [{labels_auto[tid]}]: {aligned_str}{novel_flag}")

    if args.full_report or args.novel:
        comparator = TopicLabelComparator(modeler)
        novel = comparator.find_novel_topics(articles)
        print(f"\nNOVEL TOPICS (no strong label alignment):")
        print("-" * 60)
        if novel.empty:
            print("  No novel topics found (all topics align with at least one label).")
        else:
            for _, row in novel.iterrows():
                tid = row['topic_id']
                topics_data = modeler.get_topics(n_words=args.n_words)
                words_str = ", ".join(w['word'] for w in topics_data[tid]['top_words'][:6])
                best = row['most_aligned_labels']
                if best:
                    best_str = f"(best: {best[0]['label'].title()} at {best[0]['score']:.2f})"
                else:
                    best_str = "(no label matches)"
                print(f"  Topic {tid} [{labels_auto[tid]}]: {words_str}")
                print(f"    No matching label {best_str}")
                print(f"    -> This is a HIDDEN thematic cluster!")

    if args.full_report or args.mislabeled:
        comparator = TopicLabelComparator(modeler)
        mislabeled = comparator.find_mislabeled_articles(articles)
        print(f"\nPOTENTIALLY MISLABELED ARTICLES:")
        print("-" * 60)
        if mislabeled.empty:
            print("  No strongly mislabeled articles detected.")
        else:
            print(f"  Found {len(mislabeled)} articles where NMF topic disagrees with assigned labels")
            for _, row in mislabeled.head(20).iterrows():
                assigned = ", ".join(row['assigned_labels'][:3])
                print(f"  {row['title'][:60]}")
                print(f"    Labels: {assigned}  |  NMF: {row['nmf_topic']} (score: {row['topic_score']:.2f})")

    if args.full_report or args.trends:
        trend_analyzer = TopicTrendAnalyzer(modeler)
        trending = trend_analyzer.get_trending_topics(recent_months=args.recent_months)
        print(f"\nTOPIC TRENDS (last {args.recent_months} months):")
        print("-" * 60)
        for _, row in trending.iterrows():
            if row['direction'] == 'rising':
                marker = '+'
            elif row['direction'] == 'declining':
                marker = '-'
            else:
                marker = '='
            print(f"  [{marker}] Topic {row['topic_id']} [{row['topic_label']}]: "
                  f"{row['trend_ratio']}x ({row['direction']}, "
                  f"recent={row['recent_count']}, hist_avg={row['historical_avg']})")


if __name__ == "__main__":
    main()
