# openfirenet.github.io

Source of the Open Firenet website, served by GitHub Pages at https://openfirenet.github.io.

## Editing

- Page contents are in `src/<page>.html`; the common header, navigation and footer are in `src/layout.html`.
- The style is in `assets/style.css`, the images in `assets/img/`.
- After a change, run `python3 build.py` (Python standard library only) and commit both the source and the generated pages at the root. `python3 build.py --check` tells whether the generated pages are up to date.
- To add a page: create `src/<name>.html` starting with the two comment lines (`title`, `description`) and add it to `PAGES` in `build.py`.

Preview locally with `python3 -m http.server` and open http://localhost:8000.

GitHub Pages serves the files as they are (`.nojekyll`): nothing is built on GitHub's side.
