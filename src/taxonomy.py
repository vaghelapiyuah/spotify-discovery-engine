"""Controlled vocabularies for the discovery problem taxonomy.

Every AI classification maps into one of these fixed enums rather than free text.
That is what makes aggregation (counting, ranking, scoring) meaningful — two
reviews that mean the same thing land in the same bucket.

These mirror the taxonomy defined in the project spec (sections 4 and 5).
"""

from __future__ import annotations

from enum import Enum


class Source(str, Enum):
    APP_STORE = "app_store"
    PLAY_STORE = "play_store"
    REDDIT = "reddit"
    COMMUNITY_FORUM = "community_forum"
    SOCIAL_MEDIA = "social_media"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class TopicCluster(str, Enum):
    """Spec section 4.B — group similar complaints together."""

    REPETITIVE_RECOMMENDATIONS = "repetitive_recommendations"
    WEAK_GENRE_EXPLORATION = "weak_genre_exploration"
    POOR_MOOD_UNDERSTANDING = "poor_mood_understanding"
    TOO_MUCH_EFFORT = "too_much_effort"
    DISCOVERY_FEELS_RISKY = "discovery_feels_risky"
    PLAYLIST_FATIGUE = "playlist_fatigue"
    ALGORITHM_OVER_PERSONALIZATION = "algorithm_over_personalization"
    OTHER = "other"


class ListeningIntent(str, Enum):
    """Spec section 4.C — what the user is trying to achieve."""

    ACTIVITY_BASED = "activity_based"          # "songs for gym"
    MOOD_BASED = "mood_based"                   # "chill music after work"
    SIMILAR_BUT_FRESH = "similar_but_fresh"     # "like this but not the same"
    DEEP_DISCOVERY = "deep_discovery"           # "underground artists"
    LOW_EFFORT_DISCOVERY = "low_effort_discovery"  # "don't want to keep skipping"
    SOCIAL_DISCOVERY = "social_discovery"       # "what my friends listen to"
    OTHER = "other"


class Frustration(str, Enum):
    """Spec section 4.D — why users are unhappy with recommendations."""

    SAME_SONGS_REPEATED = "same_songs_repeated"
    SAME_ARTISTS_REPEATED = "same_artists_repeated"
    BAD_RECOMMENDATIONS = "bad_recommendations"
    TOO_MANY_SKIPS = "too_many_skips"
    WRONG_MOOD = "wrong_mood"
    OVER_PERSONALIZED_FEED = "over_personalized_feed"
    POOR_CONTROL = "poor_control"
    HIDDEN_DISCOVERY = "hidden_discovery"
    NONE = "none"


class Segment(str, Enum):
    """Spec section 4.E — sub-segments of 18-30 daily listeners."""

    HABITUAL_REPEATERS = "habitual_repeaters"
    MOOD_LISTENERS = "mood_listeners"
    SOCIAL_LISTENERS = "social_listeners"
    GENRE_EXPLORERS = "genre_explorers"
    PASSIVE_LISTENERS = "passive_listeners"
    HIGH_SKIP_LISTENERS = "high_skip_listeners"
    PLAYLIST_LOYALISTS = "playlist_loyalists"
    ARTIST_LOYALISTS = "artist_loyalists"
    UNKNOWN = "unknown"


class UnmetNeed(str, Enum):
    """Spec section 4.F — what users want but are not getting."""

    FRESH_BUT_FAMILIAR = "fresh_but_familiar"
    BETTER_CONTROL = "better_control"
    MOOD_AWARE_DISCOVERY = "mood_aware_discovery"
    LESS_REPETITIVE_PLAYLISTS = "less_repetitive_playlists"
    EFFORTLESS_DISCOVERY = "effortless_discovery"
    SOCIAL_PROOF = "social_proof"
    RECOMMENDATION_EXPLANATION = "recommendation_explanation"
    BETTER_RESET_REFRESH = "better_reset_refresh"
    NONE = "none"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# --- Scoring weights (spec section 9: Opportunity Score) ----------------------

SEVERITY_WEIGHT: dict[str, float] = {
    Severity.LOW.value: 1.0,
    Severity.MEDIUM.value: 2.0,
    Severity.HIGH.value: 3.0,
}

# Business impact is a product judgement, not derivable from a single review,
# so it is configured here per frustration category. Tune to match strategy.
BUSINESS_IMPACT: dict[str, float] = {
    Frustration.SAME_SONGS_REPEATED.value: 3.0,
    Frustration.SAME_ARTISTS_REPEATED.value: 2.0,
    Frustration.BAD_RECOMMENDATIONS.value: 3.0,
    Frustration.TOO_MANY_SKIPS.value: 2.0,
    Frustration.WRONG_MOOD.value: 3.0,
    Frustration.OVER_PERSONALIZED_FEED.value: 2.0,
    Frustration.POOR_CONTROL.value: 2.0,
    Frustration.HIDDEN_DISCOVERY.value: 1.0,
    Frustration.NONE.value: 0.0,
}


# Human-readable labels for dashboards / reports.
FRUSTRATION_LABELS: dict[str, str] = {
    Frustration.SAME_SONGS_REPEATED.value: "Same songs repeated",
    Frustration.SAME_ARTISTS_REPEATED.value: "Same artists repeated",
    Frustration.BAD_RECOMMENDATIONS.value: "Bad recommendations",
    Frustration.TOO_MANY_SKIPS.value: "Too many skips",
    Frustration.WRONG_MOOD.value: "Wrong mood / context",
    Frustration.OVER_PERSONALIZED_FEED.value: "Over-personalized feed",
    Frustration.POOR_CONTROL.value: "Poor control",
    Frustration.HIDDEN_DISCOVERY.value: "Hidden discovery tools",
    Frustration.NONE.value: "No frustration",
}

UNMET_NEED_TO_OPPORTUNITY: dict[str, str] = {
    UnmetNeed.FRESH_BUT_FAMILIAR.value: "Fresh-but-familiar discovery mode",
    UnmetNeed.BETTER_CONTROL.value: "AI discovery assistant (user control)",
    UnmetNeed.MOOD_AWARE_DISCOVERY.value: "Mood-based AI discovery",
    UnmetNeed.LESS_REPETITIVE_PLAYLISTS.value: "Anti-repeat / evolving playlists",
    UnmetNeed.EFFORTLESS_DISCOVERY.value: "One-tap daily discovery journey",
    UnmetNeed.SOCIAL_PROOF.value: "Social proof in recommendations",
    UnmetNeed.RECOMMENDATION_EXPLANATION.value: "Recommendation explanations",
    UnmetNeed.BETTER_RESET_REFRESH.value: "Taste reset / refresh option",
    UnmetNeed.NONE.value: "—",
}


# --- Discovery problem taxonomy: root causes (spec section 5) -----------------

class RootCause(str, Enum):
    RECOMMENDATION_FATIGUE = "recommendation_fatigue"
    TASTE_BUBBLE = "taste_bubble"
    LOW_TRUST = "low_trust"
    HIGH_EFFORT = "high_effort"
    CONTEXT_MISMATCH = "context_mismatch"
    WEAK_FEEDBACK_CONTROL = "weak_feedback_control"
    LACK_OF_NOVELTY_BALANCE = "lack_of_novelty_balance"
    NONE = "none"


# The single framing statement for the whole analysis (spec section 5).
MAIN_PROBLEM = (
    "Users repeat familiar music because discovery feels risky, repetitive, "
    "or effortful."
)

ROOT_CAUSE_LABELS: dict[str, str] = {
    RootCause.RECOMMENDATION_FATIGUE.value: "Recommendation fatigue",
    RootCause.TASTE_BUBBLE.value: "Taste bubble",
    RootCause.LOW_TRUST.value: "Low trust",
    RootCause.HIGH_EFFORT.value: "High effort",
    RootCause.CONTEXT_MISMATCH.value: "Context mismatch",
    RootCause.WEAK_FEEDBACK_CONTROL.value: "Weak feedback control",
    RootCause.LACK_OF_NOVELTY_BALANCE.value: "Lack of novelty balance",
    RootCause.NONE.value: "—",
}

ROOT_CAUSE_EXPLANATIONS: dict[str, str] = {
    RootCause.RECOMMENDATION_FATIGUE.value: "Users feel the same songs keep coming back.",
    RootCause.TASTE_BUBBLE.value: "Spotify keeps users inside old listening habits.",
    RootCause.LOW_TRUST.value: "Users are not confident new songs will be good.",
    RootCause.HIGH_EFFORT.value: "Searching for new music takes time.",
    RootCause.CONTEXT_MISMATCH.value: "Recommendations don't match user mood/activity.",
    RootCause.WEAK_FEEDBACK_CONTROL.value: "Users cannot easily guide what they want.",
    RootCause.LACK_OF_NOVELTY_BALANCE.value: "New songs are either too similar or too random.",
    RootCause.NONE.value: "No discovery problem expressed.",
}

# Map an observed frustration to its underlying root cause.
FRUSTRATION_TO_ROOTCAUSE: dict[str, str] = {
    Frustration.SAME_SONGS_REPEATED.value: RootCause.RECOMMENDATION_FATIGUE.value,
    Frustration.SAME_ARTISTS_REPEATED.value: RootCause.TASTE_BUBBLE.value,
    Frustration.BAD_RECOMMENDATIONS.value: RootCause.LOW_TRUST.value,
    Frustration.TOO_MANY_SKIPS.value: RootCause.HIGH_EFFORT.value,
    Frustration.WRONG_MOOD.value: RootCause.CONTEXT_MISMATCH.value,
    Frustration.OVER_PERSONALIZED_FEED.value: RootCause.TASTE_BUBBLE.value,
    Frustration.POOR_CONTROL.value: RootCause.WEAK_FEEDBACK_CONTROL.value,
    Frustration.HIDDEN_DISCOVERY.value: RootCause.HIGH_EFFORT.value,
    Frustration.NONE.value: RootCause.NONE.value,
}

# Fallback when no explicit frustration: infer root cause from the topic cluster.
TOPIC_TO_ROOTCAUSE: dict[str, str] = {
    TopicCluster.REPETITIVE_RECOMMENDATIONS.value: RootCause.RECOMMENDATION_FATIGUE.value,
    TopicCluster.WEAK_GENRE_EXPLORATION.value: RootCause.TASTE_BUBBLE.value,
    TopicCluster.POOR_MOOD_UNDERSTANDING.value: RootCause.CONTEXT_MISMATCH.value,
    TopicCluster.TOO_MUCH_EFFORT.value: RootCause.HIGH_EFFORT.value,
    TopicCluster.DISCOVERY_FEELS_RISKY.value: RootCause.LOW_TRUST.value,
    TopicCluster.PLAYLIST_FATIGUE.value: RootCause.RECOMMENDATION_FATIGUE.value,
    TopicCluster.ALGORITHM_OVER_PERSONALIZATION.value: RootCause.TASTE_BUBBLE.value,
    TopicCluster.OTHER.value: RootCause.NONE.value,
}


def root_cause_for(frustration: str, topic: str) -> str:
    """Resolve a review's root cause: prefer frustration, fall back to topic."""
    rc = FRUSTRATION_TO_ROOTCAUSE.get(frustration, RootCause.NONE.value)
    if rc == RootCause.NONE.value:
        rc = TOPIC_TO_ROOTCAUSE.get(topic, RootCause.NONE.value)
    return rc
