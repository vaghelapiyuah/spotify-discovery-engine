"""Offline, no-API analyzer.

A keyword-rule implementation of the same interface as `Analyzer`
(`analyze` + `synthesize`). It lets the full pipeline run on real reviews with
no API key and zero tokens. Classifications are necessarily coarser than the
LLM's, but the cleaning, aggregation, scoring, dashboard, and synthesis all
exercise real data end-to-end.

`synthesize` here is deterministic and grounds every PM answer in the actual
aggregate numbers (no model call).
"""

from __future__ import annotations

from ..models import (
    AnalyzedReview,
    CleanReview,
    PMAnswer,
    ReviewAnalysis,
    Synthesis,
)
from ..taxonomy import (
    FRUSTRATION_LABELS,
    UNMET_NEED_TO_OPPORTUNITY,
    Frustration,
    ListeningIntent,
    Segment,
    Sentiment,
    Severity,
    TopicCluster,
    UnmetNeed,
)

PM_QUESTIONS = [
    "Why do users struggle to discover new music?",
    "What are the most common frustrations with recommendations?",
    "What listening behaviors are users trying to achieve?",
    "What causes users to repeatedly listen to the same content?",
    "Which user segments experience different discovery challenges?",
    "What unmet needs emerge consistently?",
]


def _classify(text: str, rating: float | None) -> ReviewAnalysis:
    t = text.lower()

    def make(**kw) -> ReviewAnalysis:
        base = dict(
            normalized_summary=text[:140].strip(),
            is_app_bug=False,
            sentiment=Sentiment.NEUTRAL,
            topic_cluster=TopicCluster.OTHER,
            listening_intent=ListeningIntent.OTHER,
            frustration=Frustration.NONE,
            frustration_severity=Severity.LOW,
            segment=Segment.UNKNOWN,
            unmet_need=UnmetNeed.NONE,
            confidence=0.5,
        )
        base.update(kw)
        return ReviewAnalysis(**base)

    # Sentiment from rating where available (overridden by clear text cues).
    if rating is not None:
        sentiment = (
            Sentiment.NEGATIVE if rating <= 2
            else Sentiment.POSITIVE if rating >= 4
            else Sentiment.NEUTRAL
        )
    else:
        sentiment = Sentiment.NEUTRAL

    bug_words = ("crash", "bug", "glitch", "won't open", "wont open", "freeze",
                 "freezes", "broken", "not working", "doesn't work", "error",
                 "loading", "log in", "login")
    if any(w in t for w in bug_words):
        return make(is_app_bug=True, sentiment=sentiment)

    if any(w in t for w in ("same song", "again and again", "repeat", "repetitive",
                            "over and over", "loop", "discover weekly is dead")):
        return make(
            sentiment=sentiment if sentiment != Sentiment.POSITIVE else Sentiment.MIXED,
            topic_cluster=TopicCluster.REPETITIVE_RECOMMENDATIONS,
            listening_intent=ListeningIntent.SIMILAR_BUT_FRESH,
            frustration=Frustration.SAME_SONGS_REPEATED,
            frustration_severity=Severity.HIGH,
            segment=Segment.HABITUAL_REPEATERS,
            unmet_need=UnmetNeed.FRESH_BUT_FAMILIAR,
            confidence=0.6,
        )
    if any(w in t for w in ("genre", "boxed in", "one genre", "same artist")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.WEAK_GENRE_EXPLORATION,
            listening_intent=ListeningIntent.DEEP_DISCOVERY,
            frustration=Frustration.SAME_ARTISTS_REPEATED,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.GENRE_EXPLORERS,
            unmet_need=UnmetNeed.BETTER_CONTROL,
            confidence=0.6,
        )
    if any(w in t for w in ("mood", "chill", "calm", "wind down", "vibe")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.POOR_MOOD_UNDERSTANDING,
            listening_intent=ListeningIntent.MOOD_BASED,
            frustration=Frustration.WRONG_MOOD,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.MOOD_LISTENERS,
            unmet_need=UnmetNeed.MOOD_AWARE_DISCOVERY,
            confidence=0.55,
        )
    if "skip" in t:
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.TOO_MUCH_EFFORT,
            listening_intent=ListeningIntent.LOW_EFFORT_DISCOVERY,
            frustration=Frustration.TOO_MANY_SKIPS,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.HIGH_SKIP_LISTENERS,
            unmet_need=UnmetNeed.EFFORTLESS_DISCOVERY,
            confidence=0.55,
        )
    if any(w in t for w in ("friends", "trending", "trends", "viral", "tiktok")):
        return make(
            sentiment=sentiment,
            listening_intent=ListeningIntent.SOCIAL_DISCOVERY,
            frustration=Frustration.HIDDEN_DISCOVERY,
            frustration_severity=Severity.LOW,
            segment=Segment.SOCIAL_LISTENERS,
            unmet_need=UnmetNeed.SOCIAL_PROOF,
            confidence=0.5,
        )
    if any(w in t for w in ("playlist", "stale", "bored")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.PLAYLIST_FATIGUE,
            frustration=Frustration.BAD_RECOMMENDATIONS,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.PLAYLIST_LOYALISTS,
            unmet_need=UnmetNeed.LESS_REPETITIVE_PLAYLISTS,
            confidence=0.5,
        )
    if any(w in t for w in ("reset", "bubble", "trapped", "escape", "stuck")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.ALGORITHM_OVER_PERSONALIZATION,
            frustration=Frustration.OVER_PERSONALIZED_FEED,
            frustration_severity=Severity.HIGH,
            segment=Segment.HABITUAL_REPEATERS,
            unmet_need=UnmetNeed.BETTER_RESET_REFRESH,
            confidence=0.5,
        )
    if any(w in t for w in ("why this", "explain", "no idea why", "don't know why")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.DISCOVERY_FEELS_RISKY,
            frustration=Frustration.POOR_CONTROL,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.PASSIVE_LISTENERS,
            unmet_need=UnmetNeed.RECOMMENDATION_EXPLANATION,
            confidence=0.5,
        )
    if any(w in t for w in ("recommend", "discover", "suggestion", "new music",
                            "new songs", "algorithm")):
        return make(
            sentiment=sentiment,
            topic_cluster=TopicCluster.DISCOVERY_FEELS_RISKY,
            listening_intent=ListeningIntent.SIMILAR_BUT_FRESH,
            frustration=Frustration.BAD_RECOMMENDATIONS,
            frustration_severity=Severity.MEDIUM,
            segment=Segment.PASSIVE_LISTENERS,
            unmet_need=UnmetNeed.FRESH_BUT_FAMILIAR,
            confidence=0.45,
        )

    # No discovery signal — sentiment only.
    return make(sentiment=sentiment)


class RuleBasedAnalyzer:
    """Offline analyzer with the same interface as src.analysis.Analyzer."""

    def analyze(self, reviews: list[CleanReview]) -> list[AnalyzedReview]:
        return [
            AnalyzedReview(review=r, analysis=_classify(r.raw.text, r.raw.rating))
            for r in reviews
        ]

    def synthesize(self, aggregates: dict) -> Synthesis:
        complaints = aggregates.get("top_discovery_complaints", [])
        needs = aggregates.get("unmet_needs", [])
        segs = aggregates.get("discovery_issue_by_segment", {})
        intents = aggregates.get("distributions", {}).get("listening_intent", {})
        topics = aggregates.get("distributions", {}).get("topic_cluster", {})
        scores = aggregates.get("opportunity_scores", [])

        def top(items, n=3):
            return items[:n]

        top_complaints_str = ", ".join(
            f"{c['frustration']} ({c['pct_of_feedback']}%)" for c in top(complaints)
        ) or "no dominant frustration"
        top_needs_str = ", ".join(
            f"{n['unmet_need']} ({n['pct_of_feedback']}%)" for n in top(needs)
        ) or "none surfaced"
        top_intents_str = ", ".join(
            f"{k} ({v})" for k, v in list(intents.items())[:3]
        ) or "unclear"
        top_topics_str = ", ".join(
            f"{k} ({v})" for k, v in list(topics.items())[:3]
        ) or "unclear"
        seg_str = "; ".join(
            f"{s}: {v['main_issue']}" for s, v in list(segs.items())[:4]
        ) or "no clear segments"
        p0 = [s["frustration"] for s in scores if s.get("priority") == "P0"]
        p0_str = ", ".join(p0) or (scores[0]["frustration"] if scores else "n/a")

        answers = [
            PMAnswer(
                question=PM_QUESTIONS[0],
                answer=f"The most common discovery problems raised are {top_topics_str}. "
                "Users describe discovery as repetitive, risky, or effort-heavy "
                "rather than rejecting it outright.",
            ),
            PMAnswer(
                question=PM_QUESTIONS[1],
                answer=f"Ranked by frequency: {top_complaints_str}.",
            ),
            PMAnswer(
                question=PM_QUESTIONS[2],
                answer=f"The most common listening intents are {top_intents_str}.",
            ),
            PMAnswer(
                question=PM_QUESTIONS[3],
                answer="Repeat listening is driven mainly by "
                f"'{(complaints[0]['frustration'] if complaints else 'repetition')}' "
                "and over-personalization — familiar music feels safer than risking "
                "a bad new recommendation.",
            ),
            PMAnswer(
                question=PM_QUESTIONS[4],
                answer=f"Segment-level challenges: {seg_str}.",
            ),
            PMAnswer(
                question=PM_QUESTIONS[5],
                answer=f"Consistently unmet needs: {top_needs_str}.",
            ),
        ]

        return Synthesis(
            executive_summary=(
                "Users are not rejecting discovery — they reject discovery that "
                f"feels repetitive, random, or effort-heavy. The top frustrations are "
                f"{top_complaints_str}, and the highest-priority opportunity is "
                f"addressing: {p0_str}."
            ),
            pm_answers=answers,
            final_product_insight=(
                "Make discovery feel low-risk, contextual to the user's current "
                "mood, and different enough to feel fresh without becoming random. "
                f"Start with the P0 frustration ({p0_str}) and the top unmet need "
                f"({needs[0]['product_opportunity'] if needs else 'fresh-but-familiar discovery'})."
            ),
        )
