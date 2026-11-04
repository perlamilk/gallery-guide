#!/usr/bin/env python3
"""Download what the New Bedford Whaling Museum guide is built from (then run tools/build_nbwm.py).

whalingmuseum.org is a WordPress site. Its pages answer 403 to scripts (Cloudflare), but its robots.txt allows
everything and its WordPress REST API (/wp-json/wp/v2/...) and uploaded files (/wp-content/uploads/...) answer
normally. We read:

  .cache/nbwm/exhibitions.json   every exhibition post (title, text, pictures with captions, category)
  .cache/nbwm/page-<id>.json     the Permanent Exhibitions page, the whale skeleton pages, the plastic scrimshaw page
  .cache/nbwm/self-guide.pdf     the museum's 2026 self-guide with its map of all three levels (traced for the map)

The museum's collection database (newbedford.emuseum.com) is behind a Cloudflare check and is not used.
One request a second; everything is cached, so running this again only fetches what is missing.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'nbwm'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
API = 'https://www.whalingmuseum.org/wp-json/wp/v2'
PAGES = {5574: 'Permanent Exhibitions', 2531: 'Skeletons of the Deep', 2540: 'Blue Whale', 2546: 'Humpback Whale',
         2547: 'North Atlantic Right Whale', 2554: 'Sperm Whale', 7877: 'Plastic Scrimshaw'}
SELF_GUIDE = 'https://www.whalingmuseum.org/wp-content/uploads/2026/01/General-Self-Guide-2026.pdf'


def get(url, dest):
    if dest.exists() and dest.stat().st_size > 0: return
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '120', '-A', UA, url], capture_output=True).stdout
    time.sleep(1)
    if not out: raise SystemExit(f'could not download {url}')
    dest.write_bytes(out)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    ex = CACHE / 'exhibitions.json'
    if not ex.exists():
        rows = []
        for page in (1, 2, 3):
            part = CACHE / f'exhibitions-{page}.json'
            try:
                get(f'{API}/exhibition?per_page=100&page={page}', part)
            except SystemExit:
                break
            got = json.loads(part.read_text())
            if not isinstance(got, list) or not got: break
            rows += got
            part.unlink()
        ex.write_text(json.dumps(rows, ensure_ascii=False))
    for pid in PAGES:
        get(f'{API}/pages/{pid}', CACHE / f'page-{pid}.json')
    get(SELF_GUIDE, CACHE / 'self-guide.pdf')
    print(f'{len(json.loads(ex.read_text()))} exhibitions, {len(PAGES)} pages, self-guide map cached in {CACHE}')


if __name__ == '__main__':
    sys.exit(main())
