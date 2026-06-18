"""Collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawReview


class Collector(ABC):
    """A source of raw user feedback."""

    @abstractmethod
    def collect(self) -> list[RawReview]:
        """Return raw reviews from this source."""
        raise NotImplementedError
