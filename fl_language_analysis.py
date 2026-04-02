#!/usr/bin/env python3
"""
FL Language Classification and Analysis
Catalogs the constructed languages used across FL articles by analyzing
label metadata, co-occurrence patterns, and temporal evolution.
"""

import sys
import io
import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_DIR = "data"

# ---------------------------------------------------------------------------
# Known topic labels (not language names)
# ---------------------------------------------------------------------------

KNOWN_TOPICS = {
    'Defense', 'Religion', 'Philosophy of Language', 'Dark Millenium',
    'Dreams', 'Poetry', 'Alchemy', 'Theosophy', 'Nag Hammadi', 'Tarot',
    'Folk', 'Anti-language', 'NodeSpaces', 'General', 'Cassini Diskus',
    'MilOrb', 'DOLYN', 'MASINT', 'NDE', 'Liber Visionum',
    'Vita Adae et Evae', 'Glossolalia', 'Vampyr', 'Angelic language',
    'Pre-Indoeuropean', 'Semitic cryptolect', 'South Atlantic Anomaly',
    # Additional topic/meta labels detected from data
    'Video', 'Cryptolect', 'Phonosemantics', 'Neurolinguistics',
    'Chemolinguistics', 'Ethnopoetry', 'Bibliographica', 'Topic',
    'Media', 'Abstract', 'Fashion', 'Future Cities', 'Landscape',
    'DNA', 'Fantasy', 'Hybrid', 'Zine', 'Technolect',
    'Unknown', 'dictionary', 'logoddely',
    # Real-world language/linguistic family references (not FL constructed langs)
    'Celtic languages', 'Old English', 'Old Gaelic', 'Old Norse',
    'Old Welsh', 'Old Finnish', 'Old High German', 'Old Slavonic',
    'Ladino', 'Lingua Franca', 'Pidgin', 'Polari',
    'Carian', 'Lycian', 'Lydian', 'Thracian', 'Lemnos',
    'Venetic', 'Messapian', 'Tartessian', 'Celtiberian', 'Phrygian',
    'Phrygia', 'Konkani', 'Kashmiri', 'Kasmiri', 'Khwarshi',
    'Na-Dene', 'Proto-Eyak', 'Nilotic', 'Magyar',
    'Sammarinese', 'Romagnol', 'Liguria', 'Gallo',
    'Konikovo', 'Freising Folia', 'Codex Gigas', 'Codex Cumanicus',
    'Ketubah', 'Wenamon',
    # Religious/mythological/historical references
    'Lilith', 'Nazorean', 'Sephardim', 'Psalter', 'Montanus',
    'Plotinus', 'Nymphas', 'Nehalennia', 'Nantosuelta', 'Morana',
    'Hercules', 'Goddess', 'Slav Godess', 'Celtic Gods and Goddesses',
    'Sechinah', 'Pict', 'Iruña-Veleia',
    'Lingua Ignota', 'Lingua Damnata', 'Lingua Demonica',
    'Confusio Linguarum', 'Legio Diabolica',
    'Guanche', 'Norn', 'Runeau',
    # Meta categories
    'Sielic Languages', 'Lakhi languages',
    'Austronesia', 'Aegean', 'Polynesian', 'Amerindia',
    'Bantu', 'Tungus', 'Turkic', 'Caucasica', 'Sinitica',
    'Semitica', 'Slavica', 'Romani',
}

# Labels that are definitely FL constructed language names
KNOWN_LANGUAGES = {
    'Millangivm', 'Dediaalif', 'De Altero Genere', 'Elyam', 'Romaniel',
    'Naoed', 'Weddag', 'Aylid', 'Niriden', 'Alashi', 'Nymma',
    'Ladd cryptolect', 'Transit', 'Drizza', 'Ned', 'Nashta',
    'Passat', 'Belas', 'Yid', 'Sla', 'Dareg', 'Eddag', 'Sca', 'Sco',
    'Ahaddi', 'Idhun', 'Dwryne', 'Tainish', 'Rhydd', 'Isparomi',
    'Norwish', 'Yanani', 'Karbeli', 'Nordiske', 'Hawa', 'Yryel',
    'Eska', 'Shue', 'Niao', 'Antient', 'Laari', 'Akeyra', 'Nura',
    'Siel', 'Azeli', 'Engser', 'Anagel', 'Adwhi', 'Anani',
    'Elyamit', 'Nilyaz', 'Elengi', 'Traddsatodd', 'Aym', 'Evat',
    'Drizeel', 'Aljamia', 'Dagani', 'Iress', 'Darid', 'Honi',
    'Arsha', 'Surati', 'Belassur', 'Zarin', 'Adyn', 'Nada',
    'Fakidi', 'Abraau', 'Illyria', 'Sarkeri', 'Taniti', 'Zayit',
    'Nythra', 'Adana', 'Naitsei', 'Mie', 'Cattell', 'Deyl',
    'Amarti', 'Sanct', 'Nyldryl', 'Akhet', 'Danae', 'Englabi',
    'Ninabi', 'Chana', 'Adar', 'Drizel', 'Kedwuylil',
    'Czecin', 'Slaagid', 'Kamri', 'Damshu', 'Nisad',
    'Halefi', 'Angi', 'Loglosia', 'Huexe', 'Pari',
    'Eastkarbelian', 'Wuarsi', 'Golden Lisu', 'Purple Lisu',
    'Yuhani', 'Dirya', 'Enais', 'Urni', 'Niriden2', 'Trova',
    'Kea', 'Romul', 'Feishu', 'Mirat', 'Zussi', 'Verta', 'Yari',
    'Nirsa', 'South Elangi', 'Meri', 'Dymma', 'Nordien',
    'Lawei', 'Sudkarbeli', 'Larta', 'Wunad', 'Tai-Lai',
    'Ska', 'Phasin ter Daenna', 'Zindzar', 'Layl', 'Dili',
    'Zirani', 'Taram', 'Suruye', 'Ladyr', 'Yryeluwa',
    'Slahu', 'Dena', 'Minuwa', 'Baran', 'Kurzi', 'Naz',
    'Tenga Bithnua', 'Ruidthich', 'Deruidim', 'Surysk',
    'Lia', 'Keshunia', 'Klina', 'Red Xie', 'Abys', 'Eru',
    'Ireshu', 'Scoshu', 'Noric', 'Nabta', 'Ishkal', 'Tenwa',
    'Awin', 'Fabiri', 'Nuir', 'Weels', 'Nhue',
    'Ofryv', 'Surna', 'Noawai', 'Aedrhy', 'Azteclan',
    'Ikhlan', 'Nordkarbeli', 'Sargi', 'Turuye East', 'Kayt',
    'Lyatt', 'Zami', 'Yelen', 'Affikh', 'Zoari', 'Ralish',
    'South Guli', 'Central Guli', 'North Guli', 'Guli',
    'Klasika', 'Dungir', 'Deringian', 'Zagdashi', 'Alari',
    'Engbas', 'Ngomu', 'Idde', 'Zalim', 'Yerna', 'Safayit',
    'Fawa', 'Tursad', 'Cytinlok', 'Lanugi', 'Zanesk', 'Qiri',
    'Javagagi', 'Sudwelf', 'Edeni', 'Belashi', 'Etshu',
    'South Gewa', 'Ludoun', 'Irssa', 'Aran', 'Newa', 'Sewa',
    'Nadwish', 'Sadd', 'Thun', 'Dreide', 'Niriden3',
    'Suraz', 'South Aran', 'Elunari', 'Issim',
    'Gitmaz', 'Naiad', 'Sif', 'Yedt', 'Nysk',
    'Tulkan', 'Atharta', 'Dumut', 'Darşi', 'East Elangi',
    'Arusi', 'Marnai', 'Unai', 'Sibe', 'Gsastidd',
    'Sufism',  # Used as language context in FL
    'Ired', 'Tora', 'Ragusa-Reškija',
    'Nordiske', 'Vietyang', 'Tai-Teng',
    'Kebəri', 'Lanči', 'Račiv', 'Crínóc', 'Gunlaug',
    'Finä', 'Xié', 'Muzika',
    'Ruçu', 'Arniţ', 'Merşi', 'Romşi', 'Ruşni', 'Çarni', 'Ešik',
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _prepare_articles_df(articles):
    """Convert articles list to DataFrame with parsed dates."""
    df = pd.DataFrame(articles)
    df['date_parsed'] = pd.to_datetime(
        df['date'] + '-01', format='%Y-%m-%d', errors='coerce'
    )
    df = df.dropna(subset=['date_parsed'])
    df['year'] = df['date_parsed'].dt.year
    df['month'] = df['date_parsed'].dt.month
    return df


def _explode_labels(articles_df):
    """Explode labels so each row is one (article, label) pair."""
    df = articles_df.copy()
    df = df[df['labels'].apply(lambda x: isinstance(x, list) and len(x) > 0)]
    return df.explode('labels').rename(columns={'labels': 'label'})


def _is_constructed_word(label):
    """Heuristic: does this label look like a constructed/fictional word?"""
    # Contains non-ASCII (CJK, Arabic, Cyrillic, diacritics beyond basic Latin)
    if any(ord(c) > 127 for c in label):
        return True
    # Very short single words (2-4 chars) that aren't common English
    common_short = {'DNA', 'NDE', 'Folk', 'Zine', 'Video', 'Media', 'Topic'}
    if label in common_short:
        return False
    # Single word, not capitalized like a proper English word pattern
    words = label.split()
    if len(words) == 1 and len(label) <= 6 and label[0].isupper():
        return True  # Short single-word labels are likely language names
    return False


# ---------------------------------------------------------------------------
# 1. LanguageClassifier
# ---------------------------------------------------------------------------

class LanguageClassifier:
    """Classify each label as TOPIC, LANGUAGE, or AMBIGUOUS."""

    def __init__(self, articles_df):
        self.articles_df = articles_df
        self.exploded = _explode_labels(articles_df)
        self._classification = None

    def classify_labels(self):
        """Classify all labels. Returns DataFrame with columns:
        label, classification, article_count, confidence
        """
        if self._classification is not None:
            return self._classification

        label_counts = self.exploded['label'].value_counts()
        # Build co-occurrence info: for each label, what other labels appear
        # on the same articles?
        label_colabels = defaultdict(Counter)
        for _, row in self.articles_df.iterrows():
            labels = row.get('labels', [])
            if not isinstance(labels, list):
                continue
            for lbl in labels:
                for other in labels:
                    if other != lbl:
                        label_colabels[lbl][other] += 1

        rows = []
        for label, count in label_counts.items():
            if label in KNOWN_TOPICS:
                classification = 'topic'
                confidence = 0.95
            elif label in KNOWN_LANGUAGES:
                classification = 'language'
                confidence = 0.95
            else:
                # Heuristic classification
                confidence = 0.5
                topic_score = 0
                lang_score = 0

                # Check co-occurrence with known topics vs known languages
                colabels = label_colabels.get(label, Counter())
                topic_cooccur = sum(
                    v for k, v in colabels.items() if k in KNOWN_TOPICS
                )
                lang_cooccur = sum(
                    v for k, v in colabels.items() if k in KNOWN_LANGUAGES
                )
                total_cooccur = sum(colabels.values())

                if total_cooccur > 0:
                    topic_ratio = topic_cooccur / total_cooccur
                    lang_ratio = lang_cooccur / total_cooccur
                    # Labels that co-occur mostly with topics (but aren't
                    # topics themselves) are likely languages
                    if topic_ratio > 0.6:
                        lang_score += 2
                    elif lang_ratio > 0.6:
                        topic_score += 2

                # Non-ASCII characters suggest constructed language
                if any(ord(c) > 127 for c in label):
                    lang_score += 2
                    confidence += 0.1

                # Phrases in FL's characteristic constructed patterns
                fl_patterns = [
                    r'^[A-Z][a-z]{2,8}$',     # Short single word (Trova, Sewa)
                    r' aff ',                   # FL particle
                    r' dys ',                   # FL particle
                    r' dy ',                    # FL particle
                    r' yr ',                    # FL particle
                    r' ud ',                    # FL particle
                    r' aeg ',                   # FL particle
                    r"'s ",                     # Possessive (Affel's)
                ]
                for pat in fl_patterns:
                    if re.search(pat, label):
                        lang_score += 1

                # Common English topic words
                topic_words = {
                    'language', 'languages', 'god', 'goddess', 'old',
                    'cities', 'future', 'south', 'north', 'east', 'west',
                    'central', 'proto', 'pre',
                }
                label_lower_words = set(label.lower().split())
                if label_lower_words & topic_words:
                    topic_score += 1

                # Labels with very high article counts that aren't in known
                # sets tend to be languages (FL languages are prolific)
                if count >= 30 and lang_score >= topic_score:
                    lang_score += 1
                    confidence += 0.1

                if lang_score > topic_score:
                    classification = 'language'
                    confidence = min(0.9, confidence + 0.1 * (lang_score - topic_score))
                elif topic_score > lang_score:
                    classification = 'topic'
                    confidence = min(0.9, confidence + 0.1 * (topic_score - lang_score))
                else:
                    classification = 'ambiguous'

            rows.append({
                'label': label,
                'classification': classification,
                'article_count': count,
                'confidence': round(confidence, 2),
            })

        self._classification = pd.DataFrame(rows).sort_values(
            'article_count', ascending=False
        ).reset_index(drop=True)
        return self._classification

    def get_languages(self):
        """Return list of labels classified as languages."""
        clf = self.classify_labels()
        return clf[clf['classification'] == 'language']['label'].tolist()

    def get_topics(self):
        """Return list of labels classified as topics."""
        clf = self.classify_labels()
        return clf[clf['classification'] == 'topic']['label'].tolist()


# ---------------------------------------------------------------------------
# 2. LanguageAnalyzer
# ---------------------------------------------------------------------------

class LanguageAnalyzer:
    """Analyze language usage patterns across the corpus."""

    def __init__(self, articles_df, languages):
        self.articles_df = articles_df
        self.languages = set(languages)
        self.exploded = _explode_labels(articles_df)
        self.lang_df = self.exploded[self.exploded['label'].isin(self.languages)]

    def get_language_stats(self):
        """Per-language statistics."""
        rows = []
        for lang in sorted(self.languages):
            subset = self.lang_df[self.lang_df['label'] == lang]
            if subset.empty:
                continue
            article_count = len(subset)
            first_seen = subset['date_parsed'].min()
            last_seen = subset['date_parsed'].max()
            if pd.notna(first_seen) and pd.notna(last_seen):
                active_months = max(
                    1,
                    (last_seen.year - first_seen.year) * 12
                    + (last_seen.month - first_seen.month) + 1,
                )
            else:
                active_months = 0
            avg_excerpts = subset['excerpt_count'].mean() if 'excerpt_count' in subset.columns else 0
            rows.append({
                'language': lang,
                'article_count': article_count,
                'first_seen': first_seen.strftime('%Y-%m') if pd.notna(first_seen) else '',
                'last_seen': last_seen.strftime('%Y-%m') if pd.notna(last_seen) else '',
                'active_months': active_months,
                'avg_excerpts': round(avg_excerpts, 1),
            })
        return pd.DataFrame(rows).sort_values(
            'article_count', ascending=False
        ).reset_index(drop=True)

    def get_language_timeline(self, language):
        """Monthly article count for a specific language."""
        subset = self.lang_df[self.lang_df['label'] == language]
        if subset.empty:
            return pd.DataFrame(columns=['date', 'count'])
        counts = subset.groupby('date_parsed').size()
        full_idx = pd.date_range(counts.index.min(), counts.index.max(), freq='MS')
        counts = counts.reindex(full_idx, fill_value=0)
        return pd.DataFrame({'date': counts.index, 'count': counts.values})

    def get_language_cooccurrence(self):
        """Which languages appear together on the same articles."""
        pairs = Counter()
        for _, row in self.articles_df.iterrows():
            labels = row.get('labels', [])
            if not isinstance(labels, list):
                continue
            langs_on_article = [l for l in labels if l in self.languages]
            for i, a in enumerate(langs_on_article):
                for b in langs_on_article[i + 1:]:
                    key = tuple(sorted([a, b]))
                    pairs[key] += 1
        rows = []
        for (a, b), count in pairs.most_common():
            rows.append({'language_a': a, 'language_b': b, 'cooccurrence': count})
        return pd.DataFrame(rows)

    def get_language_topic_matrix(self):
        """Which topics each language covers (co-occurrence matrix)."""
        topic_set = KNOWN_TOPICS
        # Build lang -> topic counts
        lang_topics = defaultdict(Counter)
        for _, row in self.articles_df.iterrows():
            labels = row.get('labels', [])
            if not isinstance(labels, list):
                continue
            langs = [l for l in labels if l in self.languages]
            topics = [l for l in labels if l in topic_set]
            for lang in langs:
                for topic in topics:
                    lang_topics[lang][topic] += 1

        # Build matrix
        all_topics = sorted(
            set(t for counts in lang_topics.values() for t in counts)
        )
        rows = []
        for lang in sorted(lang_topics.keys()):
            row = {'language': lang}
            for t in all_topics:
                row[t] = lang_topics[lang].get(t, 0)
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.set_index('language')
            # Sort by total topic associations
            df['_total'] = df.sum(axis=1)
            df = df.sort_values('_total', ascending=False).drop(columns=['_total'])
        return df

    def get_prolific_languages(self, top_n=30):
        """Most-used languages ranked by article count."""
        stats = self.get_language_stats()
        return stats.head(top_n)


# ---------------------------------------------------------------------------
# 3. LanguageFamilyDetector
# ---------------------------------------------------------------------------

class LanguageFamilyDetector:
    """Group languages into families based on topic co-occurrence similarity."""

    def __init__(self, language_analyzer):
        self.analyzer = language_analyzer
        self._families = None

    def _cosine_similarity(self, vec_a, vec_b):
        """Cosine similarity between two lists/arrays."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def detect_families(self, similarity_threshold=0.6, min_articles=5):
        """Cluster languages into families using greedy agglomerative approach.
        Returns dict of family_id -> list of language names.
        """
        if self._families is not None:
            return self._families

        matrix = self.analyzer.get_language_topic_matrix()
        if matrix.empty:
            self._families = {}
            return self._families

        # Filter to languages with at least min_articles topic associations
        row_sums = matrix.sum(axis=1)
        matrix = matrix[row_sums >= min_articles]

        if matrix.empty:
            self._families = {}
            return self._families

        languages = list(matrix.index)
        vectors = {lang: list(matrix.loc[lang]) for lang in languages}

        # Greedy clustering: assign each language to closest existing family
        # or create new family
        families = {}
        family_id = 0
        assigned = set()

        # Sort by article count (most prolific first as seeds)
        stats = self.analyzer.get_language_stats()
        lang_order = [
            l for l in stats['language'].tolist() if l in set(languages)
        ]
        # Add any remaining
        for l in languages:
            if l not in lang_order:
                lang_order.append(l)

        for lang in lang_order:
            if lang not in vectors or lang in assigned:
                continue

            best_family = None
            best_sim = 0.0

            # Compare with existing family centroids
            for fid, members in families.items():
                # Family centroid = average of member vectors
                centroid = [0.0] * len(vectors[lang])
                for m in members:
                    for i, v in enumerate(vectors[m]):
                        centroid[i] += v
                centroid = [c / len(members) for c in centroid]
                sim = self._cosine_similarity(vectors[lang], centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_family = fid

            if best_sim >= similarity_threshold and best_family is not None:
                families[best_family].append(lang)
            else:
                families[family_id] = [lang]
                family_id += 1

            assigned.add(lang)

        self._families = families
        return self._families

    def get_family_summary(self):
        """Summary DataFrame of language families."""
        families = self.detect_families()
        stats = self.analyzer.get_language_stats()
        stats_dict = dict(zip(stats['language'], stats['article_count']))
        matrix = self.analyzer.get_language_topic_matrix()

        rows = []
        for fid, members in sorted(families.items()):
            total_articles = sum(stats_dict.get(m, 0) for m in members)

            # Determine primary topics for this family
            if not matrix.empty:
                family_members_in_matrix = [m for m in members if m in matrix.index]
                if family_members_in_matrix:
                    topic_sums = matrix.loc[family_members_in_matrix].sum()
                    top_topics = topic_sums.nlargest(3)
                    primary_topics = ', '.join(
                        f"{t} ({int(v)})"
                        for t, v in top_topics.items() if v > 0
                    )
                else:
                    primary_topics = ''
            else:
                primary_topics = ''

            rows.append({
                'family_id': fid,
                'languages': ', '.join(members[:10]) + (
                    f' (+{len(members)-10} more)' if len(members) > 10 else ''
                ),
                'language_count': len(members),
                'primary_topics': primary_topics,
                'article_count': total_articles,
            })

        return pd.DataFrame(rows).sort_values(
            'article_count', ascending=False
        ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. LanguageEvolutionTracker
# ---------------------------------------------------------------------------

class LanguageEvolutionTracker:
    """Track how languages appear, grow, and go dormant over time."""

    def __init__(self, articles_df, languages):
        self.articles_df = articles_df
        self.languages = set(languages)
        self.exploded = _explode_labels(articles_df)
        self.lang_df = self.exploded[self.exploded['label'].isin(self.languages)]
        # Determine the latest date in the dataset for dormancy checks
        self._max_date = articles_df['date_parsed'].max()

    def get_language_lifecycle(self, dormant_months=18):
        """Lifecycle status for each language.
        Status: active (seen in last dormant_months months),
                dormant (not seen recently but not very old),
                retired (inactive for 3+ years).
        """
        rows = []
        cutoff_dormant = self._max_date - pd.DateOffset(months=dormant_months)
        cutoff_retired = self._max_date - pd.DateOffset(months=36)

        for lang in sorted(self.languages):
            subset = self.lang_df[self.lang_df['label'] == lang]
            if subset.empty:
                continue

            birth_date = subset['date_parsed'].min()
            last_active = subset['date_parsed'].max()

            if pd.isna(birth_date) or pd.isna(last_active):
                continue

            lifespan_months = max(
                1,
                (last_active.year - birth_date.year) * 12
                + (last_active.month - birth_date.month) + 1,
            )

            # Find peak month
            monthly = subset.groupby('date_parsed').size()
            peak_month = monthly.idxmax()

            if last_active >= cutoff_dormant:
                status = 'active'
            elif last_active >= cutoff_retired:
                status = 'dormant'
            else:
                status = 'retired'

            rows.append({
                'language': lang,
                'birth_date': birth_date.strftime('%Y-%m'),
                'last_active': last_active.strftime('%Y-%m'),
                'lifespan_months': lifespan_months,
                'status': status,
                'peak_month': peak_month.strftime('%Y-%m'),
                'article_count': len(subset),
            })

        return pd.DataFrame(rows).sort_values(
            'article_count', ascending=False
        ).reset_index(drop=True)

    def get_era_languages(self, year_start, year_end):
        """Languages active in the given year range."""
        mask = (
            (self.lang_df['year'] >= year_start)
            & (self.lang_df['year'] <= year_end)
        )
        subset = self.lang_df[mask]
        counts = subset['label'].value_counts().reset_index()
        counts.columns = ['language', 'article_count']
        return counts

    def get_new_languages_by_year(self):
        """Count of new language first appearances per year."""
        first_seen = {}
        for lang in self.languages:
            subset = self.lang_df[self.lang_df['label'] == lang]
            if subset.empty:
                continue
            first = subset['date_parsed'].min()
            if pd.notna(first):
                first_seen[lang] = first.year

        year_counts = Counter(first_seen.values())
        years = sorted(year_counts.keys())
        return pd.DataFrame({
            'year': years,
            'new_languages': [year_counts[y] for y in years],
        })


# ---------------------------------------------------------------------------
# 5. Plotly Visualizations
# ---------------------------------------------------------------------------

def plot_language_timeline(analyzer, top_n=15):
    """Top N languages over time as multi-line chart."""
    stats = analyzer.get_language_stats()
    top_langs = stats.head(top_n)['language'].tolist()

    fig = go.Figure()
    for lang in top_langs:
        tl = analyzer.get_language_timeline(lang)
        if tl.empty:
            continue
        # Smooth with 3-month rolling average for readability
        tl['smoothed'] = tl['count'].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=tl['date'], y=tl['smoothed'],
            mode='lines', name=lang,
            hovertemplate=f'{lang}<br>%{{x|%Y-%m}}: %{{y:.1f}} articles<extra></extra>',
        ))

    fig.update_layout(
        title=f'Top {top_n} FL Languages Over Time (3-month rolling avg)',
        xaxis_title='Date',
        yaxis_title='Articles per Month',
        template='plotly_white',
        height=500,
        legend=dict(font=dict(size=9)),
    )
    return fig


def plot_language_topic_heatmap(analyzer, top_n=30):
    """Heatmap of languages x topics."""
    matrix = analyzer.get_language_topic_matrix()
    if matrix.empty:
        fig = go.Figure()
        fig.update_layout(title='No language-topic data')
        return fig

    # Filter to top N languages by total
    row_totals = matrix.sum(axis=1)
    top_langs = row_totals.nlargest(top_n).index
    matrix = matrix.loc[top_langs]

    # Remove columns (topics) with all zeros
    col_sums = matrix.sum(axis=0)
    active_topics = col_sums[col_sums > 0].index
    matrix = matrix[active_topics]

    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=list(matrix.columns),
        y=list(matrix.index),
        colorscale='YlOrRd',
        hoverongaps=False,
    ))
    fig.update_layout(
        title=f'Language-Topic Association Heatmap (top {top_n} languages)',
        xaxis_title='Topic',
        yaxis_title='Language',
        template='plotly_white',
        height=max(400, top_n * 20),
        xaxis=dict(tickangle=45),
    )
    return fig


def plot_language_births(tracker):
    """Bar chart of new languages per year."""
    data = tracker.get_new_languages_by_year()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title='No language birth data')
        return fig

    fig = go.Figure(go.Bar(
        x=data['year'],
        y=data['new_languages'],
        marker_color='steelblue',
        text=data['new_languages'],
        textposition='outside',
    ))
    fig.update_layout(
        title='New FL Languages Introduced Per Year',
        xaxis_title='Year',
        yaxis_title='New Languages',
        template='plotly_white',
        height=400,
    )
    return fig


def plot_language_families(detector):
    """Treemap showing language families."""
    summary = detector.get_family_summary()
    if summary.empty:
        fig = go.Figure()
        fig.update_layout(title='No language family data')
        return fig

    # Build treemap data: each language as a leaf under its family
    families = detector.detect_families()
    stats = detector.analyzer.get_language_stats()
    stats_dict = dict(zip(stats['language'], stats['article_count']))

    labels_list = []
    parents_list = []
    values_list = []
    texts_list = []

    for fid, members in sorted(families.items()):
        family_name = f"Family {fid}"
        # Add family node
        labels_list.append(family_name)
        parents_list.append('')
        values_list.append(0)
        texts_list.append(f"{len(members)} languages")

        for member in members:
            count = stats_dict.get(member, 1)
            labels_list.append(member)
            parents_list.append(family_name)
            values_list.append(count)
            texts_list.append(f"{count} articles")

    fig = go.Figure(go.Treemap(
        labels=labels_list,
        parents=parents_list,
        values=values_list,
        text=texts_list,
        textinfo='label+text',
        hovertemplate='%{label}<br>%{text}<extra></extra>',
    ))
    fig.update_layout(
        title='FL Language Families (grouped by topic similarity)',
        height=600,
        template='plotly_white',
    )
    return fig


# ---------------------------------------------------------------------------
# Data loading (standalone CLI)
# ---------------------------------------------------------------------------

def load_data():
    """Load articles data from JSON."""
    articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
    with open(articles_path, encoding='utf-8') as f:
        articles = json.load(f)
    return articles


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Fix Windows console encoding
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace'
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace'
        )

    parser = argparse.ArgumentParser(
        description='FL Language Classification and Analysis'
    )
    parser.add_argument(
        '--classify', action='store_true',
        help='Show label classification (topic vs language)',
    )
    parser.add_argument(
        '--languages', action='store_true',
        help='List all identified constructed languages',
    )
    parser.add_argument(
        '--stats', action='store_true',
        help='Show language usage statistics',
    )
    parser.add_argument(
        '--families', action='store_true',
        help='Detect and show language families',
    )
    parser.add_argument(
        '--evolution', action='store_true',
        help='Show language lifecycle and evolution',
    )
    parser.add_argument(
        '--full-report', action='store_true',
        help='Run all analyses and print full report',
    )
    parser.add_argument(
        '--top-n', type=int, default=30,
        help='Number of top items to display (default: 30)',
    )

    args = parser.parse_args()

    if not any([
        args.classify, args.languages, args.stats,
        args.families, args.evolution, args.full_report,
    ]):
        args.full_report = True

    print("Loading data...")
    articles = load_data()
    articles_df = _prepare_articles_df(articles)
    print(f"  {len(articles_df)} articles loaded")

    sep = "=" * 70

    # Classify
    classifier = LanguageClassifier(articles_df)
    clf = classifier.classify_labels()
    languages = classifier.get_languages()
    topics = classifier.get_topics()

    if args.classify or args.full_report:
        print(f"\n{sep}")
        print("LABEL CLASSIFICATION")
        print(sep)
        print(f"  Total unique labels: {len(clf)}")
        print(f"  Classified as LANGUAGE: {len(clf[clf['classification'] == 'language'])}")
        print(f"  Classified as TOPIC: {len(clf[clf['classification'] == 'topic'])}")
        print(f"  Classified as AMBIGUOUS: {len(clf[clf['classification'] == 'ambiguous'])}")

        print(f"\n  Top languages by article count:")
        lang_clf = clf[clf['classification'] == 'language'].head(args.top_n)
        for _, r in lang_clf.iterrows():
            bar = '#' * min(int(r['article_count'] / 10), 50)
            print(f"    {r['label']:40s} {r['article_count']:5d}  conf={r['confidence']:.2f}  {bar}")

        print(f"\n  Topic labels:")
        topic_clf = clf[clf['classification'] == 'topic'].head(40)
        for _, r in topic_clf.iterrows():
            print(f"    {r['label']:40s} {r['article_count']:5d}")

        ambig = clf[clf['classification'] == 'ambiguous']
        if not ambig.empty:
            print(f"\n  Ambiguous labels ({len(ambig)}):")
            for _, r in ambig.iterrows():
                print(f"    {r['label']:40s} {r['article_count']:5d}  conf={r['confidence']:.2f}")

    if args.languages or args.full_report:
        print(f"\n{sep}")
        print(f"IDENTIFIED LANGUAGES ({len(languages)})")
        print(sep)
        for i, lang in enumerate(sorted(languages)):
            count = clf[clf['label'] == lang]['article_count'].values
            count_str = f"({count[0]} articles)" if len(count) > 0 else ""
            print(f"  {i+1:3d}. {lang:40s} {count_str}")

    # Analyzer
    analyzer = LanguageAnalyzer(articles_df, languages)

    if args.stats or args.full_report:
        print(f"\n{sep}")
        print("LANGUAGE STATISTICS")
        print(sep)
        stats = analyzer.get_language_stats()
        prolific = stats.head(args.top_n)
        print(f"\n  Top {args.top_n} most-used languages:")
        print(f"  {'Language':35s} {'Articles':>8s} {'First':>8s} {'Last':>8s} {'Months':>7s} {'Excerpts':>8s}")
        print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")
        for _, r in prolific.iterrows():
            print(
                f"  {r['language']:35s} {r['article_count']:8d} "
                f"{r['first_seen']:>8s} {r['last_seen']:>8s} "
                f"{r['active_months']:7d} {r['avg_excerpts']:8.1f}"
            )

        # Co-occurrence
        cooccur = analyzer.get_language_cooccurrence()
        if not cooccur.empty:
            print(f"\n  Top language co-occurrences:")
            for _, r in cooccur.head(15).iterrows():
                print(f"    {r['language_a']:25s} + {r['language_b']:25s} = {r['cooccurrence']:3d} articles")

    if args.families or args.full_report:
        print(f"\n{sep}")
        print("LANGUAGE FAMILIES")
        print(sep)
        detector = LanguageFamilyDetector(analyzer)
        summary = detector.get_family_summary()
        if summary.empty:
            print("  No families detected (insufficient topic co-occurrence data)")
        else:
            for _, r in summary.iterrows():
                print(f"\n  Family {r['family_id']} ({r['language_count']} languages, {r['article_count']} articles)")
                print(f"    Languages: {r['languages']}")
                if r['primary_topics']:
                    print(f"    Topics:    {r['primary_topics']}")

    if args.evolution or args.full_report:
        print(f"\n{sep}")
        print("LANGUAGE EVOLUTION")
        print(sep)
        tracker = LanguageEvolutionTracker(articles_df, languages)
        lifecycle = tracker.get_language_lifecycle()

        active = lifecycle[lifecycle['status'] == 'active']
        dormant = lifecycle[lifecycle['status'] == 'dormant']
        retired = lifecycle[lifecycle['status'] == 'retired']
        print(f"  Active languages:  {len(active)}")
        print(f"  Dormant languages: {len(dormant)}")
        print(f"  Retired languages: {len(retired)}")

        if not active.empty:
            print(f"\n  Active languages (top {min(20, len(active))}):")
            for _, r in active.head(20).iterrows():
                print(
                    f"    {r['language']:30s} born {r['birth_date']}  "
                    f"last {r['last_active']}  peak {r['peak_month']}  "
                    f"{r['article_count']} articles"
                )

        if not dormant.empty:
            print(f"\n  Dormant languages (top {min(15, len(dormant))}):")
            for _, r in dormant.head(15).iterrows():
                print(
                    f"    {r['language']:30s} born {r['birth_date']}  "
                    f"last {r['last_active']}  {r['article_count']} articles"
                )

        if not retired.empty:
            print(f"\n  Retired languages (top {min(15, len(retired))}):")
            for _, r in retired.head(15).iterrows():
                print(
                    f"    {r['language']:30s} born {r['birth_date']}  "
                    f"last {r['last_active']}  {r['article_count']} articles"
                )

        new_by_year = tracker.get_new_languages_by_year()
        if not new_by_year.empty:
            print(f"\n  New languages introduced per year:")
            for _, r in new_by_year.iterrows():
                bar = '#' * r['new_languages']
                print(f"    {int(r['year'])}: {r['new_languages']:3d} {bar}")

    print(f"\n{sep}")
    print("Analysis complete.")


if __name__ == "__main__":
    main()
