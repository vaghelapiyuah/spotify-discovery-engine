"""Theme clustering layer.

Groups reviews into emergent themes via TF-IDF + KMeans (offline, no API),
complementing the fixed taxonomy `topic_cluster`. Where the taxonomy answers
"which known bucket?", clustering surfaces "what themes actually emerge in
this batch?".
"""

from .themes import ThemeClusterer, Theme

__all__ = ["ThemeClusterer", "Theme"]
