#!/usr/bin/env python3
"""Assemble the site: every src/<page>.html is wrapped in src/layout.html and written to the repository root.

Run `python3 build.py` after editing a page in src/, then commit both the source and the generated page.
GitHub Pages serves the generated files as they are; nothing is built on GitHub's side.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
# (file name, label in the navigation bar)
PAGES = [
    ("index", "Home"),
    ("get-started", "Get started"),
    ("compatibility", "Compatibility"),
    ("home-assistant", "Home Assistant"),
    ("api", "API"),
    ("troubleshooting", "Troubleshooting"),
]


def build(check=False):
    layout = (SRC / "layout.html").read_text()
    stale = []
    for name, _ in PAGES:
        page = (SRC / f"{name}.html").read_text()
        # The first two lines of a page are its title and its description, as HTML comments.
        m = re.match(r"<!-- title: (.*?) -->\n<!-- description: (.*?) -->\n", page)
        if not m:
            sys.exit(f"src/{name}.html must start with the title and description comment lines")
        active = ' class="active" aria-current="page"'
        nav = "\n".join(
            f'      <a href="{n}.html"{active if n == name else ""}>{label}</a>' for n, label in PAGES
        )
        html = (layout.replace("{{title}}", m.group(1)).replace("{{description}}", m.group(2))
                .replace("{{nav}}", nav).replace("{{content}}", page[m.end():].rstrip("\n")))
        out = ROOT / f"{name}.html"
        if check:
            if not out.exists() or out.read_text() != html:
                stale.append(out.name)
        else:
            out.write_text(html)
    if check and stale:
        sys.exit("out of date, run build.py: " + ", ".join(stale))
    print("check ok" if check else f"built {len(PAGES)} pages")


if __name__ == "__main__":
    build(check="--check" in sys.argv)
