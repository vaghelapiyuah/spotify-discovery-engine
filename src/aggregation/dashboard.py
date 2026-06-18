"""Turn analyzed reviews into dashboard tables and opportunity scores.

Produces a JSON-serializable dict matching the spec's output dashboard
(section 8) and prioritization framework (section 9):

  - top_discovery_complaints   : frustration distribution (% of feedback)
  - sentiment_by_source        : sentiment split per source
  - discovery_issue_by_segment : dominant issue per listener segment
  - unmet_needs                : need counts -> product opportunities
  - opportunity_scores         : Frequency x Severity x Business impact -> P0-P3
  - distributions              : topic / intent / segment counts
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..models import AnalyzedReview
from ..taxonomy import (
    BUSINESS_IMPACT,
    FRUSTRATION_LABELS,
    MAIN_PROBLEM,
    ROOT_CAUSE_EXPLANATIONS,
    ROOT_CAUSE_LABELS,
    SEVERITY_WEIGHT,
    UNMET_NEED_TO_OPPORTUNITY,
    Frustration,
    RootCause,
    UnmetNeed,
    root_cause_for,
)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _priority_from_rank(rank: int, total: int) -> str:
    """P0 for the top quartile of scored frustrations, down to P3."""
    if total <= 1:
        return "P0"
    quartile = rank / total  # 0.0 = top
    if quartile < 0.25:
        return "P0"
    if quartile < 0.5:
        return "P1"
    if quartile < 0.75:
        return "P2"
    return "P3"


def build_dashboard(analyzed: list[AnalyzedReview]) -> dict:
    total = len(analyzed)
    discovery = [a for a in analyzed if not a.analysis.is_app_bug]
    n_discovery = len(discovery)

    # --- A. Top discovery complaints (frustration distribution) --------------
    frustration_counts: Counter[str] = Counter(
        a.analysis.frustration.value
        for a in discovery
        if a.analysis.frustration != Frustration.NONE
    )
    top_complaints = [
        {
            "frustration": FRUSTRATION_LABELS[f],
            "count": c,
            "pct_of_feedback": _pct(c, n_discovery),
        }
        for f, c in frustration_counts.most_common()
    ]

    # --- B. Sentiment by source ----------------------------------------------
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for a in analyzed:
        by_source[a.review.raw.source.value][a.analysis.sentiment.value] += 1
    sentiment_by_source = {
        source: {
            "total": sum(counts.values()),
            "positive": _pct(counts["positive"], sum(counts.values())),
            "neutral": _pct(counts["neutral"], sum(counts.values())),
            "negative": _pct(counts["negative"], sum(counts.values())),
            "mixed": _pct(counts["mixed"], sum(counts.values())),
        }
        for source, counts in sorted(by_source.items())
    }

    # --- C. Discovery issue by segment ---------------------------------------
    seg_topics: dict[str, Counter[str]] = defaultdict(Counter)
    seg_needs: dict[str, Counter[str]] = defaultdict(Counter)
    for a in discovery:
        seg = a.analysis.segment.value
        seg_topics[seg][a.analysis.topic_cluster.value] += 1
        if a.analysis.unmet_need != UnmetNeed.NONE:
            seg_needs[seg][a.analysis.unmet_need.value] += 1
    discovery_issue_by_segment = {
        seg: {
            "count": sum(topics.values()),
            "main_issue": topics.most_common(1)[0][0],
            "top_unmet_need": (
                seg_needs[seg].most_common(1)[0][0] if seg_needs[seg] else "none"
            ),
        }
        for seg, topics in sorted(
            seg_topics.items(), key=lambda kv: sum(kv[1].values()), reverse=True
        )
    }

    # --- D. Unmet needs -> product opportunities -----------------------------
    need_counts: Counter[str] = Counter(
        a.analysis.unmet_need.value
        for a in discovery
        if a.analysis.unmet_need != UnmetNeed.NONE
    )
    unmet_needs = [
        {
            "unmet_need": n,
            "count": c,
            "pct_of_feedback": _pct(c, n_discovery),
            "product_opportunity": UNMET_NEED_TO_OPPORTUNITY[n],
        }
        for n, c in need_counts.most_common()
    ]

    # --- Opportunity scores (section 9) --------------------------------------
    # Score = Frequency x avg(Severity weight) x Business impact.
    sev_by_frustration: dict[str, list[float]] = defaultdict(list)
    for a in discovery:
        if a.analysis.frustration != Frustration.NONE:
            sev_by_frustration[a.analysis.frustration.value].append(
                SEVERITY_WEIGHT[a.analysis.frustration_severity.value]
            )

    raw_scores = []
    for f, count in frustration_counts.items():
        avg_sev = sum(sev_by_frustration[f]) / len(sev_by_frustration[f])
        impact = BUSINESS_IMPACT[f]
        score = round(count * avg_sev * impact, 2)
        raw_scores.append(
            {
                "frustration": FRUSTRATION_LABELS[f],
                "frequency": count,
                "avg_severity": round(avg_sev, 2),
                "business_impact": impact,
                "opportunity_score": score,
            }
        )
    raw_scores.sort(key=lambda r: r["opportunity_score"], reverse=True)
    for rank, row in enumerate(raw_scores):
        row["priority"] = _priority_from_rank(rank, len(raw_scores))

    # --- Root-cause taxonomy (section 5) -------------------------------------
    root_counts: Counter[str] = Counter()
    for a in discovery:
        rc = root_cause_for(
            a.analysis.frustration.value, a.analysis.topic_cluster.value
        )
        if rc != RootCause.NONE.value:
            root_counts[rc] += 1
    n_rooted = sum(root_counts.values())
    root_causes = [
        {
            "root_cause": ROOT_CAUSE_LABELS[rc],
            "key": rc,
            "count": c,
            "pct": _pct(c, n_rooted),
            "explanation": ROOT_CAUSE_EXPLANATIONS[rc],
        }
        for rc, c in root_counts.most_common()
    ]

    # --- Distributions (supporting context) ----------------------------------
    distributions = {
        "topic_cluster": dict(
            Counter(a.analysis.topic_cluster.value for a in discovery).most_common()
        ),
        "listening_intent": dict(
            Counter(a.analysis.listening_intent.value for a in discovery).most_common()
        ),
        "segment": dict(
            Counter(a.analysis.segment.value for a in discovery).most_common()
        ),
    }

    return {
        "main_problem": MAIN_PROBLEM,
        "totals": {
            "analyzed_reviews": total,
            "discovery_reviews": n_discovery,
            "app_bug_reviews": total - n_discovery,
        },
        "top_discovery_complaints": top_complaints,
        "sentiment_by_source": sentiment_by_source,
        "discovery_issue_by_segment": discovery_issue_by_segment,
        "unmet_needs": unmet_needs,
        "root_causes": root_causes,
        "opportunity_scores": raw_scores,
        "distributions": distributions,
    }
