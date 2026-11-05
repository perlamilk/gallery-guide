#!/usr/bin/env python3
"""Read Old Sturbridge Village's building and collection pages once, slowly, into .cache/osv/pages.

    python3 tools/harvest_osv.py

osv.org's robots.txt allows everything; we still wait 4 seconds between pages. The building pages
(osv.org/building/...) and the collection highlights (osv.org/collection/...) are custom WordPress post types
with no REST API, so the page HTML is kept and read by tools/build_osv.py, together with their pictures.
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'osv'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DELAY = 4


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 1000: return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
    if out: dest.write_bytes(out)
    else: print('could not read', url)
    return True


def main():
    for kind, prefix in (('osv_buildings', 'b'), ('osv_collectionitems', 'c')):
        sm = CACHE / f'{kind}-sitemap.xml'
        fetch(f'https://www.osv.org/{kind}-sitemap.xml', sm)
        for url in re.findall(r'<loc>([^<]+)</loc>', sm.read_text()):
            slug = url.rstrip('/').rsplit('/', 1)[1]
            if fetch(url, CACHE / 'pages' / f'{prefix}-{slug}.html'):
                print('read', url, flush=True); time.sleep(DELAY)


if __name__ == '__main__':
    main()
