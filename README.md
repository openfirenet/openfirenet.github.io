# openfirenet.github.io

Source of the Open Firenet website, served by GitHub Pages at https://openfirenet.github.io.

## Editing

- Page contents are in `src/<page>.html`; the common header, navigation and footer are in `src/layout.html`.
- The style is in `assets/style.css`, the images in `assets/img/`.
- After a change, run `python3 build.py` (Python standard library only) and commit both the source and the generated pages at the root. `python3 build.py --check` tells whether the generated pages are up to date.
- The API reference page is generated from `src/openapi.json`, a copy of the firmware's `openapi.yaml`. After a change of the API, refresh it with `python3 build.py --sync ../open-firenet/openapi.yaml` (needs PyYAML) and commit the result.
- The site is in English, French, German, Italian and Spanish. English pages are at the root, built from `src/<page>.html`; each other language is in its own folder (`fr/`, `de/`, `it/`, `es/`), built from `src/<code>/<page>.html`. The texts of the header, menu and footer are in `TEXTS` in `build.py`.
- Each translation starts with a `<!-- source: ... -->` line, the fingerprint of the English page it was translated from. When an English page changes, `build.py` names the translations that are now out of date: bring them in line, then run `python3 build.py --stamp src/fr/<page>.html`.
- The API reference is translated through `src/<code>/openapi-strings.json`, which maps each text of the API description to its translation; resource paths, field names, types and values are not translated. `build.py` keeps that file in step with `src/openapi.json`: a new or changed text is added with an empty translation, which `--check` reports, and a text the description no longer has is dropped.
- To add a language: add its code to `LANGS`, its texts to `TEXTS` in `build.py` and to `LABELS` in `apiref.py`, translate every page listed in `TRANSLATED` into `src/<code>/`, stamp them, run `build.py` and fill `src/<code>/openapi-strings.json`.
- To add a page: create `src/<name>.html` starting with the two comment lines (`title`, `description`) and add it to `PAGES` in `build.py`, to `NAV` if it must appear in the navigation bar, and to `TRANSLATED` with its translations.

Preview locally with `python3 -m http.server` and open http://localhost:8000.

GitHub Pages serves the files as they are (`.nojekyll`): nothing is built on GitHub's side.
