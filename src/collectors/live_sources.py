"""Live feedback-source collectors (spec section 2).

Implemented (no API key required):
  - AppStoreCollector : Apple iTunes RSS customer-reviews feed
  - PlayStoreCollector: google-play-scraper package

Stubs (where additional ingestion would plug in):
  - RedditCollector, CommunityForumCollector, SocialMediaCollector

All return RawReview objects, so the rest of the pipeline is source-agnostic.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
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


# --- Reddit (official API; anonymous JSON is blocked by Reddit) --------------


class RedditCollector(Collector):
    """Reddit posts from music/Spotify communities via the official OAuth API.

    Reddit blocks anonymous JSON access (HTTP 403), so this needs free app
    credentials. Create a "script" or "web" app at
    https://www.reddit.com/prefs/apps and set:
        REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
    """

    def __init__(
        self,
        subreddits: list[str] | None = None,
        query: str = "discover OR recommendations OR discover weekly",
        limit: int = 100,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.subreddits = subreddits or ["spotify", "truespotify", "Music"]
        self.query = query
        self.limit = limit
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")

    def _token(self) -> str:
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=data,
            headers={"Authorization": f"Basic {auth}", "User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))["access_token"]

    def collect(self) -> list[RawReview]:
        if not (self.client_id and self.client_secret):
            raise RuntimeError(
                "Reddit needs API credentials (anonymous access is blocked). "
                "Create an app at https://www.reddit.com/prefs/apps and set "
                "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
            )
        token = self._token()
        subs = "+".join(self.subreddits)
        params = urllib.parse.urlencode(
            {"q": self.query, "restrict_sr": "1", "sort": "new",
             "limit": str(self.limit), "t": "year"}
        )
        url = f"https://oauth.reddit.com/r/{subs}/search?{params}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"bearer {token}", "User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        out: list[RawReview] = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            text = f"{d.get('title','')}. {d.get('selftext','')}".strip(". ").strip()
            if not text:
                continue
            out.append(
                RawReview(
                    id=f"reddit-{d.get('id','')}",
                    source=Source.REDDIT,
                    text=text,
                    date=None,
                    country=None,
                )
            )
        return out


class CommunityForumCollector(Collector):
    """Spotify Community forum (Khoros/Lithium).

    The Khoros community API is auth-gated and HTML scraping is brittle/often
    blocked, so this stays a stub: provide community export JSON via FileCollector,
    or implement against the Khoros LiQL API with a community API key.
    """

    def collect(self) -> list[RawReview]:
        raise RuntimeError(
            "Spotify Community needs Khoros API access (no free anonymous API). "
            "Export posts to JSON and load via FileCollector, or wire the Khoros "
            "LiQL API here."
        )


class SocialMediaCollector(Collector):
    """Social media via the YouTube Data API (comments on Spotify videos).

    Free key: https://console.cloud.google.com -> enable YouTube Data API v3.
    Set YOUTUBE_API_KEY. (X/Twitter and TikTok require paid/restricted APIs.)
    """

    def __init__(
        self,
        query: str = "spotify discover weekly recommendations",
        max_videos: int = 8,
        per_video: int = 50,
        api_key: str | None = None,
    ):
        self.query = query
        self.max_videos = max_videos
        self.per_video = per_video
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def collect(self) -> list[RawReview]:
        if not self.api_key:
            raise RuntimeError(
                "Social media (YouTube) needs YOUTUBE_API_KEY. Enable the "
                "YouTube Data API v3 in Google Cloud and set the key. "
                "(X/Twitter and TikTok require paid APIs.)"
            )
        base = "https://www.googleapis.com/youtube/v3"
        search_url = (
            f"{base}/search?part=snippet&type=video&maxResults={self.max_videos}"
            f"&q={urllib.parse.quote(self.query)}&key={self.api_key}"
        )
        video_ids = [
            it["id"]["videoId"]
            for it in self._get(search_url).get("items", [])
            if it.get("id", {}).get("videoId")
        ]

        out: list[RawReview] = []
        for vid in video_ids:
            c_url = (
                f"{base}/commentThreads?part=snippet&videoId={vid}"
                f"&maxResults={self.per_video}&textFormat=plainText&key={self.api_key}"
            )
            try:
                items = self._get(c_url).get("items", [])
            except urllib.error.HTTPError:
                continue  # comments disabled, etc.
            for it in items:
                sn = it["snippet"]["topLevelComment"]["snippet"]
                text = (sn.get("textDisplay") or "").strip()
                if not text:
                    continue
                out.append(
                    RawReview(
                        id=f"youtube-{it['id']}",
                        source=Source.SOCIAL_MEDIA,
                        text=text,
                        date=(sn.get("publishedAt") or "")[:10] or None,
                    )
                )
        return out
