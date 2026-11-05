#!/usr/bin/env python3
"""Read the Fitchburg Art Museum's visit and exhibition pages, its visitor map and the FESTIVAL catalogue once,
slowly, into .cache/fitchburg.

    python3 tools/harvest_fitchburg.py

fitchburgartmuseum.org is WordPress; its robots.txt only closes /wp-admin/. We read the few pages the guide needs and
wait 3 seconds between them. The museum has no online catalogue yet ("FAM is currently conducting a full inventory"),
so the works come from its exhibition pages and from the FESTIVAL catalogue PDF, whose checklist pictures every
object in the show. The catalogue is big (about 120 MB): it is read once and kept in the cache.
"""
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'fitchburg'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://fitchburgartmuseum.org'
DELAY = 3
PAGES = ['visit', 'accessibility', 'exhibitions', 'collection', 'kaleidoscope', 'elisa-h-hamilton-heirlooms',
         'festival-a-celebration-of-african-art', 'la-bodega-de-mis-suenos', 'community-gallery',
         'discover-ancient-egypt', 'public-art', 'thurston']
FILES = ['wp-content/uploads/2026/01/VisitorMapStandard-scaled.png',          # the visitor map, January 2026
         'wp-content/uploads/2026/07/FAM-FESTIVAL-Catalog-FINAL.pdf',         # FESTIVAL catalogue with checklist
         'wp-content/uploads/2026/05/Kaleidoscope_NewPressRelease.pdf']       # Kaleidoscope press release


def get(url, dest, delay=DELAY):
    """Fetch url into dest once (cached)."""
    if dest.exists() and dest.stat().st_size > 500: return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '600', '-A', UA, url], capture_output=True).stdout
    time.sleep(delay)
    if not out:
        print('could not read', url)
        return None
    dest.write_bytes(out)
    print('read', url, flush=True)
    return out


def main():
    for slug in PAGES:
        get(f'{SITE}/{slug}/', CACHE / 'pages' / f'{slug}.html')
    for f in FILES:
        get(f'{SITE}/{f}', CACHE / 'files' / f.rsplit('/', 1)[1])


if __name__ == '__main__':
    main()
