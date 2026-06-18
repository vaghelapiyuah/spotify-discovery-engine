"""Data collection layer (spec section 3, step 1).

`FileCollector` reads reviews from a local JSON file. `AppStoreCollector` and
`PlayStoreCollector` pull live Spotify reviews (no API key required). The
remaining sources are interface stubs showing where ingestion plugs in.
"""

from .base import Collector
from .file_collector import FileCollector
from .live_sources import (
    AppStoreCollector,
    CommunityForumCollector,
    PlayStoreCollector,
    RedditCollector,
    SocialMediaCollector,
    SPOTIFY_APP_STORE_ID,
    SPOTIFY_PLAY_STORE_PACKAGE,
)

__all__ = [
    "Collector",
    "FileCollector",
    "AppStoreCollector",
    "PlayStoreCollector",
    "RedditCollector",
    "CommunityForumCollector",
    "SocialMediaCollector",
    "SPOTIFY_APP_STORE_ID",
    "SPOTIFY_PLAY_STORE_PACKAGE",
]
