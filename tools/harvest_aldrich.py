#!/usr/bin/env python3
"""Read The Aldrich Contemporary Art Museum's visit, exhibition and Sculpture Garden pages once, slowly, into
.cache/aldrich/pages.

    python3 tools/harvest_aldrich.py

thealdrich.org's robots.txt allows every page to general user agents (Content-Signal: search=yes, ai-train=no,
use=reference) and closes the site to AI *training* crawlers. This guide only reads a handful of pages for reference,
for one person's museum guide, never for training: the visit page, the exhibitions on view and the Sculpture Garden
page (its numbered map of the works outside). We wait 3 seconds between pages. Pictures are fetched later by
tools/build_aldrich.py, also once and cached. The Aldrich has no permanent collection and no online catalogue.
"""
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'aldrich'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://thealdrich.org'
DELAY = 3
PAGES = ['visit', 'exhibitions', 'exhibitions/the-aldrich-decennial-new-art-made-in-connecticut',
         'exhibitions/kristy-hughes', 'exhibitions/tim-youd-connecticut-retyped', 'page/sculpture-garden']


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


def page_path(slug):
    return CACHE / 'pages' / (slug.replace('/', '__') + '.html')


def main():
    for slug in PAGES:
        get(f'{SITE}/{slug}', page_path(slug))


if __name__ == '__main__':
    main()
