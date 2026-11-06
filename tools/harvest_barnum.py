#!/usr/bin/env python3
"""Read the Barnum Museum's catalogue on Connecticut Collections once, slowly, into .cache/barnum.

    python3 tools/harvest_barnum.py list      every object: id, accession number, title, picture (about 30 pages)
    python3 tools/harvest_barnum.py detail    each object's and picture's page (--all: documents and books too): maker, date, medium, credit, larger picture

The museum's website (barnum-museum.org, its "Connecticut Collections" story) links its catalogue to Connecticut Collections (ctcollections.org, CollectiveAccess), source facet 1069,
1,002 objects. robots.txt there closes /Browse/*/images/* and the download and representation-info paths, so this
reads only the list view (/Browse/.../view/list) and the object pages (/Detail/objects/ID), and waits between
requests (DELAY seconds). Everything is cached, so a second run reads nothing it already has. Pictures are not
downloaded: the guide links Connecticut Collections' own "medium" and "large" images.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'barnum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
CTC = 'https://ctcollections.org/index.php'
DELAY = 2.0
TYPES = {'26': 'Still Image', '24': 'Physical Object', '27': 'Document', '1065': 'Book', '25': 'Audio'}


def get(url, dest, delay=DELAY):
    if dest.exists() and dest.stat().st_size > 500: return dest.read_text(encoding='utf-8', errors='ignore')
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(delay * (1 + 2 * attempt))
        if out: break
    else:
        print('could not read', url, flush=True)
        return None
    dest.write_bytes(out)
    return out.decode('utf-8', errors='ignore')


def rows(s, kind):
    out = []
    for m in re.finditer(r"<div class='bResultListItem' id='row(\d+)'(.*?)<!-- end bResultListItemContent", s, re.S):
        oid, body = m.groups()
        img = re.search(r"<img src='([^']+)'", body)
        links = [html.unescape(re.sub(r'<[^>]+>', '', t)).strip()
                 for t in re.findall(r'<a href="/index.php/Detail/objects/\d+">(.*?)</a>', body, re.S)]
        out.append({'oid': oid, 'acc': links[0] if links else '', 'title': links[1] if len(links) > 1 else '',
                    'thumb': img.group(1) if img else None, 'kind': kind})
    return out


def harvest_list():
    base = get(f'{CTC}/Browse/objects/facet/source_facet/id/1069/view/list', CACHE / 'list' / 'base.html')
    key = re.search(r'key/([0-9a-f]{32})', base).group(1)
    allrows = {}
    for tid, kind in TYPES.items():
        first = get(f'{CTC}/Browse/objects/key/{key}/facet/type_facet/id/{tid}/view/list',
                    CACHE / 'list' / f't{tid}_0.html')
        total = int(re.search(r'(\d+) object Results?', first).group(1))
        k2 = re.search(r'Browse/objects/s/36/key/([0-9a-f]{32})', first)
        pages = [first]
        if k2:
            for s in range(36, total, 36):
                pages.append(get(f'{CTC}/Browse/objects/s/{s}/key/{k2.group(1)}/view/list',
                                 CACHE / 'list' / f't{tid}_{s}.html') or '')
        got = 0
        for p in pages:
            for r in rows(p, kind):
                allrows.setdefault(r['oid'], r); got += 1
        print(kind, total, 'listed', got, flush=True)
    (CACHE / 'objects.json').write_text(json.dumps(list(allrows.values()), ensure_ascii=False))
    print(len(allrows), 'objects')


def harvest_detail():
    objs = json.loads((CACHE / 'objects.json').read_text())
    order = {'Still Image': 0, 'Physical Object': 1}
    objs.sort(key=lambda o: order.get(o['kind'], 2))
    if '--all' not in sys.argv:                  # by default the objects and pictures, not the documents and books
        objs = [o for o in objs if o['kind'] in ('Still Image', 'Physical Object')]
    for i, o in enumerate(objs):
        get(f'{CTC}/Detail/objects/{o["oid"]}', CACHE / 'detail' / f'{o["oid"]}.html')
        if i % 100 == 0: print(i, 'of', len(objs), flush=True)


if __name__ == '__main__':
    {'list': harvest_list, 'detail': harvest_detail}[sys.argv[1]]()
