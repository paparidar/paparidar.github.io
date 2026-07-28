# Personal site — CV + blog

A small static site: a CV homepage and a markdown blog. No frameworks, no Ruby,
no npm. One Python script turns `src/` into plain HTML at the repo root, which is
exactly what GitHub Pages serves.

## Layout

```
build.py            the whole build (one file, ~250 lines)
src/
  cv.yaml           <- everything on the CV page lives here
  posts/*.md        <- one file per blog post
  templates/*.html  <- Jinja2 templates
  static/           <- copied to assets/ (CSS, photo, PDF CV)
index.html          generated — don't edit
blog/               generated — don't edit
assets/             generated — don't edit
feed.xml            generated — don't edit
```

Anything listed as generated is wiped and rewritten on every build. Edit `src/`.

## Setup (once)

```bash
python3 -m pip install -r requirements.txt
```

## Editing the CV

Open `src/cv.yaml`, change it, rebuild. Sections render in the order they appear
and come in three shapes:

- `kind: entries` — date on the left, title/subtitle/detail/bullets/tags on the
  right. Use for experience, education, projects, publications.
- `kind: groups` — label/value pairs. Use for skills, languages.
- `kind: list` — a plain bulleted list.

Delete sections you don't want; add as many as you like.

## Writing a post

Create `src/posts/YYYY-MM-DD-a-slug.md`:

```markdown
---
title: What I found in the AIS data
date: 2026-08-04
summary: One line that shows up in the post list.
tags: [python, maritime]
draft: false
---

Body in markdown. Tables, code fences, footnotes, and blockquotes all work.
```

Set `draft: true` to keep a post off the live site while you work on it;
`python3 build.py --drafts` renders drafts locally.

## Build and preview

```bash
python3 build.py            # build
python3 build.py --serve    # build, then preview at http://localhost:8000
```

## Publish

```bash
python3 build.py
git add -A
git commit -m "post: what I found in the AIS data"
git push
```

GitHub Pages redeploys within a minute or so.

## Adding a photo or a PDF CV

Drop the file in `src/static/` — it ends up at `assets/<filename>`.

- Photo: save as `src/static/photo.jpg` (square crops best), then set
  `photo: photo.jpg` in `cv.yaml`.
- PDF CV: save as `src/static/cv.pdf`, then add a link under `links:` pointing at
  `/assets/cv.pdf`. Or just open the site and print to PDF — there's a print
  stylesheet that strips the nav and photo.

## Notes

- `site_url` in `cv.yaml` is used to build absolute URLs in `feed.xml`. Set it to
  your live URL or the RSS links will be relative and break in readers.
- `.nojekyll` tells GitHub not to run Jekyll over the output. Keep it.
- The build fails loudly on a typo in a template (`StrictUndefined`) or a post
  missing a title or date. That's on purpose — better than a silently blank page.
