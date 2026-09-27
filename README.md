# Opera Log

A list of every opera I've attended, with charts of my most-seen operas and composers, published with GitHub Pages.

## Updating

1. Edit `data/operas.csv`. Add one row per performance; row order doesn't matter.
   - `Date` is written as `YYYY-MM-DD` (`DD/MM/YYYY` also works).
   - `Time` is written as `HH:MM`. Leave any column blank if you don't know it.
2. Commit and push to `main`. A GitHub Action rebuilds the page and deploys it.

To preview on your own computer, run `python3 build.py` and open `_site/index.html`. You only need Python 3; there's nothing to install.

## One-time setup

In the repo on GitHub, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
