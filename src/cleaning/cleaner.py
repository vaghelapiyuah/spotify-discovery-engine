"""Deterministic cleaning before the AI layer (spec section 3, step 2).

What happens here (cheap, no LLM):
  - Duplicate removal      -> normalized-text hash; later copies marked duplicate
  - Spam / bot filtering   -> heuristic (urls, gibberish, repeated chars)
  - Very short reviews     -> tagged low-detail (kept, not dropped)

What is intentionally deferred to the AI layer (src/analysis):
  - Multi-language translation, emoji/slang normalization -> `normalized_summary`
  - App-bug vs discovery-issue classification             -> `is_app_bug`

The cleaner returns CleanReview objects. Spam and duplicates are flagged; the
pipeline decides whether to exclude them from analysis.
"""

from __future__ import annotations

import re

from ..models import CleanReview, RawReview

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_REPEAT_CHAR_RE = re.compile(r"(.)\1{6,}")          # "aaaaaaaa"
_WORD_RE = re.compile(r"\w+", re.UNICODE)

_SPAM_PHRASES = (
    "free followers",
    "click here",
    "promo code",
    "make money",
    "subscribe to my",
    "check my profile",
    "download now",
)


def _normalize_for_hash(text: str) -> str:
    """Lowercased, whitespace- and punctuation-collapsed key for dedup."""
    return re.sub(r"[^\w]+", " ", text.lower()).strip()


def _looks_like_spam(text: str) -> bool:
    low = text.lower()
    if _URL_RE.search(text):
        return True
    if any(p in low for p in _SPAM_PHRASES):
        return True
    if _REPEAT_CHAR_RE.search(text):
        return True
    # Mostly non-word characters (e.g. emoji-only or symbol spam).
    words = _WORD_RE.findall(text)
    if len(text) >= 8 and len(words) == 0:
        return True
    return False


class Cleaner:
    def __init__(self, short_review_chars: int = 25):
        self.short_review_chars = short_review_chars

    def clean(self, reviews: list[RawReview]) -> list[CleanReview]:
        seen: dict[str, str] = {}  # normalized text -> canonical review id
        cleaned: list[CleanReview] = []

        for r in reviews:
            text = (r.text or "").strip()
            key = _normalize_for_hash(text)

            duplicate_of = seen.get(key) if key else None
            if key and duplicate_of is None:
                seen[key] = r.id

            cleaned.append(
                CleanReview(
                    raw=r,
                    is_short=len(text) < self.short_review_chars,
                    is_spam=_looks_like_spam(text),
                    duplicate_of=duplicate_of,
                )
            )
        return cleaned

    @staticmethod
    def analyzable(cleaned: list[CleanReview]) -> list[CleanReview]:
        """Reviews worth sending to the AI layer: not spam, not a duplicate."""
        return [c for c in cleaned if not c.is_spam and c.duplicate_of is None]
