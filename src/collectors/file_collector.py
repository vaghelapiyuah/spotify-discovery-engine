"""Collect reviews from a local JSON file.

Expected format: a JSON list of objects, each with at least `source` and `text`.
Any of the RawReview fields (id, rating, date, country, app_version, device,
language) may be supplied; `id` is auto-generated when missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import RawReview
from .base import Collector


class FileCollector(Collector):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def collect(self) -> list[RawReview]:
        if not self.path.exists():
            raise FileNotFoundError(f"Review file not found: {self.path}")

        records = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Review file must contain a JSON list of reviews.")

        reviews: list[RawReview] = []
        for i, rec in enumerate(records):
            rec.setdefault("id", f"{rec.get('source', 'src')}-{i:04d}")
            reviews.append(RawReview.model_validate(rec))
        return reviews
