"""Recreate Slide 10 — FreshMix AI agent architecture — as a crisp 1920x1080
vector PDF (Spotify dark theme), consistent with slides 08/09.

Run:  python make_slide10.py  ->  slides/Slide_10_Architecture.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas

from make_kpi_slides import (
    BG, BLACK, BLUE, BORDER, CARD, CARD2, G, ORANGE, PURPLE, TAKE, WHITE,
    W50, W70, YELLOW, H, W, disc, pill, rrect, spans, txt, wrap,
)


def arrow_right(c, x1, x2, ytop, color, wdt=3):
    y = H - ytop
    c.setStrokeColor(color); c.setLineWidth(wdt)
    c.line(x1, y, x2 - 10, y)
    p = c.beginPath(); p.moveTo(x2 - 13, y + 7); p.lineTo(x2, y); p.lineTo(x2 - 13, y - 7)
    p.close(); c.setFillColor(color); c.drawPath(p, fill=1, stroke=0)


def arrow_down(c, x, y1top, y2top, color, wdt=3):
    c.setStrokeColor(color); c.setLineWidth(wdt)
    c.line(x, H - y1top, x, H - y2top + 10)
    yy = H - y2top
    p = c.beginPath(); p.moveTo(x - 7, yy + 13); p.lineTo(x, yy); p.lineTo(x + 7, yy + 13)
    p.close(); c.setFillColor(color); c.drawPath(p, fill=1, stroke=0)


def node(c, x, top, w, h, num, title, desc, accent=G, highlight=False):
    rrect(c, x, top, w, h, 16, fill=CARD2, border=(accent if highlight else BORDER),
          bw=2 if highlight else 1)
    disc(c, x + 36, top + 36, 19, fill=accent, alpha=0.16, border=accent)
    txt(c, x + 36, top + 45, str(num), 26, accent, bold=True, center=True)
    txt(c, x + 70, top + 45, title, 26, WHITE, bold=True)
    wrap(c, desc, x + 20, top + 86, w - 40, 26, W70, lead=30, max_lines=3)


def slide10(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

    pill(c, 70, 46, "SLIDE 10", 28, G, G, alpha=0.16, border=G, h=52)
    txt(c, 70, 150, "FreshMix AI agent architecture", 44, G, bold=True)
    txt(c, 70, 204,
        "How the product turns mood, activity, and taste into trusted discovery",
        38, WHITE, bold=True)

    # ---- Left panel: high-level architecture ----
    lx, lw = 70, 1180
    ltop, lh = 248, 600
    rrect(c, lx, ltop, lw, lh, 22, fill=CARD, border=BORDER)
    rrect(c, lx + 22, ltop, lw - 44, 4, 2, fill=G)
    txt(c, lx + 28, ltop + 48, "HIGH-LEVEL ARCHITECTURE", 26, G, bold=True)

    nx0 = lx + 30
    nw, nh = 250, 178
    gap = (lw - 60 - 4 * nw) / 3
    xs = [nx0 + i * (nw + gap) for i in range(4)]
    r1 = ltop + 80
    r2 = ltop + 320

    nodes1 = [
        (1, "User input", "Mood, activity, language + prompt", G, False),
        (2, "FreshMix UI", "Prompt box, chips, freshness slider", G, False),
        (3, "Orchestrator", "Splits request: retrieval + generation", G, False),
        (4, "Claude AI", "Reads intent, writes the rationale", G, False),
    ]
    for (num, t, d, a, hl), x in zip(nodes1, xs):
        node(c, x, r1, nw, nh, num, t, d, a, hl)
    for i in range(3):
        arrow_right(c, xs[i] + nw + 6, xs[i + 1] - 6, r1 + nh / 2, G)

    nodes2 = [
        (5, "Music context", "Recent plays, saved songs, playlists", BLUE, False),
        (6, "RAG knowledge", "Review pain points + user context", PURPLE, False),
        (7, "Recommendation", "Fresh-but-familiar song queue", G, True),
    ]
    for (num, t, d, a, hl), x in zip(nodes2, xs[:3]):
        node(c, x, r2, nw, nh, num, t, d, a, hl)
    for i in range(2):
        arrow_right(c, xs[i] + nw + 6, xs[i + 1] - 6, r2 + nh / 2, G)

    # elbow connector node4 -> node5
    mid = (r1 + nh + r2) / 2
    x4c = xs[3] + nw / 2
    x5c = xs[0] + nw / 2
    c.setStrokeColor(G); c.setLineWidth(3)
    c.line(x4c, H - (r1 + nh), x4c, H - mid)
    c.line(x4c, H - mid, x5c, H - mid)
    arrow_down(c, x5c, mid, r2, G)

    # feedback loop bar
    fy = ltop + lh - 64
    rrect(c, lx + 30, fy, lw - 60, 48, 12, fill=G, alpha=0.12, border=G)
    txt(c, lx + 50, fy + 32, "Feedback loop  —  saves, skips & replays improve the next "
        "FreshMix queue", 26, G, bold=True)

    # ---- Right column ----
    rx, rw = 1280, 570

    # Tech stack
    ttop, th = 248, 286
    rrect(c, rx, ttop, rw, th, 22, fill=CARD, border=BORDER)
    rrect(c, rx + 22, ttop, rw - 44, 4, 2, fill=BLUE)
    txt(c, rx + 28, ttop + 46, "TECH STACK USED", 26, BLUE, bold=True)
    tech = [(G, "Claude", "AI + song reasoning"),
            (BLUE, "Streamlit", "agent UI + dashboard"),
            (YELLOW, "Python", "cleaning + workflow"),
            (PURPLE, "Spotify API", "tracks & playlists"),
            (ORANGE, "Review data", "App / Play / Reddit"),
            (G, "Vector / RAG", "review retrieval")]
    ty = ttop + 84
    for dot, name, dsc in tech:
        disc(c, rx + 40, ty - 8, 7, fill=dot)
        spans(c, rx + 60, ty, [(name + " ", WHITE), ("— " + dsc, W70)], 26, bold=False)
        ty += 34

    # Guidelines
    gtop, gh = 554, 294
    rrect(c, rx, gtop, rw, gh, 22, fill=CARD, border=BORDER)
    rrect(c, rx + 22, gtop, rw - 44, 4, 2, fill=YELLOW)
    txt(c, rx + 28, gtop + 46, "GUIDELINES TO USE AGENT", 26, YELLOW, bold=True)
    steps = ["Enter mood + activity", "Set freshness level", "Write what you want",
             'Review "why this song"', "Save, skip, or refresh"]
    sy = gtop + 90
    for i, s in enumerate(steps):
        disc(c, rx + 44, sy - 8, 18, fill=YELLOW, alpha=0.16, border=YELLOW)
        txt(c, rx + 44, sy, str(i + 1), 26, YELLOW, bold=True, center=True)
        txt(c, rx + 76, sy, s, 26, WHITE)
        sy += 40

    # Takeaway
    rrect(c, 70, 880, 1780, 116, 16, fill=TAKE, border=G, bw=2)
    rrect(c, 92, 906, 40, 40, 10, fill=G, alpha=0.18, border=G)
    txt(c, 150, 934, "KEY TAKEAWAY", 26, G, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.35); c.setLineWidth(1)
    c.line(330, H - 900, 330, H - 976); c.setStrokeAlpha(1)
    wrap(c, "FreshMix AI connects user intent, listening context, review insights, and "
            "feedback signals to generate discovery that feels relevant, fresh, and "
            "easy to trust.", 352, 926, 1480, 28, WHITE, lead=38)


def main():
    out = Path("slides"); out.mkdir(exist_ok=True)
    path = out / "Slide_10_Architecture.pdf"
    c = canvas.Canvas(str(path), pagesize=(W, H))
    slide10(c); c.showPage(); c.save()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
