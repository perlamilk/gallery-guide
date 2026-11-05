#!/usr/bin/env python3
"""Read Hancock Shaker Village's pages once, slowly, into .cache/hsv/pages.

    python3 tools/harvest_hsv.py

hancockshakervillage.org's robots.txt (Yoast) allows everything; we still wait 4 seconds between pages. We read the
building pages (shakers/museum/historic-architecture/...), the visit pages (map, hours, current exhibitions) and the
exhibition pages, and tools/build_hsv.py reads them, together with their pictures.
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'hsv'
SITE = 'https://hancockshakervillage.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 4
WANT = r'historic-architecture|/visit/|interactive-map|current-exhibitions|/exhibitions/$|/collections/$|hsv-facts|faqs'


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 1000: return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
    if out: dest.write_bytes(out)
    else: print('could not read', url)
    return True


def slug(url):
    return url.replace(SITE, '').strip('/').replace('/', '__') or 'home'


def main():
    urls = []
    for kind in ('page', 'avada_portfolio'):
        sm = CACHE / f'{kind}-sitemap.xml'
        if fetch(f'{SITE}/{kind}-sitemap.xml', sm): time.sleep(DELAY)
        locs = re.findall(r'<loc>([^<]+)</loc>', sm.read_text())
        urls += [u for u in locs if kind == 'avada_portfolio' or re.search(WANT, u)]
    for url in urls:
        if fetch(url, CACHE / 'pages' / f'{slug(url)}.html'):
            print('read', url, flush=True); time.sleep(DELAY)


if __name__ == '__main__':
    main()
