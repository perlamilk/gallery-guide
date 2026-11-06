#!/usr/bin/env python3
"""Read the Audrain Automobile Museum's pages once, slowly, into .cache/audrain/html.

    python3 tools/harvest_audrain.py

audrainautomuseum.org is a Squarespace site. Its robots.txt lists the AI crawlers in the same group as every other
robot, which only keeps robots out of /config, /search, /api/, /static/ and the ?format=json views. We read plain
pages only, 5 seconds apart: the visit pages and the cars in the current exhibition (from /current-exhibition).
tools/build_audrain.py reads them, with their pictures.
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'audrain'
SITE = 'https://www.audrainautomuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 5
PAGES = ['current-exhibition', 'tickets', 'history', '222-bellevue', 'simulators', 'contact', 'future-exhibitions',
         'digital-guide', 'plan-your-event']


def get(url):
    return subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout


def name(path):
    return path.strip('/').replace('/', '_') + '.html'


def main():
    (CACHE / 'html').mkdir(parents=True, exist_ok=True)
    paths = list(PAGES)
    i = 0
    while i < len(paths):
        p = paths[i]; i += 1
        dest = CACHE / 'html' / name(p)
        if not (dest.exists() and dest.stat().st_size > 1000):
            out = get(f'{SITE}/{p}')
            if out: dest.write_bytes(out); print('read', p, flush=True)
            else: print('could not read', p); continue
            time.sleep(DELAY)
        if p == 'current-exhibition':
            for q in re.findall(r'href="/(current-exhibition/[^"#?]+)"', dest.read_text(errors='replace')):
                if q not in paths: paths.append(q)


if __name__ == '__main__':
    main()
