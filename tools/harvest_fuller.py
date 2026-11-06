#!/usr/bin/env python3
"""Harvest the Fuller Craft Museum's (Brockton, MA) digital archive.

collections.fullercraft.org is the museum's own public "Digital Archive" (Proficio Web Module, linked from
fullercraft.org as "Collection"). Its pages call a JSON web service (ProficioWcfService.svc); we call the same service:
every object record of the CRAFT directory (with its "On Display" field and exhibit label), and the objects linked to
each exhibition the archive lists. One request at a time with a pause between them; everything is cached in
.cache/fuller/, so a re-run asks nothing again (delete the files to refresh).

    .cache/fuller/objects.json     every object record (fields below, plus Thumbnail/FullImage paths)
    .cache/fuller/exhibits.json    {exhibition id: [record_id, ...]} for the exhibitions in the archive

Then run tools/build_fuller.py.
"""
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'fuller'
SVC = 'http://collections.fullercraft.org/ProficioWcfServices/ProficioWcfService.svc/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DIR = 'CRAFT'
FIELDS = 'record_id,CAT_NBR,CATEG_2,ARTIST,CAT_NAM,CATEG_16,MATERIAL,WEIGHT,CREDIT_LINE,USER1,ExhibitLbl,USER2,file_name'


def call(method, **kw):
    for attempt in range(5):
        try:
            req = urllib.request.Request(SVC + method, json.dumps(kw).encode(),
                                         {'Content-Type': 'application/json; charset=utf-8', 'User-Agent': UA})
            out = json.loads(urllib.request.urlopen(req, timeout=120).read())['d']
            time.sleep(3)
            return out
        except Exception as e:
            print(f'  retry {method} ({e})', file=sys.stderr)
            time.sleep(15 * (attempt + 1))
    raise SystemExit(f'{method} kept failing')


def rows(xml):
    if not xml: return []
    xml = re.sub(r'&#(x0*[0-8bcefBCEF]|x0*1[0-9a-fA-F]|0*[0-8]|0*1[1-24-9]|0*2[0-9]|0*3[01]);', ' ', xml)  # control chars
    return [{c.tag: (c.text or '').strip() for c in r} for r in ET.fromstring(xml)]


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / 'objects.json'
    if not f.exists():
        n = int(call('FindItXmlStringPageCount', Words='*', TableName='objects', Directory=DIR, OnlyIfImages=False,
                     AttachedMediaOption=''))
        print(f'{n} objects')
        found = {}
        for page in range(1, (n + 99) // 100 + 1):
            xml = call('FindItXmlStringPage', Words='*', TableName='objects', Directory=DIR, FieldList=FIELDS,
                       SortFields='', OnlyIfImages=False, IncludeImage=True, RecordsPerPage='100',
                       PageNumber=str(page), AttachedMediaOption='')
            for r in rows(xml):
                r.pop('sortable15', None)
                found[r['record_id']] = r
            print(f'  page {page}: {len(found)}')
        f.write_text(json.dumps(found, ensure_ascii=False, indent=0))
    found = json.loads(f.read_text())
    e = CACHE / 'exhibits.json'
    if not e.exists():
        exs = rows(call('FindItXmlStringPage', Words='*', TableName='exhibt', Directory=DIR,
                        FieldList='record_id,exhibt_id,exhibt_dsc', SortFields='EXHIBT_DSC', OnlyIfImages=False,
                        IncludeImage=False, RecordsPerPage='100', PageNumber='1', AttachedMediaOption=''))
        out = {}
        for x in exs:
            objs = rows(call('GetObjectRecordsForExhibitFieldsSort', Directory=DIR, readablePrimaryKey=x['exhibt_id'],
                             OnlyIfImages=False, MaxRecords=1200, ObjectsFieldList='cat_nbr;cat_nam;artist',
                             SortFields='sortable1'))
            out[x['exhibt_id']] = [o['record_id'] for o in objs]
        e.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    exhibits = json.loads(e.read_text())
    print(f'{len(found)} objects, {sum(bool(r.get("FullImage")) for r in found.values())} with pictures, '
          f'{sum(bool(r.get("USER1")) for r in found.values())} marked on display; exhibitions: '
          + ', '.join(f'{k} ({len(v)})' for k, v in exhibits.items()))


if __name__ == '__main__':
    main()
