"""Live feedback-source collectors (spec section 2).

Implemented (no API key required):
  - AppStoreCollector : Apple iTunes RSS customer-reviews feed
  - PlayStoreCollector: google-play-scraper package

Stubs (where additional ingestion would plug in):
  - RedditCollector, CommunityForumCollector, SocialMediaCollector

All return RawReview objects, so the rest of the pipeline is source-agnostic.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..models import RawReview, Source
from .base import Collector

# Spotify identifiers.
SPOTIFY_APP_STORE_ID = "324684580"
SPOTIFY_PLAY_STORE_PACKAGE = "com.spotify.music"

# Apple's RSS feed returns an empty (metadata-only) response for non-browser
# User-Agents, so present a standard browser UA.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class AppStoreCollector(Collector):
    """Apple App Store reviews via the public iTunes RSS customer-reviews feed.

    No API key required. The feed is paginated (up to ~10 pages of ~50 reviews
    per country) and returns rating, title+body text, version, author, and date.
    """

    def __init__(
        self,
        app_id: str = SPOTIFY_APP_STORE_ID,
        countries: list[str] | None = None,
        max_pages: int = 5,
    ):
        self.app_id = app_id
        self.countries = countries or ["us"]
        self.max_pages = max_pages

    def _feed_url(self, country: str, page: int) -> str:
        # Apple is order-sensitive: id= must precede page=, and the param is
        # sortBy=mostRecent. Other orderings return an empty (metadata-only) feed.
        return (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"id={self.app_id}/page={page}/sortBy=mostRecent/json"
        )

    def _fetch(self, url: str) -> dict | None:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

    @staticmethod
    def _entry_to_review(entry: dict, country: str) -> RawReview | None:
        # The first feed entry is app metadata (no im:rating) — skip those.
        if "im:rating" not in entry:
            return None
        title = entry.get("title", {}).get("label", "")
        body = entry.get("content", {}).get("label", "")
        text = f"{title}. {body}".strip(". ").strip()
        if not text:
            return None
        return RawReview(
            id=f"appstore-{entry.get('id', {}).get('label', '')}",
            source=Source.APP_STORE,
            text=text,
            rating=float(entry["im:rating"]["label"]),
            date=entry.get("updated", {}).get("label"),
            country=country.upper(),
            app_version=entry.get("im:version", {}).get("label"),
        )

    def collect(self) -> list[RawReview]:
        reviews: list[RawReview] = []
        for country in self.countries:
            for page in range(1, self.max_pages + 1):
                data = self._fetch(self._feed_url(country, page))
                entries = (data or {}).get("feed", {}).get("entry")
                if not entries:
                    break
                if isinstance(entries, dict):  # single-entry feeds aren't lists
                    entries = [entries]
                for entry in entries:
                    review = self._entry_to_review(entry, country)
                    if review:
                        reviews.append(review)
        return reviews


class PlayStoreCollector(Collector):
    """Google Play reviews via the `google-play-scraper` package (no API key).

    Install with: pip install google-play-scraper
    """

    def __init__(
        self,
        package_name: str = SPOTIFY_PLAY_STORE_PACKAGE,
        lang: str = "en",
        country: str = "us",
        count: int = 200,
    ):
        self.package_name = package_name
        self.lang = lang
        self.country = country
        self.count = count

    def collect(self) -> list[RawReview]:
        try:
            from google_play_scraper import Sort, reviews
        except ImportError as e:
            raise ImportError(
                "PlayStoreCollector needs the google-play-scraper package. "
                "Install it with: pip install google-play-scraper"
            ) from e

        results, _ = reviews(
            self.package_name,
            lang=self.lang,
            country=self.country,
            sort=Sort.NEWEST,
            count=self.count,
        )

        out: list[RawReview] = []
        for r in results:
            text = (r.get("content") or "").strip()
            if not text:
                continue
            at = r.get("at")
            out.append(
                RawReview(
                    id=f"playstore-{r.get('reviewId', '')}",
                    source=Source.PLAY_STORE,
                    text=text,
                    rating=float(r["score"]) if r.get("score") is not None else None,
                    date=at.date().isoformat() if at else None,
                    country=self.country.upper(),
                    app_version=r.get("reviewCreatedVersion"),
                    language=self.lang,
                )
            )
        return out


# --- Stubs (not yet implemented) ---------------------------------------------


class RedditCollector(Collector):
    """Reddit posts/comments from music/Spotify communities via PRAW."""

    def __init__(self, subreddits: list[str] | None = None, query: str = "discover"):
        self.subreddits = subreddits or ["spotify", "Music", "truespotify"]
        self.query = query

    def collect(self) -> list[RawReview]:
        raise NotImplementedError(
            "RedditCollector is a stub. Implement against PRAW (Reddit API)."
        )


class CommunityForumCollector(Collector):
    """Spotify Community forum feature requests / bug reports."""

    def collect(self) -> list[RawReview]:
        raise NotImplementedError(
            "CommunityForumCollector is a stub. Implement against the Spotify "
            "Community (Khoros/Lithium) API or HTML scraping."
        )


class SocialMediaCollector(Collector):
    """Tweets/X, Instagram/TikTok, YouTube comments mentioning Spotify discovery."""

    def collect(self) -> list[RawReview]:
        raise NotImplementedError(
            "SocialMediaCollector is a stub. Implement against the relevant "
            "platform APIs (X API, YouTube Data API, etc.)."
        )
