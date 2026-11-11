#!/usr/bin/env python3
"""Builds the Worcester Art Museum map guide's works (run: python3 tools/build_worcester.py).

The museum's collection site (worcester.emuseum.com) sits behind a bot check, so the works come
from Wikidata (CC0): everything it lists in the museum's collection (about 1,500 works, nearly all
paintings), with the picture from Wikimedia Commons when there is one. One query, no scraping.

Wikidata says what the museum owns, not what is on view or where. So each work gets the gallery
whose label on the museum's floor map matches its origin and date (GALLERY RULES below), and the app
says so ("gallery guessed… may not be on view"). Works no rule fits stay out of the map guide; they
are still in "In the Collection" on the museum page (data/guides/Q847508.json, from build_guides.py).

Writes data/worcester/artworks.json, in the same shape as data/artworks.json (MFA).
Run tools/trace_worcester.py first for data/worcester/floors.json.
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'worcester' / 'artworks.json'
MUSEUM = 'Q847508'
EXTRA_PHOTOS = json.loads((Path(__file__).resolve().parent / 'data' / 'worcester-commons-photos.json').read_text())
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'
PLACE_NOTE = ('Gallery guessed from the work’s date and origin. Wikidata lists what the museum owns, '
              'so this work may not be on view.')
QUERY = """
SELECT ?w ?wLabel ?creatorLabel ?cit ?origin ?inception ?typeLabel ?img ?acc ?matLabel WHERE {
  ?w wdt:P195 wd:%s .
  OPTIONAL { ?w wdt:P170 ?creator . OPTIONAL { ?creator wdt:P27 ?c . ?c rdfs:label ?cit FILTER(lang(?cit)='en') } }
  OPTIONAL { ?w wdt:P495 ?o . ?o rdfs:label ?origin FILTER(lang(?origin)='en') }
  OPTIONAL { ?w wdt:P571 ?inception }
  OPTIONAL { ?w wdt:P31 ?type }
  OPTIONAL { ?w wdt:P18 ?img }
  OPTIONAL { ?w p:P217 ?st . ?st ps:P217 ?acc . ?st pq:P195 wd:%s }
  OPTIONAL { ?w wdt:P186 ?mat }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}""" % (MUSEUM, MUSEUM)

AMERICA = re.compile(r'United States|American|Thirteen Colonies|Province of Massachusetts|Colony', re.I)
JAPAN = re.compile(r'Japan', re.I)
CHINA_KOREA = re.compile(r'China|Chinese|Qing|Ming|Korea|Joseon|Song dynasty|Yuan', re.I)
WEST_ASIA = re.compile(r'Ilkhanate|Iran|Persia|Safavid|Mughal|India|Timurid|Ottoman', re.I)
UNKNOWN_CREATOR = re.compile(r'^(anonymous|unknown|unidentified)', re.I)


def european(y):
    """The European gallery whose centuries (map legend) hold year y."""
    for upto, g in ((1450, '2001'), (1500, '2002'), (1550, '2003'), (1600, '2004'), (1650, '2005'),
                    (1700, '2007'), (1760, '2006'), (1810, '2008'), (1860, '2009'), (1886, '2010'), (1910, '2011')):
        if y < upto: return g
    return None


def gallery_of(w):
    y, cit, origin, typ = w.get('year'), ' '.join(w['cit']), w.get('origin') or '', w.get('type') or ''
    where = f'{cit} {origin}'
    if typ == 'mosaic': return '0-court'                                   # the Antioch mosaics
    if WEST_ASIA.search(where) or 'manuscript' in typ or typ == 'folio': return '0004'
    if JAPAN.search(where): return '0003'
    if CHINA_KOREA.search(where): return '0002'
    if y is None: return None
    if y >= 1950: return '4002'                                            # Contemporary Art
    if y >= 1910: return '4001'                                            # Modern Art
    if AMERICA.search(where):
        return '3000' if y < 1800 else '3001' if y < 1850 else '3002' if y < 1880 else '3003'
    if cit or y < 1600:                                                    # European painters, or old anonymous panels
        return european(y)
    return None


def fetch():
    url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': QUERY})
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)['results']['bindings']


def main():
    rows = json.load(open(sys.argv[1]))['results']['bindings'] if len(sys.argv) > 1 else fetch()
    floors = json.load(open(ROOT / 'data' / 'worcester' / 'floors.json'))
    rooms = {r['id']: (f['id'], r.get('name', '')) for f in floors['floors'] for r in f['rooms']}
    works = {}
    for b in rows:
        v = lambda k: b.get(k, {}).get('value')
        qid = v('w').rsplit('/', 1)[1]
        w = works.setdefault(qid, {'id': qid, 'cit': set(), 'mat': set()})
        w['title'] = v('wLabel')
        if v('creatorLabel') and not w.get('artist'): w['artist'] = v('creatorLabel')
        if v('cit'): w['cit'].add(v('cit'))
        if v('origin'): w['origin'] = v('origin')
        if v('inception') and 'year' not in w:
            m = re.match(r'(-?)0*(\d+)-', v('inception'))
            if m: w['year'] = int(m[2]) * (-1 if m[1] else 1)
        if v('typeLabel') and (not w.get('type') or w['type'] == 'painting'): w['type'] = v('typeLabel')
        if v('img'): w['image'] = urllib.parse.unquote(v('img').rsplit('/', 1)[1])
        if v('acc'): w['accession'] = v('acc')
        if v('matLabel'): w['mat'].add(v('matLabel'))
    out, skipped = [], 0
    for w in works.values():
        if re.fullmatch(r'Q\d+', w.get('title') or ''): continue           # no English title
        g = gallery_of(w)
        if not g or g not in rooms:
            skipped += 1; continue
        floor, gname = rooms[g]
        artist = w.get('artist') or ''
        if UNKNOWN_CREATOR.match(artist) or re.fullmatch(r'Q\d+', artist): artist = ''
        a = {'id': f'wam-{w["id"]}', 'title': w['title'], 'artist': artist,
             'date': str(w['year']) if w.get('year') is not None else '', 'year': w.get('year'),
             'medium': ', '.join(sorted(w['mat'])).capitalize(), 'accession': w.get('accession', ''),
             'type': (w.get('type') or '').capitalize(), 'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': PLACE_NOTE, 'url': f'https://www.wikidata.org/wiki/{w["id"]}', 'wikidata': w['id']}
        if not w.get('image'):
            # Commons photos of the work that Wikidata doesn't link yet (tools/data/worcester-commons-photos.json)
            w['image'] = EXTRA_PHOTOS.get(w['id'])
        if w.get('image'):
            a['image'] = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(w['image']) + '?width=600'
            a['imageCredit'] = 'Wikimedia Commons'
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    out.sort(key=lambda a: (a['floor'], a['gallery'], a.get('year') or 0))
    doc = {'source': 'Wikidata (CC0), pictures from Wikimedia Commons; galleries guessed from date and origin',
           'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in out: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{len(works)} works in Wikidata; {len(out)} placed on the map '
          f'({sum(1 for a in out if "image" in a)} with pictures), {skipped} without a gallery')
    for k in sorted(by): print(f'  {k} {rooms[k][1]}: {by[k]}')


if __name__ == '__main__':
    main()
