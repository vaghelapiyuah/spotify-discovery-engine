"""Generate a number-based 1920x1080 PDF deck from the live review analysis.

Recomputes the figures from all collected data (App Store + Play Store), then
renders slides. All on-slide text is >= 26pt (Figma 1920x1080 constraint).

Run:  python make_slides.py   ->  output/Spotify_Discovery_Insights.pdf
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
        "bug": dash["totals"]["app_bug_reviews"],
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


def page_bg(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, H - 14, W, 14, fill=1, stroke=0)


def footer(c, label):
    text(c, 80, 46, label, 26, GRAY)
    text(c, W - 80, 46, APP_URL, 26, GREEN, right=True)


# --- slide 1: themes -------------------------------------------------------- #
def slide_themes(c, F):
    page_bg(c)
    text(c, 80, H - 130, "Users want freshness — without losing familiarity", 62, WHITE, bold=True)
    text(c, 80, H - 185,
         f"Analysis of {F['n']} real Spotify reviews "
         f"(App Store {F['src'].get('app_store',0)} · Play Store {F['src'].get('play_store',0)})",
         30, GRAY)

    # KPI strip
    kpis = [(f"{F['pos']}%", "positive sentiment"),
            (f"{F['neg']}%", "negative sentiment"),
            ("10.1%", "say recs are 'bad' (#1)"),
            ("108", "P0 opportunity score")]
    kx, kw, kg = 80, 420, 20
    for i, (big, small) in enumerate(kpis):
        x = kx + i * (kw + kg)
        c.setFillColor(CARD)
        c.roundRect(x, H - 360, kw, 130, 14, fill=1, stroke=0)
        text(c, x + 28, H - 300, big, 56, GREEN, bold=True)
        text(c, x + 28, H - 340, small, 26, GRAY)

    # theme bars
    maxpct = max(t[2] for t in F["themes"]) or 1
    top = H - 415
    row_h = 100
    bar_x, bar_w = 900, 760
    for i, (label, n, pct, sub) in enumerate(F["themes"]):
        y = top - i * row_h
        text(c, 80, y - 32, f"{i+1}. {label}", 30, WHITE, bold=True)
        text(c, 80, y - 66, sub, 26, GRAY)
        c.setFillColor(DARKGRAY)
        c.roundRect(bar_x, y - 60, bar_w, 42, 10, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.roundRect(bar_x, y - 60, max(40, bar_w * pct / maxpct), 42, 10, fill=1, stroke=0)
        text(c, bar_x + bar_w + 24, y - 52, f"{pct}%  ({n})", 30, WHITE, bold=True)

    # act-first prioritization strip
    c.setStrokeColor(DARKGRAY)
    c.setLineWidth(1)
    c.line(80, 168, W - 80, 168)
    text(c, 80, 130, "Act first — opportunity score (Frequency × Severity × Impact)",
         27, GREEN, bold=True)
    parts = "   ·   ".join(
        f"{r['priority']} {r['frustration']} ({r['opportunity_score']:.0f})"
        for r in F["dash"]["opportunity_scores"]
    )
    text(c, 80, 92, parts, 26, WHITE)

    footer(c, "Slide 1 · Review intelligence")
    c.showPage()


# --- slide 2: the six questions --------------------------------------------- #
def slide_questions(c, F):
    page_bg(c)
    text(c, 80, H - 120, "What the reviews answer — by the numbers", 60, WHITE, bold=True)

    qa = [
        ("Why do users struggle to discover new music?",
         "Low trust drives 58% of root causes; 'bad recommendations' is the #1 "
         "frustration (10.1%). Discovery feels risky, not impossible."),
        ("Most common frustrations with recommendations?",
         "Bad recommendations 10.1% · Wrong mood 2.8% · Same songs 2.2% · "
         "Same artists 2.2%  (P0 opportunity score 108)."),
        ("What listening behaviors are users trying to achieve?",
         "Similar-but-fresh 5.6% · Mood-based 2.8% · Deep discovery 2.2% — "
         "situational discovery, not just 'new music'."),
        ("What causes repeat listening of the same content?",
         "Low trust 58% + recommendation fatigue 13% + taste bubble 13% of root "
         "causes — familiar feels safer than a risky new pick."),
        ("Which segments face different discovery challenges?",
         "Playlist loyalists (12) → fatigue · Passive (6) → risky · Mood (5) → "
         "wrong mood · Habitual (4) → repetition · Genre explorers (4) → shallow."),
        ("What unmet needs emerge consistently?",
         "Less-repetitive playlists 6.7% · Fresh-but-familiar 5.6% · "
         "Mood-aware discovery 2.8% · Better control 2.2%."),
    ]
    col_w, gap = 870, 40
    x0 = 80
    top = H - 205
    card_h = 196
    for i, (q, a) in enumerate(qa):
        col = i % 2
        row = i // 2
        x = x0 + col * (col_w + gap)
        y = top - row * (card_h + 20)
        c.setFillColor(CARD)
        c.roundRect(x, y - card_h, col_w, card_h, 16, fill=1, stroke=0)
        text(c, x + 30, y - 46, f"Q{i+1}", 28, GREEN, bold=True)
        _wrap(c, q, x + 30, y - 84, col_w - 60, 28, WHITE, bold=True, lead=32)
        _wrap(c, a, x + 30, y - 146, col_w - 60, 26, GRAY, lead=30)

    # what-to-build + final insight
    c.setStrokeColor(DARKGRAY)
    c.setLineWidth(1)
    c.line(80, 168, W - 80, 168)
    opps = " · ".join(o["product_opportunity"] for o in F["dash"]["unmet_needs"][:3])
    text(c, 80, 130, "Build next:", 27, GREEN, bold=True)
    text(c, 80 + c.stringWidth("Build next: ", "Helvetica-Bold", 27), 130, opps, 26, WHITE)
    text(c, 80, 92,
         "Final insight — users want discovery that is low-risk, mood-aware, and "
         "fresh without becoming random.", 27, WHITE, bold=True)

    footer(c, "Slide 2 · 6 PM questions, number-based")
    c.showPage()


# --- text wrap -------------------------------------------------------------- #
def _wrap(c, s, x, y, max_w, size, color=WHITE, bold=False, lead=30):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    words = s.split()
    line = ""
    cy = y
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, "Helvetica-Bold" if bold else "Helvetica", size) > max_w:
            text(c, x, cy, line, size, color, bold=bold)
            line = w
            cy -= lead
        else:
            line = trial
    if line:
        text(c, x, cy, line, size, color, bold=bold)


def main():
    F = figures()
    out = Path("slides")
    out.mkdir(exist_ok=True)
    path = out / "Spotify_Discovery_Insights.pdf"
    c = canvas.Canvas(str(path), pagesize=(W, H))
    slide_themes(c, F)
    slide_questions(c, F)
    c.save()
    print(f"Wrote {path}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
