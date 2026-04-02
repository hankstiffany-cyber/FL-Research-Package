#!/usr/bin/env python3
"""
FL Bibliography & Citation Analysis
Analyzes bibliography and citation data extracted from Forgotten Languages
articles to understand what real-world academic sources FL draws from.
"""

import sys
import io
import argparse
import json
import re
import os
from collections import Counter, defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_DIR = "data"

# ---------------------------------------------------------------------------
# Field classification keywords
# ---------------------------------------------------------------------------

FIELD_KEYWORDS = {
    "Linguistics/Language": [
        "language", "linguistic", "syntax", "morphology", "phonology", "dialect",
        "grammar", "lexicon", "semantics", "phonetic", "etymolog", "lexicograph",
        "sociolinguistic", "bilingual", "multilingual", "orthograph", "vowel",
        "consonant", "syllable", "prosod", "speech", "tongue", "word",
        "nomenclature", "place-name", "place name", "toponym", "onomastic",
    ],
    "Religion/Occult": [
        "religion", "magic", "witchcraft", "ritual", "occult", "sacred",
        "theology", "spiritual", "mystical", "supernatural", "demon",
        "divine", "church", "biblical", "scripture", "prayer", "cult",
        "esoteric", "hermetic", "kabbala", "gnostic", "pagan",
    ],
    "Defense/Military": [
        "defense", "defence", "military", "intelligence", "surveillance",
        "weapons", "warfare", "nuclear", "missile", "strategic",
        "security", "classified", "pentagon", "nato",
    ],
    "Science/Physics": [
        "physics", "quantum", "energy", "science", "mathematical",
        "chemistry", "biology", "particle", "relativity", "thermodynamic",
        "electron", "photon", "experiment", "laboratory",
    ],
    "History": [
        "history", "medieval", "ancient", "century", "archaeological",
        "historical", "chronicle", "antiquit", "archive", "civilization",
        "roman", "greek", "dynasty",
    ],
    "Philosophy": [
        "philosophy", "consciousness", "mind", "epistemology",
        "metaphysic", "ontolog", "phenomenolog", "logic", "ethical",
    ],
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    """Load bibliography, citation, and article data from files."""
    bib_path = os.path.join(DATA_DIR, "fl_bibliography.csv")
    cit_path = os.path.join(DATA_DIR, "fl_citations.csv")
    art_path = os.path.join(DATA_DIR, "fl_articles_raw.json")

    bib_df = pd.read_csv(bib_path, encoding="utf-8")
    cit_df = pd.read_csv(cit_path, encoding="utf-8")
    with open(art_path, encoding="utf-8") as f:
        articles = json.load(f)

    return bib_df, cit_df, articles


def _prepare_articles_df(articles):
    """Convert articles list to DataFrame with parsed dates."""
    df = pd.DataFrame(articles)
    df["date_parsed"] = pd.to_datetime(
        df["date"] + "-01", format="%Y-%m-%d", errors="coerce"
    )
    df = df.dropna(subset=["date_parsed"])
    df["year"] = df["date_parsed"].dt.year
    df["month"] = df["date_parsed"].dt.month
    # Build article_id from URL for joining
    return df


# ---------------------------------------------------------------------------
# 1. BibliographyCleaner
# ---------------------------------------------------------------------------

class BibliographyCleaner:
    """Filter out FL constructed-language noise from bibliography entries."""

    # Patterns commonly found in FL noise entries
    FL_NOISE_PATTERNS = [
        r"[a-z]{4,}ff\b",           # FL word endings like "tinkyff"
        r"\bdys\b",                  # FL function word
        r"\byr\b",                   # FL function word
        r"\beid\b",                  # FL function word
        r"\baeg\b",                  # FL function word
        r"\begel\b",                 # FL function word
        r"\bsid\b",                  # FL function word
        r"\bmer\b",                  # FL function word (sentence start)
        r"\bidalbitau\b",            # FL-specific
        r"\bimass\b",               # FL-specific
        r"\bcynegy\b",              # FL-specific
    ]

    def __init__(self):
        self._noise_stats = {"total_removed": 0, "reasons": Counter()}
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.FL_NOISE_PATTERNS]

    def _is_noise(self, row):
        """Return (is_noise: bool, reason: str or None)."""
        author = str(row.get("author", ""))
        entry_text = str(row.get("entry_text", ""))

        # Long author names are FL noise
        if len(author) > 50:
            return True, "author_too_long"

        # Entry text that is very long and contains FL patterns
        fl_hits = sum(1 for pat in self._compiled if pat.search(entry_text))
        if fl_hits >= 3:
            return True, "fl_language_patterns"

        # Author field contains FL patterns (multiple hits)
        author_hits = sum(1 for pat in self._compiled if pat.search(author))
        if author_hits >= 2:
            return True, "fl_author_patterns"

        # Entry text very long with no recognizable academic structure
        if len(entry_text) > 500 and not any(
            c in entry_text for c in [".", "(", ")", ":", ";"]
        ):
            return True, "unstructured_long_text"

        return False, None

    def clean(self, bib_df):
        """Remove FL noise entries and return cleaned DataFrame."""
        self._noise_stats = {"total_removed": 0, "reasons": Counter()}
        mask = []
        for _, row in bib_df.iterrows():
            is_noise, reason = self._is_noise(row)
            if is_noise:
                self._noise_stats["total_removed"] += 1
                self._noise_stats["reasons"][reason] += 1
            mask.append(not is_noise)

        cleaned = bib_df[mask].copy()

        # Normalize author names
        cleaned["author"] = cleaned["author"].apply(self._normalize_author)

        # Clean years
        cleaned["year"] = cleaned["year"].apply(self._clean_year)

        return cleaned

    def get_noise_stats(self):
        """Return dict with counts of removed entries and reasons."""
        return {
            "total_removed": self._noise_stats["total_removed"],
            "reasons": dict(self._noise_stats["reasons"]),
        }

    @staticmethod
    def _normalize_author(name):
        if pd.isna(name):
            return name
        name = str(name).strip()
        # Remove trailing/leading punctuation
        name = name.strip(".,;: ")
        return name

    @staticmethod
    def _clean_year(year):
        if pd.isna(year):
            return None
        try:
            y = int(float(str(year).strip()))
            if 1000 <= y <= 2030:
                return y
        except (ValueError, TypeError):
            pass
        # Try to extract 4-digit year
        m = re.search(r"\b(\d{4})\b", str(year))
        if m:
            y = int(m.group(1))
            if 1000 <= y <= 2030:
                return y
        return None


# ---------------------------------------------------------------------------
# 2. AuthorAnalyzer
# ---------------------------------------------------------------------------

class AuthorAnalyzer:
    """Analyze who FL cites."""

    def __init__(self, bib_df, cit_df=None):
        self.bib = bib_df
        self.cit = cit_df

    def get_most_cited_authors(self, top_n=30):
        """Top cited authors with citation count, articles citing, year range, sample titles."""
        valid = self.bib.dropna(subset=["author"])
        valid = valid[valid["author"].str.strip() != ""]

        grouped = valid.groupby("author")
        records = []
        for author, grp in grouped:
            years = grp["year"].dropna()
            year_range = ""
            if len(years) > 0:
                yr_min, yr_max = int(years.min()), int(years.max())
                year_range = str(yr_min) if yr_min == yr_max else f"{yr_min}-{yr_max}"

            titles = grp["title"].dropna().unique()
            sample = "; ".join(str(t).strip()[:60] for t in titles[:3])

            records.append({
                "author": author,
                "citation_count": len(grp),
                "articles_citing": grp["article_id"].nunique(),
                "year_range": year_range,
                "sample_titles": sample,
            })

        result = pd.DataFrame(records)
        result = result.sort_values("citation_count", ascending=False).head(top_n)
        return result.reset_index(drop=True)

    def get_author_fields(self):
        """Categorize authors by field based on journal/title keywords."""
        valid = self.bib.dropna(subset=["author"])
        records = []

        for author, grp in valid.groupby("author"):
            # Combine all title and journal text for this author
            text_parts = []
            for col in ["title", "journal"]:
                vals = grp[col].dropna().astype(str)
                text_parts.extend(vals.tolist())
            combined = " ".join(text_parts).lower()

            field = _classify_field(combined)
            records.append({"author": author, "field": field, "citation_count": len(grp)})

        return pd.DataFrame(records)

    def get_author_cooccurrence(self, top_n=20):
        """Which authors are frequently cited together in the same article."""
        valid = self.bib.dropna(subset=["author"])
        # Get top authors first
        top_authors = (
            valid["author"].value_counts().head(top_n).index.tolist()
        )
        valid_top = valid[valid["author"].isin(top_authors)]

        # For each article, find pairs of co-cited authors
        pair_counts = Counter()
        for article_id, grp in valid_top.groupby("article_id"):
            authors_in_article = sorted(grp["author"].unique())
            for i in range(len(authors_in_article)):
                for j in range(i + 1, len(authors_in_article)):
                    pair_counts[(authors_in_article[i], authors_in_article[j])] += 1

        records = [
            {"author_1": a1, "author_2": a2, "cooccurrence_count": cnt}
            for (a1, a2), cnt in pair_counts.most_common(50)
            if cnt > 1
        ]
        return pd.DataFrame(records) if records else pd.DataFrame(
            columns=["author_1", "author_2", "cooccurrence_count"]
        )

    def get_author_timeline(self):
        """When each author first/last appeared in FL bibliography."""
        # We need article dates - join via article_id
        # For simplicity, use the year from the bibliography year column as proxy
        valid = self.bib.dropna(subset=["author"])
        grouped = valid.groupby("author").agg(
            first_article=("article_id", "min"),
            last_article=("article_id", "max"),
            citation_count=("id", "count"),
        ).reset_index()
        return grouped.sort_values("citation_count", ascending=False)


# ---------------------------------------------------------------------------
# 3. SourceAnalyzer
# ---------------------------------------------------------------------------

class SourceAnalyzer:
    """Analyze journals, publishers, and publication types."""

    def __init__(self, bib_df):
        self.bib = bib_df

    def get_top_journals(self, top_n=20):
        """Top journals by entry count."""
        valid = self.bib.dropna(subset=["journal"])
        valid = valid[valid["journal"].str.strip() != ""]

        grouped = valid.groupby("journal").agg(
            entry_count=("id", "count"),
            unique_authors=("author", "nunique"),
        ).reset_index()

        return grouped.sort_values("entry_count", ascending=False).head(top_n).reset_index(drop=True)

    def get_top_publishers(self, top_n=20):
        """Top publishers by entry count."""
        valid = self.bib.dropna(subset=["publisher"])
        valid = valid[valid["publisher"].str.strip() != ""]

        grouped = valid.groupby("publisher").agg(
            entry_count=("id", "count"),
        ).reset_index()

        return grouped.sort_values("entry_count", ascending=False).head(top_n).reset_index(drop=True)

    def get_cited_year_distribution(self):
        """Distribution of publication years of cited works."""
        valid = self.bib.dropna(subset=["year"])
        valid = valid[valid["year"].apply(lambda y: isinstance(y, (int, float)) and 1000 <= y <= 2030)]
        counts = valid["year"].astype(int).value_counts().sort_index()
        return pd.DataFrame({"year": counts.index, "count": counts.values})

    def get_field_distribution(self):
        """Categorize bibliography by academic field using keywords."""
        records = []
        for _, row in self.bib.iterrows():
            text_parts = []
            for col in ["title", "journal", "entry_text"]:
                val = row.get(col)
                if pd.notna(val):
                    text_parts.append(str(val))
            combined = " ".join(text_parts).lower()
            field = _classify_field(combined)
            records.append(field)

        field_counts = Counter(records)
        total = sum(field_counts.values())
        result = []
        for field, count in field_counts.most_common():
            result.append({
                "field": field,
                "count": count,
                "percentage": round(100 * count / total, 1) if total > 0 else 0,
            })
        return pd.DataFrame(result)


# ---------------------------------------------------------------------------
# 4. CitationNetworkAnalyzer
# ---------------------------------------------------------------------------

class CitationNetworkAnalyzer:
    """Analyze citation patterns across FL articles."""

    def __init__(self, bib_df, cit_df, articles_df):
        self.bib = bib_df
        self.cit = cit_df
        self.articles_df = articles_df

    def get_most_cited_works(self, top_n=30):
        """Specific works (author+year+title) cited most often across FL articles."""
        valid = self.bib.dropna(subset=["author"])
        # Build a work key from author + year
        valid = valid.copy()
        valid["work_key"] = (
            valid["author"].astype(str).str.strip()
            + " ("
            + valid["year"].astype(str).str.strip()
            + ")"
        )
        valid["title_clean"] = valid["title"].fillna("").astype(str).str.strip()

        grouped = valid.groupby("work_key").agg(
            articles_citing=("article_id", "nunique"),
            total_citations=("id", "count"),
            title=("title_clean", "first"),
        ).reset_index()

        grouped = grouped.sort_values(
            ["articles_citing", "total_citations"], ascending=False
        ).head(top_n)
        return grouped.reset_index(drop=True)

    def get_citation_density_by_category(self):
        """Which FL article categories have the most citations per article."""
        # Map article_id to labels
        if "labels" not in self.articles_df.columns:
            return pd.DataFrame(columns=["category", "total_citations", "articles_with_citations", "citations_per_article"])

        # Get article_id -> URL mapping via index position
        # article_id in bib corresponds to the index in articles list
        art_labels = self.articles_df.explode("labels").dropna(subset=["labels"])

        # Count citations per article
        bib_counts = self.bib.groupby("article_id").size().reset_index(name="bib_count")

        # We need to join article_id to labels
        # article_id is 0-based index in the articles list
        art_with_idx = self.articles_df.copy()
        art_with_idx["article_idx"] = range(len(art_with_idx))

        # Explode labels
        exploded = art_with_idx.explode("labels").dropna(subset=["labels"])

        # Merge with bib counts
        merged = exploded.merge(
            bib_counts, left_on="article_idx", right_on="article_id", how="inner"
        )

        if merged.empty:
            return pd.DataFrame(columns=["category", "total_citations", "articles_with_citations", "citations_per_article"])

        result = merged.groupby("labels").agg(
            total_citations=("bib_count", "sum"),
            articles_with_citations=("article_idx", "nunique"),
        ).reset_index()
        result = result.rename(columns={"labels": "category"})
        result["citations_per_article"] = (
            result["total_citations"] / result["articles_with_citations"]
        ).round(1)
        result = result.sort_values("citations_per_article", ascending=False)
        return result.reset_index(drop=True)

    def get_citation_timeline(self):
        """How citation frequency changes over FL article publication dates."""
        art_with_idx = self.articles_df.copy()
        art_with_idx["article_idx"] = range(len(art_with_idx))

        bib_counts = self.bib.groupby("article_id").size().reset_index(name="bib_count")

        merged = art_with_idx.merge(
            bib_counts, left_on="article_idx", right_on="article_id", how="inner"
        )

        if "date_parsed" not in merged.columns:
            return pd.DataFrame(columns=["date", "total_citations", "articles_with_bib", "avg_citations"])

        monthly = merged.groupby(merged["date_parsed"].dt.to_period("M")).agg(
            total_citations=("bib_count", "sum"),
            articles_with_bib=("article_idx", "nunique"),
        ).reset_index()
        monthly["date"] = monthly["date_parsed"].dt.to_timestamp()
        monthly["avg_citations"] = (
            monthly["total_citations"] / monthly["articles_with_bib"]
        ).round(1)
        monthly = monthly.sort_values("date")
        return monthly[["date", "total_citations", "articles_with_bib", "avg_citations"]].reset_index(drop=True)

    def get_cross_article_citations(self, min_articles=2, top_n=30):
        """Authors/works cited across multiple FL articles (shared intellectual sources)."""
        valid = self.bib.dropna(subset=["author"])
        author_articles = valid.groupby("author").agg(
            articles=("article_id", "nunique"),
            total_citations=("id", "count"),
        ).reset_index()

        result = author_articles[author_articles["articles"] >= min_articles]
        result = result.sort_values(
            ["articles", "total_citations"], ascending=False
        ).head(top_n)
        return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Field classification helper
# ---------------------------------------------------------------------------

def _classify_field(text):
    """Classify text into an academic field based on keyword matching."""
    if not text or not isinstance(text, str):
        return "Other"

    text_lower = text.lower()
    scores = {}
    for field, keywords in FIELD_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[field] = score

    if not scores:
        return "Other"
    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# 5. Plotly Visualizations
# ---------------------------------------------------------------------------

def plot_top_authors(author_df, top_n=20):
    """Horizontal bar chart of most-cited authors."""
    data = author_df.head(top_n).sort_values("citation_count", ascending=True)
    fig = go.Figure(go.Bar(
        x=data["citation_count"],
        y=data["author"],
        orientation="h",
        marker_color="steelblue",
        text=data["citation_count"],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Top {top_n} Most-Cited Authors in FL Bibliography",
        xaxis_title="Citation Count",
        yaxis_title="",
        template="plotly_white",
        height=max(400, top_n * 25),
        margin=dict(l=200),
    )
    return fig


def plot_cited_year_distribution(year_df):
    """Histogram of publication years of cited works."""
    fig = go.Figure(go.Bar(
        x=year_df["year"],
        y=year_df["count"],
        marker_color="teal",
    ))
    fig.update_layout(
        title="Publication Years of Cited Works",
        xaxis_title="Year",
        yaxis_title="Number of Citations",
        template="plotly_white",
        height=400,
    )
    return fig


def plot_field_distribution(field_df):
    """Donut chart of academic fields."""
    fig = go.Figure(go.Pie(
        labels=field_df["field"],
        values=field_df["count"],
        hole=0.4,
        textinfo="label+percent",
        marker=dict(colors=px.colors.qualitative.Set2),
    ))
    fig.update_layout(
        title="Academic Field Distribution of FL Bibliography",
        template="plotly_white",
        height=450,
    )
    return fig


def plot_citation_timeline(timeline_df):
    """Line chart of citation density over time."""
    if timeline_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Citation Timeline (no data)")
        return fig

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=timeline_df["date"],
        y=timeline_df["total_citations"],
        name="Total citations",
        marker_color="steelblue",
        opacity=0.6,
    ))
    fig.add_trace(go.Scatter(
        x=timeline_df["date"],
        y=timeline_df["avg_citations"],
        name="Avg citations/article",
        yaxis="y2",
        line=dict(color="orange", width=2),
    ))
    fig.update_layout(
        title="FL Citation Frequency Over Time",
        xaxis_title="FL Publication Date",
        yaxis_title="Total Citations",
        yaxis2=dict(title="Avg Citations/Article", overlaying="y", side="right"),
        template="plotly_white",
        height=400,
    )
    return fig


def plot_author_network(cooccurrence_df, top_n=15):
    """Co-citation network visualization (authors as nodes, edges if co-cited)."""
    if cooccurrence_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Author Co-citation Network (no data)")
        return fig

    data = cooccurrence_df.head(30)

    # Collect unique authors and assign positions in a circle
    authors = set()
    for _, row in data.iterrows():
        authors.add(row["author_1"])
        authors.add(row["author_2"])
    authors = sorted(authors)[:top_n]

    import math
    n = len(authors)
    pos = {}
    for i, a in enumerate(authors):
        angle = 2 * math.pi * i / n
        pos[a] = (math.cos(angle), math.sin(angle))

    # Draw edges
    edge_x, edge_y = [], []
    edge_weights = []
    for _, row in data.iterrows():
        a1, a2 = row["author_1"], row["author_2"]
        if a1 in pos and a2 in pos:
            x0, y0 = pos[a1]
            x1, y1 = pos[a2]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_weights.append(row["cooccurrence_count"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=1, color="lightgray"),
        hoverinfo="none",
        showlegend=False,
    ))

    # Draw nodes
    node_x = [pos[a][0] for a in authors]
    node_y = [pos[a][1] for a in authors]
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(size=12, color="steelblue"),
        text=[a.split(",")[0] if "," in a else a for a in authors],
        textposition="top center",
        textfont=dict(size=9),
        hovertext=authors,
        hoverinfo="text",
        showlegend=False,
    ))

    fig.update_layout(
        title="Author Co-citation Network",
        template="plotly_white",
        height=550,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


# ---------------------------------------------------------------------------
# Full Report
# ---------------------------------------------------------------------------

def generate_report(bib_df, cit_df, articles):
    """Generate a full text report of bibliography analysis."""
    articles_df = _prepare_articles_df(articles)

    cleaner = BibliographyCleaner()
    cleaned = cleaner.clean(bib_df)
    noise_stats = cleaner.get_noise_stats()

    lines = []
    lines.append("BIBLIOGRAPHY ANALYSIS")
    lines.append("=" * 60)
    lines.append(f"Total entries: {len(bib_df):,} ({len(cleaned):,} real, {noise_stats['total_removed']:,} noise removed)")

    articles_with_bib = bib_df["article_id"].nunique()
    total_articles = len(articles)
    pct = 100 * articles_with_bib / total_articles if total_articles > 0 else 0
    lines.append(f"Unique articles with bibliography: {articles_with_bib} of {total_articles:,} ({pct:.1f}%)")

    unique_authors = cleaned.dropna(subset=["author"])["author"].nunique()
    lines.append(f"Unique cited authors: ~{unique_authors}")

    if noise_stats["reasons"]:
        lines.append(f"\nNoise removal breakdown:")
        for reason, count in sorted(noise_stats["reasons"].items(), key=lambda x: -x[1]):
            lines.append(f"  {reason}: {count}")

    # Top authors
    lines.append("")
    lines.append("TOP CITED AUTHORS:")
    author_analyzer = AuthorAnalyzer(cleaned)
    top_authors = author_analyzer.get_most_cited_authors(top_n=20)
    for _, r in top_authors.iterrows():
        lines.append(
            f"  {r['author']}: {r['citation_count']} citations across "
            f"{r['articles_citing']} article(s)"
        )

    # Field distribution
    lines.append("")
    lines.append("ACADEMIC FIELD DISTRIBUTION:")
    source_analyzer = SourceAnalyzer(cleaned)
    fields = source_analyzer.get_field_distribution()
    for _, r in fields.iterrows():
        lines.append(f"  {r['field']}: {r['percentage']}% ({r['count']:,} entries)")

    # Top journals
    lines.append("")
    lines.append("TOP JOURNALS:")
    journals = source_analyzer.get_top_journals(top_n=15)
    for _, r in journals.iterrows():
        lines.append(f"  {r['journal']}: {r['entry_count']} entries ({r['unique_authors']} authors)")

    # Cited year distribution summary
    lines.append("")
    lines.append("CITED YEAR DISTRIBUTION:")
    year_dist = source_analyzer.get_cited_year_distribution()
    if not year_dist.empty:
        lines.append(f"  Earliest cited work: {int(year_dist['year'].min())}")
        lines.append(f"  Latest cited work: {int(year_dist['year'].max())}")
        # Decade breakdown
        year_dist_copy = year_dist.copy()
        year_dist_copy["decade"] = (year_dist_copy["year"] // 10) * 10
        decade_counts = year_dist_copy.groupby("decade")["count"].sum().sort_index()
        lines.append("  By decade:")
        for decade, cnt in decade_counts.items():
            lines.append(f"    {int(decade)}s: {int(cnt)}")

    # Citation density by category
    lines.append("")
    lines.append("CITATION DENSITY BY FL CATEGORY:")
    network_analyzer = CitationNetworkAnalyzer(cleaned, cit_df, articles_df)
    density = network_analyzer.get_citation_density_by_category()
    if not density.empty:
        for _, r in density.head(15).iterrows():
            lines.append(
                f"  {r['category']}: {r['citations_per_article']} citations/article "
                f"({r['articles_with_citations']} articles)"
            )

    # Cross-article citations
    lines.append("")
    lines.append("CROSS-ARTICLE CITED AUTHORS (appearing in 2+ FL articles):")
    cross = network_analyzer.get_cross_article_citations(min_articles=2, top_n=15)
    if not cross.empty:
        for _, r in cross.iterrows():
            lines.append(
                f"  {r['author']}: {r['articles']} articles, {r['total_citations']} total citations"
            )
    else:
        lines.append("  (none found)")

    # Co-occurrence
    lines.append("")
    lines.append("AUTHOR CO-OCCURRENCE (top pairs):")
    cooc = author_analyzer.get_author_cooccurrence(top_n=20)
    if not cooc.empty:
        for _, r in cooc.head(10).iterrows():
            lines.append(
                f"  {r['author_1']} + {r['author_2']}: co-cited in {r['cooccurrence_count']} articles"
            )
    else:
        lines.append("  (none found)")

    # Citation type breakdown
    lines.append("")
    lines.append("CITATION TYPES:")
    if cit_df is not None and "citation_type" in cit_df.columns:
        type_counts = cit_df["citation_type"].value_counts()
        for ctype, cnt in type_counts.items():
            lines.append(f"  {ctype}: {cnt}")
        lines.append(f"  Total citations: {len(cit_df):,}")
        lines.append(f"  Articles with citations: {cit_df['article_id'].nunique()}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="FL Bibliography & Citation Analysis")
    parser.add_argument("--authors", action="store_true", help="Show top cited authors")
    parser.add_argument("--journals", action="store_true", help="Show top journals")
    parser.add_argument("--fields", action="store_true", help="Show field distribution")
    parser.add_argument("--timeline", action="store_true", help="Show citation timeline")
    parser.add_argument("--network", action="store_true", help="Show author co-occurrence network")
    parser.add_argument("--full-report", action="store_true", help="Run full analysis report")
    parser.add_argument("--top-n", type=int, default=20, help="Number of top results (default: 20)")

    args = parser.parse_args()

    # Default to full report if nothing specified
    if not any([args.authors, args.journals, args.fields, args.timeline, args.network, args.full_report]):
        args.full_report = True

    print("Loading data...")
    bib_df, cit_df, articles = load_data()
    print(f"  {len(bib_df):,} bibliography entries, {len(cit_df):,} citations, {len(articles):,} articles")

    if args.full_report:
        print()
        print(generate_report(bib_df, cit_df, articles))
        return

    # Clean data for individual analyses
    cleaner = BibliographyCleaner()
    cleaned = cleaner.clean(bib_df)
    noise_stats = cleaner.get_noise_stats()
    print(f"  Cleaned: {len(cleaned):,} real entries ({noise_stats['total_removed']:,} noise removed)")

    articles_df = _prepare_articles_df(articles)

    if args.authors:
        print("\nTOP CITED AUTHORS:")
        analyzer = AuthorAnalyzer(cleaned)
        top = analyzer.get_most_cited_authors(top_n=args.top_n)
        for _, r in top.iterrows():
            lines = [
                f"  {r['author']}: {r['citation_count']} citations",
                f"across {r['articles_citing']} article(s)",
            ]
            if r["year_range"]:
                lines.append(f"[{r['year_range']}]")
            print(" ".join(lines))

    if args.journals:
        print("\nTOP JOURNALS:")
        analyzer = SourceAnalyzer(cleaned)
        journals = analyzer.get_top_journals(top_n=args.top_n)
        for _, r in journals.iterrows():
            print(f"  {r['journal']}: {r['entry_count']} entries ({r['unique_authors']} authors)")

    if args.fields:
        print("\nACADEMIC FIELD DISTRIBUTION:")
        analyzer = SourceAnalyzer(cleaned)
        fields = analyzer.get_field_distribution()
        for _, r in fields.iterrows():
            bar = "#" * int(r["percentage"] / 2)
            print(f"  {r['field']}: {r['percentage']}% ({r['count']:,} entries)  {bar}")

    if args.timeline:
        print("\nCITATION TIMELINE:")
        analyzer = CitationNetworkAnalyzer(cleaned, cit_df, articles_df)
        tl = analyzer.get_citation_timeline()
        if not tl.empty:
            for _, r in tl.iterrows():
                date_str = r["date"].strftime("%Y-%m") if hasattr(r["date"], "strftime") else str(r["date"])
                print(f"  {date_str}: {int(r['total_citations'])} citations in {int(r['articles_with_bib'])} articles (avg {r['avg_citations']})")
        else:
            print("  (no timeline data)")

    if args.network:
        print("\nAUTHOR CO-OCCURRENCE:")
        analyzer = AuthorAnalyzer(cleaned)
        cooc = analyzer.get_author_cooccurrence(top_n=args.top_n)
        if not cooc.empty:
            for _, r in cooc.iterrows():
                print(f"  {r['author_1']} + {r['author_2']}: {r['cooccurrence_count']} co-citations")
        else:
            print("  (no co-occurrence data)")


if __name__ == "__main__":
    main()
