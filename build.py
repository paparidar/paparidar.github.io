#!/usr/bin/env python3
"""Build the static site.

Reads:
    src/cv.yaml          -- CV content (edit this to change the homepage)
    src/posts/*.md       -- blog posts, newest first by filename date
    src/templates/*.html -- Jinja2 templates
    src/static/*         -- copied verbatim to assets/

Writes (at the repo root, ready for GitHub Pages):
    index.html, blog/index.html, blog/<slug>/index.html, assets/, feed.xml

Usage:
    python3 build.py            # build
    python3 build.py --serve    # build, then serve at http://localhost:8000
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src"
POSTS_DIR = SRC / "posts"
OUT = ROOT

# Everything the build owns and is allowed to wipe between runs.
GENERATED = ("index.html", "blog", "assets", "feed.xml")

MD_EXTENSIONS = ["extra", "sane_lists", "smarty", "toc", "codehilite"]
MD_CONFIG = {"codehilite": {"noclasses": True, "pygments_style": "friendly"}}


@dataclass
class Post:
    slug: str
    title: str
    date: dt.date
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    html: str = ""
    draft: bool = False

    @property
    def date_display(self) -> str:
        return self.date.strftime("%d %b %Y").lstrip("0")

    @property
    def date_rfc822(self) -> str:
        stamp = dt.datetime.combine(self.date, dt.time(12, 0))
        return stamp.strftime("%a, %d %b %Y %H:%M:%S +0000")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", text) or "post"


def split_front_matter(raw: str) -> tuple[dict, str]:
    """Pull a leading `---` YAML block off a markdown file."""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter must be a YAML mapping")
    return meta, parts[2].lstrip("\n")


def load_posts(include_drafts: bool = False) -> list[Post]:
    posts: list[Post] = []
    if not POSTS_DIR.exists():
        return posts

    for path in sorted(POSTS_DIR.glob("*.md")):
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))

        if not meta.get("title"):
            raise SystemExit(f"{path.name}: front matter needs a `title:`")

        raw_date = meta.get("date")
        if isinstance(raw_date, dt.datetime):
            raw_date = raw_date.date()
        if not isinstance(raw_date, dt.date):
            # Fall back to a leading YYYY-MM-DD in the filename.
            match = re.match(r"(\d{4})-(\d{2})-(\d{2})", path.stem)
            if not match:
                raise SystemExit(
                    f"{path.name}: needs a `date: YYYY-MM-DD` in front matter "
                    f"or a date prefix in the filename"
                )
            raw_date = dt.date(*(int(g) for g in match.groups()))

        post = Post(
            slug=meta.get("slug") or slugify(re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)),
            title=str(meta["title"]),
            date=raw_date,
            summary=str(meta.get("summary", "")),
            tags=[str(t) for t in (meta.get("tags") or [])],
            draft=bool(meta.get("draft", False)),
            html=markdown.markdown(
                body, extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG
            ),
        )
        if post.draft and not include_drafts:
            continue
        posts.append(post)

    posts.sort(key=lambda p: p.date, reverse=True)

    seen: set[str] = set()
    for post in posts:
        if post.slug in seen:
            raise SystemExit(f"duplicate post slug: {post.slug}")
        seen.add(post.slug)

    return posts


# Optional keys, filled in so templates can test them under StrictUndefined
# (strict mode stays on so a genuine typo in a template is a loud failure).
CV_OPTIONAL = {
    "role": "",
    "affiliation": "",
    "location": "",
    "tagline": "",
    "photo": "",
    "site_url": "",
    "about": "",
    "links": [],
    "sections": [],
}
ENTRY_OPTIONAL = {
    "date": "",
    "title": "",
    "subtitle": "",
    "detail": "",
    "url": "",
    "bullets": [],
    "tags": [],
}


def load_cv() -> dict:
    cv = yaml.safe_load((SRC / "cv.yaml").read_text(encoding="utf-8")) or {}

    if not cv.get("name"):
        raise SystemExit("src/cv.yaml: `name:` is required")

    for key, default in CV_OPTIONAL.items():
        if cv.get(key) is None:
            cv[key] = default() if callable(default) else type(default)(default)

    cv["about_html"] = markdown.markdown(cv["about"], extensions=["extra", "smarty"])

    for section in cv["sections"]:
        section.setdefault("kind", "entries")
        section.setdefault("items", [])
        if section["kind"] != "entries":
            continue
        for item in section["items"]:
            for key, default in ENTRY_OPTIONAL.items():
                if item.get(key) is None:
                    item[key] = type(default)(default)

    return cv


def clean() -> None:
    for name in GENERATED:
        target = OUT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_feed(cv: dict, posts: list[Post]) -> str:
    base = cv.get("site_url", "").rstrip("/")

    def esc(text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    items = []
    for post in posts[:20]:
        url = f"{base}/blog/{post.slug}/"
        items.append(
            "    <item>\n"
            f"      <title>{esc(post.title)}</title>\n"
            f"      <link>{esc(url)}</link>\n"
            f"      <guid isPermaLink=\"true\">{esc(url)}</guid>\n"
            f"      <pubDate>{post.date_rfc822}</pubDate>\n"
            f"      <description>{esc(post.summary or post.title)}</description>\n"
            "    </item>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n  <channel>\n'
        f"    <title>{esc(cv['name'])} — blog</title>\n"
        f"    <link>{esc(base)}/blog/</link>\n"
        f"    <description>{esc(cv.get('tagline', ''))}</description>\n"
        "    <language>en</language>\n"
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )


def build(include_drafts: bool = False) -> int:
    cv = load_cv()
    posts = load_posts(include_drafts)

    env = Environment(
        loader=FileSystemLoader(SRC / "templates"),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    year = dt.date.today().year
    common = {"cv": cv, "posts": posts, "year": year}

    clean()

    write(
        OUT / "index.html",
        env.get_template("index.html").render(page="home", root="", **common),
    )
    write(
        OUT / "blog" / "index.html",
        env.get_template("blog_index.html").render(page="blog", root="../", **common),
    )
    for post in posts:
        write(
            OUT / "blog" / post.slug / "index.html",
            env.get_template("post.html").render(
                page="blog", root="../../", post=post, **common
            ),
        )

    shutil.copytree(SRC / "static", OUT / "assets")
    write(OUT / "feed.xml", render_feed(cv, posts))
    (OUT / ".nojekyll").touch()

    print(f"built: 1 CV page, {len(posts)} post(s), feed.xml")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="serve on localhost:8000")
    parser.add_argument("--drafts", action="store_true", help="include draft posts")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    status = build(include_drafts=args.drafts)
    if status or not args.serve:
        return status

    import functools
    import http.server
    import socketserver

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        print(f"serving http://localhost:{args.port}  (ctrl-c to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
