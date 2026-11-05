#!/usr/bin/env python3
"""Read Rough Point's pages on newportrestoration.org once, slowly, into .cache/roughpoint/html.

    python3 tools/harvest_roughpoint.py

newportrestoration.org is a WordPress site; its robots.txt (Yoast) disallows nothing for any robot. We still wait 5
seconds between pages and read only the visit pages, the Collection highlights (collection-sitemap.xml) and the
exhibition pages. tools/build_roughpoint.py reads them, with their pictures.
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'roughpoint'
SITE = 'https://www.newportrestoration.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 5
PAGES = ['plan-a-visit/', 'buy-tickets/', 'properties/680-bellevue-avenue/', 'collection/', 'exhibitions/',
         'programs-initiatives/telling-stories-dispersed-monument/rough-point/', 'a-rough-point-holiday-staff-remembers-rough-point/',
         'about-nrf/people/founder-doris-duke/']


def get(url):
    return subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout


def name(path):
    return path.strip('/').replace('/', '_') + '.html'


def main():
    (CACHE / 'html').mkdir(parents=True, exist_ok=True)
    paths = list(PAGES)
    for sm in ('collection', 'exhibition'):
        f = CACHE / f'sm_{sm}.xml'
        if not f.exists():
            f.write_bytes(get(f'{SITE}/{sm}-sitemap.xml')); time.sleep(DELAY)
        for u in re.findall(r'<loc>([^<]+)</loc>', f.read_text()):
            if 'wp-content' in u: continue
            p = u.replace(SITE + '/', '')
            if p.count('/') >= 2 and p not in paths: paths.append(p)
    for p in paths:
        dest = CACHE / 'html' / name(p)
        if dest.exists() and dest.stat().st_size > 1000: continue
        out = get(f'{SITE}/{p}')
        if out: dest.write_bytes(out); print('read', p, flush=True)
        else: print('could not read', p)
        time.sleep(DELAY)


if __name__ == '__main__':
    main()
