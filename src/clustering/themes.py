"""Emergent theme clustering with TF-IDF + KMeans (offline)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..models import AnalyzedReview


@dataclass
class Theme:
    id: int
    label: str                       # human-readable, from top terms
    size: int
    keywords: list[str]
    dominant_topic: str
    dominant_segment: str
    sample_summaries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "size": self.size,
            "keywords": self.keywords,
            "dominant_topic": self.dominant_topic,
            "dominant_segment": self.dominant_segment,
            "sample_summaries": self.sample_summaries,
        }


class ThemeClusterer:
    """Cluster analyzed reviews into emergent themes.

    Uses TF-IDF features over each review's normalized summary and KMeans.
    Theme labels are the top distinguishing terms per cluster.
    """

    def __init__(self, max_clusters: int = 8, random_state: int = 42):
        self.max_clusters = max_clusters
        self.random_state = random_state

    @staticmethod
    def _choose_k(n: int, cap: int) -> int:
        return max(2, min(cap, n // 8))

    def cluster(self, analyzed: list[AnalyzedReview]) -> list[Theme]:
        # Lazy imports keep these heavy deps out of non-clustering code paths.
        from sklearn.cluster import KMeans
        from sklearn.feature_extraction.text import TfidfVectorizer

        docs = [
            (a.analysis.normalized_summary or a.review.raw.text or "").strip()
            for a in analyzed
        ]
        usable = [i for i, d in enumerate(docs) if d]
        if len(usable) < 4:
            return self._single_theme(analyzed)

        texts = [docs[i] for i in usable]
        vectorizer = TfidfVectorizer(
            stop_words="english", max_features=2000, ngram_range=(1, 2), min_df=1
        )
        X = vectorizer.fit_transform(texts)

        k = self._choose_k(len(usable), self.max_clusters)
        km = KMeans(n_clusters=k, n_init=10, random_state=self.random_state)
        labels = km.fit_predict(X)

        terms = vectorizer.get_feature_names_out()
        centroids = km.cluster_centers_

        themes: list[Theme] = []
        for c in range(k):
            members = [usable[j] for j, lab in enumerate(labels) if lab == c]
            if not members:
                continue
            top_idx = centroids[c].argsort()[::-1][:6]
            keywords = [terms[t] for t in top_idx if centroids[c][t] > 0][:6]
            member_reviews = [analyzed[i] for i in members]
            themes.append(
                Theme(
                    id=c,
                    label=", ".join(keywords[:3]) or f"theme {c}",
                    size=len(members),
                    keywords=keywords,
                    dominant_topic=_mode(
                        r.analysis.topic_cluster.value for r in member_reviews
                    ),
                    dominant_segment=_mode(
                        r.analysis.segment.value for r in member_reviews
                    ),
                    sample_summaries=[
                        (r.analysis.normalized_summary or r.review.raw.text)[:160]
                        for r in member_reviews[:3]
                    ],
                )
            )

        themes.sort(key=lambda t: t.size, reverse=True)
        return themes

    @staticmethod
    def _single_theme(analyzed: list[AnalyzedReview]) -> list[Theme]:
        if not analyzed:
            return []
        return [
            Theme(
                id=0,
                label="all reviews",
                size=len(analyzed),
                keywords=[],
                dominant_topic=_mode(a.analysis.topic_cluster.value for a in analyzed),
                dominant_segment=_mode(a.analysis.segment.value for a in analyzed),
                sample_summaries=[
                    (a.analysis.normalized_summary or a.review.raw.text)[:160]
                    for a in analyzed[:3]
                ],
            )
        ]


def _mode(values) -> str:
    c = Counter(values)
    return c.most_common(1)[0][0] if c else "unknown"
