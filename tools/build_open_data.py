#!/usr/bin/env python3
"""Build the app's open data from Wikidata (run: python3 tools/build_open_data.py).

Writes
  data/museums.json   US art museums: name, place, coordinates, photo, website, Wikipedia article
  data/discover.json  popular artworks, artists and museums, artist pages and themes

"Popular" means how many Wikipedia language editions have an article about it (Wikidata sitelinks):
an open, honest measure of how well known something is. Pictures are Wikimedia Commons file names;
the app loads small versions from Commons when online.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
UA = 'GalleryGuidePersonal/1.0 (personal museum guide app)'
# QLever (University of Freiburg): a fast public mirror of Wikidata; the official endpoint times out on big collections
ENDPOINT = 'https://qlever.dev/api/wikidata'
PREFIXES = '''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
'''


def sparql(query, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                ENDPOINT + '?' + urllib.parse.urlencode({'query': PREFIXES + query}),
                headers={'Accept': 'application/sparql-results+json', 'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as res:
                rows = json.load(res)['results']['bindings']
            time.sleep(1)
            return [{k: v['value'] for k, v in r.items()} for r in rows]
        except urllib.error.HTTPError as e:  # 429: asked to slow down; 5xx: timeout
            wait = int(e.headers.get('Retry-After') or 0) or 30 * (attempt + 1)
            print(f'  query failed ({e.code}); waiting {wait}s', file=sys.stderr)
            time.sleep(wait)
        except Exception as e:
            print(f'  query failed ({e}); retrying', file=sys.stderr)
            time.sleep(30 * (attempt + 1))
    raise SystemExit('Wikidata did not answer; try again later')


qid = lambda uri: uri.rsplit('/', 1)[-1]
file_name = lambda uri: urllib.parse.unquote(uri.rsplit('/', 1)[-1]) if uri else None


def point(wkt):  # "Point(-71.09 42.33)" -> [lat, lon]
    lon, lat = wkt[wkt.index('(') + 1:-1].split()
    return [round(float(lat), 5), round(float(lon), 5)]


def year(v):
    try:
        return int(v[:5].lstrip('+')[:4]) if v and not v.startswith('-') else None
    except ValueError:
        return None


# ---------- museums ----------
MUSEUM_TYPES = 'wd:Q207694 wd:Q3196771 wd:Q3844310 wd:Q1007870 wd:Q3329412 wd:Q17431399 wd:Q10855061'  # art museum (two items), national gallery, art gallery, university art museum, national museum, archaeological museum

def museums():
    rows = sparql(f'''
SELECT ?m ?name ?coord ?img ?site ?article ?city ?state ?addr ?links WHERE {{
  VALUES ?type {{ {MUSEUM_TYPES} }}
  ?m wdt:P31 ?type ; wdt:P17 wd:Q30 ; wdt:P625 ?coord ; wikibase:sitelinks ?links .
  OPTIONAL {{ ?m rdfs:label ?name FILTER(LANG(?name) = "en") }}
  FILTER NOT EXISTS {{ ?m wdt:P576 ?closed }}
  OPTIONAL {{ ?m wdt:P18 ?img }}
  OPTIONAL {{ ?m wdt:P856 ?site }}
  OPTIONAL {{ ?m wdt:P6375 ?addr FILTER(LANG(?addr) = "en") }}
  OPTIONAL {{ ?article schema:about ?m ; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?m wdt:P131 ?c . ?c rdfs:label ?city FILTER(LANG(?city) = "en") }}
  OPTIONAL {{ ?m wdt:P131/wdt:P131* ?s . ?s wdt:P31 wd:Q35657 ; rdfs:label ?state FILTER(LANG(?state) = "en") }}
}}''')
    out = {}
    for r in rows:
        id_ = qid(r['m'])
        name = r.get('name') or (urllib.parse.unquote(r['article'].rsplit('/', 1)[-1]).replace('_', ' ') if r.get('article') else None)
        if not name:
            continue
        m = out.setdefault(id_, {'id': id_, 'name': name, 'at': point(r['coord']), 'links': int(r['links'])})
        for key, field, fn in [('img', 'image', file_name), ('site', 'website', str), ('city', 'city', str),
                               ('state', 'state', str), ('addr', 'address', str),
                               ('article', 'wikipedia', lambda u: urllib.parse.unquote(u.rsplit('/', 1)[-1]))]:
            if r.get(key) and field not in m:
                m[field] = fn(r[key])
    return sorted(out.values(), key=lambda m: -m['links'])


# ---------- discover ----------
def museum_works(museum_id, limit=40):
    """The best-known paintings Wikidata lists in one museum's collection."""
    rows = sparql(f'''
SELECT ?w ?title ?img ?artist ?artistName ?date ?links ?mov ?genre WHERE {{
  {{ SELECT ?w ?links WHERE {{
      ?w wdt:P195 wd:{museum_id} ; wdt:P31 wd:Q3305213 ; wdt:P18 ?anyImg ; wikibase:sitelinks ?links .
    }} ORDER BY DESC(?links) LIMIT {limit} }}
  ?w rdfs:label ?title FILTER(LANG(?title) = "en")
  ?w wdt:P18 ?img .
  OPTIONAL {{ ?w wdt:P170 ?artist . ?artist rdfs:label ?artistName FILTER(LANG(?artistName) = "en") }}
  OPTIONAL {{ ?w wdt:P571 ?date }}
  OPTIONAL {{ ?w wdt:P135 ?mov }}
  OPTIONAL {{ ?w wdt:P136 ?genre }}
}}''')
    out = {}
    for r in rows:
        id_ = qid(r['w'])
        w = out.setdefault(id_, {'id': id_, 'title': r['title'], 'image': file_name(r['img']), 'links': int(r['links']),
                                 'museumId': museum_id, '_mov': set(), '_genre': set()})
        if r.get('artistName') and 'artist' not in w:
            w['artist'], w['artistId'] = r['artistName'], qid(r['artist'])
        if r.get('date') and 'year' not in w:
            w['year'] = year(r['date'])
        if r.get('mov'):
            w['_mov'].add(qid(r['mov']))
        if r.get('genre'):
            w['_genre'].add(qid(r['genre']))
    return list(out.values())


def artist_details(ids):
    out = {}
    for i in range(0, len(ids), 100):
        values = ' '.join(f'wd:{x}' for x in ids[i:i + 100])
        for r in sparql(f'''SELECT ?a ?name ?img ?born ?died ?links WHERE {{ VALUES ?a {{ {values} }}
            ?a rdfs:label ?name FILTER(LANG(?name) = "en") . ?a wikibase:sitelinks ?links .
            OPTIONAL {{ ?a wdt:P18 ?img }} OPTIONAL {{ ?a wdt:P569 ?born }} OPTIONAL {{ ?a wdt:P570 ?died }} }}'''):
            a = out.setdefault(qid(r['a']), {'id': qid(r['a']), 'name': r['name'], 'links': int(r['links'])})
            if r.get('img') and 'image' not in a:
                a['image'] = file_name(r['img'])
            a.setdefault('born', year(r.get('born')))
            a.setdefault('died', year(r.get('died')))
    return out


def artist_works(artist_id, limit=30):
    """An artist's paintings in any US collection."""
    rows = sparql(f'''
SELECT ?w ?title ?img ?date ?coll ?collName ?links WHERE {{
  ?w wdt:P170 wd:{artist_id} ; wdt:P31 wd:Q3305213 ; wdt:P18 ?img ; wdt:P195 ?coll ; wikibase:sitelinks ?links .
  ?coll wdt:P17 wd:Q30 ; rdfs:label ?collName FILTER(LANG(?collName) = "en")
  ?w rdfs:label ?title FILTER(LANG(?title) = "en")
  OPTIONAL {{ ?w wdt:P571 ?date }}
}} ORDER BY DESC(?links) LIMIT {limit * 3}''')
    out = {}
    for r in rows:
        w = out.setdefault(qid(r['w']), {'id': qid(r['w']), 'title': r['title'], 'image': file_name(r['img']),
                                         'links': int(r['links']), 'artistId': artist_id,
                                         'museumId': qid(r['coll']), 'museum': r['collName']})
        if r.get('date') and 'year' not in w:
            w['year'] = year(r['date'])
    return sorted(out.values(), key=lambda w: -w['links'])[:limit]


def wiki_titles(ids):
    titles = {}
    for i in range(0, len(ids), 150):
        values = ' '.join(f'wd:{x}' for x in ids[i:i + 150])
        for r in sparql(f'''SELECT ?x ?article WHERE {{ VALUES ?x {{ {values} }}
            ?article schema:about ?x ; schema:isPartOf <https://en.wikipedia.org/> }}'''):
            titles[qid(r['x'])] = urllib.parse.unquote(r['article'].rsplit('/', 1)[-1])
    return titles


THEMES = [
    {'id': 'impressionism', 'kind': 'Movement', 'title': 'Impressionism', 'tagline': 'Light, colour and modern life, painted fast.',
     'wikipedia': 'Impressionism', 'test': lambda w: 'Q40415' in w['_mov']},
    {'id': 'post-impressionism', 'kind': 'Movement', 'title': 'Post-Impressionism', 'tagline': 'After the Impressionists: colour with structure and feeling.',
     'wikipedia': 'Post-Impressionism', 'test': lambda w: 'Q166713' in w['_mov']},
    {'id': 'hudson-river', 'kind': 'Movement', 'title': 'Hudson River School', 'tagline': "America's first great landscape painters.",
     'wikipedia': 'Hudson_River_School', 'test': lambda w: 'Q1393599' in w['_mov']},
    {'id': '1400s', 'kind': 'Era', 'title': 'Step into the 1400s', 'tagline': 'The century of the Renaissance.',
     'wikipedia': 'Italian_Renaissance_painting', 'test': lambda w: 1400 <= (w.get('year') or 0) < 1500},
    {'id': '1600s', 'kind': 'Era', 'title': 'The Golden Age of the 1600s', 'tagline': 'Rembrandt, Vermeer, Velázquez and their world.',
     'wikipedia': 'Baroque_painting', 'test': lambda w: 1600 <= (w.get('year') or 0) < 1700},
    {'id': 'portraits', 'kind': 'Genre', 'title': 'Faces through time', 'tagline': 'Portraits: who people wanted to be seen as.',
     'wikipedia': 'Portrait_painting', 'test': lambda w: 'Q134307' in w['_genre']},
    {'id': 'landscapes', 'kind': 'Genre', 'title': 'Into the landscape', 'tagline': 'Mountains, rivers and skies.',
     'wikipedia': 'Landscape_painting', 'test': lambda w: 'Q191163' in w['_genre']},
]


def main():
    path = os.path.join(DATA, 'museums.json')
    if '--museums' in sys.argv or not os.path.exists(path):
        print('museums…')
        ms = museums()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'source': 'Wikidata (CC0)', 'museums': ms}, f, ensure_ascii=False, separators=(',', ':'))
    ms = json.load(open(path))['museums']
    names = {m['id']: m['name'] for m in ms}
    print(f'  {len(ms)} museums')

    pool = {}
    for m in ms[:45]:
        print('  paintings in', m['name'])
        for w in museum_works(m['id']):
            w['museum'] = m['name']
            pool.setdefault(w['id'], w)
    ranked = sorted(pool.values(), key=lambda w: -w['links'])

    # artists: the best known among those with paintings in the pool
    counts = {}
    for w in ranked:
        if w.get('artistId'):
            counts[w['artistId']] = counts.get(w['artistId'], 0) + 1
    details = artist_details(list(counts))
    top = sorted((a for a in details.values() if counts.get(a['id'], 0) >= 2), key=lambda a: -a['links'])[:40]
    titles = wiki_titles([a['id'] for a in top])
    artists = {}
    for a in top:
        print('  works by', a['name'])
        ws = artist_works(a['id'])
        for w in ws:
            pool.setdefault(w['id'], w | {'artist': a['name'], '_mov': set(), '_genre': set()})
        where = {}
        for w in ws:
            where.setdefault(w['museumId'], w['museum'])
        artists[a['id']] = a | {'wikipedia': titles.get(a['id']), 'works': [w['id'] for w in ws],
                                'museums': [{'id': k, 'name': names.get(k, v)} for k, v in where.items()]}

    themes = []
    for t in THEMES:
        ws = [w for w in sorted(pool.values(), key=lambda w: -w['links']) if t['test'](w)][:24]
        themes.append({k: v for k, v in t.items() if k != 'test'} | {'works': [w['id'] for w in ws]})

    for w in pool.values():
        w.pop('_mov', None)
        w.pop('_genre', None)
    doc = {
        'source': 'Wikidata (CC0); pictures from Wikimedia Commons',
        'popularArtworks': [w['id'] for w in ranked[:30]],
        'popularArtists': [a['id'] for a in top if artists[a['id']]['works']],
        'popularMuseums': [m['id'] for m in ms[:12]],
        'themes': themes,
        'artists': artists,
        'works': pool,
    }
    with open(os.path.join(DATA, 'discover.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"  {len(pool)} works · {len(artists)} artists · " + ', '.join(f"{t['title']} {len(t['works'])}" for t in themes))


if __name__ == '__main__':
    main()
