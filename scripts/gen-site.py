#!/usr/bin/env python3
"""Render the repo's markdown into a static docs site for GitHub Pages.

Usage: python3 scripts/gen-site.py [--out site] [--check]

The source of truth stays the markdown in place — nothing is moved or
rewritten. This script only maps the published documents to HTML:

    README.md            -> index.html
    docs/**/README.md    -> docs/**/index.html
    docs/**/x.md         -> docs/**/x.html
    AGENTS/SECURITY/TODO -> .html
    tools/**/*.md        -> .html   (skipping test fixtures)

Links are rewritten to keep working inside the site: relative `.md` links
become `.html`, and anything outside the published set (source files, the
LICENSE, test fixtures) points at the GitHub blob/tree URL instead of 404ing.

Requires: pip install markdown
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import markdown
except ImportError:  # reported in main(), so --help still works
    markdown = None

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/carteakey/alvidaa"
BRANCH = "main"

# Published documents, in sidebar order. Everything under docs/ and tools/*.md
# is picked up automatically; these are the root-level pages.
ROOT_PAGES = ["README.md", "AGENTS.md", "SECURITY.md", "TODO.md"]
SCAN_DIRS = ["docs", "tools"]
SKIP_PARTS = {"fixtures", "node_modules", ".git"}

SECTIONS = [
    ("Start here", ["README.md", "AGENTS.md", "docs/README.md", "TODO.md", "SECURITY.md"]),
    ("Model guides", ["docs/models/"]),
    ("Research", ["docs/research/"]),
    ("Launcher", ["docs/launcher/"]),
    ("Project", ["docs/project/"]),
    ("Tooling", ["tools/"]),
]

CSS = """
:root{
  --bg:#0d1117; --panel:#161b22; --line:#21262d; --fg:#c9d1d9;
  --dim:#8b949e; --accent:#58a6ff; --ok:#3fb950; --warn:#d29922;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em}
code{background:#1f242c;padding:.15em .35em;border-radius:4px}
pre{background:#0b0f14;border:1px solid var(--line);border-radius:8px;
  padding:14px 16px;overflow:auto;line-height:1.5}
pre code{background:none;padding:0}
#wrap{display:flex;min-height:100vh}
#side{width:290px;flex:0 0 290px;background:var(--panel);border-right:1px solid var(--line);
  padding:18px 14px 60px;position:sticky;top:0;height:100vh;overflow:auto}
#side .brand{font-weight:700;font-size:18px;letter-spacing:.3px;margin:0 0 2px}
#side .brand a{color:var(--fg)}
#side .tag{color:var(--dim);font-size:12px;margin-bottom:14px}
#filter{width:100%;background:#0d1117;border:1px solid var(--line);color:var(--fg);
  border-radius:6px;padding:7px 9px;font-size:13px;margin-bottom:14px}
#side h4{margin:18px 0 6px;font-size:11px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--dim);font-weight:600}
#side ul{list-style:none;margin:0;padding:0}
#side li a{display:block;padding:3px 6px;border-radius:5px;font-size:13.5px;color:var(--fg)}
#side li a:hover{background:#1f242c;text-decoration:none}
#side li a.on{background:#1f2a37;color:var(--accent)}
#side ul ul{margin-left:10px;border-left:1px solid var(--line);padding-left:6px}
main{flex:1;min-width:0;padding:34px 44px 90px;max-width:900px}
.crumb{color:var(--dim);font-size:12.5px;margin-bottom:10px}
h1,h2,h3,h4{line-height:1.3;margin:1.6em 0 .5em;font-weight:650}
h1{font-size:2em;margin-top:0;padding-bottom:.3em;border-bottom:1px solid var(--line)}
h2{font-size:1.45em;padding-bottom:.25em;border-bottom:1px solid var(--line)}
h3{font-size:1.15em}
hr{border:0;border-top:1px solid var(--line);margin:2em 0}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;margin:1.2em 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top}
th{background:var(--panel);font-weight:600;white-space:nowrap}
tr:nth-child(even) td{background:#10151b}
blockquote{margin:1.2em 0;padding:.2em 1em;border-left:3px solid var(--warn);color:var(--dim)}
img{max-width:100%}
.foot{margin-top:60px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--dim);font-size:13px;display:flex;gap:18px;flex-wrap:wrap}
#menu{display:none}
@media(max-width:900px){
  #wrap{display:block}
  #side{position:static;width:auto;height:auto;border-right:0;border-bottom:1px solid var(--line)}
  #side.closed{display:none}
  #menu{display:block;position:fixed;right:14px;bottom:14px;z-index:9;
    background:var(--accent);color:#06101f;border:0;border-radius:999px;
    padding:11px 18px;font-weight:700;font-size:14px}
  main{padding:22px 18px 90px}
}
"""

JS = """
document.getElementById('filter').addEventListener('input',function(e){
  var q=e.target.value.toLowerCase();
  document.querySelectorAll('#side li').forEach(function(li){
    var a=li.querySelector('a'); if(!a) return;
    li.style.display = a.textContent.toLowerCase().indexOf(q)>-1 ? '' : 'none';
  });
});
document.getElementById('menu').addEventListener('click',function(){
  document.getElementById('side').classList.toggle('closed');
});
"""


def published() -> list:
    """Every markdown file that becomes a page, as repo-relative posix paths."""
    out = [p for p in ROOT_PAGES if (ROOT / p).exists()]
    for base in SCAN_DIRS:
        for path in sorted((ROOT / base).rglob("*.md")):
            rel = path.relative_to(ROOT)
            if SKIP_PARTS & set(rel.parts):
                continue
            out.append(rel.as_posix())
    return out


def page_url(rel: str) -> str:
    p = Path(rel)
    if p.name == "README.md":
        parent = p.parent.as_posix()
        return "index.html" if parent == "." else parent + "/index.html"
    return p.with_suffix(".html").as_posix()


def title_of(rel: str) -> str:
    try:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return Path(rel).stem
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return Path(rel).stem


def slugger():
    """GitHub-compatible heading anchors (keeps `_`, drops punctuation)."""
    seen = {}

    def slug(value, separator="-"):
        base = re.sub(r"[^\w\s-]", "", value.strip().lower())
        base = re.sub(r"\s", separator, base)
        n = seen.get(base, 0)
        seen[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    return slug


def gh_url(rel: str) -> str:
    target = ROOT / rel
    kind = "tree" if target.is_dir() else "blob"
    return f"{REPO}/{kind}/{BRANCH}/{rel}"


def rewrite_links(html: str, src_rel: str, pages: dict) -> str:
    src_dir = Path(src_rel).parent.as_posix()

    def fix(match):
        attr, value = match.group(1), match.group(2)
        if not value or value.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
            return match.group(0)
        path, _, frag = value.partition("#")
        if not path:
            return match.group(0)
        joined = os.path.normpath(os.path.join(src_dir, path)).replace(os.sep, "/")
        if joined.startswith(".."):
            return f'{attr}="{gh_url(path.lstrip("./"))}"'
        target = joined.rstrip("/")
        if target in pages:
            dest = pages[target]
        elif (target + "/README.md") in pages:
            dest = pages[target + "/README.md"]
        elif (ROOT / target).exists():
            return f'{attr}="{gh_url(target)}"'
        else:
            return f'{attr}="{gh_url(target)}"'
        rel = os.path.relpath(dest, src_dir or ".").replace(os.sep, "/")
        return f'{attr}="{rel}{("#" + frag) if frag else ""}"'

    return re.sub(r'(href|src)="([^"]*)"', fix, html)


def build_tree(pages: dict) -> list:
    """Sidebar sections -> list of (heading, [(depth, title, url)])."""
    out = []
    claimed = set()
    for heading, prefixes in SECTIONS:
        items = []
        for prefix in prefixes:
            for rel in pages:
                if rel in claimed:
                    continue
                # archived vendor notes stay published and linkable, but they
                # are not navigation
                if "/source/" in rel:
                    continue
                if prefix.endswith("/"):
                    if not rel.startswith(prefix):
                        continue
                elif rel != prefix:
                    continue
                claimed.add(rel)
                depth = rel.count("/")
                items.append((depth, title_of(rel), pages[rel]))
        if items:
            # README first within a directory, then alphabetical
            items.sort(key=lambda it: (it[2].replace("index.html", "!index.html"), it[2]))
            out.append((heading, items))
    return out


def render(page_rel: str, pages: dict, nav: list) -> str:
    text = (ROOT / page_rel).read_text(encoding="utf-8", errors="ignore")
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {"slugify": slugger(), "permalink": False}},
    )
    body = md.convert(text)
    body = rewrite_links(body, page_rel, pages)

    url = pages[page_rel]
    depth = url.count("/")
    up = "../" * depth

    side = []
    for heading, items in nav:
        side.append(f"<h4>{heading}</h4><ul>")
        for depth, title, href in items:
            rel_href = os.path.relpath(href, os.path.dirname(url) or ".").replace(os.sep, "/")
            on = ' class="on"' if href == url else ""
            pad = f' style="padding-left:{6 + min(max(0, depth - 1), 2) * 10}px"' if depth > 1 else ""
            side.append(f'<li><a{on} href="{rel_href}"{pad}>{title}</a></li>')
        side.append("</ul>")

    crumb = " / ".join(Path(page_rel).with_suffix("").parts[:-1]) or "alvidaa"
    edit = f"{REPO}/blob/{BRANCH}/{page_rel}"
    page_title = title_of(page_rel)
    doc_title = "alvidaa — VIDAA launcher & root research" if page_title == "alvidaa" else f"{page_title} — alvidaa"

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{doc_title}</title>
<style>{CSS}</style>
</head><body>
<div id="wrap">
<aside id="side">
  <div class="brand"><a href="{up}index.html">alvidaa</a></div>
  <div class="tag">Hisense VIDAA launcher &amp; root research</div>
  <input id="filter" placeholder="filter pages…" aria-label="filter pages">
  {''.join(side)}
</aside>
<main>
  <div class="crumb">{crumb}</div>
  {body}
  <div class="foot">
    <a href="{edit}">Edit this page on GitHub</a>
    <a href="{REPO}">Repository</a>
    <a href="{REPO}/blob/{BRANCH}/SECURITY.md">Disclosure stance</a>
  </div>
</main>
</div>
<button id="menu">pages</button>
<script>{JS}</script>
</body></html>
"""


def build(out: Path) -> int:
    pages = {rel: page_url(rel) for rel in published()}
    nav = build_tree(pages)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    for rel, url in pages.items():
        dest = out / url
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(rel, pages, nav), encoding="utf-8")
    return len(pages)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="site", help="output directory (default: site)")
    ap.add_argument("--check", action="store_true", help="build to a temp dir and report")
    args = ap.parse_args()

    try:
        import markdown  # noqa: F401
    except ImportError:
        print("gen-site: the 'markdown' package is required (pip install markdown)", file=sys.stderr)
        return 2
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            n = build(Path(tmp))
        print(f"site builds: {n} pages")
        return 0

    n = build((ROOT / args.out) if not os.path.isabs(args.out) else Path(args.out))
    print(f"site: {n} pages -> {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
