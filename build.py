#!/usr/bin/env python3
"""Assemble the site: every src/<page>.html is wrapped in src/layout.html and written to the repository root, and
every translation src/<language>/<page>.html to <language>/<page>.html.

Run `python3 build.py` after editing a page in src/, then commit both the source and the generated page. A change of
an English page makes its translations out of date: bring them in line, then `python3 build.py --stamp
src/fr/<page>.html` (several files can follow). `python3 build.py --check` fails while a page is not rebuilt or a
translation is missing or out of date.
`python3 build.py --sync ../open-firenet/openapi.yaml` refreshes the API description the reference page is built from.
GitHub Pages serves the generated files as they are; nothing is built on GitHub's side.
"""
import hashlib, json, pathlib, re, shutil, sys

import apiref

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
SITE = "https://openfirenet.github.io/"
# Every page built from src/<name>.html.
PAGES = ["index", "get-started", "hardware", "compatibility", "home-assistant", "mqtt", "api", "troubleshooting",
         "contribute", "screen"]
# Languages of the site. English is the reference, at the root; each other language lives in <code>/, built from
# src/<code>/<name>.html. A page with no translation (the developer pages: REST API, MQTT, API reference) is only
# in English, and the translated pages link to it.
LANGS = ["en", "fr"]
LANG_NAMES = {"en": "English", "fr": "Français", "de": "Deutsch", "it": "Italiano", "es": "Español"}
TRANSLATED = ["index", "get-started", "hardware", "compatibility", "home-assistant", "troubleshooting", "contribute",
              "screen"]
# The navigation bar: a page (file name, label key), or a group (label key, [pages]) shown as a drop-down menu. The
# home page is reached through the logo.
NAV = [
    ("get-started", "nav_get_started"),
    ("nav_stove_board", [("compatibility", "nav_compatibility"), ("hardware", "nav_hardware"), ("screen", "nav_screen")]),
    ("nav_integrations", [("home-assistant", "nav_home_assistant"), ("mqtt", "nav_mqtt"), ("api", "nav_api")]),
    ("troubleshooting", "nav_troubleshooting"),
    ("contribute", "nav_contribute"),
]
# Texts of the layout (header, navigation, footer), per language.
TEXTS = {
    "en": {
        "nav_get_started": "Get started", "nav_stove_board": "Stove & board", "nav_compatibility": "Stove compatibility",
        "nav_hardware": "Hardware", "nav_screen": "Stick screen", "nav_integrations": "Integrations",
        "nav_home_assistant": "Home Assistant", "nav_mqtt": "MQTT", "nav_api": "REST API",
        "nav_troubleshooting": "Troubleshooting", "nav_contribute": "Contribute",
        "menu": "☰ Menu", "nav_label": "Main", "lang_label": "Language",
        "footer_disclaimer": "Open Firenet is an open-source project, not affiliated with or endorsed by RIKA Innovative "
                             "Ofentechnik GmbH. The protocol was reverse-engineered for interoperability only. Use at "
                             "your own risk, no warranty.",
        "footer_contribute": "Contribute", "footer_questions": "Questions and problems",
        "footer_bridge_issues": "bridge and firmware issues", "footer_ha_issues": "Home Assistant integration issues",
        "english_only": "",
    },
    "fr": {
        "nav_get_started": "Démarrer", "nav_stove_board": "Poêle et matériel", "nav_compatibility": "Compatibilité des poêles",
        "nav_hardware": "Matériel", "nav_screen": "Écran de la clé", "nav_integrations": "Intégrations",
        "nav_home_assistant": "Home Assistant", "nav_mqtt": "MQTT (en anglais)", "nav_api": "API REST (en anglais)",
        "nav_troubleshooting": "Dépannage", "nav_contribute": "Contribuer",
        "menu": "☰ Menu", "nav_label": "Navigation principale", "lang_label": "Langue",
        "footer_disclaimer": "Open Firenet est un projet open source indépendant, sans affiliation avec RIKA Innovative "
                             "Ofentechnik GmbH ni approbation de sa part. Le protocole a été rétro-ingénié à des fins "
                             "d'interopérabilité uniquement. Utilisation sous votre propre responsabilité, sans garantie.",
        "footer_contribute": "Contribuer", "footer_questions": "Questions et support",
        "footer_bridge_issues": "issues de la clé et du firmware", "footer_ha_issues": "issues de l'intégration Home Assistant",
    },
}


def page_path(lang, name):
    """Path of a page from the site root; a page that is not translated is the English one."""
    if lang != "en" and name not in TRANSLATED:
        lang = "en"
    return ("" if lang == "en" else lang + "/") + name + ".html"


def rel(from_lang, lang, name):
    """Link from a page in from_lang to the page name in lang."""
    return ("../" if from_lang != "en" else "") + page_path(lang, name)


def absolute(lang, name):
    path = page_path(lang, name)
    return SITE + (path[:-len("index.html")] if path.endswith("index.html") else path)


# Flags of the language menu, drawn as SVG as on the bridge's page (emoji flags show as letters on Windows).
FLAGS = {
    "fr": '<rect width="1" height="2" fill="#0055a4"/><rect x="1" width="1" height="2" fill="#fff"/><rect x="2" width="1" height="2" fill="#ef4135"/>',
    "es": '<rect width="3" height="2" fill="#c60b1e"/><rect y="0.5" width="3" height="1" fill="#ffc400"/>',
    "it": '<rect width="1" height="2" fill="#009246"/><rect x="1" width="1" height="2" fill="#fff"/><rect x="2" width="1" height="2" fill="#ce2b37"/>',
    "de": '<rect width="3" height="0.67" fill="#000"/><rect y="0.67" width="3" height="0.67" fill="#dd0000"/><rect y="1.33" width="3" height="0.67" fill="#ffce00"/>',
    "en": '<rect width="3" height="2" fill="#012169"/><path d="M0 0L3 2M3 0L0 2" stroke="#fff" stroke-width="0.4"/><path d="M0 0L3 2M3 0L0 2" stroke="#c8102e" stroke-width="0.14"/><path d="M1.5 0V2M0 1H3" stroke="#fff" stroke-width="0.66"/><path d="M1.5 0V2M0 1H3" stroke="#c8102e" stroke-width="0.4"/>',
}


def flag(code):
    return f'<svg class="flag" viewBox="0 0 3 2" preserveAspectRatio="none" aria-hidden="true">{FLAGS.get(code, "")}</svg>'


def nav_html(lang, active_name, page_lang):
    t = TEXTS[lang]
    active = ' class="active" aria-current="page"'
    out = []
    link = lambda name: rel(page_lang, lang, name)
    for entry in NAV:
        if isinstance(entry[1], str):
            name, key = entry
            out.append(f'      <a href="{link(name)}"{active if name == active_name else ""}>{t[key]}</a>')
        else:
            key, pages = entry
            inside = any(name == active_name for name, _ in pages)
            out.append(f'      <details class="nav-group{" active" if inside else ""}">')
            out.append(f'        <summary>{t[key]}</summary>')
            out.append('        <div class="nav-menu">')
            out += [f'          <a href="{link(name)}"{active if name == active_name else ""}>{t[sub]}</a>'
                    for name, sub in pages]
            out.append('        </div>')
            out.append('      </details>')
    # Language menu: the same page in each language, or the language's home page when the page is English only.
    out.append(f'      <details class="nav-group nav-lang">')
    out.append(f'        <summary aria-label="{t["lang_label"]}">{flag(lang)}{LANG_NAMES[lang]}</summary>')
    out.append('        <div class="nav-menu">')
    for code in LANGS:
        target = active_name if (code == "en" or active_name in TRANSLATED) else "index"
        cur = active if code == lang else ""
        out.append(f'          <a href="{rel(page_lang, code, target)}" hreflang="{code}" lang="{code}" '
                   f'data-lang="{code}"{cur}>{flag(code)}{LANG_NAMES[code]}</a>')
    out.append('        </div>')
    out.append('      </details>')
    return "\n".join(out)


def localize_paths(html, page_lang):
    """A page in a language folder reaches the shared files and the English-only pages one level up."""
    if page_lang == "en":
        return html
    html = re.sub(r'((?:href|src)=")(assets/|openapi\.yaml)', r"\1../\2", html)
    english_only = [n for n in PAGES if n not in TRANSLATED] + [g[0] for g in GENERATED]
    return re.sub(r'(href=")((?:' + "|".join(map(re.escape, english_only)) + r')\.html)', r"\1../\2", html)


def source_hash(name):
    """Fingerprint of an English source page, written in each translation to tell when it is out of date."""
    return hashlib.sha256((SRC / f"{name}.html").read_bytes()).hexdigest()[:12]


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


HEADER = re.compile(r"(?:<!-- source: (\w+) -->\n)?<!-- title: (.*?) -->\n<!-- description: (.*?) -->\n")


def alternates(name):
    """<link rel="alternate"> lines: the page in each language it exists in, English as the default."""
    langs = [c for c in LANGS if c == "en" or name in TRANSLATED]
    if len(langs) < 2:
        return ""
    out = [f'<link rel="alternate" hreflang="{c}" href="{absolute(c, name)}">' for c in langs]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{absolute("en", name)}">')
    return "\n".join(out) + "\n"


def render(layout, lang, name, active_name, page):
    m = HEADER.match(page)
    if not m:
        sys.exit(f"the page {lang}/{name} must start with the title and description comment lines")
    t = TEXTS[lang]
    html = layout
    for key, value in t.items():
        html = html.replace("{{t:" + key + "}}", value)
    html = (html.replace("{{lang}}", lang).replace("{{title}}", m.group(2)).replace("{{description}}", m.group(3))
            .replace("{{alternates}}", alternates(name)).replace("{{page}}", name.removesuffix(".html"))
            .replace("{{nav}}", nav_html(lang, active_name, lang))
            .replace("{{content}}", page[m.end():].rstrip("\n")))
    return localize_paths(html, lang), m.group(1)


def build(check=False):
    layout = (SRC / "layout.html").read_text()
    stale, outdated, missing = [], [], []
    outputs = []
    for name in PAGES:
        outputs.append(("en", name, name, (SRC / f"{name}.html").read_text()))
    for name, active_name, title, description, make in GENERATED:
        outputs.append(("en", name, active_name, f"<!-- title: {title} -->\n<!-- description: {description} -->\n{make()}\n"))
    for lang in LANGS[1:]:
        for name in TRANSLATED:
            src = SRC / lang / f"{name}.html"
            if not src.exists():
                missing.append(f"{lang}/{name}")
                continue
            outputs.append((lang, name, name, src.read_text()))
    for lang, name, active_name, page in outputs:
        html, source = render(layout, lang, name, active_name, page)
        if lang != "en" and source != source_hash(name):
            outdated.append(f"src/{lang}/{name}.html")
        out = ROOT / page_path(lang, name)
        if check:
            if not out.exists() or out.read_text() != html:
                stale.append(str(out.relative_to(ROOT)))
        else:
            out.parent.mkdir(exist_ok=True)
            out.write_text(html)
    problems = []
    if missing:
        problems.append("translation missing: " + ", ".join(missing))
    if outdated:
        problems.append("the English page changed since this translation, update it and run build.py --stamp "
                        "<file>: " + ", ".join(outdated))
    if check and stale:
        problems.append("out of date, run build.py: " + ", ".join(stale))
    for p in problems:
        print(p, file=sys.stderr)
    if check and problems:
        sys.exit(1)
    print("check ok" if check else f"built {len(outputs)} pages")


def stamp(files):
    """Marks translations as up to date with their English page, once their text has been brought in line."""
    for f in files:
        path = pathlib.Path(f).resolve()
        name, lang = path.stem, path.parent.name
        if lang not in LANGS[1:] or name not in TRANSLATED:
            sys.exit(f"{f} is not a translated page (src/<language>/<page>.html)")
        text = HEADER.sub(lambda m: f"<!-- source: {source_hash(name)} -->\n<!-- title: {m.group(2)} -->\n"
                                     f"<!-- description: {m.group(3)} -->\n", path.read_text(), count=1)
        path.write_text(text)
        print(f"stamped {lang}/{name}")


if __name__ == "__main__":
    if "--sync" in sys.argv:
        sync(sys.argv[sys.argv.index("--sync") + 1])
    if "--stamp" in sys.argv:
        stamp(sys.argv[sys.argv.index("--stamp") + 1:])
    build(check="--check" in sys.argv)
