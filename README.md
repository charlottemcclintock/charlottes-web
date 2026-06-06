# minimal-blog

A blog that is one Python script, one stylesheet, and a folder of markdown.

```
blog/
├── build.py          # the whole generator (~200 lines, read it)
├── content/          # your posts, one .md file each
│   └── hello-world.md
├── static/
│   └── style.css     # minimal editorial styling, copied to dist/static/
└── dist/             # generated output (git-ignore this)
```

## Setup

```bash
pip install markdown pyyaml
```

## Write a post

Drop a `.md` file in `content/`. Front matter is optional:

```markdown
---
title: My Post Title
date: 2026-06-01
slug: custom-url-slug   # optional; defaults to the filename
---

Body in **markdown**.
```

- No `title` → derived from the filename (`my-post.md` → "My Post").
- No `date`  → falls back to the file's modification time.

## Build

```bash
python build.py
```

Writes `dist/`: a page per post at `dist/<slug>/index.html`, a date-sorted
`index.html`, an RSS `feed.xml`, and your `static/` assets.

## Preview locally

```bash
python -m http.server -d dist 8000   # then open http://localhost:8000
```

## Deploy

`dist/` is plain static files — push it to GitHub Pages, Netlify, Cloudflare
Pages, or any bucket. Set `BASE_URL` near the top of `build.py` first so the
RSS links are absolute.

## Things you'll probably want to change

All at the top of `build.py`: `SITE_TITLE`, `SITE_DESC`, `BASE_URL`, `AUTHOR`,
and `MD_EXTENSIONS`. The HTML lives in the template strings just below the
config; edit them directly.
