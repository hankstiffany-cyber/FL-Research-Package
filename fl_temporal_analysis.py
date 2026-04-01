#!/usr/bin/env python3
"""
FL Temporal Pattern Analysis
Detects publication bursts, category trend shifts, keyword spikes,
seasonal patterns, and coordinate timing from FL articles (2009-2026).
"""

import sys
import io
import argparse
import json
import re
import os
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

DATA_DIR = "data"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _extract_date_from_url(url):
    m = re.search(r'/(\d{4})/(\d{2})/', url)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _prepare_articles_df(articles):
    df = pd.DataFrame(articles)
    df['date_parsed'] = pd.to_datetime(df['date'] + '-01', format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['date_parsed'])
    df['year'] = df['date_parsed'].dt.year
    df['month'] = df['date_parsed'].dt.month
    return df


def _build_monthly_series(counts_series, start=None, end=None):
    """Reindex a monthly count series to a complete date range, filling zeros."""
    if counts_series.empty:
        return counts_series
    if start is None:
        start = counts_series.index.min()
    if end is None:
        end = counts_series.index.max()
    full_idx = pd.date_range(start, end, freq='MS')
    return counts_series.reindex(full_idx, fill_value=0)


# ---------------------------------------------------------------------------
# 1. Publication Rate Analyzer
# ---------------------------------------------------------------------------

class PublicationRateAnalyzer:
    def __init__(self, articles_df):
        self.df = articles_df
        self._monthly = None

    def _get_monthly(self):
        if self._monthly is None:
            counts = self.df.groupby('date_parsed').size()
            self._monthly = _build_monthly_series(counts)
        return self._monthly

    def get_monthly_counts(self):
        s = self._get_monthly()
        return pd.DataFrame({'date': s.index, 'count': s.values})

    def get_yearly_counts(self):
        counts = self.df.groupby('year').size().reset_index(name='count')
        return counts

    def get_rolling_average(self, window=6):
        s = self._get_monthly()
        ra = s.rolling(window, min_periods=1).mean()
        return pd.DataFrame({'date': s.index, 'count': s.values, 'rolling_avg': ra.values})

    def detect_bursts(self, z_threshold=2.0, window=12):
        s = self._get_monthly()
        rm = s.rolling(window, min_periods=3).mean()
        rs = s.rolling(window, min_periods=3).std().replace(0, 1)
        z = (s - rm) / rs
        result = pd.DataFrame({
            'date': s.index,
            'count': s.values,
            'rolling_mean': rm.values,
            'z_score': z.values,
            'is_burst': z.values > z_threshold,
        })
        return result

    def detect_quiet_periods(self, z_threshold=-1.5, window=12):
        s = self._get_monthly()
        rm = s.rolling(window, min_periods=3).mean()
        rs = s.rolling(window, min_periods=3).std().replace(0, 1)
        z = (s - rm) / rs
        result = pd.DataFrame({
            'date': s.index,
            'count': s.values,
            'rolling_mean': rm.values,
            'z_score': z.values,
            'is_quiet': z.values < z_threshold,
        })
        return result

    def get_summary_stats(self):
        s = self._get_monthly()
        bursts = self.detect_bursts()
        quiet = self.detect_quiet_periods()
        peak_idx = s.idxmax()
        trough_idx = s.idxmin()
        return {
            'total_articles': int(s.sum()),
            'total_months': len(s),
            'avg_per_month': round(s.mean(), 1),
            'median_per_month': round(s.median(), 1),
            'std_per_month': round(s.std(), 1),
            'peak_month': peak_idx.strftime('%Y-%m'),
            'peak_count': int(s[peak_idx]),
            'quietest_month': trough_idx.strftime('%Y-%m'),
            'quietest_count': int(s[trough_idx]),
            'num_bursts': int(bursts['is_burst'].sum()),
            'num_quiet_periods': int(quiet['is_quiet'].sum()),
        }

    def plot_publication_rate(self):
        ra = self.get_rolling_average(window=6)
        bursts = self.detect_bursts()
        burst_points = bursts[bursts['is_burst']]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=ra['date'], y=ra['count'],
            name='Monthly articles', marker_color='steelblue', opacity=0.6,
        ))
        fig.add_trace(go.Scatter(
            x=ra['date'], y=ra['rolling_avg'],
            name='6-month rolling avg', line=dict(color='orange', width=2),
        ))
        if not burst_points.empty:
            fig.add_trace(go.Scatter(
                x=burst_points['date'], y=burst_points['count'],
                mode='markers', name='Burst',
                marker=dict(color='red', size=10, symbol='triangle-up'),
            ))
        fig.update_layout(
            title='FL Publication Rate Over Time',
            xaxis_title='Date', yaxis_title='Articles per Month',
            template='plotly_white', height=450,
        )
        return fig

    def plot_bursts(self):
        data = self.detect_bursts()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['z_score'],
            mode='lines', name='Z-score', line=dict(color='steelblue'),
        ))
        fig.add_hline(y=2.0, line_dash='dash', line_color='red',
                      annotation_text='Burst threshold (z=2.0)')
        fig.add_hline(y=-1.5, line_dash='dash', line_color='blue',
                      annotation_text='Quiet threshold (z=-1.5)')
        fig.update_layout(
            title='Publication Rate Z-Score',
            xaxis_title='Date', yaxis_title='Z-Score',
            template='plotly_white', height=350,
        )
        return fig


# ---------------------------------------------------------------------------
# 2. Category Trend Analyzer
# ---------------------------------------------------------------------------

class CategoryTrendAnalyzer:
    def __init__(self, articles_df):
        self.df = articles_df
        # Explode labels for per-label grouping
        self._exploded = articles_df.explode('labels').dropna(subset=['labels'])

    def get_category_timeline(self, category):
        subset = self._exploded[self._exploded['labels'] == category]
        counts = subset.groupby('date_parsed').size()
        counts = _build_monthly_series(counts,
                                       self.df['date_parsed'].min(),
                                       self.df['date_parsed'].max())
        return pd.DataFrame({'date': counts.index, 'count': counts.values})

    def _get_top_categories(self, n=20):
        return self._exploded['labels'].value_counts().head(n).index.tolist()

    def detect_trending_categories(self, recent_months=12):
        cutoff = self.df['date_parsed'].max() - pd.DateOffset(months=recent_months)
        results = []
        for cat in self._get_top_categories(50):
            subset = self._exploded[self._exploded['labels'] == cat]
            recent = subset[subset['date_parsed'] > cutoff]
            historical = subset[subset['date_parsed'] <= cutoff]
            hist_months = max(len(historical['date_parsed'].dt.to_period('M').unique()), 1)
            recent_months_actual = max(recent_months, 1)
            recent_avg = len(recent) / recent_months_actual
            hist_avg = len(historical) / hist_months
            ratio = recent_avg / hist_avg if hist_avg > 0 else (999 if recent_avg > 0 else 0)
            results.append({
                'category': cat,
                'recent_avg': round(recent_avg, 2),
                'historical_avg': round(hist_avg, 2),
                'trend_ratio': round(ratio, 2),
                'total_count': len(subset),
                'direction': 'rising' if ratio > 1.2 else ('declining' if ratio < 0.8 else 'stable'),
            })
        return pd.DataFrame(results).sort_values('trend_ratio', ascending=False)

    def detect_new_categories(self):
        first_dates = self._exploded.groupby('labels')['date_parsed'].min().reset_index()
        first_dates.columns = ['category', 'first_date']
        counts = self._exploded['labels'].value_counts().reset_index()
        counts.columns = ['category', 'total_count']
        merged = first_dates.merge(counts, on='category')
        return merged.sort_values('first_date', ascending=False)

    def get_cooccurrence_timeline(self, cat1, cat2):
        both = self.df[self.df['labels'].apply(
            lambda ls: isinstance(ls, list) and cat1 in ls and cat2 in ls
        )]
        counts = both.groupby('date_parsed').size()
        counts = _build_monthly_series(counts,
                                       self.df['date_parsed'].min(),
                                       self.df['date_parsed'].max())
        return pd.DataFrame({'date': counts.index, 'count': counts.values})

    def detect_cooccurrence_shifts(self, recent_months=12, top_n=20):
        cutoff = self.df['date_parsed'].max() - pd.DateOffset(months=recent_months)
        # Find top co-occurring pairs
        from collections import Counter
        pair_counts = Counter()
        for _, row in self.df.iterrows():
            labels = row.get('labels', [])
            if not isinstance(labels, list) or len(labels) < 2:
                continue
            for i in range(len(labels)):
                for j in range(i + 1, len(labels)):
                    pair = tuple(sorted([labels[i], labels[j]]))
                    pair_counts[pair] += 1

        results = []
        for (c1, c2), total in pair_counts.most_common(top_n):
            both = self.df[self.df['labels'].apply(
                lambda ls: isinstance(ls, list) and c1 in ls and c2 in ls
            )]
            recent = both[both['date_parsed'] > cutoff]
            historical = both[both['date_parsed'] <= cutoff]
            hist_months_count = max(len(historical['date_parsed'].dt.to_period('M').unique()), 1)
            recent_avg = len(recent) / max(recent_months, 1)
            hist_avg = len(historical) / hist_months_count
            ratio = recent_avg / hist_avg if hist_avg > 0 else (999 if recent_avg > 0 else 0)
            results.append({
                'category_1': c1, 'category_2': c2,
                'recent_avg': round(recent_avg, 2),
                'historical_avg': round(hist_avg, 2),
                'shift_ratio': round(ratio, 2),
                'total': total,
            })
        return pd.DataFrame(results).sort_values('shift_ratio', ascending=False)

    def plot_category_trends(self, categories=None):
        if categories is None:
            categories = self._get_top_categories(8)
        fig = go.Figure()
        for cat in categories:
            tl = self.get_category_timeline(cat)
            # Use 6-month rolling avg for readability
            tl['smoothed'] = tl['count'].rolling(6, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=tl['date'], y=tl['smoothed'],
                name=cat, mode='lines',
            ))
        fig.update_layout(
            title='Category Trends (6-month rolling average)',
            xaxis_title='Date', yaxis_title='Articles/month',
            template='plotly_white', height=450,
        )
        return fig

    def plot_trending_vs_declining(self):
        trends = self.detect_trending_categories()
        rising = trends[trends['direction'] == 'rising'].head(10)
        declining = trends[trends['direction'] == 'declining'].head(10)
        combined = pd.concat([rising, declining])
        colors = ['green' if d == 'rising' else 'red' for d in combined['direction']]
        fig = go.Figure(go.Bar(
            x=combined['category'], y=combined['trend_ratio'],
            marker_color=colors,
            text=combined['direction'],
        ))
        fig.add_hline(y=1.0, line_dash='dash', line_color='gray')
        fig.update_layout(
            title='Category Trend Ratios (recent 12 months vs historical)',
            xaxis_title='Category', yaxis_title='Trend Ratio',
            template='plotly_white', height=400,
        )
        return fig


# ---------------------------------------------------------------------------
# 3. Keyword Burst Detector
# ---------------------------------------------------------------------------

class KeywordBurstDetector:
    def __init__(self, keyword_index, articles_df):
        self.keyword_index = keyword_index
        self.articles_df = articles_df
        self._date_range = (articles_df['date_parsed'].min(), articles_df['date_parsed'].max())

    def get_keyword_monthly_counts(self, keyword):
        entries = self.keyword_index.get(keyword, [])
        if not entries:
            entries = self.keyword_index.get(keyword.lower(), [])
        dates = []
        for entry in entries:
            url = entry if isinstance(entry, str) else entry.get('url', '')
            d = _extract_date_from_url(url)
            if d:
                dates.append(pd.to_datetime(d + '-01'))
        if not dates:
            return pd.DataFrame(columns=['date', 'count'])
        s = pd.Series(dates).value_counts().sort_index()
        s = _build_monthly_series(s, self._date_range[0], self._date_range[1])
        return pd.DataFrame({'date': s.index, 'count': s.values})

    def detect_bursts(self, keyword, z_threshold=2.5, window=12):
        mc = self.get_keyword_monthly_counts(keyword)
        if mc.empty or mc['count'].sum() == 0:
            return pd.DataFrame()
        # Require minimum data points
        nonzero = (mc['count'] > 0).sum()
        if nonzero < 6:
            return pd.DataFrame()

        s = mc.set_index('date')['count']
        rm = s.rolling(window, min_periods=3).mean()
        rs = s.rolling(window, min_periods=3).std()
        global_std = s.std()
        rs = rs.replace(0, global_std).fillna(global_std)
        if global_std == 0:
            return pd.DataFrame()
        z = (s - rm) / rs
        result = pd.DataFrame({
            'date': s.index,
            'count': s.values,
            'z_score': z.values,
            'rolling_mean': rm.values,
            'is_burst': z.values > z_threshold,
        })
        return result

    def detect_all_bursts(self, z_threshold=2.5):
        all_bursts = []
        for keyword in self.keyword_index:
            result = self.detect_bursts(keyword, z_threshold)
            if result.empty:
                continue
            burst_rows = result[result['is_burst']]
            for _, row in burst_rows.iterrows():
                all_bursts.append({
                    'keyword': keyword,
                    'date': row['date'],
                    'count': row['count'],
                    'z_score': round(row['z_score'], 2),
                })
        if not all_bursts:
            return pd.DataFrame(columns=['keyword', 'date', 'count', 'z_score'])
        return pd.DataFrame(all_bursts).sort_values('z_score', ascending=False)

    def detect_emergent_keywords(self, recent_months=24):
        cutoff = self._date_range[1] - pd.DateOffset(months=recent_months)
        results = []
        for keyword, entries in self.keyword_index.items():
            dates = []
            for entry in entries:
                url = entry if isinstance(entry, str) else entry.get('url', '')
                d = _extract_date_from_url(url)
                if d:
                    dates.append(pd.to_datetime(d + '-01'))
            if not dates:
                continue
            first = min(dates)
            last = max(dates)
            recent_count = sum(1 for d in dates if d > cutoff)
            results.append({
                'keyword': keyword,
                'first_date': first,
                'last_date': last,
                'total_count': len(dates),
                'recent_count': recent_count,
                'is_emergent': first > cutoff,
            })
        df = pd.DataFrame(results)
        return df.sort_values('first_date', ascending=False)

    def detect_vanishing_keywords(self, quiet_months=12):
        cutoff = self._date_range[1] - pd.DateOffset(months=quiet_months)
        results = []
        for keyword, entries in self.keyword_index.items():
            dates = []
            for entry in entries:
                url = entry if isinstance(entry, str) else entry.get('url', '')
                d = _extract_date_from_url(url)
                if d:
                    dates.append(pd.to_datetime(d + '-01'))
            if not dates:
                continue
            last = max(dates)
            if last < cutoff and len(dates) >= 5:
                results.append({
                    'keyword': keyword,
                    'last_active': last,
                    'total_count': len(dates),
                })
        if not results:
            return pd.DataFrame(columns=['keyword', 'last_active', 'total_count'])
        return pd.DataFrame(results).sort_values('last_active', ascending=False)

    def plot_keyword_burst(self, keyword):
        data = self.detect_bursts(keyword)
        if data.empty:
            fig = go.Figure()
            fig.update_layout(title=f'No burst data for "{keyword}"')
            return fig
        burst_pts = data[data['is_burst']]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=data['date'], y=data['count'],
            name='Monthly count', marker_color='steelblue', opacity=0.6,
        ))
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['rolling_mean'],
            name='Rolling mean', line=dict(color='orange', width=2),
        ))
        if not burst_pts.empty:
            fig.add_trace(go.Scatter(
                x=burst_pts['date'], y=burst_pts['count'],
                mode='markers', name='Burst',
                marker=dict(color='red', size=10, symbol='triangle-up'),
            ))
        fig.update_layout(
            title=f'Keyword Burst Analysis: "{keyword}"',
            xaxis_title='Date', yaxis_title='Mentions/month',
            template='plotly_white', height=400,
        )
        return fig

    def plot_burst_timeline(self):
        bursts = self.detect_all_bursts()
        if bursts.empty:
            fig = go.Figure()
            fig.update_layout(title='No keyword bursts detected')
            return fig
        fig = px.scatter(
            bursts, x='date', y='keyword', size='z_score', color='z_score',
            color_continuous_scale='Reds', size_max=18,
            title='Keyword Burst Events',
        )
        fig.update_layout(template='plotly_white', height=500)
        return fig


# ---------------------------------------------------------------------------
# 4. Seasonal Pattern Analyzer
# ---------------------------------------------------------------------------

class SeasonalPatternAnalyzer:
    def __init__(self, articles_df):
        self.df = articles_df
        self._monthly = None

    def _get_monthly(self):
        if self._monthly is None:
            counts = self.df.groupby('date_parsed').size()
            self._monthly = _build_monthly_series(counts)
        return self._monthly

    def get_month_of_year_pattern(self):
        s = self._get_monthly()
        monthly_df = pd.DataFrame({'date': s.index, 'count': s.values})
        monthly_df['cal_month'] = monthly_df['date'].dt.month
        monthly_df['year'] = monthly_df['date'].dt.year
        agg = monthly_df.groupby('cal_month')['count'].agg(['mean', 'std', 'sum']).reset_index()
        agg.columns = ['month', 'avg_count', 'std_count', 'total_count']
        agg['avg_count'] = agg['avg_count'].round(1)
        agg['std_count'] = agg['std_count'].round(1)
        return agg

    def get_yearly_cadence(self):
        s = self._get_monthly()
        monthly_df = pd.DataFrame({'date': s.index, 'count': s.values})
        monthly_df['year'] = monthly_df['date'].dt.year
        monthly_df['cal_month'] = monthly_df['date'].dt.month
        pivot = monthly_df.pivot_table(index='year', columns='cal_month',
                                       values='count', fill_value=0)
        pivot.columns = [f'Month {m}' for m in pivot.columns]
        return pivot

    def detect_periodicity_autocorrelation(self, max_lag=48):
        s = self._get_monthly().astype(float)
        s = s - s.mean()  # detrend (mean subtraction)
        n = len(s)
        if n < max_lag + 1:
            max_lag = n - 1
        acorr = [s.autocorr(lag=lag) for lag in range(1, max_lag + 1)]
        confidence = 2.0 / math.sqrt(n)
        significant = [i + 1 for i, a in enumerate(acorr) if abs(a) > confidence]
        return {
            'autocorrelation': acorr,
            'lags': list(range(1, max_lag + 1)),
            'significant_lags': significant,
            'confidence_band': round(confidence, 4),
        }

    def detect_periodicity_fft(self):
        if not HAS_NUMPY:
            return {'warning': 'numpy not available for FFT analysis'}
        s = self._get_monthly().astype(float).values
        # Detrend with linear fit
        x = np.arange(len(s))
        coeffs = np.polyfit(x, s, 1)
        trend = np.polyval(coeffs, x)
        detrended = s - trend
        # FFT
        fft_vals = np.fft.rfft(detrended)
        power = np.abs(fft_vals) ** 2
        freqs = np.fft.rfftfreq(len(detrended), d=1)  # d=1 month
        # Skip DC component
        power = power[1:]
        freqs = freqs[1:]
        # Find dominant periods
        top_indices = np.argsort(power)[::-1][:5]
        dominant = []
        for idx in top_indices:
            if freqs[idx] > 0:
                period = 1.0 / freqs[idx]
                dominant.append({
                    'period_months': round(period, 1),
                    'power': round(float(power[idx]), 1),
                })
        return {
            'frequencies': freqs.tolist(),
            'power': power.tolist(),
            'dominant_periods': dominant,
        }

    def plot_seasonality(self):
        pattern = self.get_month_of_year_pattern()
        cadence = self.get_yearly_cadence()

        fig = make_subplots(rows=2, cols=1,
                            subplot_titles=['Average Articles by Calendar Month',
                                           'Year × Month Heatmap'],
                            vertical_spacing=0.15)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        fig.add_trace(go.Bar(
            x=month_names, y=pattern['avg_count'],
            error_y=dict(type='data', array=pattern['std_count']),
            marker_color='steelblue',
        ), row=1, col=1)

        fig.add_trace(go.Heatmap(
            z=cadence.values,
            x=[m.replace('Month ', '') for m in cadence.columns],
            y=cadence.index.astype(str),
            colorscale='Blues',
        ), row=2, col=1)

        fig.update_layout(
            template='plotly_white', height=700, showlegend=False,
            title_text='Seasonal Publication Patterns',
        )
        return fig

    def plot_periodicity(self):
        acorr_data = self.detect_periodicity_autocorrelation()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=acorr_data['lags'], y=acorr_data['autocorrelation'],
            marker_color='steelblue',
        ))
        cb = acorr_data['confidence_band']
        fig.add_hline(y=cb, line_dash='dash', line_color='red',
                      annotation_text=f'95% confidence ({cb:.3f})')
        fig.add_hline(y=-cb, line_dash='dash', line_color='red')
        fig.update_layout(
            title='Autocorrelation of Monthly Publication Rate',
            xaxis_title='Lag (months)', yaxis_title='Autocorrelation',
            template='plotly_white', height=350,
        )
        return fig


# ---------------------------------------------------------------------------
# 5. Coordinate Temporal Analyzer
# ---------------------------------------------------------------------------

class CoordinateTemporalAnalyzer:
    def __init__(self, coords_df, articles_df):
        self.coords = coords_df.copy()
        self.articles_df = articles_df
        if 'date' in self.coords.columns:
            self.coords['date_parsed'] = pd.to_datetime(
                self.coords['date'] + '-01', format='%Y-%m-%d', errors='coerce'
            )
        else:
            self.coords['date_parsed'] = pd.NaT

    def get_coordinate_timeline(self):
        valid = self.coords.dropna(subset=['date_parsed'])
        if valid.empty:
            return pd.DataFrame(columns=['date', 'count'])
        counts = valid.groupby('date_parsed').size()
        counts = _build_monthly_series(counts)
        return pd.DataFrame({'date': counts.index, 'count': counts.values})

    def detect_coordinate_clusters(self, window_months=3):
        tl = self.get_coordinate_timeline()
        if tl.empty:
            return pd.DataFrame()
        s = tl.set_index('date')['count']
        rolled = s.rolling(window_months, min_periods=1).sum()
        avg = s.mean() * window_months
        threshold = max(avg * 2, 3)
        clusters = []
        valid = self.coords.dropna(subset=['date_parsed'])
        for date, window_count in rolled.items():
            if window_count >= threshold:
                window_start = date - pd.DateOffset(months=window_months - 1)
                mask = (valid['date_parsed'] >= window_start) & (valid['date_parsed'] <= date)
                window_coords = valid[mask]
                if len(window_coords) > 0 and 'lat' in window_coords.columns:
                    lat_vals = pd.to_numeric(window_coords['lat'], errors='coerce').dropna()
                    lon_vals = pd.to_numeric(window_coords['lon'], errors='coerce').dropna()
                    centroid_lat = lat_vals.mean() if len(lat_vals) > 0 else None
                    centroid_lon = lon_vals.mean() if len(lon_vals) > 0 else None
                else:
                    centroid_lat = centroid_lon = None
                clusters.append({
                    'window_end': date,
                    'count': int(window_count),
                    'centroid_lat': round(centroid_lat, 3) if centroid_lat else None,
                    'centroid_lon': round(centroid_lon, 3) if centroid_lon else None,
                })
        return pd.DataFrame(clusters)

    def get_geographic_shifts(self, period_months=12):
        valid = self.coords.dropna(subset=['date_parsed'])
        if valid.empty or 'lat' not in valid.columns:
            return pd.DataFrame()
        valid = valid.copy()
        valid['lat_num'] = pd.to_numeric(valid['lat'], errors='coerce')
        valid['lon_num'] = pd.to_numeric(valid['lon'], errors='coerce')
        valid = valid.dropna(subset=['lat_num', 'lon_num'])
        valid['period'] = valid['date_parsed'].dt.to_period(f'{period_months}M')
        grouped = valid.groupby('period').agg(
            centroid_lat=('lat_num', 'mean'),
            centroid_lon=('lon_num', 'mean'),
            count=('lat_num', 'size'),
        ).reset_index()
        grouped['period'] = grouped['period'].astype(str)
        grouped['centroid_lat'] = grouped['centroid_lat'].round(2)
        grouped['centroid_lon'] = grouped['centroid_lon'].round(2)
        return grouped

    def plot_coordinate_timeline(self):
        tl = self.get_coordinate_timeline()
        if tl.empty:
            fig = go.Figure()
            fig.update_layout(title='No coordinate temporal data')
            return fig
        fig = go.Figure(go.Bar(
            x=tl['date'], y=tl['count'],
            marker_color='teal',
        ))
        fig.update_layout(
            title='Coordinate-Containing Articles Over Time',
            xaxis_title='Date', yaxis_title='Coordinates/month',
            template='plotly_white', height=350,
        )
        return fig

    def plot_geographic_over_time(self):
        valid = self.coords.dropna(subset=['date_parsed'])
        if valid.empty or 'lat' not in valid.columns:
            fig = go.Figure()
            fig.update_layout(title='No coordinate data for map')
            return fig
        valid = valid.copy()
        valid['lat_num'] = pd.to_numeric(valid['lat'], errors='coerce')
        valid['lon_num'] = pd.to_numeric(valid['lon'], errors='coerce')
        valid = valid.dropna(subset=['lat_num', 'lon_num'])
        valid['year'] = valid['date_parsed'].dt.year.astype(str)
        fig = px.scatter_geo(
            valid, lat='lat_num', lon='lon_num',
            color='year', hover_name='title' if 'title' in valid.columns else None,
            title='Coordinates by Year',
            projection='natural earth',
        )
        fig.update_layout(height=500, template='plotly_white')
        return fig


# ---------------------------------------------------------------------------
# 6. Orchestrator
# ---------------------------------------------------------------------------

class TemporalAnalysisSuite:
    def __init__(self, articles, excerpts_df, keyword_index, coords_df):
        self.articles_df = _prepare_articles_df(articles)
        self.pub_analyzer = PublicationRateAnalyzer(self.articles_df)
        self.cat_analyzer = CategoryTrendAnalyzer(self.articles_df)
        self.kw_detector = KeywordBurstDetector(keyword_index, self.articles_df)
        self.season_analyzer = SeasonalPatternAnalyzer(self.articles_df)
        self.coord_analyzer = CoordinateTemporalAnalyzer(coords_df, self.articles_df)

    def run_all_analyses(self):
        return {
            'publication_rate': self.pub_analyzer.get_summary_stats(),
            'bursts': self.pub_analyzer.detect_bursts(),
            'trending_categories': self.cat_analyzer.detect_trending_categories(),
            'new_categories': self.cat_analyzer.detect_new_categories(),
            'keyword_bursts': self.kw_detector.detect_all_bursts(),
            'emergent_keywords': self.kw_detector.detect_emergent_keywords(),
            'vanishing_keywords': self.kw_detector.detect_vanishing_keywords(),
            'seasonality': self.season_analyzer.get_month_of_year_pattern(),
            'periodicity': self.season_analyzer.detect_periodicity_autocorrelation(),
            'coordinate_clusters': self.coord_analyzer.detect_coordinate_clusters(),
            'geographic_shifts': self.coord_analyzer.get_geographic_shifts(),
        }

    def get_report(self):
        lines = []
        sep = "=" * 60

        # Publication Rate
        lines.append(sep)
        lines.append("PUBLICATION RATE ANALYSIS")
        lines.append(sep)
        stats = self.pub_analyzer.get_summary_stats()
        for k, v in stats.items():
            lines.append(f"  {k}: {v}")

        bursts = self.pub_analyzer.detect_bursts()
        burst_rows = bursts[bursts['is_burst']].sort_values('z_score', ascending=False)
        if not burst_rows.empty:
            lines.append(f"\n  Publication Bursts (z > 2.0): {len(burst_rows)} months")
            for _, r in burst_rows.head(10).iterrows():
                bar = '#' * min(int(r['count'] / 5), 40)
                lines.append(f"    {r['date'].strftime('%Y-%m')}: {int(r['count'])} articles (z={r['z_score']:.1f}) {bar}")

        quiet = self.pub_analyzer.detect_quiet_periods()
        quiet_rows = quiet[quiet['is_quiet']].sort_values('z_score')
        if not quiet_rows.empty:
            lines.append(f"\n  Quiet Periods (z < -1.5): {len(quiet_rows)} months")
            for _, r in quiet_rows.head(5).iterrows():
                lines.append(f"    {r['date'].strftime('%Y-%m')}: {int(r['count'])} articles (z={r['z_score']:.1f})")

        # Category Trends
        lines.append(f"\n{sep}")
        lines.append("CATEGORY TRENDS (last 12 months vs historical)")
        lines.append(sep)
        trends = self.cat_analyzer.detect_trending_categories()
        rising = trends[trends['direction'] == 'rising']
        declining = trends[trends['direction'] == 'declining']

        if not rising.empty:
            lines.append(f"\n  Rising Categories ({len(rising)}):")
            for _, r in rising.head(10).iterrows():
                lines.append(f"    {r['category']}: {r['trend_ratio']}x (recent {r['recent_avg']}/mo vs historical {r['historical_avg']}/mo)")
        if not declining.empty:
            lines.append(f"\n  Declining Categories ({len(declining)}):")
            for _, r in declining.head(10).iterrows():
                lines.append(f"    {r['category']}: {r['trend_ratio']}x (recent {r['recent_avg']}/mo vs historical {r['historical_avg']}/mo)")

        # Keyword Bursts
        lines.append(f"\n{sep}")
        lines.append("KEYWORD BURST EVENTS")
        lines.append(sep)
        kw_bursts = self.kw_detector.detect_all_bursts()
        if not kw_bursts.empty:
            lines.append(f"  Total burst events: {len(kw_bursts)}")
            for _, r in kw_bursts.head(15).iterrows():
                date_str = r['date'].strftime('%Y-%m') if hasattr(r['date'], 'strftime') else str(r['date'])
                lines.append(f"    {r['keyword']}: {date_str} ({int(r['count'])} mentions, z={r['z_score']})")
        else:
            lines.append("  No keyword bursts detected at z > 2.5")

        emergent = self.kw_detector.detect_emergent_keywords()
        em_new = emergent[emergent['is_emergent']]
        if not em_new.empty:
            lines.append(f"\n  Emergent Keywords (appeared in last 24 months): {len(em_new)}")
            for _, r in em_new.head(10).iterrows():
                lines.append(f"    {r['keyword']}: first {r['first_date'].strftime('%Y-%m')}, {int(r['total_count'])} total")

        vanishing = self.kw_detector.detect_vanishing_keywords()
        if not vanishing.empty:
            lines.append(f"\n  Vanishing Keywords (no activity in 12 months): {len(vanishing)}")
            for _, r in vanishing.head(10).iterrows():
                lines.append(f"    {r['keyword']}: last active {r['last_active'].strftime('%Y-%m')}, {int(r['total_count'])} total")

        # Seasonality
        lines.append(f"\n{sep}")
        lines.append("SEASONAL PATTERNS")
        lines.append(sep)
        pattern = self.season_analyzer.get_month_of_year_pattern()
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        lines.append("  Average articles by calendar month:")
        for _, r in pattern.iterrows():
            m = int(r['month'])
            bar = '#' * int(r['avg_count'] / 2)
            lines.append(f"    {month_names[m-1]}: {r['avg_count']:5.1f} +/- {r['std_count']:4.1f}  {bar}")

        acorr = self.season_analyzer.detect_periodicity_autocorrelation()
        if acorr['significant_lags']:
            lines.append(f"\n  Significant periodicities (lags): {acorr['significant_lags'][:10]}")
            lines.append(f"  Confidence band: +/- {acorr['confidence_band']}")

        if HAS_NUMPY:
            fft = self.season_analyzer.detect_periodicity_fft()
            if 'dominant_periods' in fft:
                lines.append(f"\n  Dominant FFT periods:")
                for p in fft['dominant_periods'][:5]:
                    lines.append(f"    {p['period_months']} months (power={p['power']})")

        # Coordinates
        lines.append(f"\n{sep}")
        lines.append("COORDINATE TEMPORAL ANALYSIS")
        lines.append(sep)
        tl = self.coord_analyzer.get_coordinate_timeline()
        if not tl.empty:
            total_coords = tl['count'].sum()
            lines.append(f"  Total coordinate posts: {int(total_coords)}")
            peak = tl.loc[tl['count'].idxmax()]
            lines.append(f"  Peak month: {peak['date'].strftime('%Y-%m')} ({int(peak['count'])} coordinates)")

        clusters = self.coord_analyzer.detect_coordinate_clusters()
        if not clusters.empty:
            lines.append(f"\n  Temporal clusters (high-density windows): {len(clusters)}")
            for _, r in clusters.head(5).iterrows():
                loc = ""
                if r.get('centroid_lat') is not None:
                    loc = f" near ({r['centroid_lat']}, {r['centroid_lon']})"
                lines.append(f"    {r['window_end'].strftime('%Y-%m')}: {int(r['count'])} coordinates{loc}")

        shifts = self.coord_analyzer.get_geographic_shifts()
        if not shifts.empty:
            lines.append(f"\n  Geographic centroid shifts by period:")
            for _, r in shifts.iterrows():
                lines.append(f"    {r['period']}: ({r['centroid_lat']}, {r['centroid_lon']}) n={int(r['count'])}")

        lines.append(f"\n{sep}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data loading (for standalone CLI use)
# ---------------------------------------------------------------------------

def load_data():
    articles_path = os.path.join(DATA_DIR, "fl_articles_raw.json")
    excerpts_path = os.path.join(DATA_DIR, "fl_excerpts_raw.csv")
    keywords_path = os.path.join(DATA_DIR, "fl_keyword_index.json")
    coords_path = os.path.join(DATA_DIR, "fl_coordinates_complete_decoded.csv")

    with open(articles_path, encoding='utf-8') as f:
        articles = json.load(f)

    excerpts_df = pd.read_csv(excerpts_path, encoding='utf-8') if os.path.exists(excerpts_path) else pd.DataFrame()

    keyword_index = {}
    if os.path.exists(keywords_path):
        with open(keywords_path, encoding='utf-8') as f:
            keyword_index = json.load(f)

    coords_df = pd.read_csv(coords_path, encoding='utf-8') if os.path.exists(coords_path) else pd.DataFrame()

    return articles, excerpts_df, keyword_index, coords_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Fix Windows console encoding
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description='FL Temporal Pattern Analysis')
    parser.add_argument('--full-report', action='store_true', help='Run all analyses and print report')
    parser.add_argument('--bursts', action='store_true', help='Detect publication bursts')
    parser.add_argument('--category-trends', action='store_true', help='Show trending/declining categories')
    parser.add_argument('--keyword-bursts', metavar='KEYWORD', help='Detect bursts for keyword (or "all")')
    parser.add_argument('--seasonality', action='store_true', help='Analyze seasonal patterns')
    parser.add_argument('--coordinates', action='store_true', help='Coordinate temporal analysis')
    parser.add_argument('--recent-months', type=int, default=12, help='Recent window size (default: 12)')
    parser.add_argument('--z-threshold', type=float, default=2.0, help='Z-score threshold (default: 2.0)')

    args = parser.parse_args()

    if not any([args.full_report, args.bursts, args.category_trends,
                args.keyword_bursts, args.seasonality, args.coordinates]):
        args.full_report = True

    print("Loading data...")
    articles, excerpts_df, keyword_index, coords_df = load_data()
    print(f"  {len(articles)} articles, {len(keyword_index)} keywords, {len(coords_df)} coordinates")

    suite = TemporalAnalysisSuite(articles, excerpts_df, keyword_index, coords_df)

    if args.full_report:
        print(suite.get_report())
        return

    articles_df = _prepare_articles_df(articles)

    if args.bursts:
        analyzer = PublicationRateAnalyzer(articles_df)
        stats = analyzer.get_summary_stats()
        print("\nPublication Rate Summary:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        burst_data = analyzer.detect_bursts(z_threshold=args.z_threshold)
        burst_rows = burst_data[burst_data['is_burst']]
        print(f"\nBursts (z > {args.z_threshold}): {len(burst_rows)} months")
        for _, r in burst_rows.sort_values('z_score', ascending=False).head(15).iterrows():
            print(f"  {r['date'].strftime('%Y-%m')}: {int(r['count'])} articles (z={r['z_score']:.2f})")

    if args.category_trends:
        analyzer = CategoryTrendAnalyzer(articles_df)
        trends = analyzer.detect_trending_categories(recent_months=args.recent_months)
        print("\nCategory Trends:")
        for _, r in trends.head(20).iterrows():
            marker = '+' if r['direction'] == 'rising' else ('-' if r['direction'] == 'declining' else '=')
            print(f"  [{marker}] {r['category']}: {r['trend_ratio']}x ({r['direction']})")

    if args.keyword_bursts:
        detector = KeywordBurstDetector(keyword_index, articles_df)
        if args.keyword_bursts.lower() == 'all':
            bursts = detector.detect_all_bursts()
            print(f"\nAll Keyword Bursts: {len(bursts)} events")
            for _, r in bursts.head(20).iterrows():
                date_str = r['date'].strftime('%Y-%m') if hasattr(r['date'], 'strftime') else str(r['date'])
                print(f"  {r['keyword']}: {date_str} (z={r['z_score']})")
        else:
            data = detector.detect_bursts(args.keyword_bursts)
            if data.empty:
                print(f"\nNo data for keyword '{args.keyword_bursts}'")
            else:
                burst_rows = data[data['is_burst']]
                print(f"\nBursts for '{args.keyword_bursts}': {len(burst_rows)} events")
                for _, r in burst_rows.iterrows():
                    print(f"  {r['date'].strftime('%Y-%m')}: {int(r['count'])} (z={r['z_score']:.2f})")

    if args.seasonality:
        analyzer = SeasonalPatternAnalyzer(articles_df)
        pattern = analyzer.get_month_of_year_pattern()
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        print("\nMonthly Seasonality:")
        for _, r in pattern.iterrows():
            m = int(r['month'])
            bar = '#' * int(r['avg_count'] / 2)
            print(f"  {month_names[m-1]}: {r['avg_count']:5.1f} +/- {r['std_count']:4.1f}  {bar}")

    if args.coordinates:
        analyzer = CoordinateTemporalAnalyzer(coords_df, articles_df)
        tl = analyzer.get_coordinate_timeline()
        if not tl.empty:
            print(f"\nCoordinate Timeline: {int(tl['count'].sum())} total")
            nonzero = tl[tl['count'] > 0]
            for _, r in nonzero.iterrows():
                bar = '#' * int(r['count'])
                print(f"  {r['date'].strftime('%Y-%m')}: {int(r['count'])} {bar}")


if __name__ == "__main__":
    main()
