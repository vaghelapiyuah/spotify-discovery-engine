"""Render Slide 08 (KPI tree / metrics framework) and Slide 09 (FreshMix AI
product feature) as a 1920x1080 PDF, from the Figma design spec.

Run:  python make_kpi_slides.py  ->  slides/Slides_08_09.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

W, H = 1920, 1080
G = HexColor("#1DB954")
BG = HexColor("#080808")
CARD = HexColor("#111111")
CARD2 = HexColor("#181818")
BORDER = HexColor("#222222")
WHITE = HexColor("#FFFFFF")
W70 = HexColor("#b3b3b3")
W60 = HexColor("#999999")
W40 = HexColor("#666666")
W30 = HexColor("#4a4a4a")
BLUE = HexColor("#4fc3f7")
ORANGE = HexColor("#ff7043")
PURPLE = HexColor("#a855f7")
YELLOW = HexColor("#facc15")
NSGREEN = HexColor("#0c1a0e")
TAKE = HexColor("#101a10")


def rrect(c, x, top, w, h, rad, fill=None, border=None, alpha=1.0, bw=1):
    y0 = H - top - h
    if fill is not None:
        c.setFillColor(fill); c.setFillAlpha(alpha)
        c.roundRect(x, y0, w, h, rad, fill=1, stroke=0); c.setFillAlpha(1)
    if border is not None:
        c.setStrokeColor(border); c.setStrokeAlpha(alpha if fill is None else 1)
        c.setLineWidth(bw); c.roundRect(x, y0, w, h, rad, fill=0, stroke=1)
        c.setStrokeAlpha(1)


def txt(c, x, top, s, size, color, bold=False, center=False, right=False,
        oblique=False, alpha=1.0):
    c.setFillColor(color); c.setFillAlpha(alpha)
    font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if oblique else "Helvetica")
    c.setFont(font, size)
    y = H - top
    if center:
        c.drawCentredString(x, y, s)
    elif right:
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)
    c.setFillAlpha(1)


def spans(c, x, top, parts, size, bold=False):
    cx = x
    for s, col, *rest in parts:
        ob = bool(rest and rest[0])
        txt(c, cx, top, s, size, col, bold=bold, oblique=ob)
        font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if ob else "Helvetica")
        cx += c.stringWidth(s, font, size)


def pill(c, x, top, s, size, fg, bgcol, alpha=0.15, border=None, h=30, padx=14):
    w = c.stringWidth(s, "Helvetica-Bold", size) + padx * 2
    rrect(c, x, top, w, h, h / 2, fill=bgcol, alpha=alpha, border=border)
    txt(c, x + padx, top + h - (h - size) / 2 - size * 0.16, s, size, fg, bold=True)
    return w


def disc(c, cx, cy_top, r, fill=None, border=None, bw=2, alpha=1.0):
    cy = H - cy_top
    if fill is not None:
        c.setFillColor(fill); c.setFillAlpha(alpha)
        c.circle(cx, cy, r, fill=1, stroke=0); c.setFillAlpha(1)
    if border is not None:
        c.setStrokeColor(border); c.setLineWidth(bw); c.circle(cx, cy, r, fill=0, stroke=1)


def badge_label(c, x, top, s):
    txt(c, x, top, s, 13, G, bold=True)


# --------------------------------------------------------------------------- #
# Slide 08 — KPI tree
# --------------------------------------------------------------------------- #
def slide8(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

    # Header
    pill(c, 70, 50, "SLIDE 08  ·  METRICS FRAMEWORK", 14, G, G, alpha=0.15, border=G, h=32)
    spans(c, 70, 124, [("Success will be measured by ", WHITE),
                       ("Meaningful Discovery Rate", G), (",", WHITE)], 40, bold=True)
    txt(c, 70, 172, "not just number of songs played", 40, WHITE, bold=True)
    txt(c, 1850, 78, "SPOTIFY", 15, W60, bold=True, right=True, alpha=0.45)

    # North Star card
    rrect(c, 70, 200, 1780, 150, 22, fill=NSGREEN, border=G, alpha=1, bw=1)
    rrect(c, 70, 200, 1780, 150, 22, border=G, bw=1)
    disc(c, 129, 275, 30, fill=G, border=None)
    disc(c, 129, 275, 14, fill=NSGREEN)
    txt(c, 185, 238, "NORTH STAR METRIC", 13, G, bold=True)
    txt(c, 185, 282, "Meaningful Discovery Rate", 32, WHITE, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.25); c.setLineWidth(1)
    c.line(595, H - 222, 595, H - 332); c.setStrokeAlpha(1)
    txt(c, 625, 238, "FORMULA", 12, W30, bold=True)
    spans(c, 625, 282, [("New tracks w/ positive actions", G), ("   ÷   ", W30),
                        ("Total discovery tracks played", W60)], 19, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.25); c.setLineWidth(1)
    c.line(1255, H - 222, 1255, H - 332); c.setStrokeAlpha(1)
    txt(c, 1285, 238, "WHY IT MATTERS", 12, W30, bold=True)
    txt(c, 1285, 278, "Measures whether discovery actually creates useful", 20, W60)
    txt(c, 1285, 308, "new listening — not just more plays.", 20, W60)

    # KPI tree columns
    ctop, ch = 374, 466
    cw = 501
    x1 = 70
    xmdr = x1 + cw + 68
    x2 = xmdr + 88 + 68
    xshield = x2 + cw
    x3 = xshield + 52

    def colcard(x, accent, title, purpose, badge, metrics):
        rrect(c, x, ctop, cw, ch, 22, fill=CARD, border=BORDER)
        rrect(c, x + 24, ctop, cw - 48, 4, 2, fill=accent)
        rrect(c, x + 26, ctop + 24, 48, 48, 12, fill=accent, alpha=0.10, border=accent)
        txt(c, x + 88, ctop + 56, title, 26, WHITE, bold=True)
        txt(c, x + 88, ctop + 82, purpose, 17, W60)
        pill(c, x + 26, ctop + 100, badge, 13, accent, accent, alpha=0.12, border=accent, h=28)
        ry = ctop + 150
        for m in metrics:
            rrect(c, x + 26, ry, cw - 52, 56, 12, fill=CARD2, border=BORDER)
            disc(c, x + 50, ry + 28, 6, fill=accent)
            txt(c, x + 72, ry + 36, m, 24, WHITE)
            ry += 66

    colcard(x1, BLUE, "Input Metrics", "Are users trying the feature?", "INPUTS",
            ["Feature starts", "User prompts entered", "Freshness slider usage",
             "Mood / activity selections"])
    colcard(x2, G, "Output Metrics", "Are users finding value?", "OUTPUTS",
            ["Save rate", "Replay within 7 days", "Playlist add rate",
             "Artist follow rate"])
    colcard(x3, ORANGE, "Guardrail Metrics", "Avoiding bad discovery?", "SAFETY CHECK",
            ["Skip rate under 30 sec", "Session abandonment",
             "User satisfaction score", "Repetition complaints"])

    # Connectors
    def connector(cx, label):
        c.setStrokeColor(G); c.setLineWidth(2)
        c.line(cx - 17, H - (ctop + ch / 2), cx + 13, H - (ctop + ch / 2))
        txt(c, cx + 17, ctop + ch / 2 + 5, ">", 22, G, bold=True)
        txt(c, cx, ctop + ch / 2 + 34, label, 12, W30, bold=True, center=True)

    connector(x1 + cw + 34, "DRIVES")
    connector(xmdr + 88 + 34, "YIELDS")

    # MDR node
    mcx = xmdr + 44
    disc(c, mcx, ctop + ch / 2, 40, fill=G, border=G, bw=2)
    disc(c, mcx, ctop + ch / 2, 20, fill=BG)
    txt(c, mcx, ctop + ch / 2 + 90, "MDR", 14, G, bold=True, center=True)

    # Shield connector
    scx = xshield + 26
    rrect(c, scx - 18, ctop + ch / 2 - 18, 36, 36, 9, fill=ORANGE, alpha=0.16, border=ORANGE)
    txt(c, scx, ctop + ch / 2 + 50, "SAFETY", 12, ORANGE, bold=True, center=True, alpha=0.8)

    # Takeaway bar
    rrect(c, 70, 880, 1780, 80, 16, fill=TAKE, border=G, alpha=1)
    rrect(c, 70, 880, 1780, 80, 16, border=G, bw=1)
    disc(c, 105, 920, 19, fill=G, border=G); disc(c, 105, 920, 8, fill=BG)
    txt(c, 138, 928, "KEY TAKEAWAY", 13, G, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.3); c.setLineWidth(1)
    c.line(290, H - 902, 290, H - 938); c.setStrokeAlpha(1)
    spans(c, 312, 929, [("Success is not ", WHITE), ("“more songs played”", W60, True),
                        (" — success is users discovering music they ", WHITE),
                        ("save, replay, and trust.", G)], 25, bold=False)


# --------------------------------------------------------------------------- #
# Slide 09 — FreshMix AI product feature
# --------------------------------------------------------------------------- #
def slide9(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

    pill(c, 70, 50, "SLIDE 09  ·  PRODUCT FEATURE", 14, G, G, alpha=0.15, border=G, h=32)
    spans(c, 70, 124, [("FreshMix AI", G),
                       (" helps users discover new music through", WHITE)], 38, bold=True)
    txt(c, 70, 170, "mood, activity, and freshness control", 38, WHITE, bold=True)
    txt(c, 1850, 78, "SPOTIFY", 15, W40, bold=True, right=True, alpha=0.45)

    btop, bh = 360, 600
    xL, wL = 70, 360
    xM = xL + wL + 28
    wR = 440
    xR = 1850 - wR
    wM = xR - 28 - xM

    # LEFT — MVP flow
    rrect(c, xL, btop, wL, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xL + 20, btop, wL - 40, 4, 2, fill=G)
    txt(c, xL + 24, btop + 38, "MVP FLOW", 13, G, bold=True)
    steps = [(1, "User opens FreshMix AI", None),
             (2, "Selects mood, activity & language", None),
             (3, "Adjusts freshness level", "Familiar  <->  Fresh slider"),
             (4, "AI generates fresh-but-familiar queue", None),
             (5, "Saves, skips, or refreshes songs", "Feedback improves future mixes")]
    sy = btop + 80
    for num, label, sub in steps:
        disc(c, xL + 24 + 19, sy + 19, 19, fill=G, alpha=0.12, border=G)
        txt(c, xL + 24 + 19, sy + 27, str(num), 16, G, bold=True, center=True)
        _wrap(c, label, xL + 70, sy + 22, wL - 96, 22, bold=True, lead=26, color=WHITE)
        if sub:
            txt(c, xL + 70, sy + 52, sub, 16, W40)
        if num != 5:
            c.setStrokeColor(W30); c.setLineWidth(2)
            c.line(xL + 24 + 19, H - (sy + 44), xL + 24 + 19, H - (sy + 70))
        sy += 96

    # MIDDLE — phone wireframe
    rrect(c, xM, btop, wM, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xM + 20, btop, wM - 40, 4, 2, fill=PURPLE)
    txt(c, xM + 26, btop + 38, "FEATURE WIREFRAME", 13, PURPLE, bold=True)
    phone(c, xM + wM / 2 - 165, btop + 64, 330)
    # prompt examples
    py = btop + bh - 70
    ex = ['"Give me fresh Hindi indie songs for late-night work."',
          '"Refresh my gym playlist with 60% new songs."']
    ew = (wM - 52 - 16) / 2
    for i, e in enumerate(ex):
        ex_x = xM + 26 + i * (ew + 16)
        rrect(c, ex_x, py, ew, 54, 27, fill=CARD2, border=BORDER)
        _wrap(c, e, ex_x + 20, py + 22, ew - 36, 16, bold=False, lead=19, color=W70, oblique=True)

    # RIGHT — why AI
    rrect(c, xR, btop, wR, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xR + 20, btop, wR - 40, 4, 2, fill=YELLOW)
    txt(c, xR + 24, btop + 38, "WHY AI IS NEEDED", 13, YELLOW, bold=True)
    cards = [(BLUE, "Understands natural language", '"like this playlist, but less repetitive"'),
             (G, "Reads real-time context", "Mood, activity, language, and moment"),
             (PURPLE, "Balances familiar + fresh", "Avoids songs that feel too random"),
             (YELLOW, "Learns from feedback", "Uses saves, skips, replays to improve")]
    iy = btop + 64
    ih = 116
    for accent, title, ex in cards:
        rrect(c, xR + 24, iy, wR - 48, ih, 16, fill=CARD, border=BORDER)
        rrect(c, xR + 24, iy + 16, 4, ih - 32, 2, fill=accent)
        rrect(c, xR + 42, iy + 22, 40, 40, 10, fill=accent, alpha=0.16, border=accent)
        txt(c, xR + 98, iy + 44, title, 23, WHITE, bold=True)
        _wrap(c, ex, xR + 98, iy + 74, wR - 140, 18, bold=False, lead=24, color=W40, oblique=True)
        iy += ih + 12

    # Takeaway
    rrect(c, 70, 982, 1780, 74, 16, fill=TAKE, border=G)
    rrect(c, 90, 1002, 36, 36, 10, fill=G, alpha=0.16, border=G)
    txt(c, 138, 1027, "KEY TAKEAWAY", 13, G, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.3); c.setLineWidth(1)
    c.line(290, H - 1002, 290, H - 1038); c.setStrokeAlpha(1)
    spans(c, 312, 1028, [("AI turns discovery from ", WHITE),
                         ("passive recommendations", W40, True),
                         (" into an ", WHITE),
                         ("interactive music guide.", G)], 25, bold=False)


def phone(c, x, top, w):
    ph = 452
    rrect(c, x, top, w, ph, 32, fill=HexColor("#0d0d0d"), border=HexColor("#2a2a2a"), bw=2)
    rrect(c, x + w / 2 - 40, top + 11, 80, 14, 7, fill=HexColor("#111111"))
    # header
    rrect(c, x + 18, top + 40, 28, 28, 8, fill=G)
    txt(c, x + 54, top + 60, "FreshMix AI", 15, WHITE, bold=True)
    # prompt
    rrect(c, x + 14, top + 84, w - 28, 40, 10, fill=HexColor("#1a1a1a"), border=HexColor("#2a2a2a"))
    txt(c, x + 26, top + 109, '"Refresh my playlist, keep the vibe"', 12, W40)
    # mood
    txt(c, x + 16, top + 146, "MOOD", 10, W40, bold=True)
    chips(c, x + 14, top + 154, ["Focus", "Gym", "Chill", "Travel"], 0)
    # activity
    txt(c, x + 16, top + 196, "ACTIVITY", 10, W40, bold=True)
    chips(c, x + 14, top + 204, ["Work", "Commute", "Workout"], 0)
    # freshness
    txt(c, x + 16, top + 246, "FRESHNESS  —  70% FRESH", 10, G, bold=True)
    rrect(c, x + 14, top + 256, w - 28, 6, 3, fill=HexColor("#2a2a2a"))
    rrect(c, x + 14, top + 256, (w - 28) * 0.7, 6, 3, fill=G)
    disc(c, x + 14 + (w - 28) * 0.7, top + 259, 7, fill=G, border=WHITE, bw=2)
    # generate
    rrect(c, x + 14, top + 280, w - 28, 36, 9, fill=G)
    txt(c, x + w / 2, top + 304, "Generate FreshMix", 14, HexColor("#000000"), bold=True, center=True)
    # song cards
    for i, (t, a) in enumerate([("New Discovery #1", "Indie Artist · 2024"),
                                ("New Discovery #2", "Electronic · Trending")]):
        cy = top + 330 + i * 72
        rrect(c, x + 14, cy, w - 28, 64, 10, fill=HexColor("#1a1a1a"), border=HexColor("#252525"))
        rrect(c, x + 26, cy + 12, 30, 30, 7, fill=G, alpha=0.25, border=G)
        txt(c, x + 66, cy + 24, t, 13, WHITE, bold=True)
        txt(c, x + 66, cy + 40, a, 11, W40)
        for j, lbl in enumerate(["Save", "Skip", "Refresh"]):
            bw_ = (w - 52 - 12) / 3
            bx = x + 26 + j * (bw_ + 6)
            rrect(c, bx, cy + 46, bw_, 14, 4, fill=HexColor("#252525"), border=HexColor("#333333"))
            txt(c, bx + bw_ / 2, cy + 56, lbl, 9, W70, bold=True, center=True)


def chips(c, x, top, labels, active_idx):
    cx = x
    for i, lbl in enumerate(labels):
        w = c.stringWidth(lbl, "Helvetica-Bold", 12) + 22
        act = i == 0
        rrect(c, cx, top, w, 24, 12, fill=(G if act else HexColor("#1a1a1a")),
              alpha=(0.22 if act else 1), border=(G if act else HexColor("#2a2a2a")))
        txt(c, cx + 11, top + 17, lbl, 12, (G if act else W70), bold=act)
        cx += w + 6


def _wrap(c, s, x, top, max_w, size, bold=False, lead=22, color=W40, oblique=False):
    font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if oblique else "Helvetica")
    words, line, cy = s.split(), "", top
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, font, size) > max_w:
            txt(c, x, cy, line, size, color, bold=bold, oblique=oblique)
            line, cy = w, cy + lead
        else:
            line = trial
    if line:
        txt(c, x, cy, line, size, color, bold=bold, oblique=oblique)


def main():
    out = Path("slides"); out.mkdir(exist_ok=True)
    path = out / "Slides_08_09.pdf"
    c = canvas.Canvas(str(path), pagesize=(W, H))
    slide8(c); c.showPage()
    slide9(c); c.showPage()
    c.save()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
