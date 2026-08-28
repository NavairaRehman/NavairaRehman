#!/usr/bin/env python3
"""
Generates a neofetch-style terminal card for a GitHub profile README:
ASCII-art avatar on the left, dotted key/value stats on the right.
Pulls live data from the GitHub REST API.

Uses explicit textLength on every line so column alignment stays exact
regardless of which monospace font the renderer substitutes.

Usage:
    python3 generate_svg.py <username> <output_path>
"""

import sys
import os
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image

# ---- theme -----------------------------------------------------------
BG = "#0d1117"
BORDER = "#30363d"
LABEL = "#c9d1d9"
VALUE = "#a58cff"
HEADER = "#8f7cff"
DOT = "#484f58"
TITLE_DOT = "#6e7681"
ASCII_FILL = "#8f7cff"

# ---- static config: things that aren't in the GitHub API -------------
ROLE = "Co-founder @ GeMorph"
FOCUS = "Deep Learning, Gen AI, LLMs, Computational Bio/Bioinformatics"
ML_STACK = "Transformers, LoRA/PEFT, GANs, Diffusion, Hyperbolic GNNs"
TOOLS = "PyTorch, TensorFlow, GCP"
EMAIL = "navaira@gemorph.com"
WEBSITE = "gemorph.com"
BIRTHDATE = "2003-06-18"  # YYYY-MM-DD

ASCII_RAMP = " .:-=+*#%@"

FONT = "Consolas, 'Fira Code', 'DejaVu Sans Mono', monospace"
FONT_SIZE = 13
CHAR_W = FONT_SIZE * 0.6          # enforced via textLength, not relied on for real metrics
LINE_H = 23

LABEL_COL_CHARS = 24    # ". Languages.Programming:" etc
DOTS_COL_CHARS = 12
ASCII_FONT_SIZE = 8.6
ASCII_CHAR_W = ASCII_FONT_SIZE * 0.6
ASCII_LINE_H = 10.4


def api_get(url, token=None):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-card-generator"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def fetch_all_repos(username, token=None):
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}"
        batch = api_get(url, token)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def top_languages(repos, top_n=4):
    counts = Counter()
    for r in repos:
        lang = r.get("language")
        if lang:
            counts[lang] += 1
    return [lang for lang, _ in counts.most_common(top_n)]


def account_age(created_at):
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    delta_days = (datetime.now(timezone.utc) - created).days
    years, months = delta_days // 365, (delta_days % 365) // 30
    return f"{years}y {months}m"


def compute_age(birthdate_str):
    born = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age


def avatar_to_ascii(avatar_bytes, cols=44):
    img = Image.open(BytesIO(avatar_bytes)).convert("L")
    aspect_correction = 0.5
    rows = max(1, int(cols * img.height / img.width * aspect_correction))
    img = img.resize((cols, rows))
    pixels = list(img.getdata())
    grid = []
    for r in range(rows):
        row = "".join(
            ASCII_RAMP[int((255 - pixels[r * cols + c]) / 255 * (len(ASCII_RAMP) - 1))]
            for c in range(cols)
        )
        grid.append(row)
    return grid


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text_fixed(x, y, content, size, fill, weight="400", width=None, anchor="start"):
    """A <text> element whose rendered width is pinned via textLength."""
    attrs = f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"'
    if width:
        attrs += f' textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs"'
    return f'<text {attrs} xml:space="preserve">{esc(content)}</text>'


def build_svg(username, user, repos, ascii_grid, avatar_url):
    langs = top_languages(repos)
    age = account_age(user["created_at"])

    ascii_cols = max((len(r) for r in ascii_grid), default=0)
    ascii_px_w = ascii_cols * ASCII_CHAR_W
    ascii_px_h = len(ascii_grid) * ASCII_LINE_H

    pad = 24
    gap = 40
    label_col_w = LABEL_COL_CHARS * CHAR_W
    dots_col_w = DOTS_COL_CHARS * CHAR_W
    value_col_w = 62 * CHAR_W

    right_w = label_col_w + dots_col_w + value_col_w
    width = int(pad * 2 + ascii_px_w + gap + right_w)

    header_h = 44
    top = header_h + pad

    avatar_size = 40
    body = []

    # ASCII art
    for i, row in enumerate(ascii_grid):
        y = top + (i + 1) * ASCII_LINE_H
        body.append(text_fixed(pad, y, row, ASCII_FONT_SIZE, ASCII_FILL, width=ascii_px_w))
        body[-1] = body[-1].replace('fill="#8f7cff"', f'fill="{ASCII_FILL}" opacity="{0.35 + 0.55 * (i % 5) / 5:.2f}"')

    rx = pad + ascii_px_w + gap
    ry = [top]  # mutable box so nested funcs can update

    def section(title):
        y = ry[0]
        body.append(text_fixed(rx, y, f"- {title} ", 13, LABEL, weight="700"))
        dash_w = right_w - (len(title) + 3) * CHAR_W
        if dash_w > 0:
            body.append(
                text_fixed(rx + (len(title) + 3) * CHAR_W, y, "-" * 40, 13, BORDER, width=dash_w)
            )
        ry[0] += LINE_H

    def field(label, value):
        y = ry[0]
        label_text = f". {label}:"
        body.append(text_fixed(rx, y, label_text, FONT_SIZE, HEADER, weight="700", width=label_col_w))
        body.append(text_fixed(rx + label_col_w, y, "." * DOTS_COL_CHARS, FONT_SIZE, DOT, width=dots_col_w))
        body.append(text_fixed(rx + label_col_w + dots_col_w + CHAR_W * 0.6, y, str(value), FONT_SIZE, VALUE, weight="600"))
        ry[0] += LINE_H

    section("navaira@github")
    field("Role", ROLE)
    field("Focus", FOCUS)
    field("Languages.ML", ML_STACK)
    field("Languages.Programming", ", ".join(langs) if langs else "—")
    field("Tools", TOOLS)
    ry[0] += 10

    section("GitHub Stats")
    field("Age", compute_age(BIRTHDATE))
    field("Repos", user.get("public_repos", len(repos)))
    field("Account age", age)
    field("Top language", langs[0] if langs else "—")
    ry[0] += 10

    section("Contact")
    field("GitHub", f"github.com/{username}")
    field("Org", f"github.com/GeMorph · {WEBSITE}")
    field("Email", EMAIL)
    ry[0] += 20

    # ---- now that layout is known, compute final canvas height --------
    height = int(max(top + ascii_px_h, ry[0]) + pad)

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body.append(text_fixed(rx, height - pad + 8, f"last synced {updated}", 9.5, DOT))

    chrome = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<circle cx="{pad}" cy="{pad}" r="6" fill="#ff5f56"/>',
        f'<circle cx="{pad+18}" cy="{pad}" r="6" fill="#ffbd2e"/>',
        f'<circle cx="{pad+36}" cy="{pad}" r="6" fill="#27c93f"/>',
        text_fixed(pad + 56, pad + 5, f"{username} / README.md", 13, TITLE_DOT),
        f'<line x1="{pad}" y1="{pad+20}" x2="{width-pad}" y2="{pad+20}" stroke="{BORDER}"/>',
        f'<defs><clipPath id="avatarClip"><circle cx="{width - pad - avatar_size/2}" cy="{pad}" r="{avatar_size/2}"/></clipPath></defs>',
        f'<image href="{esc(avatar_url)}" x="{width - pad - avatar_size}" y="{pad - avatar_size/2}" '
        f'width="{avatar_size}" height="{avatar_size}" clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>',
        f'<circle cx="{width - pad - avatar_size/2}" cy="{pad}" r="{avatar_size/2}" fill="none" stroke="{HEADER}" stroke-width="1.5"/>',
    ]

    return "".join(chrome) + "".join(body) + "</svg>"


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_svg.py <username> <output_path>")
        sys.exit(1)

    username, output_path = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN")

    user = api_get(f"https://api.github.com/users/{username}", token)
    repos = fetch_all_repos(username, token)
    avatar_bytes = fetch_bytes(user["avatar_url"])
    ascii_grid = avatar_to_ascii(avatar_bytes, cols=44)

    svg = build_svg(username, user, repos, ascii_grid, user["avatar_url"])
    with open(output_path, "w") as f:
        f.write(svg)
    print(f"Wrote {output_path} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
