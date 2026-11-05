#!/usr/bin/env python3
"""Read Chesterwood's pages once, slowly, into .cache/chesterwood/pages.

    python3 tools/harvest_chesterwood.py

chesterwood.org is a Squarespace site; its robots.txt gives every robot the same rules (only /config, /search,
/account, /api and /static are closed). We still wait 5 seconds between pages, and read only the visit, grounds,
residence, studio, gallery and collection pages. tools/build_chesterwood.py reads them, with their pictures.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'chesterwood'
SITE = 'https://www.chesterwood.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 5
PAGES = ['', 'home-1', 'hours-admissions', 'the-grounds-2025', 'the-grounds', 'the-studio-2025',
         'the-residence-and-studio', 'new-gallery', 'upcoming-exhibitions', 'the-collection-2025', 'the-collection',
         'the-collection-2', 'the-collection-3', 'the-collection-4', 'the-collection-5', 'the-collection-nk8mh',
         'daniel-chester-french', 'lincoln-memorial', 'andromeda-at-chesterwood', 'french-work-world', 'book-now',
         'artists-in-residence', 'contemporary-sculpture-show-map', 'contemporary-scultpure-show-map-2020']


def main(pages):
    for p in pages:
        dest = CACHE / 'pages' / f'{p or "home"}.html'
        if dest.exists() and dest.stat().st_size > 1000: continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, f'{SITE}/{p}'], capture_output=True).stdout
        if out: dest.write_bytes(out); print('read', p or 'home', flush=True)
        else: print('could not read', p)
        time.sleep(DELAY)


if __name__ == '__main__':
    main(sys.argv[1:] or PAGES)
