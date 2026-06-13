#!/usr/bin/env python3
"""
A minimal static blog generator with sections.

What it does, top to bottom:
  1. Reads every .md file under CONTENT_DIR/<section>/ (macro, micro, tactile).
  2. Splits off the YAML front matter (the block between the leading --- fences).
  3. Renders the markdown body to HTML.
  4. Writes a page per post           -> dist/<section>/<slug>/index.html
  5. Writes a page per section        -> dist/<section>/index.html
       - macro:   a date-sorted list of essays
       - micro:   a social-media-style feed (title, date, content inline)
       - tactile: a visual gallery grid
  6. Writes a landing page            -> dist/index.html
  7. Copies everything in static/     -> dist/static/
  8. Writes dist/CNAME                -> for GitHub Pages custom domain

Run it:  python build.py
Deps:    pip install markdown pyyaml
"""

from __future__ import annotations

import datetime as dt
import html
import re
import shutil
import urllib.parse
from pathlib import Path

import markdown
import yaml

# ---------------------------------------------------------------------------
# Config — edit these.
# ---------------------------------------------------------------------------
SITE_TITLE = "charlotte's web"
SITE_DESC = "Notes and writing."
CUSTOM_DOMAIN = "charlottes.website"  # written to dist/CNAME for GitHub Pages
AUTHOR = "Charlotte"

# Sections. Each section is a content/<key>/ folder rendered with one of three
# layouts ("kind"): "list" (essays), "feed" (snapshots), "gallery" (objects).
SECTIONS = [
    {
        "key": "macro",
        "label": "macro",
        "kind": "list",
        "blurb": "Longer essays and things I'm working through.",
    },
    {
        "key": "micro",
        "label": "micro",
        "kind": "feed",
        "blurb": "Quick snapshots: half-formed ideas, links, small noticings.",
    },
    {
        "key": "tactile",
        "label": "tactile",
        "kind": "gallery",
        "blurb": "Physical things I've made with my hands.",
    },
]

ROOT = Path(__file__).parent
CONTENT_DIR = ROOT / "content"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

# Markdown extensions: fenced code blocks, tables, footnotes, smart typography.
MD_EXTENSIONS = ["fenced_code", "tables", "footnotes", "smarty", "toc"]

# ---------------------------------------------------------------------------
# Templates — plain str.format(). Edit the HTML/structure freely.
# @@ROOT@@ inside rendered markdown bodies is replaced with the page's relative
# root at render time, so embedded images resolve from any depth.
# ---------------------------------------------------------------------------
BASE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <script>document.documentElement.dataset.view=localStorage.getItem("view")||"terminal"</script>
  <link rel="icon" href="{root}static/favicon.png" type="image/png">
  <link rel="stylesheet" href="{root}static/style.css">
</head>
<body>
  <div class="layout">
{sidebar}    <div class="main-col">
      <main>
{body}
      </main>
      <footer class="site-footer">
        <p>&copy; {year} {author}</p>
        <div class="view-switch" role="group" aria-label="Switch typeface">
          <span class="view-switch-label" id="view-switch-label">type</span>
          <div class="view-switch-options">
            <button type="button" class="view-switch-terminal" data-view="terminal" aria-describedby="view-switch-label">terminal</button>
            <button type="button" class="view-switch-magazine" data-view="magazine" aria-describedby="view-switch-label">magazine</button>
          </div>
        </div>
      </footer>
    </div>
  </div>
  <script src="{root}static/view.js"></script>
</body>
</html>
"""

SIDEBAR = """    <nav class="site-nav" aria-label="Sections">
      <a class="site-title" href="{root}">{site_title}</a>
      <ul class="nav-list">
{items}
      </ul>
    </nav>
"""

NAV_ITEM = """        <li><a class="nav-link{active}" href="{root}{key}/"{current}>{label}</a></li>"""

POST_BODY = """    <div class="page-layout{layout_class}">
{toc}      <article class="post{post_class}">
      <h1>{title}</h1>
      <p class="post-meta"><time datetime="{iso}">{date}</time></p>
{content}
      </article>
    </div>
    <p class="back"><a href="{root}{section}/">&larr; {section_label}</a></p>
"""

LIST_ITEM = """          <li>
            <a href="{root}{section}/{slug}/">{title}</a>
            <time datetime="{iso}">{date}</time>
          </li>"""

LIST_BODY = """    <div class="page-layout">
      <div class="content">
        <h1 class="section-title">{label}</h1>
        <p class="section-desc">{blurb}</p>
        <ul class="post-list">
{items}
        </ul>
      </div>
    </div>
"""

FEED_ITEM = """          <article class="feed-item">
            <header class="feed-item-head">
              <h2 class="feed-item-title"><a href="{root}{section}/{slug}/">{title}</a></h2>
              <time datetime="{iso}">{date}</time>
            </header>
            <div class="feed-item-body post">
{content}
            </div>
          </article>"""

FEED_BODY = """    <div class="page-layout">
      <div class="content">
        <h1 class="section-title">{label}</h1>
        <p class="section-desc">{blurb}</p>
        <div class="feed">
{items}
        </div>
      </div>
    </div>
"""

GALLERY_CARD = """          <li class="gallery-card">
            <a href="{root}{section}/{slug}/">
              {media}
              <span class="gallery-card-title">{title}</span>
            </a>
          </li>"""

GALLERY_BODY = """    <div class="page-layout">
      <div class="content content-wide">
        <h1 class="section-title">{label}</h1>
        <p class="section-desc">{blurb}</p>
        <ul class="gallery">
{cards}
        </ul>
      </div>
    </div>
"""

LANDING_SECTION = """          <a class="section-card" href="{root}{key}/">
            <span class="section-card-label">{label}</span>
            <span class="section-card-blurb">{blurb}</span>
          </a>"""

LANDING_BODY = """    <div class="page-layout">
      <div class="content">
        <h1 class="index-title">{site_title}</h1>
        <p class="index-desc">{site_desc}</p>
        <div class="section-cards">
{sections}
        </div>
      </div>
    </div>
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LIST_LINE_RE = re.compile(r"^( +)([-+*]|\d+\.) ")
SIDENOTE_RE = re.compile(r"\^\[([^\]]+)\]")
WIKILINK_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")
FIRST_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')


def section_image_src(section: str, name: str) -> str:
    """Relative (token) src for an image that lives in content/<section>/."""
    return "@@ROOT@@" + section + "/" + urllib.parse.quote(name)


def convert_wikilinks(raw: str, section: str) -> str:
    """Convert Obsidian ![[file.jpg|width]] embeds into <img> tags.

    Images live alongside the post in content/<section>/ (copied to dist). The
    src uses an @@ROOT@@ token so it resolves correctly from any page depth.
    """

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        parts = [p.strip() for p in inner.split("|")]
        name = parts[0]
        attr = ""
        if len(parts) > 1 and parts[1].isdigit():
            attr = f' width="{parts[1]}"'
        src = section_image_src(section, name)
        alt = html.escape(name.rsplit(".", 1)[0])
        return f'<img src="{src}" alt="{alt}"{attr} loading="lazy">'

    return WIKILINK_IMG_RE.sub(repl, raw)


def extract_sidenotes(raw: str) -> tuple[str, list[str]]:
    """Pull Pandoc-style ^[sidenote] markers out before markdown runs."""
    notes: list[str] = []

    def repl(match: re.Match[str]) -> str:
        notes.append(match.group(1))
        return f"@@SN{len(notes)}@@"

    return SIDENOTE_RE.sub(repl, raw), notes


def render_sidenote_content(text: str) -> str:
    inner = markdown.markdown(text, extensions=["smarty"]).strip()
    if inner.startswith("<p>") and inner.endswith("</p>"):
        inner = inner[3:-4]
    return inner


def inject_sidenotes(body_html: str, notes: list[str]) -> str:
    for n, content in enumerate(notes, start=1):
        note_html = render_sidenote_content(content)
        marker = (
            f'<span class="sidenote-group">'
            f'<label for="sn-{n}" class="sidenote-ref">{n}</label>'
            f'<input type="checkbox" id="sn-{n}" class="sidenote-toggle">'
            f'<span class="sidenote">{note_html}</span>'
            f"</span>"
        )
        body_html = body_html.replace(f"@@SN{n}@@", marker, 1)
    return body_html


def build_toc(body_html: str) -> str:
    """TOC from markdown # headings (h1 in rendered HTML)."""
    h1s = re.findall(r'<h1 id="([^"]+)">([^<]+)</h1>', body_html)
    if not h1s:
        return ""
    items = "\n".join(
        f'          <li><a href="#{html.escape(id_, quote=True)}">{html.escape(title)}</a></li>'
        for id_, title in h1s
    )
    return f"""      <nav class="post-toc" aria-label="Table of contents">
        <ul>
{items}
        </ul>
      </nav>
"""


def normalize_list_indent(raw: str) -> str:
    """Expand 2-space list indents to 4-space for Python-Markdown nesting."""
    out = []
    for line in raw.splitlines():
        m = LIST_LINE_RE.match(line)
        if m:
            depth = len(m.group(1)) // 2
            out.append(" " * (depth * 4) + line.lstrip())
        else:
            out.append(line)
    return "\n".join(out)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


def root_for_depth(depth: int) -> str:
    """Relative path back to dist/ from a page nested `depth` dirs deep."""
    return "../" * depth


def parse_post(path: Path, section: str) -> dict:
    """Return {meta, html, slug, ...} for one markdown file."""
    raw = path.read_text(encoding="utf-8")

    meta = {}
    m = FRONT_MATTER_RE.match(raw)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        raw = raw[m.end() :]

    raw = convert_wikilinks(normalize_list_indent(raw), section)
    raw, sidenotes = extract_sidenotes(raw)

    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    body_html = inject_sidenotes(md.convert(raw), sidenotes)
    toc = build_toc(body_html)

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

    # cover image (gallery thumbnail). An explicit front-matter `cover` is also
    # rendered at the bottom of the post; otherwise we fall back to the first
    # image in the body for the thumbnail only.
    cover_file = meta.get("cover")
    cover_explicit = bool(cover_file)
    if cover_file:
        cover = section_image_src(section, str(cover_file))
    else:
        first = FIRST_IMG_RE.search(body_html)
        cover = first.group(1) if first else None

    return {
        "title": title,
        "slug": slug,
        "date": date,
        "html": body_html,
        "toc": toc,
        "sidenotes": sidenotes,
        "section": section,
        "cover": cover,
        "cover_explicit": cover_explicit,
    }


def render_sidebar(root: str, current_key: str | None) -> str:
    items = "\n".join(
        NAV_ITEM.format(
            root=root,
            key=s["key"],
            label=html.escape(s["label"]),
            active=" active" if s["key"] == current_key else "",
            current=' aria-current="page"' if s["key"] == current_key else "",
        )
        for s in SECTIONS
    )
    return SIDEBAR.format(
        root=root,
        site_title=html.escape(SITE_TITLE),
        items=items,
    )


def render_page(
    title: str, body: str, root: str, *, current_key: str | None = None
) -> str:
    page = BASE.format(
        title=html.escape(title),
        sidebar=render_sidebar(root, current_key),
        body=body,
        root=root,
        author=html.escape(AUTHOR),
        year=dt.date.today().year,
    )
    return page.replace("@@ROOT@@", root)


def fmt_date(d: dt.date) -> str:
    return d.strftime("%B %-d, %Y")


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def render_post_page(post: dict, section: dict) -> str:
    root = root_for_depth(2)
    layout_class = ""
    if post["toc"]:
        layout_class += " has-toc"
    if post["sidenotes"]:
        layout_class += " has-sidenotes"
    content = post["html"]
    if post["cover_explicit"] and post["cover"]:
        content += (
            f'\n<figure class="post-cover">'
            f'<img src="{post["cover"]}" alt="{html.escape(post["title"])}" loading="lazy">'
            f"</figure>"
        )
    body = POST_BODY.format(
        title=html.escape(post["title"]),
        content=content,
        toc=post["toc"],
        date=fmt_date(post["date"]),
        iso=post["date"].isoformat(),
        root=root,
        section=section["key"],
        section_label=html.escape(section["label"]),
        layout_class=layout_class,
        post_class=" has-sidenotes" if post["sidenotes"] else "",
    )
    return render_page(post["title"], body, root, current_key=section["key"])


def render_list_section(section: dict, posts: list[dict]) -> str:
    root = root_for_depth(1)
    items = "\n".join(
        LIST_ITEM.format(
            root=root,
            section=section["key"],
            slug=p["slug"],
            title=html.escape(p["title"]),
            date=fmt_date(p["date"]),
            iso=p["date"].isoformat(),
        )
        for p in posts
    )
    body = LIST_BODY.format(
        label=html.escape(section["label"]),
        blurb=html.escape(section["blurb"]),
        items=items,
    )
    return render_page(section["label"], body, root, current_key=section["key"])


def render_feed_section(section: dict, posts: list[dict]) -> str:
    root = root_for_depth(1)
    items = "\n".join(
        FEED_ITEM.format(
            root=root,
            section=section["key"],
            slug=p["slug"],
            title=html.escape(p["title"]),
            date=fmt_date(p["date"]),
            iso=p["date"].isoformat(),
            content=p["html"],
        )
        for p in posts
    )
    body = FEED_BODY.format(
        label=html.escape(section["label"]),
        blurb=html.escape(section["blurb"]),
        items=items,
    )
    return render_page(section["label"], body, root, current_key=section["key"])


def render_gallery_section(section: dict, posts: list[dict]) -> str:
    root = root_for_depth(1)
    cards = []
    for p in posts:
        if p["cover"]:
            media = (
                f'<span class="gallery-card-media">'
                f'<img src="{p["cover"]}" alt="{html.escape(p["title"])}" loading="lazy">'
                f"</span>"
            )
        else:
            media = '<span class="gallery-card-media gallery-card-media-empty"></span>'
        cards.append(
            GALLERY_CARD.format(
                root=root,
                section=section["key"],
                slug=p["slug"],
                title=html.escape(p["title"]),
                media=media,
            )
        )
    body = GALLERY_BODY.format(
        label=html.escape(section["label"]),
        blurb=html.escape(section["blurb"]),
        cards="\n".join(cards),
    )
    return render_page(section["label"], body, root, current_key=section["key"])


def render_landing() -> str:
    root = root_for_depth(0)
    sections = "\n".join(
        LANDING_SECTION.format(
            root=root,
            key=s["key"],
            label=html.escape(s["label"]),
            blurb=html.escape(s["blurb"]),
        )
        for s in SECTIONS
    )
    body = LANDING_BODY.format(
        site_title=html.escape(SITE_TITLE),
        site_desc=html.escape(SITE_DESC),
        sections=sections,
    )
    return render_page(SITE_TITLE, body, root, current_key=None)


SECTION_RENDERERS = {
    "list": render_list_section,
    "feed": render_feed_section,
    "gallery": render_gallery_section,
}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    total = 0
    for section in SECTIONS:
        section_dir = CONTENT_DIR / section["key"]
        paths = sorted(section_dir.glob("*.md")) if section_dir.exists() else []
        posts = [parse_post(p, section["key"]) for p in paths]
        posts.sort(key=lambda p: p["date"], reverse=True)
        total += len(posts)

        # Per-post pages: dist/<section>/<slug>/index.html
        for post in posts:
            out = OUTPUT_DIR / section["key"] / post["slug"]
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(
                render_post_page(post, section), encoding="utf-8"
            )

        # Section index: dist/<section>/index.html
        renderer = SECTION_RENDERERS[section["kind"]]
        section_out = OUTPUT_DIR / section["key"]
        section_out.mkdir(parents=True, exist_ok=True)
        (section_out / "index.html").write_text(
            renderer(section, posts), encoding="utf-8"
        )

        # Copy any non-markdown assets (images, etc.) that live alongside the
        # posts in content/<section>/ to dist/<section>/.
        for asset in sorted(section_dir.glob("*")) if section_dir.exists() else []:
            if asset.is_file() and asset.suffix.lower() != ".md":
                shutil.copy2(asset, section_out / asset.name)

    # Landing page: dist/index.html
    (OUTPUT_DIR / "index.html").write_text(render_landing(), encoding="utf-8")

    # Static assets.
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    # GitHub Pages custom domain.
    if CUSTOM_DOMAIN:
        (OUTPUT_DIR / "CNAME").write_text(f"{CUSTOM_DOMAIN}\n", encoding="utf-8")

    print(f"Built {total} post(s) across {len(SECTIONS)} section(s) -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    build()
