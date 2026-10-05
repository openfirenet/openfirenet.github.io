#!/usr/bin/env python3
"""Assemble the site: every src/<page>.html is wrapped in src/layout.html and written to the repository root.

Run `python3 build.py` after editing a page in src/, then commit both the source and the generated page.
`python3 build.py --sync ../open-firenet/openapi.yaml` refreshes the API description the reference page is built from.
GitHub Pages serves the generated files as they are; nothing is built on GitHub's side.
"""
import json, pathlib, re, shutil, sys

import apiref

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
# Every page built from src/<name>.html.
PAGES = ["index", "get-started", "hardware", "compatibility", "home-assistant", "mqtt", "api", "troubleshooting",
         "contribute"]
# The navigation bar: a page (file name, label), or a group (label, [pages]) shown as a drop-down menu. The home
# page is reached through the logo.
NAV = [
    ("get-started", "Get started"),
    ("Stove & board", [("compatibility", "Stove compatibility"), ("hardware", "Hardware")]),
    ("Integrations", [("home-assistant", "Home Assistant"), ("mqtt", "MQTT"), ("api", "REST API")]),
    ("troubleshooting", "Troubleshooting"),
    ("contribute", "Contribute"),
]


def nav_html(active_name):
    active = ' class="active" aria-current="page"'
    out = []
    for entry in NAV:
        if isinstance(entry[1], str):
            name, label = entry
            out.append(f'      <a href="{name}.html"{active if name == active_name else ""}>{label}</a>')
        else:
            label, pages = entry
            inside = any(name == active_name for name, _ in pages)
            out.append(f'      <details class="nav-group{" active" if inside else ""}">')
            out.append(f'        <summary>{label}</summary>')
            out.append('        <div class="nav-menu">')
            out += [f'          <a href="{name}.html"{active if name == active_name else ""}>{sub}</a>' for name, sub in pages]
            out.append('        </div>')
            out.append('      </details>')
    return "\n".join(out)


# Pages generated from data instead of src/<name>.html: (file name, navigation entry shown as active, title,
# description, function returning the content)
def api_reference():
    return apiref.render(json.loads((SRC / "openapi.json").read_text()))


GENERATED = [
    ("api-reference", "api", "API reference - Open Firenet",
     "Every endpoint of the Open Firenet bridge, with its fields, types, units and ranges.", api_reference),
]


def sync(source):
    """Copies the OpenAPI description of the firmware repository: as it is to openapi.yaml (served for tools), and as
    JSON to src/openapi.json, which the build reads with the standard library only. Needs PyYAML."""
    import yaml
    text = pathlib.Path(source).read_text()
    (ROOT / "openapi.yaml").write_text(text)
    (SRC / "openapi.json").write_text(json.dumps(yaml.safe_load(text), indent=1, ensure_ascii=False) + "\n")
    print(f"synced the API description from {source}")


def build(check=False):
    layout = (SRC / "layout.html").read_text()
    stale = []
    sources = [(name, name, None, None, None) for name in PAGES] + GENERATED
    for name, active_name, title, description, make in sources:
        if make:
            page = f"<!-- title: {title} -->\n<!-- description: {description} -->\n{make()}\n"
        else:
            page = (SRC / f"{name}.html").read_text()
        # The first two lines of a page are its title and its description, as HTML comments.
        m = re.match(r"<!-- title: (.*?) -->\n<!-- description: (.*?) -->\n", page)
        if not m:
            sys.exit(f"src/{name}.html must start with the title and description comment lines")
        nav = nav_html(active_name)
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
    print("check ok" if check else f"built {len(sources)} pages")


if __name__ == "__main__":
    if "--sync" in sys.argv:
        sync(sys.argv[sys.argv.index("--sync") + 1])
    build(check="--check" in sys.argv)
