#!/usr/bin/env python3
"""
A minimal static blog generator.

What it does, top to bottom:
  1. Reads every .md file in CONTENT_DIR.
  2. Splits off the YAML front matter (the block between the leading --- fences).
  3. Renders the markdown body to HTML.
  4. Wraps each post in POST_TEMPLATE -> writes dist/<slug>/index.html
  5. Builds a date-sorted index page  -> writes dist/index.html
  6. Builds an RSS feed              -> writes dist/feed.xml
  7. Copies everything in static/    -> dist/static/
  8. Writes dist/CNAME             -> for GitHub Pages custom domain

Run it:  python build.py
Deps:    pip install markdown pyyaml
"""

from __future__ import annotations

import datetime as dt
import html
import re
import shutil
from pathlib import Path

import markdown
import yaml

# ---------------------------------------------------------------------------
# Config — edit these.
# ---------------------------------------------------------------------------
SITE_TITLE = "Charlotte's Web"
SITE_DESC = "Notes and writing."
BASE_URL = "https://charlottes.website"  # no trailing slash; used for RSS links
CUSTOM_DOMAIN = "charlottes.website"  # written to dist/CNAME for GitHub Pages
AUTHOR = "Charlotte"

ROOT = Path(__file__).parent
CONTENT_DIR = ROOT / "content"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

# Markdown extensions: fenced code blocks, tables, footnotes, smart typography.
MD_EXTENSIONS = ["fenced_code", "tables", "footnotes", "smarty", "toc"]

# ---------------------------------------------------------------------------
# Templates — plain str.format(). Edit the HTML/structure freely.
# ---------------------------------------------------------------------------
BASE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{root}static/style.css">
  <link rel="alternate" type="application/rss+xml" title="{site_title}" href="{root}feed.xml">
</head>
<body>
  <header class="site-header">
    <a class="site-title" href="{root}">{site_title}</a>
  </header>
  <main>
{body}
  </main>
  <footer class="site-footer">
    <p>&copy; {year} {author} &middot; <a href="{root}feed.xml">RSS</a></p>
  </footer>
</body>
</html>
"""

POST_BODY = """    <article class="post">
      <h1>{title}</h1>
      <p class="post-meta"><time datetime="{iso}">{date}</time></p>
{content}
    </article>
    <p class="back"><a href="{root}">&larr; All posts</a></p>
"""

INDEX_ITEM = """      <li>
        <a href="{root}{slug}/">{title}</a>
        <time datetime="{iso}">{date}</time>
      </li>"""

INDEX_BODY = """    <h1 class="index-title">{site_title}</h1>
    <p class="index-desc">{site_desc}</p>
    <ul class="post-list">
{items}
    </ul>
"""

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{site_title}</title>
<link>{base_url}</link>
<description>{site_desc}</description>
{items}
</channel></rss>
"""

RSS_ITEM = """<item>
<title>{title}</title>
<link>{base_url}/{slug}/</link>
<guid>{base_url}/{slug}/</guid>
<pubDate>{rfc822}</pubDate>
<description>{summary}</description>
</item>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


def parse_post(path: Path) -> dict:
    """Return {meta, html, slug} for one markdown file."""
    raw = path.read_text(encoding="utf-8")

    meta = {}
    m = FRONT_MATTER_RE.match(raw)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        raw = raw[m.end() :]

    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    body_html = md.convert(raw)

    # date: accept a date in front matter, else fall back to file mtime.
    date = meta.get("date")
    if isinstance(date, str):
        date = dt.date.fromisoformat(date)
    elif isinstance(date, dt.datetime):
        date = date.date()
    elif not isinstance(date, dt.date):
        date = dt.date.fromtimestamp(path.stat().st_mtime)

    title = meta.get("title") or path.stem.replace("-", " ").title()
    slug = meta.get("slug") or slugify(path.stem)

    return {
        "title": title,
        "slug": slug,
        "date": date,
        "html": body_html,
        # crude summary for RSS: first paragraph, tags stripped.
        "summary": re.sub(r"<[^>]+>", "", body_html).strip().split("\n\n")[0][:300],
    }


def render_page(title: str, body: str, root: str) -> str:
    return BASE.format(
        title=html.escape(title),
        site_title=html.escape(SITE_TITLE),
        body=body,
        root=root,
        author=html.escape(AUTHOR),
        year=dt.date.today().year,
    )


def fmt_date(d: dt.date) -> str:
    return d.strftime("%B %-d, %Y")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    posts = [parse_post(p) for p in sorted(CONTENT_DIR.glob("*.md"))]
    posts.sort(key=lambda p: p["date"], reverse=True)

    # Per-post pages (root is "../" since each post lives one dir deep).
    for post in posts:
        body = POST_BODY.format(
            title=html.escape(post["title"]),
            content=post["html"],
            date=fmt_date(post["date"]),
            iso=post["date"].isoformat(),
            root="../",
        )
        page = render_page(post["title"], body, root="../")
        out = OUTPUT_DIR / post["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page, encoding="utf-8")

    # Index (root is "./").
    items = "\n".join(
        INDEX_ITEM.format(
            slug=p["slug"],
            title=html.escape(p["title"]),
            date=fmt_date(p["date"]),
            iso=p["date"].isoformat(),
            root="",
        )
        for p in posts
    )
    index_body = INDEX_BODY.format(
        site_title=html.escape(SITE_TITLE),
        site_desc=html.escape(SITE_DESC),
        items=items,
    )
    (OUTPUT_DIR / "index.html").write_text(
        render_page(SITE_TITLE, index_body, root=""), encoding="utf-8"
    )

    # RSS.
    rss_items = "\n".join(
        RSS_ITEM.format(
            title=html.escape(p["title"]),
            slug=p["slug"],
            base_url=BASE_URL,
            summary=html.escape(p["summary"]),
            rfc822=dt.datetime.combine(p["date"], dt.time()).strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            ),
        )
        for p in posts
    )
    (OUTPUT_DIR / "feed.xml").write_text(
        RSS.format(
            site_title=html.escape(SITE_TITLE),
            site_desc=html.escape(SITE_DESC),
            base_url=BASE_URL,
            items=rss_items,
        ),
        encoding="utf-8",
    )

    # Static assets.
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    # GitHub Pages custom domain.
    if CUSTOM_DOMAIN:
        (OUTPUT_DIR / "CNAME").write_text(f"{CUSTOM_DOMAIN}\n", encoding="utf-8")

    print(f"Built {len(posts)} post(s) -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    build()
