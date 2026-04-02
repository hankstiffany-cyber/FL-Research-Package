#!/usr/bin/env python3
"""
FL Network / Graph Analysis
Analyzes connections between articles via shared labels.
Identifies hub articles, topic bridges, and community structure.

No external graph library required -- uses dicts and pandas only.
"""

import sys
import io
import argparse
import json
import os
from collections import defaultdict
from itertools import combinations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DATA_DIR = "data"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data():
    """Load articles JSON for standalone use."""
    articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
    with open(articles_path, encoding='utf-8') as f:
        articles = json.load(f)
    return articles


def prepare_articles_df(articles):
    """Convert articles list to DataFrame with parsed dates."""
    df = pd.DataFrame(articles)
    df['date_parsed'] = pd.to_datetime(
        df['date'] + '-01', format='%Y-%m-%d', errors='coerce'
    )
    df['label_count'] = df['labels'].apply(len)
    return df


# ---------------------------------------------------------------------------
# 1. ArticleNetworkBuilder
# ---------------------------------------------------------------------------

class ArticleNetworkBuilder:
    """Builds label co-occurrence and article similarity networks."""

    def __init__(self, articles):
        """
        Parameters
        ----------
        articles : list[dict]
            Raw article dicts with 'url', 'title', 'labels', etc.
        """
        self.articles = articles
        self._label_edges = None   # dict (l1,l2) -> weight
        self._label_articles = None  # label -> set of article indices

    # -- internal ----------------------------------------------------------

    def _build_indexes(self):
        if self._label_articles is not None:
            return
        label_articles = defaultdict(set)
        for idx, art in enumerate(self.articles):
            for lab in art.get('labels', []):
                label_articles[lab].add(idx)
        self._label_articles = label_articles

        edges = defaultdict(int)
        for art in self.articles:
            labs = sorted(set(art.get('labels', [])))
            for a, b in combinations(labs, 2):
                edges[(a, b)] += 1
        self._label_edges = edges

    # -- public API --------------------------------------------------------

    def build_label_network(self):
        """Return nodes (labels) and edges (label pairs + weights).

        Returns
        -------
        nodes : list[dict]  -- label, article_count
        edges : list[dict]  -- source, target, weight
        """
        self._build_indexes()
        nodes = [
            {'label': lab, 'article_count': len(idxs)}
            for lab, idxs in self._label_articles.items()
        ]
        edges = [
            {'source': a, 'target': b, 'weight': w}
            for (a, b), w in self._label_edges.items()
        ]
        return nodes, edges

    def build_article_network(self, min_shared_labels=2):
        """Return nodes (articles) and edges for articles sharing >= min_shared_labels.

        Returns
        -------
        nodes : list[dict]  -- url, title, label_count
        edges : list[dict]  -- source_url, target_url, shared_labels
        """
        self._build_indexes()
        # For each pair of labels, get shared articles
        # Then count shared labels per article pair
        pair_shared = defaultdict(int)
        for (l1, l2), w in self._label_edges.items():
            shared_arts = self._label_articles[l1] & self._label_articles[l2]
            for idx in shared_arts:
                # This article has both l1 and l2 -- but we need pairs of articles
                pass

        # More direct: for each article, record its label set, then compare
        art_labels = []
        nodes = []
        for art in self.articles:
            labs = set(art.get('labels', []))
            art_labels.append(labs)
            nodes.append({
                'url': art['url'],
                'title': art.get('title', ''),
                'label_count': len(labs),
            })

        # Build inverted index: label -> article indices (reuse)
        label_to_arts = defaultdict(set)
        for idx, labs in enumerate(art_labels):
            for lab in labs:
                label_to_arts[lab].add(idx)

        # Count shared labels for candidate pairs
        pair_counts = defaultdict(int)
        for lab, idxs in label_to_arts.items():
            idxs_list = sorted(idxs)
            # Only consider pairs if set is manageable
            if len(idxs_list) > 500:
                continue  # skip very common labels to keep runtime sane
            for i in range(len(idxs_list)):
                for j in range(i + 1, len(idxs_list)):
                    pair_counts[(idxs_list[i], idxs_list[j])] += 1

        edges = []
        for (i, j), cnt in pair_counts.items():
            if cnt >= min_shared_labels:
                edges.append({
                    'source_url': self.articles[i]['url'],
                    'target_url': self.articles[j]['url'],
                    'shared_labels': cnt,
                })
        return nodes, edges

    def get_label_stats(self):
        """Return DataFrame with label, degree, total_articles, avg_cooccurrence."""
        self._build_indexes()
        # degree = number of distinct other labels this label co-occurs with
        degree = defaultdict(int)
        total_weight = defaultdict(int)
        for (a, b), w in self._label_edges.items():
            degree[a] += 1
            degree[b] += 1
            total_weight[a] += w
            total_weight[b] += w

        rows = []
        for lab, idxs in self._label_articles.items():
            d = degree.get(lab, 0)
            tw = total_weight.get(lab, 0)
            rows.append({
                'label': lab,
                'degree': d,
                'total_articles': len(idxs),
                'avg_cooccurrence': round(tw / d, 2) if d > 0 else 0.0,
            })
        df = pd.DataFrame(rows)
        df = df.sort_values('degree', ascending=False).reset_index(drop=True)
        return df


# ---------------------------------------------------------------------------
# 2. HubDetector
# ---------------------------------------------------------------------------

class HubDetector:
    """Finds hub labels, bridge labels, and hub articles."""

    def __init__(self, articles, builder=None):
        self.articles = articles
        self.builder = builder or ArticleNetworkBuilder(articles)
        self.builder._build_indexes()
        # adjacency list for label network
        self._adj = None

    def _build_adjacency(self):
        if self._adj is not None:
            return
        adj = defaultdict(dict)  # label -> {neighbor: weight}
        for (a, b), w in self.builder._label_edges.items():
            adj[a][b] = w
            adj[b][a] = w
        self._adj = adj

    def find_hub_labels(self, top_n=20):
        """Labels with highest degree (most connections to other labels).

        Returns DataFrame: label, degree, articles_count
        """
        stats = self.builder.get_label_stats()
        top = stats.head(top_n)[['label', 'degree', 'total_articles']].copy()
        top = top.rename(columns={'total_articles': 'articles_count'})
        return top.reset_index(drop=True)

    def find_bridge_labels(self, top_n=10):
        """Labels with high approximate betweenness centrality.

        Approximation: for each label L, count how many pairs of L's
        neighbors are NOT directly connected.  A true bridge connects
        otherwise-disconnected groups, so neighbors that lack direct
        edges between them indicate L sits on the path between them.

        bridge_score = number of non-adjacent neighbor pairs / total neighbor pairs
        """
        self._build_adjacency()
        rows = []
        for lab, neighbors in self._adj.items():
            n_list = list(neighbors.keys())
            if len(n_list) < 2:
                continue
            total_pairs = 0
            non_adjacent = 0
            # sample if too many neighbors
            if len(n_list) > 100:
                n_list = n_list[:100]
            for i in range(len(n_list)):
                for j in range(i + 1, len(n_list)):
                    total_pairs += 1
                    if n_list[j] not in self._adj.get(n_list[i], {}):
                        non_adjacent += 1
            bridge_score = round(non_adjacent / total_pairs, 4) if total_pairs > 0 else 0
            # also identify which "groups" it connects
            rows.append({
                'label': lab,
                'bridge_score': bridge_score,
                'degree': len(neighbors),
                'non_adjacent_pairs': non_adjacent,
                'total_pairs': total_pairs,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Weight by degree so pure isolates don't rank high
        df['weighted_score'] = df['bridge_score'] * df['degree']
        df = df.sort_values('weighted_score', ascending=False).reset_index(drop=True)

        # For top bridges, identify which cluster pairs they connect
        connects_list = []
        for _, row in df.head(top_n).iterrows():
            lab = row['label']
            neighbors = list(self._adj[lab].keys())
            # Find two groups: neighbors that are connected to each other vs not
            # Simplification: pick the two highest-weight neighbors that are not
            # connected to each other
            pairs = []
            sorted_neigh = sorted(neighbors,
                                  key=lambda n: self._adj[lab][n], reverse=True)
            for i in range(min(len(sorted_neigh), 10)):
                for j in range(i + 1, min(len(sorted_neigh), 10)):
                    ni, nj = sorted_neigh[i], sorted_neigh[j]
                    if nj not in self._adj.get(ni, {}):
                        pairs.append(f"{ni} <-> {nj}")
                        if len(pairs) >= 3:
                            break
                if len(pairs) >= 3:
                    break
            connects_list.append(pairs if pairs else [])

        result = df.head(top_n).copy()
        result['connects'] = connects_list
        return result[['label', 'bridge_score', 'weighted_score', 'degree', 'connects']].reset_index(drop=True)

    def find_hub_articles(self, top_n=20, communities=None):
        """Articles with the most labels or spanning multiple communities.

        Parameters
        ----------
        communities : dict, optional
            community_id -> list of labels (from CommunityDetector)

        Returns DataFrame: url, title, label_count, unique_topics
        """
        # Build label -> community mapping
        label_to_community = {}
        if communities:
            for cid, labels in communities.items():
                for lab in labels:
                    label_to_community[lab] = cid

        rows = []
        for art in self.articles:
            labs = art.get('labels', [])
            if not labs:
                continue
            if communities:
                comms = set(label_to_community.get(l, -1) for l in labs)
                comms.discard(-1)
                unique_topics = len(comms)
            else:
                unique_topics = len(labs)  # fallback: count of labels
            rows.append({
                'url': art['url'],
                'title': art.get('title', ''),
                'date': art.get('date', ''),
                'label_count': len(labs),
                'unique_topics': unique_topics,
                'labels': labs,
                'excerpt_count': art.get('excerpt_count', 0),
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Sort by unique_topics desc, then label_count desc
        df = df.sort_values(['unique_topics', 'label_count'],
                            ascending=[False, False]).reset_index(drop=True)
        return df.head(top_n)


# ---------------------------------------------------------------------------
# 3. CommunityDetector
# ---------------------------------------------------------------------------

class CommunityDetector:
    """Detect topic communities using connected components on a thresholded
    co-occurrence graph, then optionally merge small components greedily."""

    def __init__(self, articles, builder=None):
        self.articles = articles
        self.builder = builder or ArticleNetworkBuilder(articles)
        self.builder._build_indexes()

    def detect_communities(self, min_cooccurrence=5):
        """Find communities via connected components on thresholded label graph.

        Parameters
        ----------
        min_cooccurrence : int
            Minimum edge weight (shared articles) to keep an edge.

        Returns
        -------
        dict : community_id -> list of labels
        """
        # Build adjacency with threshold
        adj = defaultdict(set)
        for (a, b), w in self.builder._label_edges.items():
            if w >= min_cooccurrence:
                adj[a].add(b)
                adj[b].add(a)

        # All labels (including isolated ones)
        all_labels = set(self.builder._label_articles.keys())

        # Connected components via BFS
        visited = set()
        communities = {}
        cid = 0
        # Process connected labels first (sorted by article count desc for
        # deterministic ordering)
        sorted_labels = sorted(all_labels,
                               key=lambda l: len(self.builder._label_articles[l]),
                               reverse=True)
        for start in sorted_labels:
            if start in visited:
                continue
            if start not in adj:
                # Isolated label -- skip for now, add to "Other" later
                continue
            # BFS
            queue = [start]
            component = []
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for neighbor in adj[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            if component:
                communities[cid] = sorted(
                    component,
                    key=lambda l: len(self.builder._label_articles[l]),
                    reverse=True
                )
                cid += 1

        # Collect isolated labels into an "Other" community
        isolated = [l for l in all_labels if l not in visited]
        if isolated:
            communities[cid] = sorted(
                isolated,
                key=lambda l: len(self.builder._label_articles[l]),
                reverse=True
            )

        return communities

    def get_community_summary(self, min_cooccurrence=5):
        """Summary DataFrame of detected communities.

        Returns DataFrame: community_id, size, top_label, article_count, labels
        """
        communities = self.detect_communities(min_cooccurrence)
        rows = []
        for cid, labels in communities.items():
            # Count articles that have at least one label in this community
            art_indices = set()
            for lab in labels:
                art_indices.update(self.builder._label_articles.get(lab, set()))
            top_label = labels[0] if labels else ''
            rows.append({
                'community_id': cid,
                'size': len(labels),
                'top_label': top_label,
                'article_count': len(art_indices),
                'labels': labels,
            })
        df = pd.DataFrame(rows)
        df = df.sort_values('article_count', ascending=False).reset_index(drop=True)
        return df


# ---------------------------------------------------------------------------
# 4. Plotly Visualizations
# ---------------------------------------------------------------------------

def plot_label_network(builder, communities=None, max_nodes=80, min_edge_weight=3):
    """Plotly figure showing label nodes connected by edges.

    Nodes sized by article count, colored by community.
    Only shows the top labels by degree to keep the plot readable.
    """
    builder._build_indexes()

    # Build label -> community mapping
    label_to_community = {}
    if communities:
        for cid, labels in communities.items():
            for lab in labels:
                label_to_community[lab] = cid

    # Select top labels by degree
    stats = builder.get_label_stats()
    top_labels = set(stats.head(max_nodes)['label'].tolist())

    # Filter edges
    edges = []
    for (a, b), w in builder._label_edges.items():
        if a in top_labels and b in top_labels and w >= min_edge_weight:
            edges.append((a, b, w))

    # Simple circular layout
    import math
    labels_list = sorted(top_labels)
    n = len(labels_list)
    pos = {}
    for i, lab in enumerate(labels_list):
        angle = 2 * math.pi * i / n
        pos[lab] = (math.cos(angle), math.sin(angle))

    # Force-directed nudge (simple spring iteration)
    for _ in range(50):
        forces = {lab: [0.0, 0.0] for lab in labels_list}
        # Repulsion between all nodes
        for i in range(n):
            for j in range(i + 1, n):
                li, lj = labels_list[i], labels_list[j]
                dx = pos[li][0] - pos[lj][0]
                dy = pos[li][1] - pos[lj][1]
                dist = max(math.sqrt(dx * dx + dy * dy), 0.01)
                repulsion = 0.1 / (dist * dist)
                forces[li][0] += dx / dist * repulsion
                forces[li][1] += dy / dist * repulsion
                forces[lj][0] -= dx / dist * repulsion
                forces[lj][1] -= dy / dist * repulsion
        # Attraction along edges
        for a, b, w in edges:
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = max(math.sqrt(dx * dx + dy * dy), 0.01)
            attraction = dist * 0.05 * min(w, 10)
            forces[a][0] -= dx / dist * attraction
            forces[a][1] -= dy / dist * attraction
            forces[b][0] += dx / dist * attraction
            forces[b][1] += dy / dist * attraction
        # Apply
        for lab in labels_list:
            pos[lab] = (
                pos[lab][0] + forces[lab][0] * 0.1,
                pos[lab][1] + forces[lab][1] * 0.1,
            )

    # Draw edges
    edge_x, edge_y = [], []
    for a, b, w in edges:
        x0, y0 = pos[a]
        x1, y1 = pos[b]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode='lines',
        line=dict(width=0.5, color='#ccc'),
        hoverinfo='none',
    ))

    # Draw nodes
    node_x = [pos[l][0] for l in labels_list]
    node_y = [pos[l][1] for l in labels_list]
    node_size = []
    node_color = []
    node_text = []
    for lab in labels_list:
        cnt = len(builder._label_articles.get(lab, set()))
        node_size.append(max(5, min(cnt / 5, 50)))
        node_color.append(label_to_community.get(lab, -1))
        node_text.append(f"{lab}<br>{cnt} articles")

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        marker=dict(
            size=node_size,
            color=node_color,
            colorscale='Viridis',
            line=dict(width=1, color='white'),
        ),
        text=[l if len(builder._label_articles.get(l, set())) > 20 else ''
              for l in labels_list],
        textposition='top center',
        textfont=dict(size=8),
        hovertext=node_text,
        hoverinfo='text',
    ))

    fig.update_layout(
        title='Label Co-occurrence Network',
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        template='plotly_white',
        height=700,
        width=900,
    )
    return fig


def plot_community_sizes(community_summary_df):
    """Bar chart of community sizes."""
    df = community_summary_df.copy()
    df['community_label'] = df.apply(
        lambda r: f"C{r['community_id']}: {r['top_label']}", axis=1
    )
    fig = px.bar(
        df, x='community_label', y='article_count',
        color='size',
        labels={'article_count': 'Articles', 'size': 'Labels in Community',
                'community_label': 'Community'},
        title='Topic Community Sizes',
        text='size',
    )
    fig.update_layout(template='plotly_white', height=450)
    return fig


def plot_hub_articles(hub_articles_df):
    """Scatter showing articles by label_count vs excerpt_count."""
    df = hub_articles_df.copy()
    fig = px.scatter(
        df, x='label_count', y='excerpt_count',
        hover_name='title',
        size='unique_topics',
        color='unique_topics',
        labels={
            'label_count': 'Number of Labels',
            'excerpt_count': 'Excerpt Count',
            'unique_topics': 'Unique Topic Communities',
        },
        title='Hub Articles: Labels vs Excerpts',
    )
    fig.update_layout(template='plotly_white', height=500)
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Fix Windows console encoding
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description='FL Network / Graph Analysis')
    parser.add_argument('--full-report', action='store_true',
                        help='Run all analyses and print report')
    parser.add_argument('--hubs', action='store_true',
                        help='Find hub labels')
    parser.add_argument('--bridges', action='store_true',
                        help='Find bridge labels')
    parser.add_argument('--communities', action='store_true',
                        help='Detect topic communities')
    parser.add_argument('--min-cooccurrence', type=int, default=5,
                        help='Min co-occurrence for community edges (default: 5)')
    parser.add_argument('--top-n', type=int, default=20,
                        help='Number of results to show (default: 20)')

    args = parser.parse_args()

    if not any([args.full_report, args.hubs, args.bridges, args.communities]):
        args.full_report = True

    print("Loading data...")
    articles = load_data()
    print(f"  {len(articles)} articles loaded")

    builder = ArticleNetworkBuilder(articles)
    hub_detector = HubDetector(articles, builder)
    community_detector = CommunityDetector(articles, builder)

    sep = "=" * 60

    if args.full_report or args.hubs or args.bridges or args.communities:
        # Build label network stats first
        nodes, edges = builder.build_label_network()

    if args.full_report:
        # --- Label network ---
        print(f"\n{sep}")
        print("LABEL NETWORK ANALYSIS")
        print(sep)
        print(f"Total labels: {len(nodes):,}")
        print(f"Total edges: {len(edges):,}")

        hub_labels = hub_detector.find_hub_labels(top_n=args.top_n)
        print(f"\nMost connected labels (hubs):")
        for _, r in hub_labels.iterrows():
            print(f"  {r['label']}: {r['degree']} connections, "
                  f"{r['articles_count']:,} articles")

        # --- Bridge labels ---
        print(f"\n{sep}")
        print("BRIDGE LABELS (connecting different topic areas)")
        print(sep)
        bridges = hub_detector.find_bridge_labels(top_n=10)
        if not bridges.empty:
            for _, r in bridges.iterrows():
                connects_str = '; '.join(r['connects'][:2]) if r['connects'] else 'N/A'
                print(f"  {r['label']}: bridge_score={r['bridge_score']:.3f}, "
                      f"degree={r['degree']}, bridges: {connects_str}")
        else:
            print("  No bridge labels detected")

        # --- Communities ---
        print(f"\n{sep}")
        communities = community_detector.detect_communities(args.min_cooccurrence)
        summary = community_detector.get_community_summary(args.min_cooccurrence)
        print(f"TOPIC COMMUNITIES ({len(communities)} detected)")
        print(sep)
        for _, r in summary.iterrows():
            label_preview = ', '.join(r['labels'][:6])
            if len(r['labels']) > 6:
                label_preview += f", ... (+{len(r['labels']) - 6} more)"
            print(f"  Community {r['community_id']} ({r['top_label']} cluster): "
                  f"{r['article_count']:,} articles, {r['size']} labels")
            print(f"    Labels: {label_preview}")

        # --- Hub articles ---
        print(f"\n{sep}")
        print("HUB ARTICLES (span multiple communities)")
        print(sep)
        hub_arts = hub_detector.find_hub_articles(top_n=args.top_n,
                                                   communities=communities)
        if not hub_arts.empty:
            for _, r in hub_arts.iterrows():
                print(f"  \"{r['title']}\" ({r['date']}) - "
                      f"{r['label_count']} labels across "
                      f"{r['unique_topics']} communities")
        else:
            print("  No hub articles found")

        print(f"\n{sep}")
        return

    if args.hubs:
        print(f"\n{sep}")
        print("HUB LABELS")
        print(sep)
        hub_labels = hub_detector.find_hub_labels(top_n=args.top_n)
        for _, r in hub_labels.iterrows():
            print(f"  {r['label']}: {r['degree']} connections, "
                  f"{r['articles_count']:,} articles")

    if args.bridges:
        print(f"\n{sep}")
        print("BRIDGE LABELS")
        print(sep)
        bridges = hub_detector.find_bridge_labels(top_n=args.top_n)
        if not bridges.empty:
            for _, r in bridges.iterrows():
                connects_str = '; '.join(r['connects'][:3]) if r['connects'] else 'N/A'
                print(f"  {r['label']}: bridge_score={r['bridge_score']:.3f}, "
                      f"degree={r['degree']}")
                print(f"    Bridges: {connects_str}")
        else:
            print("  No bridge labels detected")

    if args.communities:
        print(f"\n{sep}")
        communities = community_detector.detect_communities(args.min_cooccurrence)
        summary = community_detector.get_community_summary(args.min_cooccurrence)
        print(f"TOPIC COMMUNITIES ({len(communities)} detected, "
              f"min_cooccurrence={args.min_cooccurrence})")
        print(sep)
        for _, r in summary.iterrows():
            label_preview = ', '.join(r['labels'][:8])
            if len(r['labels']) > 8:
                label_preview += f", ... (+{len(r['labels']) - 8} more)"
            print(f"  Community {r['community_id']} ({r['top_label']} cluster): "
                  f"{r['article_count']:,} articles, {r['size']} labels")
            print(f"    Labels: {label_preview}")


if __name__ == "__main__":
    main()
