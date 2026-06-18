"""Pydantic schemas that flow through the pipeline.

RawReview  -> (clean) -> CleanReview -> (analyze) -> AnalyzedReview
The AI analysis layer returns a `ReviewAnalysis` validated against the taxonomy.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .taxonomy import (
    Frustration,
    ListeningIntent,
    Segment,
    Sentiment,
    Severity,
    Source,
    TopicCluster,
    UnmetNeed,
)


class RawReview(BaseModel):
    """A single piece of feedback as collected from a source."""

    id: str
    source: Source
    text: str
    rating: Optional[float] = None          # 1-5 stars where available
    date: Optional[str] = None              # ISO date string
    country: Optional[str] = None
    app_version: Optional[str] = None
    device: Optional[str] = None
    language: Optional[str] = None          # detected/declared source language


class CleanReview(BaseModel):
    """A review after deterministic cleaning."""

    raw: RawReview
    is_short: bool = False                   # low-detail tag
    is_spam: bool = False
    duplicate_of: Optional[str] = None       # id of the canonical review, if dup


class ReviewAnalysis(BaseModel):
    """Structured output the LLM must produce for each review.

    Field order and descriptions double as instructions to the model.
    """

    normalized_summary: str = Field(
        description="One neutral English sentence capturing what the user feels "
        "and which discovery problem they describe. Resolve slang/emoji/other "
        "languages into plain meaning."
    )
    is_app_bug: bool = Field(
        description="True if this is primarily an app bug/technical complaint "
        "rather than a music-discovery issue."
    )
    sentiment: Sentiment
    topic_cluster: TopicCluster
    listening_intent: ListeningIntent
    frustration: Frustration
    frustration_severity: Severity = Field(
        description="How damaging the frustration is to the experience. "
        "Use 'low' when frustration is 'none'."
    )
    segment: Segment
    unmet_need: UnmetNeed
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Your confidence in this classification, 0-1.",
    )


class AnalyzedReview(BaseModel):
    """A clean review joined with its AI analysis."""

    review: CleanReview
    analysis: ReviewAnalysis


class PMAnswer(BaseModel):
    question: str
    answer: str


class Synthesis(BaseModel):
    """Run-level synthesis the LLM produces from the aggregated results
    (spec sections 6, 8.D and 10)."""

    executive_summary: str = Field(
        description="2-4 sentence decision-ready summary of what the feedback "
        "says about Spotify music discovery."
    )
    pm_answers: list[PMAnswer] = Field(
        description="One answer for each of the six PM questions provided."
    )
    final_product_insight: str = Field(
        description="The single sharpest insight that should anchor Spotify's "
        "next product solution."
    )
