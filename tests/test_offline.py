"""Offline tests — no network, no Claude API, no tokens spent.

Run with pytest:        pytest
Or standalone:          python tests/test_offline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running this file directly (python tests/test_offline.py).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CONFIG  # noqa: E402
from src.aggregation import build_dashboard  # noqa: E402
from src.cleaning import Cleaner  # noqa: E402
from src.models import RawReview, Source  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from tests.stubs import MockCollector, StubAnalyzer  # noqa: E402


# --- fixtures ----------------------------------------------------------------

def _sample_raw() -> list[RawReview]:
    return [
        RawReview(id="a1", source=Source.APP_STORE, rating=2,
                  text="Spotify keeps recommending the same songs again and again."),
        RawReview(id="a2", source=Source.APP_STORE, rating=2,
                  text="spotify keeps recommending the SAME songs again and again."),  # dup of a1
        RawReview(id="p1", source=Source.PLAY_STORE, rating=1,
                  text="App crashes every time I open Discover Weekly."),  # app bug
        RawReview(id="p2", source=Source.PLAY_STORE, rating=3,
                  text="The chill playlists never match my mood after work."),
        RawReview(id="r1", source=Source.REDDIT,
                  text="I want new music but I hate having to skip bad songs constantly."),
        RawReview(id="s1", source=Source.SOCIAL_MEDIA,
                  text="FREE FOLLOWERS!!! click here http://spam.example get plays now"),  # spam
        RawReview(id="s2", source=Source.SOCIAL_MEDIA, text="ok"),  # short
        RawReview(id="c1", source=Source.COMMUNITY_FORUM,
                  text="Please add a reset my taste button, I feel trapped in my bubble."),
    ]


# --- cleaning ----------------------------------------------------------------

def test_cleaner_flags_dup_spam_short():
    cleaned = Cleaner(short_review_chars=5).clean(_sample_raw())
    by_id = {c.raw.id: c for c in cleaned}

    assert by_id["a2"].duplicate_of == "a1", "a2 should be a duplicate of a1"
    assert by_id["a1"].duplicate_of is None
    assert by_id["s1"].is_spam is True, "URL/promo text should be spam"
    assert by_id["s2"].is_short is True, "'ok' should be tagged low-detail"

    analyzable = Cleaner.analyzable(cleaned)
    ids = {c.raw.id for c in analyzable}
    assert "a2" not in ids and "s1" not in ids, "dup + spam excluded from analysis"
    assert "s2" in ids, "short reviews are kept, just tagged"
    print("  [ok] cleaner flags duplicates, spam, and short reviews")


# --- aggregation + scoring ---------------------------------------------------

def test_build_dashboard_scoring():
    cleaned = Cleaner(short_review_chars=5).clean(_sample_raw())
    analyzable = Cleaner.analyzable(cleaned)
    analyzed = StubAnalyzer().analyze(analyzable)

    dash = build_dashboard(analyzed)

    # app bug should be split out of discovery feedback
    assert dash["totals"]["app_bug_reviews"] >= 1

    scores = dash["opportunity_scores"]
    assert scores, "expected at least one scored frustration"
    # sorted descending by opportunity score
    vals = [r["opportunity_score"] for r in scores]
    assert vals == sorted(vals, reverse=True), "scores must be ranked desc"
    # every row carries a priority and a positive score
    assert all(r["priority"] in {"P0", "P1", "P2", "P3"} for r in scores)
    assert scores[0]["priority"] == "P0"
    assert all(r["opportunity_score"] > 0 for r in scores)

    # dashboard is JSON-serializable (enums resolved to strings)
    json.dumps(dash)

    # sentiment percentages per source stay within 0..100
    for v in dash["sentiment_by_source"].values():
        assert 0 <= v["negative"] <= 100
    print("  [ok] dashboard builds, scores rank desc, output is JSON-safe")


# --- full pipeline with stub analyzer ---------------------------------------

def test_pipeline_end_to_end_offline():
    pipeline = Pipeline(CONFIG, analyzer=StubAnalyzer(), log=lambda *a, **k: None)
    result = pipeline.run([MockCollector(_sample_raw())])

    assert result.stats["raw_reviews"] == 8
    assert result.stats["duplicates"] >= 1
    assert result.stats["spam"] >= 1
    assert result.analyzed, "pipeline produced no analyzed reviews"
    assert len(result.synthesis.pm_answers) == 6, "must answer all 6 PM questions"

    # the whole result serializes cleanly
    json.dumps(result.to_dict())
    print("  [ok] full pipeline runs offline and serializes")


# --- standalone runner -------------------------------------------------------

def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    print(f"Running {len(tests)} offline tests...\n")
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
