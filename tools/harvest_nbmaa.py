#!/usr/bin/env python3
"""Read the New Britain Museum of American Art's public collection site (ink.nbmaa.org, eMuseum), politely.

    python3 tools/harvest_nbmaa.py OUT.json

Pages through the "all objects" list (12 works a page, about 800 pages, one page every 1.5 s) and the
museum's themed collections ("Colonial & Federal Period", "American Impressionism", ...), and writes one
record per work: eMuseum id, title, artist, date, medium, object number, picture id and the themes it is in.
Resumable: pages already read are kept in OUT.json.partial.
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = 'https://ink.nbmaa.org'
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'
PAUSE = 1.5
COLLECTIONS = {
    'colonial': '6/colonial--federal-period',
    'genre': '13/19th-century-genre-academic-paintings--sculpture',
    'hudson': '46816/19th-century-landscapes-and-the-hudson-river-school',
    'ctlandscape': '5393/connecticut-landscape',
    'impressionism': '14/american-impressionism',
    'modernism': '16/early-modernism-1900--1945',
    'regionalism': '17/social-realismregionalism--thomas-hart-benton',
    'contemporary': '18/post-wwii--contemporary-art',
    'illustration': '47072/low-illustration-collection',
}

ITEM = re.compile(r'<div data-emuseum-id="(\d+)" class="item list-item.*?(?=<div data-emuseum-id=|<div class="bottom-pager"|$)', re.S)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:  # network hiccup: wait and retry
            print('  retry', url, e, file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(url)


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def parse(page):
    out = []
    for m in ITEM.finditer(page):
        block = m.group(0)
        link = re.search(r'href="/objects/(\d+)/([^;"?]*)', block)
        if not link: continue
        rec = {'oid': int(link[1]), 'slug': link[2]}
        img = re.search(r'/internal/media/dispatcher/(\d+)/', block)
        if img: rec['media'] = int(img[1])
        fields = re.findall(r'<div class="text-wrap">(.*?)</div>', block, re.S)
        vals = [text(f) for f in fields]
        if vals: rec['title'] = vals[0]
        for v in vals[1:]:
            k, sep, rest = v.partition(': ')
            if sep and k in ('Date', 'Medium', 'Object number'):
                rec[{'Date': 'date', 'Medium': 'medium', 'Object number': 'number'}[k]] = rest
            elif 'artist' not in rec and not sep:
                rec['artist'] = v
        out.append(rec)
    return out


def pages(path):
    n = 1
    while True:
        page = get(f'{BASE}/{path}?page={n}')
        items = parse(page)
        yield n, items
        if not items or n >= 400: return
        n += 1
        time.sleep(PAUSE)


def main():
    out = Path(sys.argv[1])
    part = out.with_suffix(out.suffix + '.partial')
    state = json.loads(part.read_text()) if part.exists() else {'all': {}, 'themes': {}}
    for key, path in COLLECTIONS.items():
        if key in state['themes']: continue
        ids = []
        for n, items in pages(f'collections/{path}/objects/list'):
            ids += [i['oid'] for i in items]
            for i in items: state['all'].setdefault(str(i['oid']), i)
        state['themes'][key] = ids
        print(key, len(ids), flush=True)
        part.write_text(json.dumps(state))
        time.sleep(PAUSE)
    done = set(state.get('pagesDone', []))
    n = 1
    while True:
        if n not in done:
            page = get(f'{BASE}/search/*/objects/list?page={n}')
            items = parse(page)
            for i in items: state['all'].setdefault(str(i['oid']), i)
            state.setdefault('pagesDone', []).append(n)
            if n % 25 == 0:
                part.write_text(json.dumps(state))
                print('page', n, len(state['all']), flush=True)
            if not items: break
            time.sleep(PAUSE)
        n += 1
    themes = {}
    for key, ids in state['themes'].items():
        for i in ids: themes.setdefault(str(i), []).append(key)
    works = []
    for oid, rec in state['all'].items():
        if oid in themes: rec['themes'] = themes[oid]
        works.append(rec)
    out.write_text(json.dumps({'source': BASE, 'harvested': time.strftime('%Y-%m-%d'), 'works': works},
                              ensure_ascii=False))
    print('works', len(works))


if __name__ == '__main__':
    main()
