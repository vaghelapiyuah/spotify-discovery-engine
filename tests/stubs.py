"""Offline test doubles — no network, no Claude API.

`StubAnalyzer` is the real offline analyzer (RuleBasedAnalyzer), reused here so
tests exercise the same code path as `run.py --offline`. `MockCollector`
returns a fixed list of reviews.
"""

from __future__ import annotations

from src.analysis import RuleBasedAnalyzer
from src.collectors.base import Collector
from src.models import RawReview

# Alias kept for test readability.
StubAnalyzer = RuleBasedAnalyzer


class MockCollector(Collector):
    """Returns a fixed list of RawReview objects."""

    def __init__(self, reviews: list[RawReview]):
        self._reviews = reviews

    def collect(self) -> list[RawReview]:
        return self._reviews
