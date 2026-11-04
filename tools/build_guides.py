#!/usr/bin/env python3
"""Build museum guides for more museums (run: python3 tools/build_guides.py).

For each museum in a batch it writes data/guides/<Wikidata id>.json, the works the app shows on
that museum's page, and updates data/guides.json, the index of museums that have a guide.

Sources, all open:
  Wikidata (CC0)            every museum: works in its collection, with a public-domain picture
                            from Wikimedia Commons when there is one
  Harvard Art Museums API   Harvard Art Museums: works on view, with gallery and floor
                            (free key from https://harvardartmuseums.org/collections/api;
                            set HARVARD_API_KEY, the key is never written to the data)

The MFA is left alone: its guide is data/artworks.json and guide.html.

Usage
  python3 tools/build_guides.py                 batch 1 (the major art museums in MA, RI and CT)
  python3 tools/build_guides.py --batch 2       another batch from BATCHES below
  python3 tools/build_guides.py Q49135 Q847508  just these museums
  python3 tools/build_guides.py --region        also add every museum in MA, RI and CT (history,
                                                science, house museums…) to data/museums.json

Requests go one at a time with a pause between them.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_open_data import sparql, qid, file_name, point, year  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
GUIDES = os.path.join(DATA, 'guides')
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'
MFA = 'Q49133'

# Museums in batches. Wikidata ids; names are only for reading this file.
BATCHES = {
    1: {  # the major art museums of Massachusetts, Rhode Island and Connecticut
        'Q3783572': 'Harvard Art Museums',
        'Q49135': 'Isabella Stewart Gardner Museum',
        'Q3152226': 'Institute of Contemporary Art, Boston',
        'Q847508': 'Worcester Art Museum',
        'Q1465805': 'Clark Art Institute',
        'Q588474': 'MASS MoCA',
        'Q2148186': 'RISD Museum',
        'Q1568434': 'Yale University Art Gallery',
        'Q6352575': 'Yale Center for British Art',
        'Q403080': 'Wadsworth Atheneum',
    },
    2: {
        'Q3373790': 'Peabody Essex Museum',
        'Q713204': 'Norman Rockwell Museum',
        'Q7005718': 'New Britain Museum of American Art',
        'Q6803132': 'Mead Art Museum',
        'Q12072937': 'Williams College Museum of Art',
        'Q1618645': 'Hill-Stead Museum',
        'Q14714982': 'Lyman Allyn Art Museum',
        'Q7367636': 'Rose Art Museum',
        'Q15694044': 'Davis Museum',
        'Q41512158': "D'Amour Museum of Fine Arts",
        'Q478013': 'Boston Athenæum',
        'Q4713992': 'Aldrich Contemporary Art Museum',
    },
}
# Wikidata keeps some of Harvard's works under the three museums that make it up.
ALSO = {'Q3783572': ['Q809600', 'Q1017269']}  # Fogg Museum, Busch–Reisinger Museum
STATES = {'Q771': 'Massachusetts', 'Q1387': 'Rhode Island', 'Q779': 'Connecticut'}
MAX_WORKS = 3000
MIN_WORKS = 20   # fewer than this and the museum gets no guide: an empty list would only mislead
ART_TYPES = {'painting', 'sculpture', 'drawing', 'print', 'watercolor painting', 'photograph', 'engraving',
             'etching', 'woodcut print', 'lithograph', 'pastel artwork', 'statue', 'bust', 'relief', 'tapestry', 'miniature painting'}


# ---------- Wikidata ----------
def wikidata_works(museum_id):
    """Works Wikidata lists in a museum's collection: the best-known first, pictures first."""
    colls = ' '.join(f'wd:{x}' for x in [museum_id, *ALSO.get(museum_id, [])])
    rows = sparql(f'''
SELECT ?w (SAMPLE(?t) AS ?title) (SAMPLE(?a) AS ?artist) (SAMPLE(?an) AS ?artistName) (SAMPLE(?d) AS ?date)
       (SAMPLE(?kind) AS ?type) (SAMPLE(?inv) AS ?accession) (SAMPLE(?im) AS ?img) (SAMPLE(?u) AS ?url)
       (SAMPLE(?ln) AS ?locName) (MAX(?sl) AS ?links) WHERE {{
  VALUES ?coll {{ {colls} }}
  ?w wdt:P195 ?coll ; rdfs:label ?t FILTER(LANG(?t) = "en")
  ?w wikibase:sitelinks ?sl .
  FILTER NOT EXISTS {{ ?w wdt:P31 wd:Q5 }}
  OPTIONAL {{ ?w wdt:P170 ?a . ?a rdfs:label ?an FILTER(LANG(?an) = "en") }}
  OPTIONAL {{ ?w wdt:P571 ?d }}
  OPTIONAL {{ ?w wdt:P31 ?k . ?k rdfs:label ?kind FILTER(LANG(?kind) = "en") }}
  OPTIONAL {{ ?w wdt:P217 ?inv }}
  OPTIONAL {{ ?w wdt:P18 ?im }}
  OPTIONAL {{ ?w wdt:P973 ?u }}
  # a room or wing of the museum (P276 also holds cities and past loans, which would mislead)
  OPTIONAL {{ ?w wdt:P276 ?loc . ?loc wdt:P361 ?coll ; rdfs:label ?ln FILTER(LANG(?ln) = "en") }}
}} GROUP BY ?w''')
    # best-known first; among equally known works, ones with a picture and paintings, sculpture,
    # drawings and prints before fragments, beads and other study pieces
    rows.sort(key=lambda r: (-int(r.get('links') or 0), not r.get('img'),
                             (r.get('type') or '') not in ART_TYPES, r.get('title') or ''))
    rows = rows[:MAX_WORKS]
    out = []
    for r in rows:
        w = {'id': qid(r['w']), 'title': r['title'], 'links': int(r.get('links') or 0)}
        if r.get('artistName'):
            w['artist'], w['artistId'] = r['artistName'], qid(r['artist'])
        if year(r.get('date')):
            w['year'] = year(r['date'])
        for key, field in [('type', 'type'), ('accession', 'accession'), ('url', 'url'), ('locName', 'location')]:
            if r.get(key):
                w[field] = r[key]
        if r.get('img'):
            w['image'] = file_name(r['img'])   # Commons file: the app asks Commons for a small version
        out.append(w)
    return out


# ---------- Harvard Art Museums API ----------
def harvard_on_view():
    key = os.environ.get('HARVARD_API_KEY')
    if not key:
        print('  (no HARVARD_API_KEY: Harvard gets Wikidata works only, without galleries)')
        return None
    fields = 'objectid,title,people,dated,datebegin,medium,classification,culture,gallery,objectnumber,url,imagepermissionlevel,primaryimageurl,creditline'
    works, page = [], 1
    while True:
        q = urllib.parse.urlencode({'apikey': key, 'gallery': 'any', 'size': 100, 'page': page, 'fields': fields})
        req = urllib.request.Request(f'https://api.harvardartmuseums.org/object?{q}', headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=60) as res:
            doc = json.load(res)
        for o in doc.get('records', []):
            g = o.get('gallery') or {}
            if not g.get('gallerynumber'):
                continue
            artist = next((p['name'] for p in sorted(o.get('people') or [], key=lambda p: p.get('displayorder') or 99)
                           if p.get('role') in (None, 'Artist', 'Maker', 'Author')), None)
            w = {'id': f"ham{o['objectid']}", 'title': o.get('title') or 'Untitled', 'onView': True,
                 'gallery': str(g['gallerynumber']), 'galleryName': g.get('name'), 'floor': str(g.get('floor', '')),
                 'url': o.get('url'), 'accession': o.get('objectnumber'), 'type': o.get('classification'),
                 'medium': o.get('medium'), 'culture': o.get('culture'), 'source': 'Harvard Art Museums API'}
            if artist:
                w['artist'] = artist
            if o.get('dated'):
                w['date'] = o['dated']
            if o.get('datebegin'):
                w['year'] = o['datebegin']
            # Harvard marks pictures anyone may show with imagepermissionlevel 0; keep only those,
            # as a link to Harvard's server (not copied into the app).
            if o.get('imagepermissionlevel') == 0 and o.get('primaryimageurl'):
                w['imageUrl'] = o['primaryimageurl'] + '?width=600'
                w['imageCredit'] = 'Harvard Art Museums'
            works.append({k: v for k, v in w.items() if v not in (None, '')})
        print(f'  Harvard page {page}/{doc["info"]["pages"]}: {len(works)} works on view')
        if page >= doc['info']['pages']:
            return works
        page += 1
        time.sleep(1)


ADAPTERS = {'Q3783572': harvard_on_view}


# ---------- every museum in the region ----------
def region_museums():
    """Every museum (any kind) in Massachusetts, Rhode Island and Connecticut."""
    states = ' '.join(f'wd:{x}' for x in STATES)
    rows = sparql(f'''
SELECT ?m ?name ?coord ?img ?site ?article ?city ?s ?addr ?links ?kindName WHERE {{
  VALUES ?s {{ {states} }}
  ?m wdt:P31/wdt:P279* wd:Q33506 ; wdt:P131+ ?s ; wdt:P625 ?coord ; wikibase:sitelinks ?links ;
     rdfs:label ?name FILTER(LANG(?name) = "en")
  FILTER NOT EXISTS {{ ?m wdt:P576 ?closed }}
  OPTIONAL {{ ?m wdt:P31 ?kind . ?kind rdfs:label ?kindName FILTER(LANG(?kindName) = "en") }}
  OPTIONAL {{ ?m wdt:P18 ?img }}
  OPTIONAL {{ ?m wdt:P856 ?site }}
  OPTIONAL {{ ?m wdt:P6375 ?addr FILTER(LANG(?addr) = "en") }}
  OPTIONAL {{ ?article schema:about ?m ; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?m wdt:P131 ?c . ?c rdfs:label ?city FILTER(LANG(?city) = "en") }}
}}''')
    out = {}
    for r in rows:
        m = out.setdefault(qid(r['m']), {'id': qid(r['m']), 'name': r['name'], 'at': point(r['coord']),
                                         'links': int(r['links']), 'state': STATES[qid(r['s'])]})
        for key, field, fn in [('img', 'image', file_name), ('site', 'website', str), ('city', 'city', str),
                               ('addr', 'address', str), ('kindName', 'kind', str),
                               ('article', 'wikipedia', lambda u: urllib.parse.unquote(u.rsplit('/', 1)[-1]))]:
            if r.get(key) and field not in m:
                m[field] = fn(r[key])
    return list(out.values())


def add_region_museums():
    path = os.path.join(DATA, 'museums.json')
    doc = json.load(open(path, encoding='utf-8'))
    have = {m['id'] for m in doc['museums']}
    new = [m for m in region_museums() if m['id'] not in have]
    doc['museums'] = sorted(doc['museums'] + new, key=lambda m: -m['links'])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f'  {len(new)} more museums in MA, RI and CT · {len(doc["museums"])} in all')


# ---------- one guide ----------
def build(museum_id, museums):
    m = museums.get(museum_id, {})
    print(f'{m.get("name", museum_id)}…')
    works = wikidata_works(museum_id)
    sources = ['Wikidata (CC0)']
    on_view = None
    if museum_id in ADAPTERS:
        on_view = ADAPTERS[museum_id]()
    if on_view:
        sources.insert(0, 'Harvard Art Museums API')
        # the museum's own on-view list comes first; Wikidata adds the rest, marked as not known to be on view
        seen = {(w.get('accession') or '').lower() for w in on_view}
        works = on_view + [w for w in works if (w.get('accession') or '').lower() not in seen]
    if len(works) < MIN_WORKS:
        print(f'  only {len(works)} works in open data: no guide yet')
        path = os.path.join(GUIDES, f'{museum_id}.json')
        if os.path.exists(path):
            os.remove(path)
        return None
    doc = {
        'museum': museum_id, 'name': m.get('name'), 'checked': date.today().isoformat(),
        'source': ' · '.join(sources), 'onViewKnown': bool(on_view),
        'note': 'Works in the collection. Unless onView is true, a work may not be on view today.',
        'works': works,
    }
    os.makedirs(GUIDES, exist_ok=True)
    with open(os.path.join(GUIDES, f'{museum_id}.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    pics = sum(1 for w in works if w.get('image') or w.get('imageUrl'))
    print(f'  {len(works)} works · {pics} with pictures' + (f' · {len(on_view)} on view' if on_view else ''))
    return {'works': len(works), 'pictures': pics, 'onView': len(on_view) if on_view else None,
            'galleries': bool(on_view), 'checked': doc['checked'], 'source': doc['source']}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--region' in sys.argv:
        print('every museum in MA, RI and CT…')
        add_region_museums()
    batch = int(sys.argv[sys.argv.index('--batch') + 1]) if '--batch' in sys.argv else 1
    ids = [a for a in args if a.startswith('Q')] or ([] if '--region' in sys.argv and not args and '--batch' not in sys.argv
                                                      else list(BATCHES[batch]))
    ids = [x for x in ids if x != MFA]
    museums = {m['id']: m for m in json.load(open(os.path.join(DATA, 'museums.json'), encoding='utf-8'))['museums']}

    index_path = os.path.join(DATA, 'guides.json')
    index = json.load(open(index_path, encoding='utf-8')) if os.path.exists(index_path) else {'museums': {}}
    for museum_id in ids:
        entry = build(museum_id, museums)
        if entry:
            index['museums'][museum_id] = entry
        else:
            index['museums'].pop(museum_id, None)
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
    print('Done. Bump VERSION in sw.js so phones pick up the new guides.')


if __name__ == '__main__':
    main()
