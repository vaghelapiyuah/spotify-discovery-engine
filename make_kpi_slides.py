"""Render Slide 08 (KPI tree / metrics framework) and Slide 09 (FreshMix AI
product feature) as a 1920x1080 PDF. Spotify dark theme, every text >= 26px,
no source link, no names.

Run:  python make_kpi_slides.py  ->  slides/Slides_08_09.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

W, H = 1920, 1080
G = HexColor("#1DB954")
BG = HexColor("#080808")
CARD = HexColor("#121212")
CARD2 = HexColor("#1a1a1a")
BORDER = HexColor("#262626")
WHITE = HexColor("#FFFFFF")
W70 = HexColor("#b3b3b3")
W50 = HexColor("#8a8a8a")
BLUE = HexColor("#4fc3f7")
ORANGE = HexColor("#ff7043")
PURPLE = HexColor("#a855f7")
YELLOW = HexColor("#facc15")
NSGREEN = HexColor("#0c1a0e")
TAKE = HexColor("#101a10")
BLACK = HexColor("#000000")
PHONE = HexColor("#0d0d0d")


def rrect(c, x, top, w, h, rad, fill=None, border=None, alpha=1.0, bw=1):
    y0 = H - top - h
    if fill is not None:
        c.setFillColor(fill); c.setFillAlpha(alpha)
        c.roundRect(x, y0, w, h, rad, fill=1, stroke=0); c.setFillAlpha(1)
    if border is not None:
        c.setStrokeColor(border); c.setLineWidth(bw)
        c.roundRect(x, y0, w, h, rad, fill=0, stroke=1)


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


def pill(c, x, top, s, size, fg, bgcol, alpha=0.16, border=None, h=46, padx=18, bold=True):
    w = c.stringWidth(s, "Helvetica-Bold" if bold else "Helvetica", size) + padx * 2
    rrect(c, x, top, w, h, h / 2, fill=bgcol, alpha=alpha, border=border)
    txt(c, x + padx, top + (h + size) / 2 - size * 0.30, s, size, fg, bold=bold)
    return w


def disc(c, cx, cy_top, r, fill=None, border=None, bw=2, alpha=1.0):
    cy = H - cy_top
    if fill is not None:
        c.setFillColor(fill); c.setFillAlpha(alpha)
        c.circle(cx, cy, r, fill=1, stroke=0); c.setFillAlpha(1)
    if border is not None:
        c.setStrokeColor(border); c.setLineWidth(bw); c.circle(cx, cy, r, fill=0, stroke=1)


def wrap(c, s, x, top, max_w, size, color, bold=False, lead=34, oblique=False, max_lines=99):
    font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if oblique else "Helvetica")
    words, line, cy, n = s.split(), "", top, 0
    for w_ in words:
        trial = (line + " " + w_).strip()
        if c.stringWidth(trial, font, size) > max_w and line:
            txt(c, x, cy, line, size, color, bold=bold, oblique=oblique)
            line, cy, n = w_, cy + lead, n + 1
            if n >= max_lines:
                line = ""
                break
        else:
            line = trial
    if line:
        txt(c, x, cy, line, size, color, bold=bold, oblique=oblique)
    return cy


def arrow_h(c, x1, x2, ytop, color):
    y = H - ytop
    c.setStrokeColor(color); c.setLineWidth(3)
    c.line(x1, y, x2 - 10, y)
    p = c.beginPath(); p.moveTo(x2 - 14, y + 8); p.lineTo(x2, y); p.lineTo(x2 - 14, y - 8)
    p.close(); c.setFillColor(color); c.drawPath(p, fill=1, stroke=0)


# --------------------------------------------------------------------------- #
# Slide 08
# --------------------------------------------------------------------------- #
def slide8(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

    pill(c, 70, 46, "SLIDE 08", 28, G, G, alpha=0.16, border=G, h=52)
    spans(c, 70, 150, [("Success will be measured by ", WHITE),
                       ("Meaningful Discovery Rate", G), (",", WHITE)], 46, bold=True)
    txt(c, 70, 206, "not just number of songs played", 46, WHITE, bold=True)

    # North Star card
    rrect(c, 70, 250, 1780, 232, 24, fill=NSGREEN, border=G, bw=2)
    disc(c, 132, 366, 36, fill=G); disc(c, 132, 366, 15, fill=NSGREEN)
    txt(c, 192, 326, "NORTH STAR METRIC", 28, G, bold=True)
    txt(c, 192, 388, "Meaningful Discovery Rate", 44, WHITE, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.3); c.setLineWidth(1)
    c.line(900, H - 285, 900, H - 447); c.setStrokeAlpha(1)
    txt(c, 940, 322, "FORMULA", 28, W50, bold=True)
    spans(c, 940, 372, [("New tracks w/ positive actions", G), ("  ÷  ", W50),
                        ("Total discovery plays", W70)], 30, bold=True)
    txt(c, 940, 430, "Does discovery create useful new listening — not just more plays?",
        27, W70)

    # KPI tree
    ctop, ch = 520, 392
    cw = 505
    x1 = 70
    xmdr = x1 + cw + 56
    x2 = xmdr + 96 + 56
    xshield = x2 + cw
    x3 = xshield + 56

    def colcard(x, accent, title, purpose, metrics):
        rrect(c, x, ctop, cw, ch, 22, fill=CARD, border=BORDER)
        rrect(c, x + 26, ctop, cw - 52, 4, 2, fill=accent)
        rrect(c, x + 28, ctop + 26, 46, 46, 12, fill=accent, alpha=0.14, border=accent)
        disc(c, x + 51, ctop + 49, 7, fill=accent)
        txt(c, x + 90, ctop + 56, title, 30, WHITE, bold=True)
        txt(c, x + 28, ctop + 104, purpose, 26, accent)
        ry = ctop + 132
        for m in metrics:
            rrect(c, x + 26, ry, cw - 52, 56, 12, fill=CARD2, border=BORDER)
            disc(c, x + 50, ry + 28, 6, fill=accent)
            txt(c, x + 72, ry + 37, m, 26, WHITE)
            ry += 64

    colcard(x1, BLUE, "Input Metrics", "Are users trying the feature?",
            ["Feature starts", "User prompts entered", "Freshness slider usage",
             "Mood / activity selections"])
    colcard(x2, G, "Output Metrics", "Are users finding value?",
            ["Save rate", "Replay within 7 days", "Playlist add rate",
             "Artist follow rate"])
    colcard(x3, ORANGE, "Guardrail Metrics", "Avoiding bad discovery?",
            ["Skip rate under 30 sec", "Session abandonment",
             "User satisfaction", "Repetition complaints"])

    mid = ctop + ch / 2
    arrow_h(c, x1 + cw + 6, xmdr - 6, mid, G)
    arrow_h(c, xmdr + 96 + 6, x2 - 6, mid, G)
    disc(c, xmdr + 48, mid, 46, fill=G, alpha=0.16, border=G, bw=3)
    disc(c, xmdr + 48, mid, 20, fill=BG)
    txt(c, xmdr + 48, mid + 96, "NORTH STAR", 26, G, bold=True, center=True)
    # guardrail safety link
    c.setStrokeColor(ORANGE); c.setLineWidth(3)
    c.line(x2 + cw + 6, H - mid, x3 - 6, H - mid)
    rrect(c, xshield + 8, mid - 20, 40, 40, 10, fill=ORANGE, alpha=0.18, border=ORANGE)

    # Takeaway
    rrect(c, 70, 950, 1780, 88, 16, fill=TAKE, border=G, bw=2)
    rrect(c, 92, 974, 40, 40, 10, fill=G, alpha=0.18, border=G)
    txt(c, 150, 1002, "KEY TAKEAWAY", 26, G, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.35); c.setLineWidth(1)
    c.line(330, H - 968, 330, H - 1020); c.setStrokeAlpha(1)
    spans(c, 352, 1004, [("Success is not ", WHITE), ("“more songs played”", W50, True),
                         (" — it's users discovering music they ", WHITE),
                         ("save, replay, and trust.", G)], 28, bold=False)


# --------------------------------------------------------------------------- #
# Slide 09
# --------------------------------------------------------------------------- #
def slide9(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

    pill(c, 70, 46, "SLIDE 09", 28, G, G, alpha=0.16, border=G, h=52)
    spans(c, 70, 150, [("FreshMix AI", G),
                       (" helps users discover new music through", WHITE)], 44, bold=True)
    txt(c, 70, 204, "mood, activity, and freshness control", 44, WHITE, bold=True)

    btop, bh = 220, 660
    xL, wL = 70, 384
    xM = xL + wL + 30
    wR = 472
    xR = 1850 - wR
    wM = xR - 30 - xM

    # LEFT — MVP flow
    rrect(c, xL, btop, wL, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xL + 22, btop, wL - 44, 4, 2, fill=G)
    txt(c, xL + 26, btop + 48, "MVP FLOW", 26, G, bold=True)
    steps = [("User opens FreshMix AI", None),
             ("Selects mood, activity & language", None),
             ("Adjusts freshness level", "Familiar  ->  Fresh slider"),
             ("AI generates a fresh-but-familiar queue", None),
             ("Saves, skips, or refreshes songs", "Feedback improves mixes")]
    sy = btop + 96
    step_gap = 104
    for i, (label, sub) in enumerate(steps):
        ccx = xL + 26 + 24
        disc(c, ccx, sy + 24, 24, fill=G, alpha=0.14, border=G)
        txt(c, ccx, sy + 33, str(i + 1), 28, G, bold=True, center=True)
        endy = wrap(c, label, xL + 78, sy + 30, wL - 104, 26, WHITE, bold=True, lead=32)
        if sub:
            txt(c, xL + 78, endy + 32, sub, 26, W50)
        if i < len(steps) - 1:
            c.setStrokeColor(BORDER); c.setLineWidth(3)
            c.line(ccx, H - (sy + 50), ccx, H - (sy + step_gap - 6))
        sy += step_gap

    # MIDDLE — phone
    rrect(c, xM, btop, wM, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xM + 22, btop, wM - 44, 4, 2, fill=PURPLE)
    txt(c, xM + 26, btop + 48, "FEATURE WIREFRAME", 26, PURPLE, bold=True)
    phone(c, xM + (wM - 520) / 2, btop + 70, 520)

    # RIGHT — why AI
    rrect(c, xR, btop, wR, bh, 22, fill=CARD, border=BORDER)
    rrect(c, xR + 22, btop, wR - 44, 4, 2, fill=YELLOW)
    txt(c, xR + 26, btop + 48, "WHY AI IS NEEDED", 26, YELLOW, bold=True)
    cards = [(BLUE, "Understands natural language", '"like this, but less repetitive"'),
             (G, "Reads real-time context", "Mood, activity, language, moment"),
             (PURPLE, "Balances familiar + fresh", "Avoids songs that feel random"),
             (YELLOW, "Learns from feedback", "Saves, skips, replays improve it")]
    iy = btop + 78
    ih = 126
    for accent, title, ex in cards:
        rrect(c, xR + 26, iy, wR - 52, ih, 16, fill=CARD2, border=BORDER)
        rrect(c, xR + 26, iy + 18, 5, ih - 36, 2, fill=accent)
        rrect(c, xR + 46, iy + 24, 46, 46, 11, fill=accent, alpha=0.16, border=accent)
        disc(c, xR + 69, iy + 47, 7, fill=accent)
        txt(c, xR + 108, iy + 50, title, 27, WHITE, bold=True)
        txt(c, xR + 108, iy + 90, ex, 26, W50, oblique=True)
        iy += ih + 8

    # Bottom prompt example pills
    pw = (1780 - 30) / 2
    for i, p in enumerate(['"Give me fresh Hindi indie songs for late-night work."',
                           '"Refresh my gym playlist with 60% new songs."']):
        px = 70 + i * (pw + 30)
        rrect(c, px, 896, pw, 60, 30, fill=CARD2, border=BORDER)
        disc(c, px + 36, 926, 8, fill=G)
        txt(c, px + 60, 935, p, 26, W70, oblique=True)

    # Takeaway
    rrect(c, 70, 972, 1780, 84, 16, fill=TAKE, border=G, bw=2)
    rrect(c, 92, 994, 40, 40, 10, fill=G, alpha=0.18, border=G)
    txt(c, 150, 1022, "KEY TAKEAWAY", 26, G, bold=True)
    c.setStrokeColor(G); c.setStrokeAlpha(0.35); c.setLineWidth(1)
    c.line(330, H - 988, 330, H - 1040); c.setStrokeAlpha(1)
    spans(c, 352, 1024, [("AI turns discovery from ", WHITE),
                         ("passive recommendations", W50, True),
                         (" into an ", WHITE),
                         ("interactive music guide.", G)], 28, bold=False)


def chips(c, x, top, labels):
    cx = x
    for i, lbl in enumerate(labels):
        act = i == 0
        w = c.stringWidth(lbl, "Helvetica-Bold", 26) + 30
        rrect(c, cx, top, w, 44, 22, fill=(G if act else CARD2),
              alpha=(0.22 if act else 1), border=(G if act else BORDER))
        txt(c, cx + 15, top + 31, lbl, 26, (G if act else W70), bold=act)
        cx += w + 10


def phone(c, x, top, w):
    ph = 590
    inner = w - 44
    rrect(c, x, top, w, ph, 34, fill=PHONE, border=HexColor("#2a2a2a"), bw=2)
    rrect(c, x + w / 2 - 46, top + 14, 92, 14, 7, fill=HexColor("#1a1a1a"))
    # header
    rrect(c, x + 22, top + 40, 40, 40, 10, fill=G)
    txt(c, x + 74, top + 68, "FreshMix AI", 28, WHITE, bold=True)
    # prompt
    rrect(c, x + 22, top + 92, inner, 56, 12, fill=CARD2, border=HexColor("#2a2a2a"))
    txt(c, x + 38, top + 127, '"Refresh my playlist, keep the vibe"', 26, W70)
    # mood
    txt(c, x + 24, top + 178, "MOOD", 26, W50, bold=True)
    chips(c, x + 22, top + 190, ["Focus", "Gym", "Chill"])
    # activity
    txt(c, x + 24, top + 258, "ACTIVITY", 26, W50, bold=True)
    chips(c, x + 22, top + 270, ["Work", "Commute"])
    # freshness
    txt(c, x + 24, top + 340, "FRESHNESS", 26, W50, bold=True)
    txt(c, x + w - 22, top + 340, "Fresh 70%", 26, G, bold=True, right=True)
    rrect(c, x + 22, top + 356, inner, 10, 5, fill=HexColor("#2a2a2a"))
    rrect(c, x + 22, top + 356, inner * 0.7, 10, 5, fill=G)
    disc(c, x + 22 + inner * 0.7, top + 361, 11, fill=G, border=WHITE, bw=3)
    # generate
    rrect(c, x + 22, top + 384, inner, 50, 12, fill=G)
    txt(c, x + w / 2, top + 418, "Generate FreshMix", 28, BLACK, bold=True, center=True)
    # song card (name / why / actions)
    cy = top + 448
    rrect(c, x + 22, cy, inner, 130, 14, fill=CARD2, border=HexColor("#262626"))
    rrect(c, x + 38, cy + 16, 40, 40, 9, fill=G, alpha=0.25, border=G)
    txt(c, x + 90, cy + 44, "New Discovery", 26, WHITE, bold=True)
    txt(c, x + 38, cy + 80, "Why? similar mood + new artist", 26, G)
    bwid = (inner - 32 - 24) / 3
    for i, lbl in enumerate(["Save", "Skip", "Refresh"]):
        bx = x + 38 + i * (bwid + 12)
        rrect(c, bx, cy + 88, bwid, 36, 8, fill=HexColor("#252525"), border=HexColor("#333333"))
        txt(c, bx + bwid / 2, cy + 113, lbl, 26, W70, bold=True, center=True)


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
