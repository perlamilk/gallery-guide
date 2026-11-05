#!/usr/bin/env python3
"""Read the Lyman Allyn Art Museum's gallery and exhibition pages once, slowly, into .cache/lymanallyn/pages.

    python3 tools/harvest_lymanallyn.py

lymanallyn.org is WordPress; its robots.txt only closes /site/wp-admin/. We read the few pages the guide needs (the
permanent galleries, the shows on view now, the collection page) and wait 3 seconds between them. Pictures are fetched
later by tools/build_lymanallyn.py, also once and cached. The online catalogue (lymanallyn.pastperfectonline.com)
answers 403 to the cloud, and it says nothing about what is on view, so it is not used.
"""
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'lymanallyn'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://www.lymanallyn.org'
DELAY = 3
PAGES = ['american-perspectives', 'louis-comfort-tiffany-in-new-london', 'playthings-of-the-past',
         'about-the-collection', 'current-exhibitions', 'isaac-sheffield-portraits-from-new-londons-whaling-era',
         'lydia-viscardi-time-takes-time', 'the-land-you-stand', 'visit', 'event-rental', 'family-visits']


def get(url, dest, delay=DELAY):
    """Fetch url into dest once (cached)."""
    if dest.exists() and dest.stat().st_size > 500: return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
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


if __name__ == '__main__':
    main()
