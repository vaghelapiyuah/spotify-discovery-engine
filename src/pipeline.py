"""End-to-end orchestration (spec section 3, system flow).

collect -> clean -> analyze (Claude) -> aggregate/score -> synthesize (Claude)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config import Config
from .aggregation import build_dashboard
from .analysis import Analyzer
from .cleaning import Cleaner
from .collectors import Collector
from .models import AnalyzedReview, Synthesis


@dataclass
class PipelineResult:
    dashboard: dict
    synthesis: Synthesis
    analyzed: list[AnalyzedReview]
    stats: dict

    def to_dict(self) -> dict:
        return {
            "stats": self.stats,
            "dashboard": self.dashboard,
            "synthesis": self.synthesis.model_dump(mode="json"),
            "reviews": [a.model_dump(mode="json") for a in self.analyzed],
        }


class Pipeline:
    def __init__(self, config: Config, analyzer=None, log=print):
        self.config = config
        self.cleaner = Cleaner(short_review_chars=config.short_review_chars)
        # `analyzer` is injectable so tests can pass a stub and avoid
        # constructing the real Claude client. Otherwise build the real one.
        self.analyzer = analyzer or Analyzer(
            model=config.model,
            workers=config.workers,
            max_tokens=config.max_tokens,
        )
        self.log = log

    def run(self, collectors: list[Collector]) -> PipelineResult:
        # 1. Collect ----------------------------------------------------------
        raw = []
        for c in collectors:
            collected = c.collect()
            self.log(f"  collected {len(collected):>4} from {type(c).__name__}")
            raw.extend(collected)
        self.log(f"Collected {len(raw)} raw reviews.")

        # 2. Clean ------------------------------------------------------------
        cleaned = self.cleaner.clean(raw)
        analyzable = self.cleaner.analyzable(cleaned)
        n_spam = sum(1 for c in cleaned if c.is_spam)
        n_dup = sum(1 for c in cleaned if c.duplicate_of is not None)
        n_short = sum(1 for c in cleaned if c.is_short)
        self.log(
            f"Cleaned: {len(analyzable)} analyzable "
            f"({n_dup} duplicates, {n_spam} spam, {n_short} low-detail tagged)."
        )

        # 3. Analyze ----------------------------------------------------------
        engine = isinstance(self.analyzer, Analyzer)
        label = self.config.model if engine else "rule-based offline (no API)"
        self.log(f"Analyzing {len(analyzable)} reviews with {label}...")
        analyzed = self.analyzer.analyze(analyzable)
        self.log(f"Analyzed {len(analyzed)} reviews.")

        # 4. Aggregate + score ------------------------------------------------
        dashboard = build_dashboard(analyzed)

        # 5. Synthesize -------------------------------------------------------
        self.log("Synthesizing PM insights...")
        synthesis = self.analyzer.synthesize(dashboard)

        stats = {
            "raw_reviews": len(raw),
            "duplicates": n_dup,
            "spam": n_spam,
            "low_detail": n_short,
            "analyzed": len(analyzed),
            "analyzer": label,
        }
        return PipelineResult(dashboard, synthesis, analyzed, stats)


def save_result(result: PipelineResult, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "discovery_report.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path
