"""CLI entry point for the AI-Powered Review Discovery Engine.

Examples:
    # Analyze the bundled sample file
    python run.py

    # Pull live Spotify reviews and analyze them
    python run.py --source appstore --count 100
    python run.py --source playstore --country us --lang en --count 200
    python run.py --source both

    # Just fetch live Spotify reviews to a JSON file (no API tokens spent)
    python run.py --source both --fetch-only --save-input data/spotify_live.json

    # Cheaper model for high-volume runs
    python run.py --source both --model claude-haiku-4-5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from config import CONFIG
from src.analysis import RuleBasedAnalyzer
from src.collectors import (
    AppStoreCollector,
    Collector,
    CommunityForumCollector,
    FileCollector,
    PlayStoreCollector,
    RedditCollector,
    SocialMediaCollector,
)
from src.pipeline import Pipeline, PipelineResult, save_result


def _build_collectors(args) -> list[Collector]:
    countries = [c.strip() for c in args.country.split(",") if c.strip()]
    appstore = lambda: AppStoreCollector(countries=countries, max_pages=args.pages)
    playstore = lambda: PlayStoreCollector(
        lang=args.lang, country=countries[0], count=args.count
    )
    if args.source == "file":
        return [FileCollector(args.input)]
    if args.source == "appstore":
        return [appstore()]
    if args.source == "playstore":
        return [playstore()]
    if args.source == "reddit":
        return [RedditCollector()]
    if args.source == "community":
        return [CommunityForumCollector()]
    if args.source == "social":
        return [SocialMediaCollector()]
    if args.source == "both":
        return [appstore(), playstore()]
    if args.source == "all":
        # Sources without credentials are skipped automatically by the pipeline.
        return [
            appstore(), playstore(), RedditCollector(),
            CommunityForumCollector(), SocialMediaCollector(),
        ]
    raise ValueError(f"Unknown source: {args.source}")


def _fetch_only(collectors: list[Collector], save_path: str | None) -> int:
    raw = []
    for c in collectors:
        collected = c.collect()
        print(f"  collected {len(collected):>4} from {type(c).__name__}")
        raw.extend(collected)
    print(f"Fetched {len(raw)} raw reviews.")

    if save_path:
        records = [r.model_dump(mode="json", exclude_none=True) for r in raw]
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Saved fetched reviews to: {save_path}")
        print("Analyze later with:  python run.py --input " + save_path)
    return 0


def _print_report(result: PipelineResult) -> None:
    d = result.dashboard
    s = result.synthesis
    line = "=" * 70

    print(f"\n{line}\nSPOTIFY DISCOVERY — REVIEW INTELLIGENCE REPORT\n{line}")

    t = d["totals"]
    print(
        f"\nAnalyzed {t['analyzed_reviews']} reviews "
        f"({t['discovery_reviews']} discovery, {t['app_bug_reviews']} app-bug)."
    )

    print("\n--- Top Discovery Complaints --------------------------------------")
    for row in d["top_discovery_complaints"]:
        print(f"  {row['pct_of_feedback']:>5}%  {row['frustration']} ({row['count']})")

    print("\n--- Sentiment by Source -------------------------------------------")
    print(f"  {'source':<18}{'pos':>6}{'neu':>6}{'neg':>6}{'mix':>6}")
    for src, v in d["sentiment_by_source"].items():
        print(
            f"  {src:<18}{v['positive']:>6}{v['neutral']:>6}"
            f"{v['negative']:>6}{v['mixed']:>6}"
        )

    print("\n--- Discovery Issue by Segment ------------------------------------")
    for seg, v in d["discovery_issue_by_segment"].items():
        print(f"  {seg:<22} {v['main_issue']}  (need: {v['top_unmet_need']})")

    print("\n--- Unmet Needs -> Product Opportunities --------------------------")
    for row in d["unmet_needs"]:
        print(
            f"  {row['pct_of_feedback']:>5}%  {row['unmet_need']:<26} "
            f"-> {row['product_opportunity']}"
        )

    print("\n--- Opportunity Scores (Freq x Severity x Impact) -----------------")
    print(f"  {'pri':<5}{'score':>8}  frustration")
    for row in d["opportunity_scores"]:
        print(f"  {row['priority']:<5}{row['opportunity_score']:>8}  {row['frustration']}")

    print("\n--- Executive Summary ---------------------------------------------")
    print(f"  {s.executive_summary}")

    print("\n--- PM Questions --------------------------------------------------")
    for qa in s.pm_answers:
        print(f"\n  Q: {qa.question}\n  A: {qa.answer}")

    print("\n--- Final Product Insight -----------------------------------------")
    print(f"  {s.final_product_insight}")
    print(f"\n{line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Spotify Review Discovery Engine")
    parser.add_argument(
        "--source", default="file",
        choices=["file", "appstore", "playstore", "reddit", "community",
                 "social", "both", "all"],
        help="Where to get reviews (default: file). 'all' tries every source "
             "and skips those without credentials.",
    )
    parser.add_argument(
        "--input", default="data/sample_reviews.json",
        help="JSON file of reviews when --source file (default sample).",
    )
    parser.add_argument(
        "--output", default="output",
        help="Directory for the JSON report (default: output/).",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override the Claude model (e.g. claude-haiku-4-5).",
    )
    # Live-source options.
    parser.add_argument(
        "--country", default="us",
        help="Country code(s), comma-separated for App Store (default: us).",
    )
    parser.add_argument(
        "--lang", default="en", help="Play Store language (default: en).",
    )
    parser.add_argument(
        "--count", type=int, default=200,
        help="Play Store reviews to fetch (default: 200).",
    )
    parser.add_argument(
        "--pages", type=int, default=5,
        help="App Store RSS pages per country, ~50 reviews each (default: 5).",
    )
    parser.add_argument(
        "--fetch-only", action="store_true",
        help="Only collect reviews (no AI analysis, no tokens spent).",
    )
    parser.add_argument(
        "--save-input", default=None,
        help="With --fetch-only, save collected reviews to this JSON path.",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Use the rule-based analyzer instead of Claude (no API key, no tokens).",
    )
    args = parser.parse_args()

    try:
        collectors = _build_collectors(args)
    except (ImportError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.fetch_only:
        try:
            return _fetch_only(collectors, args.save_input)
        except Exception as e:  # network / scraper errors
            print(f"ERROR while fetching: {e}", file=sys.stderr)
            return 1

    config = CONFIG if args.model is None else replace(CONFIG, model=args.model)

    if args.offline:
        analyzer = RuleBasedAnalyzer()
    else:
        if not config.has_api_key:
            print(
                "ERROR: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
                "add your key, run with --offline (rule-based, no key needed), or "
                "use --fetch-only to just collect reviews.",
                file=sys.stderr,
            )
            return 1
        analyzer = None  # Pipeline builds the real Claude-powered Analyzer

    pipeline = Pipeline(config, analyzer=analyzer)
    try:
        result = pipeline.run(collectors)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    _print_report(result)
    out_path = save_result(result, args.output)
    print(f"\nFull JSON report written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
