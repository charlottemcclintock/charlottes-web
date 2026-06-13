# minimal-blog

A blog that is one Python script, one stylesheet, and a folder of markdown.

```
blog/
├── build.py          # the whole generator (read it)
├── content/          # your posts, organized into sections
│   ├── macro/        # longer essays
│   ├── micro/        # quick snapshots
│   └── tactile/      # physical things (gallery)
├── static/
│   ├── style.css     # minimal editorial styling, copied to dist/static/
│   └── images/       # images referenced from posts
└── dist/             # generated output (git-ignore this)
```

## Sections

Content lives in three section folders. The folder a file sits in decides
where it goes and how its section page looks:

- `macro` — longer essays. Section page is a date-sorted list of links.
- `micro` — quick snapshots. Each post has its own page, and the section
  page compiles them into a social-media-style feed (title, date, content
  inline).
- `tactile` — physical things you've made. Section page is a visual gallery
  grid; each item links to its own page.

The site has a left nav bar linking to each section, and the home page (`/`)
is a landing page introducing all three. Add or rename sections by editing
the `SECTIONS` list near the top of `build.py`.

## Setup

```bash
pip install markdown pyyaml
```

## Write a post

Drop a `.md` file in the section folder you want (`content/macro/`,
`content/micro/`, or `content/tactile/`). Front matter is optional:

```markdown
---
title: My Post Title
date: 2026-06-01
slug: custom-url-slug   # optional; defaults to the filename
cover: my-photo.jpg     # optional; tactile gallery thumbnail (in static/images/)
---

Body in **markdown**.
```

- No `title` → derived from the filename (`my-post.md` → "My Post").
- No `date`  → falls back to the file's modification time.
- Pages are written to `dist/<section>/<slug>/`.

## Images

Put image files in the same section folder as the post (e.g.
`content/tactile/`). They're copied to `dist/<section>/` and can be referenced
with Obsidian-style embeds, which are converted automatically:

```markdown
![[photo.jpg]]        ![[photo.jpg|600]]   # optional width
```

For `tactile` gallery thumbnails, the build uses the `cover` front-matter
field if present, otherwise the first image in the post. Items with no image
fall back to a text-only card. A `cover` set in front matter is also rendered
at the bottom of the post.

## Build

```bash
python build.py
```

Writes `dist/`: a page per post at `dist/<section>/<slug>/index.html`, a
section page at `dist/<section>/index.html`, a landing `index.html`, and your
`static/` assets.

## Preview locally

```bash
python -m http.server -d dist 8000   # then open http://localhost:8000
```

## Deploy

`dist/` is plain static files — push it to GitHub Pages, Netlify, Cloudflare
Pages, or any bucket. Set `CUSTOM_DOMAIN` near the top of `build.py` for a
GitHub Pages custom domain (written to `dist/CNAME`).

## Things you'll probably want to change

All at the top of `build.py`: `SITE_TITLE`, `SITE_DESC`, `CUSTOM_DOMAIN`,
`AUTHOR`, `SECTIONS`, and `MD_EXTENSIONS`. The HTML lives in the template
strings just below the config; edit them directly.
