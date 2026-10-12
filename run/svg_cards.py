"""Render the transparent-theme profile SVG cards.

Both cards use the github-profile-summary-cards "transparent" palette
(title #006AFF / text #417E87): no background, no border. Layouts are adapted
from ggbdpq/svg_cards.py — languages keeps only the language bar, stats keeps
only the left stat rows and the right rank donut.
"""
from html import escape

from language_colors import LANGUAGE_COLORS

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

THEME = {"title": "#006AFF", "text": "#417E87", "icon": "#0579C3"}
OTHER_COLOR = "#8b97a8"

RANKS = [(100, "S"), (50, "A"), (20, "B"), (5, "C"), (1, "D"), (0, "E")]


def lang_color(name):
    return LANGUAGE_COLORS.get(name.lower(), OTHER_COLOR)


def svg(width, height, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">\n{body}\n</svg>\n')


def text_width(text, size):
    """Rough sans-stack advance width so the legend can wrap instead of overflowing."""
    units = 0.0
    for ch in text:
        if ch == " ":
            units += 0.3
        elif ch in "%@MWF":
            units += 0.85
        elif ch in ".,:;'!|":
            units += 0.3
        elif ch.isdigit() or ch.isupper():
            units += 0.62
        else:
            units += 0.55
    return units * size


def languages_card(t, data):
    """The language bar: one segmented bar plus a wrappable color legend."""
    w = 880
    bar_x, bar_w, bar_y, bar_h = 32, w - 64, 54, 12

    segments = []
    x = bar_x
    for name, pct in data["languages"]:
        seg = bar_w * pct / 100
        segments.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{seg + 0.5:.1f}" height="{bar_h}" '
                        f'fill="{lang_color(name)}"/>')
        x += seg

    legend_rows, row, cx = [[]], 0, bar_x
    for name, pct in data["languages"]:
        text = f"{name} {pct:g}%"
        item_w = 13 + text_width(text, 12.5) + 28
        if cx + item_w > w - bar_x and cx > bar_x:
            legend_rows.append([])
            row += 1
            cx = bar_x
        legend_rows[row].append((cx, text, lang_color(name)))
        cx += item_w

    first_baseline = bar_y + bar_h + 28
    legend = []
    for r, items in enumerate(legend_rows):
        for cx, text, color in items:
            cy = first_baseline + r * 24
            legend.append(f'<circle cx="{cx + 4:.1f}" cy="{cy - 4:.1f}" r="4" fill="{color}"/>'
                          f'<text x="{cx + 13:.1f}" y="{cy:.1f}" font-family="{FONT}" font-size="12.5" '
                          f'fill="{t["text"]}">{escape(text)}</text>')
    h = first_baseline + (len(legend_rows) - 1) * 24 + 14

    body = "\n".join([
        f'<text x="32" y="38" font-family="{MONO}" font-size="12" letter-spacing="1.5" '
        f'fill="{t["title"]}">LANGUAGES</text>',
        f'<text x="{w - 32}" y="38" text-anchor="end" font-family="{FONT}" font-size="11" '
        f'fill="{t["text"]}" fill-opacity="0.8">by code size across my repositories and organizations</text>',
        f'<clipPath id="langbar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6"/></clipPath>',
        '<g clip-path="url(#langbar)">',
        *segments,
        "</g>",
        *legend,
    ])
    label = "Language distribution by code size: " + ", ".join(
        f"{name} {pct:g}%" for name, pct in data["languages"])
    return svg(w, h, body, label)


def stats_card(t, data):
    """Left stat rows + right rank donut, transparent theme, no other decoration."""
    patches = dict(data.get("patches_by_repo") or [])
    rows = [("⭐", "Total Stars Earned", data.get("stars", 0)),
            ("🕘", "Total Contributions (last year)", data["contributions"]),
            ("💻", "Total Commits (last year)", data["commits"]),
            ("📫", "Merged Pull Requests", data["merged_prs"])]
    if patches:
        rows.append(("🩹", "Upstream Patch Commits", sum(patches.values())))
    rows.append(("📚", "Contributed to (last year)", data.get("contributed_to", 0)))
    score = data["merged_prs"] + sum(patches.values())
    rank, floor = next((letter, threshold) for threshold, letter in RANKS if score >= threshold)
    ceiling = next((threshold for threshold, _ in RANKS if threshold > floor), floor + 1)
    pct = min((score - floor) / (ceiling - floor), 1)

    w = 880
    h = max(272, 82 + len(rows) * 27 + 26)
    divider_y2 = h - 32
    parts = [f'<text x="202" y="44" text-anchor="middle" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1.5" fill="{t["title"]}">GITHUB STATS</text>']
    for i, (icon, label, value) in enumerate(rows):
        y = 82 + i * 27
        parts.append(f'<text x="64" y="{y}" font-size="14">{icon}</text>'
                     f'<text x="92" y="{y}" font-family="{FONT}" font-size="12.5" fill="{t["text"]}" '
                     f'fill-opacity="0.85">{escape(label)}</text>'
                     f'<text x="344" y="{y}" text-anchor="end" font-family="{FONT}" font-size="14" '
                     f'font-weight="700" fill="{t["text"]}">{value}</text>')
    parts.append(f'<line x1="372" y1="70" x2="372" y2="{divider_y2}" stroke="{t["text"]}" stroke-opacity="0.3"/>')

    cx, cy, r = 614, (70 + divider_y2) / 2, 52
    circ = 2 * 3.14159 * r
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["text"]}" '
                 f'stroke-opacity="0.25" stroke-width="11"/>'
                 f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["title"]}" stroke-width="11" '
                 f'stroke-linecap="round" stroke-dasharray="{pct * circ:.1f} {circ:.1f}" '
                 f'transform="rotate(-90 {cx} {cy})"/>'
                 f'<text x="{cx}" y="{cy + 15}" text-anchor="middle" font-family="{FONT}" font-size="42" '
                 f'font-weight="700" fill="{t["text"]}">{rank}</text>'
                 f'<text x="{cx}" y="{cy + r + 30}" text-anchor="middle" font-family="{MONO}" font-size="11.5" '
                 f'fill="{t["text"]}" fill-opacity="0.85">rank {rank} · {score} pts</text>')
    label = ("GitHub stats: " + ", ".join(f"{name.lower()} {value}" for _, name, value in rows)
             + f"; rank {rank} {score} pts")
    return svg(w, h, "\n".join(parts), label)
