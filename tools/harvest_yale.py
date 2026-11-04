#!/usr/bin/env python3
"""Fetch what the Yale University Art Gallery has on view (run: python3 tools/harvest_yale.py CACHE_DIR).

Two polite, slow passes, both from the museum's own open sources:
 1. The "What's On View by Floor" lists that artgallery.yale.edu/permanent-collection links to (24 works a page,
    one page every 2 seconds). Each card says the work's title, maker, type, culture, department and where it is
    on view ("On view, 2nd floor, European Art").
 2. For each of those works, its Linked Art record (CC0) on media.art.yale.edu, which gives the date, materials,
    size, credit line and the IIIF picture (open access works can be shown freely).
Results are cached in CACHE_DIR, so a rerun only fetches what is missing.
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

BASE = 'https://artgallery.yale.edu/collection?f%5B0%5D=on_view%3A'
CARD = re.compile(r'data-object-id="(\d+)"\s+data-object-title="([^"]*)"\s+data-object-creator="([^"]*)"\s+'
                  r'data-object-classification="([^"]*)"\s+data-object-culture="([^"]*)"\s+'
                  r'data-object-geography="([^"]*)"\s+data-object-department="([^"]*)"\s+'
                  r'data-object-availability="([^"]*)"')
FACET = re.compile(r'data-drupal-facet-item-value="(On view, [^"]*)" data-drupal-facet-item-count="(\d+)"')


def get(url, tries=4):
    # plain curl (the museum's site turns away Python's own HTTP client)
    for i in range(tries):
        r = subprocess.run(['curl', '-s', '-m', '90', '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = r.stdout.decode('utf-8', 'replace').rpartition('\n')
        if code == '200': return body
        if code == '404': return None
        time.sleep(10 * (i + 1))
    raise RuntimeError(url)


def cards(cache):
    path = cache / 'cards.json'
    found = json.loads(path.read_text()) if path.exists() else {}
    first = get('https://artgallery.yale.edu/collection')
    facets = [(html.unescape(v), int(n)) for v, n in FACET.findall(first) if ';' not in v]
    for value, count in facets:
        have = sum(1 for c in found.values() if value in c['where'])
        if have >= count: continue
        pages = (count + 23) // 24
        for p in range(pages):
            url = BASE + urllib.parse.quote(value) + (f'&page={p}' if p else '')
            t = get(url)
            time.sleep(2)
            for m in CARD.findall(t or ''):
                oid, title, creator, cls, culture, geo, dept, avail = (html.unescape(x) for x in m)
                found[oid] = {'id': oid, 'title': title, 'creator': creator, 'type': cls, 'culture': culture,
                              'geography': geo, 'department': dept, 'where': avail}
        print(f'{value}: {count} listed, {sum(1 for c in found.values() if value in c["where"])} found', flush=True)
        path.write_text(json.dumps(found, ensure_ascii=False))
    return found


def records(cache, ids):
    out = cache / 'lux'
    out.mkdir(exist_ok=True)
    for n, oid in enumerate(ids):
        f = out / f'{oid}.json'
        if f.exists(): continue
        t = get(f'https://media.art.yale.edu/content/lux/obj/{oid}.json')
        f.write_text(t or '{}')
        time.sleep(0.35)
        if n % 200 == 0: print(f'records {n}/{len(ids)}', flush=True)


if __name__ == '__main__':
    cache = Path(sys.argv[1])
    cache.mkdir(parents=True, exist_ok=True)
    found = cards(cache)
    print(len(found), 'works on view', flush=True)
    records(cache, sorted(found, key=int))
    print('done', flush=True)
