"""The AI analysis layer (spec section 4), powered by the Claude API.

`Analyzer.analyze` runs the six analyses per review as a single structured
output call, parallelised across reviews. `Analyzer.synthesize` makes one
run-level call that turns the aggregates into an executive summary and answers
to the PM questions.

Design notes:
  - The large taxonomy system prompt is identical for every review, so it is
    sent with cache_control={"type": "ephemeral"} (prompt caching). Only the
    short review text varies, so most input tokens are served from cache.
  - Structured output uses client.messages.parse(output_format=Model), which
    validates the response against the Pydantic schema (and transparently
    handles JSON-schema constraints the API doesn't support natively).
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models import (
    AnalyzedReview,
    CleanReview,
    ReviewAnalysis,
    Synthesis,
)
from . import prompts

# The six PM questions the synthesis must answer (spec section 6).
PM_QUESTIONS = [
    "Why do users struggle to discover new music?",
    "What are the most common frustrations with recommendations?",
    "What listening behaviors are users trying to achieve?",
    "What causes users to repeatedly listen to the same content?",
    "Which user segments experience different discovery challenges?",
    "What unmet needs emerge consistently?",
]


class Analyzer:
    def __init__(self, model: str, workers: int = 6, max_tokens: int = 2000):
        import anthropic  # lazy: keeps offline paths import-light

        self.client = anthropic.Anthropic()
        self.model = model
        self.workers = workers
        self.max_tokens = max_tokens

    def validate(self) -> tuple[bool, str]:
        """Cheap preflight: confirm the API key works. Returns (ok, message)."""
        import anthropic

        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "ok"
        except anthropic.AuthenticationError:
            return False, "Invalid ANTHROPIC_API_KEY."
        except anthropic.NotFoundError:
            return False, f"Model '{self.model}' not available for this key."
        except Exception as e:  # network, rate limit, etc.
            return False, f"{type(e).__name__}: {e}"

    # --- per-review analysis -------------------------------------------------

    def _analyze_one(self, review: CleanReview) -> AnalyzedReview:
        raw = review.raw
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": prompts.ANALYSIS_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": prompts.review_user_prompt(
                        raw.text, raw.source.value, raw.rating
                    ),
                }
            ],
            output_format=ReviewAnalysis,
        )
        analysis = response.parsed_output
        if analysis is None:  # refusal / parse failure
            raise RuntimeError(
                f"Analysis failed for review {raw.id} "
                f"(stop_reason={response.stop_reason})"
            )
        return AnalyzedReview(review=review, analysis=analysis)

    def analyze(self, reviews: list[CleanReview]) -> list[AnalyzedReview]:
        """Analyze reviews in parallel; preserves input order."""
        results: list[AnalyzedReview | None] = [None] * len(reviews)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self._analyze_one, r): i
                for i, r in enumerate(reviews)
            }
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()
        return [r for r in results if r is not None]

    # --- run-level synthesis -------------------------------------------------

    def synthesize(self, aggregates: dict) -> Synthesis:
        """Turn the aggregated dashboard data into a PM-ready synthesis."""
        user_prompt = (
            "Here are the aggregated results from the discovery engine "
            "(counts, percentages, sentiment, segments, opportunity scores):\n\n"
            f"{json.dumps(aggregates, indent=2)}\n\n"
            "Answer each of these PM questions, grounded only in the data above:\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(PM_QUESTIONS))
            + "\n\nThen give an executive summary and the single final product "
            "insight that should anchor Spotify's next solution."
        )

        response = self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=prompts.SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=Synthesis,
        )
        synthesis = response.parsed_output
        if synthesis is None:
            raise RuntimeError(
                f"Synthesis failed (stop_reason={response.stop_reason})"
            )
        return synthesis
