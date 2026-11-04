#!/usr/bin/env python3
"""Harvest the works on view at the Yale Center for British Art (run: python3 tools/harvest_ycba.py CACHE_DIR).

The museum's collection search (collections.britishart.yale.edu; its records are CC0) has an "On view" filter,
and filters by exhibition and by classification. This saves, into CACHE_DIR/onview.json, every work on view with
the current displays and the classification it is listed under, then each work's IIIF manifest
(CACHE_DIR/man/<id>.json: title, artist, medium, size, accession number, rights and the picture address).
tools/build_ycba.py turns that into the map guide's works.

Polite: one request every 1.2 seconds, and manifests already saved are not fetched again. Uses curl, like
tools/harvest_yale.py (Yale sites refuse some Python clients).
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

BASE = 'https://collections.britishart.yale.edu/'
PAUSE = 1.2
ON_VIEW = ('onview_ss', 'On view')


def get(url):
    r = subprocess.run(['curl', '-sS', '--max-time', '90', '-L', url], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'{url}: {r.stderr.strip()}')
    return r.stdout


def search(*facets):
    """Ids of every work matching all the (facet, value) pairs."""
    q = '&'.join(f'f%5B{f}%5D%5B%5D={urllib.parse.quote(v)}' for f, v in facets)
    ids, page, total = [], 0, None
    while True:
        t = get(f'{BASE}?{q}&page={page}')
        time.sleep(PAUSE)
        if total is None:
            m = re.search(r'([\d,]+) results?', t)
            total = int(m[1].replace(',', '')) if m else 0
        found = [i for i in dict.fromkeys(re.findall(r'href="/catalog/tms:(\d+)"', t)) if i not in ids]
        if not found or len(ids) >= total: break
        ids += found
        page += 1
    return ids, t if page == 0 else None


def facet_values(page, facet):
    return [urllib.parse.unquote_plus(html.unescape(v))
            for v in dict.fromkeys(re.findall(r'f\[' + facet + r'\]\[\]=([^"&]+)', page))]


def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else 'ycba-cache')
    (cache / 'man').mkdir(parents=True, exist_ok=True)
    out = cache / 'onview.json'
    if out.exists():
        works = json.loads(out.read_text())
    else:
        first = get(f'{BASE}?f%5Bonview_ss%5D%5B%5D=On%20view')
        works = {}
        for oid in search(ON_VIEW)[0]: works[oid] = {'shows': []}
        # Displays that are on now: open-ended installations ("2016 - Long Gallery 408 (…, 2016-03-29 - )")
        # and exhibitions that end this year or later.
        this_year = time.strftime('%Y')
        for ex in facet_values(first, 'exhibition_history_ss'):
            m = re.search(r'\((Yale Center for British Art), (\d{4}-\d\d-\d\d) - (\d{4}-\d\d-\d\d)?\)$', ex)
            if not m or (m[3] and m[3][:4] < str(int(this_year) - 1)): continue
            for oid in search(ON_VIEW, ('exhibition_history_ss', ex))[0]:
                works.setdefault(oid, {'shows': []})['shows'].append(ex)
        for kind in facet_values(first, 'type_ss'):
            for oid in search(ON_VIEW, ('type_ss', kind))[0]:
                works.setdefault(oid, {'shows': []})['type'] = kind
        out.write_text(json.dumps(works, indent=1))
    print(f'{len(works)} works on view')
    for i, oid in enumerate(works):
        f = cache / 'man' / f'{oid}.json'
        if f.exists() and f.stat().st_size > 500: continue
        f.write_text(get(f'https://manifests.collections.yale.edu/ycba/obj/{oid}'))
        if i % 50 == 0: print(f'  manifests {i}/{len(works)}', flush=True)
        time.sleep(PAUSE)


if __name__ == '__main__':
    main()
