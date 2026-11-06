#!/usr/bin/env python3
"""Harvest Chateau-sur-Mer's objects from the Preservation Society of Newport County's own collection site.

newportmansions.rediscoverysoftware.com is the Society's public "Digital Collections" site (linked from
newportmansions.org/our-collections). Its pages call a JSON web service (ProficioWcfService.svc); we call the same
service: a word search of the Permanent Collection directory (NEWPHIST), then each hit's image paths. One request
at a time with a pause between them; everything is cached in .cache/chateau/, so a re-run asks nothing again.

    .cache/chateau/objects.json     every object found by the searches below (all fields we use)

Then run tools/build_chateau.py.
"""
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'chateau'
SVC = 'https://newportmansions.rediscoverysoftware.com/ProficioWcfServices/ProficioWcfService.svc/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
FIELDS = 'record_id,CAT_NBR,FORM,ARTIST,CATEG_16,MAKER,MATERIAL,OBJ_MEM,WEIGHT,CREDIT_LINE,CATEG_20,CAT_NAM,file_name'
# words that find the objects made for, or kept at, Chateau-sur-Mer
WORDS = ['Chateau-sur-Mer', 'Chateau sur Mer', 'Chateau', 'Wetmore', 'George Peabody Wetmore', 'Edith Wetmore',
         'Maud Wetmore', 'William Shepard Wetmore', 'Keteltas', 'Richard Morris Hunt', 'Seth Bradford', 'Frullini',
         'Marcotte', 'Herter', 'Eastlake', 'Moon Gate', 'Gertrude', 'Annie Derby', 'Peabody']


def call(method, **kw):
    for attempt in range(5):
        try:
            req = urllib.request.Request(SVC + method, json.dumps(kw).encode(),
                                         {'Content-Type': 'application/json; charset=utf-8', 'User-Agent': UA})
            out = json.loads(urllib.request.urlopen(req, timeout=90).read())['d']
            time.sleep(2.5)
            return out
        except Exception as e:                      # the server drops a connection now and then
            print(f'  retry {method} ({e})', file=sys.stderr)
            time.sleep(15 * (attempt + 1))
    raise SystemExit(f'{method} kept failing')


def of_chateau(r):
    """Objects that name Chateau-sur-Mer, or came from the Wetmores, who built it (William Shepard Wetmore, 1852) and
    lived there until Edith and Maud Wetmore died in the 1960s; the Society bought the house and contents in 1969."""
    text = ' '.join(r.get(k, '') for k in ('FORM', 'OBJ_MEM', 'CATEG_20', 'CREDIT_LINE'))
    if re.search(r'Ch[aâ]teau[- ]sur[- ]Mer', text, re.I): return True
    prov = r.get('CATEG_20', '') + ' ' + r.get('CREDIT_LINE', '')
    return bool(re.search(r'Wetmore|Keteltas', prov))


def rows(xml):
    if not xml: return []
    return [{c.tag: (c.text or '').strip() for c in r} for r in ET.fromstring(xml)]


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / 'objects.json'
    found = json.loads(f.read_text()) if f.exists() else {}
    done_words = set(found.pop('_words', []))
    for w in WORDS:
        if w in done_words: continue
        n = call('FindItXmlStringPageCount', Words=w, TableName='objects', Directory='NEWPHIST', OnlyIfImages=False,
                 AttachedMediaOption='')
        print(f'{w}: {n}')
        for page in range(1, (int(n) + 49) // 50 + 1):
            xml = call('FindItXmlStringPage', Words=w, TableName='objects', Directory='NEWPHIST', FieldList=FIELDS,
                       SortFields='', OnlyIfImages=False, IncludeImage=False, RecordsPerPage='50',
                       PageNumber=str(page), AttachedMediaOption='')
            for r in rows(xml):
                r.pop('sortable15', None); r.pop('sortable4', None)
                found.setdefault(r['record_id'], r)
        done_words.add(w)
        f.write_text(json.dumps({**found, '_words': sorted(done_words)}, ensure_ascii=False, indent=0))
    # image paths, only for objects of Chateau-sur-Mer (see of_chateau)
    for r in found.values():
        if 'images' in r or not r.get('file_name') or not of_chateau(r): continue
        r['images'] = [x.get('FullImage', '').replace('\\', '/') for x in
                       rows(call('GetImagePaths', ImageKey=r['file_name'], Directory='NEWPHIST'))]
        f.write_text(json.dumps({**found, '_words': sorted(done_words)}, ensure_ascii=False, indent=0))
    named = [r for r in found.values() if 'images' in r]
    print(f'{len(found)} objects found, {len(named)} from Chateau-sur-Mer, '
          f'{sum(bool(r["images"]) for r in named)} with pictures')


if __name__ == '__main__':
    main()
