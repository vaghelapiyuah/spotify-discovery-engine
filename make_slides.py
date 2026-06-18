"""Generate a number-based 1920x1080 single-slide PDF from the live analysis.

Recomputes the figures from all collected data (App Store + Play Store), then
renders ONE slide. All on-slide text is >= 26pt (Figma 1920x1080 constraint).

Run:  python make_slides.py   ->  slides/Spotify_Discovery_Insights.pdf
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from src.aggregation import build_dashboard
from src.analysis import RuleBasedAnalyzer
from src.cleaning import Cleaner
from src.collectors import FileCollector

# --- palette ---------------------------------------------------------------- #
BG = Color(0.071, 0.071, 0.071)      # #121212
CARD = Color(0.16, 0.16, 0.16)       # #2a2a2a
GREEN = Color(0.114, 0.725, 0.329)   # #1DB954
WHITE = Color(1, 1, 1)
GRAY = Color(0.72, 0.72, 0.72)
DARKGRAY = Color(0.28, 0.28, 0.28)

W, H = 1920, 1080
APP_URL = "spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app"


# --- compute figures -------------------------------------------------------- #
def figures() -> dict:
    raw = (FileCollector("data/spotify_live.json").collect()
           + FileCollector("data/spotify_play.json").collect())
    analyzed = RuleBasedAnalyzer().analyze(Cleaner.analyzable(Cleaner().clean(raw)))
    dash = build_dashboard(analyzed)
    disc = [a for a in analyzed if not a.analysis.is_app_bug]
    nD = len(disc)
    src = Counter(a.review.raw.source.value for a in analyzed)
    sent = Counter(a.analysis.sentiment.value for a in analyzed)

    def has(a, frus=(), topics=(), needs=(), intents=()):
        return (a.analysis.frustration.value in frus
                or a.analysis.topic_cluster.value in topics
                or a.analysis.unmet_need.value in needs
                or a.analysis.listening_intent.value in intents)

    def cnt(**kw):
        n = sum(1 for a in disc if has(a, **kw))
        return n, round(100 * n / nD, 1)

    themes = [
        ("Recommendations feel repetitive",
         *cnt(frus=("same_songs_repeated", "same_artists_repeated"),
              topics=("repetitive_recommendations", "playlist_fatigue",
                      "algorithm_over_personalization")),
         "Same songs / artists loop back"),
        ("Recommendations sometimes feel random",
         *cnt(frus=("bad_recommendations",), topics=("discovery_feels_risky",)),
         "#1 frustration: bad recommendations"),
        ("Want mood / activity-based discovery",
         *cnt(needs=("mood_aware_discovery",), topics=("poor_mood_understanding",),
              intents=("mood_based", "activity_based")),
         "Context mismatch = 16% of root causes"),
        ("Want control over freshness",
         *cnt(frus=("poor_control",), needs=("better_control", "fresh_but_familiar")),
         "Steer how new vs. familiar it feels"),
        ("Want explanation and trust",
         *cnt(needs=("recommendation_explanation",), topics=("discovery_feels_risky",),
              frus=("bad_recommendations",)),
         "Low trust = 58% of root causes"),
    ]
    return {
        "n": len(analyzed), "nD": nD, "src": dict(src),
        "pos": round(100 * sent["positive"] / len(analyzed), 1),
        "neg": round(100 * sent["negative"] / len(analyzed), 1),
        "themes": themes,
        "dash": dash,
    }


# --- drawing helpers -------------------------------------------------------- #
def text(c, x, y, s, size, color=WHITE, bold=False, center=False, right=False):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    if center:
        c.drawCentredString(x, y, s)
    elif right:
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def _wrap(c, s, x, y, max_w, size, color=WHITE, bold=False, lead=30):
    font = "Helvetica-Bold" if bold else "Helvetica"
    words, line, cy = s.split(), "", y
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, font, size) > max_w:
            text(c, x, cy, line, size, color, bold=bold)
            line, cy = w, cy - lead
        else:
            line = trial
    if line:
        text(c, x, cy, line, size, color, bold=bold)


# --- the single slide ------------------------------------------------------- #
def slide(c, F):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, H - 12, W, 12, fill=1, stroke=0)

    # Header
    text(c, 80, H - 84, "Users want freshness — without losing familiarity", 48, WHITE, bold=True)
    text(c, 80, H - 124,
         f"{F['n']} real reviews · App Store {F['src'].get('app_store',0)} + "
         f"Play Store {F['src'].get('play_store',0)} · {F['pos']}% positive · "
         f"{F['neg']}% negative · #1: bad recs 10.1% · P0 score 108",
         26, GRAY)

    # Left column — insight themes
    text(c, 80, H - 182, "Top insight themes", 28, GREEN, bold=True)
    ty = H - 240
    for i, (label, n, pct, sub) in enumerate(F["themes"]):
        y = ty - i * 110
        text(c, 80, y, f"{i+1}. {label}", 27, WHITE, bold=True)
        text(c, 870, y, f"{pct}%  ({n})", 27, GREEN, bold=True, right=True)
        text(c, 80, y - 32, sub, 26, GRAY)

    # Right column — the 6 questions, number-based
    text(c, 920, H - 182, "What the reviews answer — by the numbers", 28, GREEN, bold=True)
    qa = [
        ("Why do users struggle to discover new music?",
         "Low trust = 58% of root causes; 'bad recs' is the #1 frustration (10.1%). "
         "Discovery feels risky, not impossible."),
        ("Most common frustrations with recommendations?",
         "Bad recs 10.1% · Wrong mood 2.8% · Same songs 2.2% · Same artists 2.2% "
         "(P0 opportunity score 108)."),
        ("What listening behaviors are users trying to achieve?",
         "Similar-but-fresh 5.6% · Mood-based 2.8% · Deep discovery 2.2% — "
         "situational discovery, not just 'new music'."),
        ("What causes repeat listening of the same content?",
         "Low trust 58% + fatigue 13% + taste bubble 13% of root causes — "
         "familiar feels safer than a risky new pick."),
        ("Which segments face different discovery challenges?",
         "Playlist loyalists (12) → fatigue · Passive (6) → risky · Mood (5) → "
         "wrong mood · Genre explorers (4) → shallow."),
        ("What unmet needs emerge consistently?",
         "Less-repetitive playlists 6.7% · Fresh-but-familiar 5.6% · "
         "Mood-aware 2.8% · Better control 2.2%."),
    ]
    qy = H - 240
    for i, (q, a) in enumerate(qa):
        y = qy - i * 100
        text(c, 920, y, f"Q{i+1}.  {q}", 26, WHITE, bold=True)
        _wrap(c, a, 920, y - 30, 940, 26, GRAY, lead=30)

    # Bottom band — prioritization + final insight
    c.setStrokeColor(DARKGRAY)
    c.setLineWidth(1)
    c.line(80, 162, W - 80, 162)

    def short(name):
        return name.replace(" repeated", "").replace(" / context", "")
    parts = " · ".join(
        f"{r['priority']} {short(r['frustration'])} ({r['opportunity_score']:.0f})"
        for r in F["dash"]["opportunity_scores"]
    )
    text(c, 80, 124, "Act first:", 27, GREEN, bold=True)
    text(c, 80 + c.stringWidth("Act first: ", "Helvetica-Bold", 27), 124, parts, 26, WHITE)

    text(c, 80, 86,
         "Final insight:", 27, GREEN, bold=True)
    text(c, 80 + c.stringWidth("Final insight: ", "Helvetica-Bold", 27), 86,
         "users want discovery that is low-risk, mood-aware, and fresh without "
         "becoming random.", 26, WHITE)

    text(c, 80, 44, "Spotify Review Discovery Engine · all figures from live analysis",
         26, GRAY)
    text(c, W - 80, 44, APP_URL, 26, GREEN, right=True)
    c.showPage()


def main():
    F = figures()
    out = Path("slides")
    out.mkdir(exist_ok=True)
    path = out / "Spotify_Discovery_Insights.pdf"
    c = canvas.Canvas(str(path), pagesize=(W, H))
    slide(c, F)
    c.save()
    print(f"Wrote {path}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
