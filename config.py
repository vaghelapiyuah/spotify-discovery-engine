"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # The Claude model used for the AI analysis layer.
    # Default is the most capable model; override to claude-haiku-4-5 or
    # claude-sonnet-4-6 for cheaper high-volume runs.
    model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    # Parallel analysis threads.
    workers: int = int(os.getenv("ENGINE_WORKERS", "6"))

    # Max tokens per analysis response (one structured object — small).
    max_tokens: int = 2000

    # Reviews shorter than this many characters are tagged low-detail.
    short_review_chars: int = 25

    @property
    def has_api_key(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))


CONFIG = Config()
