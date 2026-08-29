#!/usr/bin/env python3
"""
Generates a neofetch-style terminal card for a GitHub profile README:
ASCII-art avatar on the left, dotted key/value stats on the right.
Pulls live data from the GitHub REST API.

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

# ---- theme -------------------------------------------------------------
BG = "#0d1117"
BORDER = "#30363d"
SECTION = "#c9d1d9"     # section header text, e.g. "- navaira@github"
DASH = "#30363d"        # dashes after section header
LABEL = "#ffa657"       # ". Role:" style keys (orange)
DOT = "#484f58"         # dot leaders
VALUE = "#a5d6ff"       # values (light blue)
TITLE_DOT = "#6e7681"   # window titlebar text
ASCII_FILL = "#8b949e"  # ascii avatar art

# ---- static config: things that aren't in the GitHub API ---------------
ROLE = "Co-founder @ GeMorph"
FOCUS = "Deep Learning, Gen AI, LLMs, Computational Bio/Bioinformatics"
ML_STACK = "Transformers, LoRA/PEFT, GANs, Diffusion, Hyperbolic GNNs"
TOOLS = "PyTorch, TensorFlow, GCP"
EMAIL = "navaira@gemorph.com"
WEBSITE = "gemorph.com"
ORG = "GeMorph"

ASCII_RAMP = " .:-=+*#%@"

FONT = "Consolas, 'Fira Code', 'DejaVu Sans Mono', monospace"
FONT_SIZE = 13
LINE_H = 23

RIGHT_COL_CHARS = 100   # total characters spanned by the right-hand block (label+dots+value area)
LABEL_VALUE_GAP_CHARS = 1

ASCII_FONT_SIZE = 4.9
ASCII_CHAR_W = ASCII_FONT_SIZE * 1.0   # monospace cell width used purely for canvas sizing
ASCII_LINE_H = 5.3


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


def avatar_to_ascii(avatar_bytes, cols=100):
    img = Image.open(BytesIO(avatar_bytes)).convert("L")
    aspect_correction = 0.48
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


def text_el(x, y, content, size, fill, anchor="start", xml_space=True):
    space = ' xml:space="preserve"' if xml_space else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{space}>{esc(content)}</text>'


def build_svg(username, user, repos, ascii_grid, avatar_url):
    langs = top_languages(repos)
    age = account_age(user["created_at"])
    repo_count = user.get("public_repos", len(repos))
    top_lang = langs[0] if langs else "\u2014"
    lang_list = ", ".join(langs) if langs else "\u2014"

    # ---- canvas geometry (mirrors the reference card's proportions) ----
    width = 1079
    header_h = 44
    pad = 24
    ascii_x = 24
    ascii_top = 62.0
    right_x = 328

    body = []

    # ASCII avatar block, flat gray, one <text> per row
    y = ascii_top
    for row in ascii_grid:
        body.append(text_el(ascii_x, round(y, 1), row, ASCII_FONT_SIZE, ASCII_FILL))
        y += ASCII_LINE_H
    ascii_bottom = y

    def dashes_to_fill(prefix_text, total_chars=58):
        n = max(0, total_chars - len(prefix_text))
        return "-" * n

    def dots_to_fill(label_text, total_chars=25):
        n = max(1, total_chars - len(label_text))
        return "." * n

    ry = [68]  # first section header baseline, matches reference

    def section(title):
        yy = ry[0]
        prefix = f"- {title} "
        body.append(
            f'<text x="{right_x}" y="{yy}" font-size="13" text-anchor="start" xml:space="preserve">'
            f'<tspan fill="{SECTION}" font-weight="700">{esc(prefix)}</tspan>'
            f'<tspan fill="{DASH}" font-weight="400">{dashes_to_fill(prefix)}</tspan></text>'
        )
        ry[0] += LINE_H

    def field(label, value):
        yy = ry[0]
        label_text = f". {label}:"
        body.append(
            f'<text x="{right_x}" y="{yy}" font-size="13" text-anchor="start" xml:space="preserve">'
            f'<tspan fill="{LABEL}" font-weight="700">{esc(label_text)}</tspan>'
            f'<tspan fill="{DOT}" font-weight="400">{dots_to_fill(label_text)}</tspan>'
            f'<tspan fill="{VALUE}" font-weight="600"> {esc(value)}</tspan></text>'
        )
        ry[0] += LINE_H

    section("navaira@github")
    field("Role", ROLE)
    field("Focus", FOCUS)
    field("Languages.ML", ML_STACK)
    field("Languages.Programming", lang_list)
    field("Tools", TOOLS)
    ry[0] += 10

    section("GitHub Stats")
    field("Repos", repo_count)
    field("Account age", age)
    field("Top language", top_lang)
    ry[0] += 10

    section("Contact")
    field("GitHub", f"github.com/{username}")
    field("Org", f"github.com/{ORG} \u00b7 {WEBSITE}")
    field("Email", EMAIL)
    ry[0] += 30

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d UTC")
    footer_y = ry[0]
    body.append(text_el(right_x, footer_y, f"last synced {updated}", 9.5, DOT))

    height = int(max(ascii_bottom + pad, footer_y + pad))

    avatar_size = 40
    chrome = [
        f'<svg width="{int(width*0.71)}" height="{int(height*0.71)}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<circle cx="24" cy="24" r="6" fill="#ff5f56"/><circle cx="42" cy="24" r="6" fill="#ffbd2e"/><circle cx="60" cy="24" r="6" fill="#27c93f"/>',
        text_el(80, 29, f"{username} / README.md", 13, TITLE_DOT),
        f'<line x1="24" y1="44" x2="{width-24}" y2="44" stroke="{BORDER}"/>',
        f'<defs><clipPath id="avatarClip"><circle cx="{width-44}" cy="24" r="20"/></clipPath></defs>',
        f'<image href="{esc(avatar_url)}" x="{width-64}" y="4" width="{avatar_size}" height="{avatar_size}" '
        f'clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>',
        f'<circle cx="{width-44}" cy="24" r="20" fill="none" stroke="#ffa657" stroke-width="1.5"/>',
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
    ascii_grid = avatar_to_ascii(avatar_bytes, cols=100)

    svg = build_svg(username, user, repos, ascii_grid, user["avatar_url"])
    with open(output_path, "w") as f:
        f.write(svg)
    print(f"Wrote {output_path} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
