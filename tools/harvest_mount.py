#!/usr/bin/env python3
"""Read The Mount's pages once, slowly, into .cache/mount/pages.

    python3 tools/harvest_mount.py            (or name pages: python3 tools/harvest_mount.py the-mansion)

edithwharton.org is a WordPress site; its robots.txt (Yoast) disallows nothing for any robot. We still wait 5 seconds
between pages and read only the visit, estate, house, garden, exhibition and library pages.
tools/build_mount.py reads them, with their pictures.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'mount'
SITE = 'https://edithwharton.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 5
PAGES = ['', 'the-estate', 'the-mansion', 'the-gardens', 'the-stable', 'hours-admission', 'directions-parking',
         'terrace-cafe', 'accessibility', 'tours', 'sculpture-at-the-mount', 'bookstore', 'online-exhibits',
         'life-in-the-dale', 'writing-the-age-of-innocence-tour', 'library-insights', 'edith-wharton-biography',
         'thomas-reynolds-online-exhibition', 'nightwood', 'ghost-tours', 'artist-statement-biographies',
         'photography-film-and-video-policies', 'edith-whartons-legacy']


def main(pages):
    for p in pages:
        dest = CACHE / 'pages' / f'{p or "home"}.html'
        if dest.exists() and dest.stat().st_size > 1000: continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, f'{SITE}/{p}{"/" if p else ""}'],
                             capture_output=True).stdout
        if out: dest.write_bytes(out); print('read', p or 'home', flush=True)
        else: print('could not read', p)
        time.sleep(DELAY)


if __name__ == '__main__':
    main(sys.argv[1:] or PAGES)
