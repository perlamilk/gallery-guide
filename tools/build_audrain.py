#!/usr/bin/env python3
"""Build the Audrain Automobile Museum (Newport, RI) map guide (run: python3 tools/build_audrain.py).

    data/audrain/floors.json     the museum's one public floor seen from above (a flat 2D plan)
    data/audrain/artworks.json   the cars in the exhibition on view now, with the museum's own photos and words
    data/audrain/images/         their pictures, made smaller for phones
    data/guides/Q4820080.json    the same list, for the museum page

First run tools/harvest_audrain.py: it reads the museum's pages into .cache/audrain/html.

The map
-------
The Audrain publishes no floor plan (its guide on Bloomberg Connects is a list of cars). The museum fills the ground
floor of the Audrain Building (Bruce Price, 1902), 222 Bellevue Avenue; the second floor is private offices. The plan
here is APPROXIMATE, put together from
  - the building's outline in OpenStreetMap (way 1170440781, "Audrain Auto Museum"), with Bellevue Avenue, the
    driveway on the north side and the RIPTA bus stops,
  - the architects' and builders' project pages (Northeast Collaborative Architects; Parker Construction): the
    shop-front walls were taken out to make one open exhibition hall under steel trusses, a two-storey arched door
    on the south side lets the cars in, and the restrooms are clad in stainless steel,
  - the museum's pages and visitors' reviews: a front desk and a small shop by the entrance on Bellevue Avenue, and
    the racing simulators.
Where the restrooms and simulators are inside the hall is a guess; the map says so.
Coordinates are metres east/north of 41.4820, -71.3082, times 12.

The cars
--------
The museum shows 15-20 cars at a time from more than 300 it can draw on, in exhibitions of a few months. Each car in
the current one has its own page under /current-exhibition (awards, highlights, story and photos). The cars are not
placed in any order the museum publishes, so they all sit in the one hall, sorted by year.
"""
import html
import io
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'audrain'
CACHE = ROOT / '.cache' / 'audrain'
MUSEUM = 'Q4820080'                     # Audrain Building (Wikidata has no item for the museum itself)
SITE = 'https://www.audrainautomuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
TODAY = date.today()
SHOW = 'Best Shown: Winners from the Audrain Collections'
SHOW_DATES = 'September 19, 2026 – January 10, 2027'
SOURCE = ('Approximate: OpenStreetMap building outline, the architects’ and builders’ project pages and the '
          'museum’s own pages')
K = 12          # pixels per metre


def P(x, y):
    """Metres east/north of 41.4820, -71.3082 -> map pixels (north up)."""
    return [round((x + 36) * K, 1), round((30 - y) * K, 1)]


def poly(*pts):
    return [P(x, y) for x, y in pts]


# The building (OpenStreetMap way 1170440781), metres east / north
NW, SW, SE, NE = (-12.9, 17.8), (-13.2, -15.5), (8.2, -17.6), (8.6, 15.7)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def at(u, v):
    """A point inside the building: u from the Bellevue Avenue (west) wall to the back (east) wall, v from the south
    end to the north end, both 0-1."""
    return lerp(lerp(SW, SE, u), lerp(NW, NE, u), v)


def box(u0, v0, u1, v1):
    return poly(at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1))


HALL = [(0, 0), (1, 0), (1, 0.38), (0.78, 0.38), (0.78, 0.66), (1, 0.66), (1, 0.78), (0.72, 0.78), (0.72, 1), (0, 1),
        (0, 0.62), (0.36, 0.62), (0.36, 0.38), (0, 0.38)]
ROOMS = [
    ('Exhibition Hall', 'gallery', f'The exhibition hall: “{SHOW}” ({SHOW_DATES})', [P(*at(u, v)) for u, v in HALL],
     'Exhibition Hall'),
    ('Lobby', 'corridor', 'Entrance lobby · front desk (tickets) · museum shop', box(0, 0.38, 0.36, 0.62), None),
]
SPACES = [
    ('Simulators', 'space', 'Racing simulators (Sector3SIMS; best for ages 9-12+; free time for members) — place '
     'approximate', box(0.72, 0.78, 1, 1), None),
    ('Restrooms', 'space', 'Restrooms (stainless steel, by Northeast Collaborative Architects) — place approximate',
     box(0.78, 0.38, 1, 0.56), None),
    ('Offices', 'space', 'Stairs and caged elevator to the second floor: private offices, not open to visitors',
     box(0.78, 0.56, 1, 0.66), None),
]
DOORS = [('Lobby', 'Exhibition Hall', at(0.36, 0.5)), ('Lobby', 'Exhibition Hall', at(0.18, 0.38)),
         ('Lobby', 'Exhibition Hall', at(0.18, 0.62)), ('Exhibition Hall', 'Simulators', at(0.86, 0.78)),
         ('Exhibition Hall', 'Restrooms', at(0.78, 0.47)), ('Exhibition Hall', 'Offices', at(0.78, 0.61))]
AMENITIES = [('entrance', *at(0, 0.5)), ('info', *at(0.12, 0.5)), ('shop', *at(0.27, 0.44)),
             ('restroom-all', *at(0.89, 0.47)), ('elevator', *at(0.89, 0.61))]
LABELS = [
    ('Bellevue Avenue', 'area', -24.5, -40),
    ('Main entrance on Bellevue Avenue', 'note', -35, 4),
    ('Big two-storey arched door on the south side: how the cars come in (not a visitors’ entrance)', 'note', -24, -22),
    ('Bus stops (RIPTA 67 and the trolley): “Bellevue & Memorial Blvd (at Tennis Hall of Fame)”, just north', 'note',
     -35, 44),
    ('International Tennis Hall of Fame (across Bellevue Ave, to the north)', 'note', -34, 58),
    ('Parking: street parking on Bellevue Avenue and nearby; no museum lot', 'note', 12, 26),
    ('One public floor · the hall is one open room under steel trusses · places of restrooms and simulators approximate',
     'note', -20, -30),
]
AREA = 'Entrance · front desk · shop · exhibition hall · simulators · restrooms'


def build_floors():
    rooms = [{'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if short else {})}
             for rid, kind, name, pl, short in ROOMS + SPACES]
    ids = {r['id'] for r in rooms}
    doors = [{'a': a, 'b': b, 'at': P(*p), 'width': 10, 'axis': 'o'} for a, b, p in DOORS]
    for d in doors:
        assert d['a'] in ids and d['b'] in ids, d
    floor = {'id': '1', 'label': 'Ground floor', 'order': 1, 'transform': [1, 0, 0], 'area': AREA,
             'rooms': rooms, 'closed': [],
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS],
             'doors': doors, 'homeView': ['Exhibition Hall']}
    return {'about': 'Built by tools/build_audrain.py. The Audrain publishes no floor plan: this one is approximate, '
                     'from the building’s outline in OpenStreetMap, the architects’ and builders’ project pages and the '
                     'museum’s pages. The museum is one open hall on the ground floor of the Audrain Building.',
            'source': SOURCE, 'units': 'metres x 12, north up', 'approximate': True, 'defaultFloor': '1',
            'galleryWord': 'Hall', 'floors': [floor]}


# ---- cars ----------------------------------------------------------------------------------------------------
_last = [0.0]


def picture(key, url):
    """Download once (politely, 4 s apart) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/audrain/images/{key}.jpg'
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        wait = _last[0] + 4 - time.time()
        if wait > 0: time.sleep(wait)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        _last[0] = time.time()
        if not out: print('  no picture from', url); return None
        raw.write_bytes(out)
    try: im = Image.open(io.BytesIO(raw.read_bytes()))
    except Exception:
        print('  not a picture:', url); raw.unlink(); return None
    im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/audrain/images/{key}.jpg'


def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:48]


def short(words, n=900):
    if len(words) <= n: return words
    cut = words[:n].rsplit('. ', 1)[0]
    return (cut + '.' if len(cut) > 300 else words[:n].rsplit(' ', 1)[0] + '…')


# Who made each car (the pages give the car's name only)
MAKERS = {
    'Panhard': 'Panhard et Levassor, Paris, France', 'Renault': 'Renault Frères, Billancourt, France',
    'American Underslung': 'American Motor Car Company, Indianapolis, Indiana',
    'Fiat': 'FIAT (Fabbrica Italiana Automobili Torino), Turin, Italy', 'Packard': 'Packard Motor Car Company, Detroit',
    'Duesenberg Model A': 'Duesenberg Automobile & Motors Company, Indianapolis',
    'Duesenberg Model J': 'Duesenberg, Inc., Indianapolis · body by Walter M. Murphy Company, Pasadena',
    'Minerva': 'Minerva Motors, Antwerp, Belgium',
    'Isotta Fraschini': 'Isotta Fraschini, Milan, Italy · body by Fleetwood Metal Body, Pennsylvania',
    'Rolls-Royce': 'Rolls-Royce of America, Springfield, Massachusetts · body by Brewster & Co.',
    'Marmon': 'Marmon Motor Car Company, Indianapolis · body by LeBaron',
    'Chrysler': 'Chrysler Corporation, Detroit', 'Alfa Romeo': 'Alfa Romeo, Milan, Italy · body by Touring (Superleggera)',
    'Pegaso': 'ENASA (Empresa Nacional de Autocamiones), Barcelona, Spain', 'Lancia': 'Lancia, Turin, Italy · body by Viotti',
    'Ferrari': 'Ferrari, Maranello, Italy · body by Pinin Farina', 'Porsche': 'Porsche, Stuttgart, Germany',
}


def maker(title):
    return next((v for k, v in MAKERS.items() if k in title), 'Audrain Automobile Museum')


def car(path):
    s = path.read_text(errors='replace')
    title = clean(re.search(r'<meta property="og:title" content="([^"]*)"', s)[1]).split(' — ')[0].strip()
    img = re.search(r'<meta property="og:image" content="([^"]*)"', s)
    m = s.find('<article'); body = s[m:s.find('</article>', m)]
    awards, notes, paras = [], [], []
    for blk in re.findall(r'data-sqsp-text-block-content>(.*?)</div>', body, re.S):
        items = [clean(x) for x in re.findall(r'<li>(.*?)</li>', blk, re.S)]
        if 'Awards' in blk[:200]:
            awards += [x for x in items if x]
            continue
        notes += [x for x in items if x]
        for p in re.findall(r'<(?:p|h\d)[^>]*>(.*?)</(?:p|h\d)>', re.sub(r'<li>.*?</li>', '', blk, flags=re.S), re.S):
            t = clean(p)
            if len(t) > 80: paras.append(t)
    return {'title': title, 'image': img[1] if img else None, 'awards': awards, 'notes': notes, 'words': ' '.join(paras),
            'url': f'{SITE}/current-exhibition/{path.stem.split("_", 1)[1]}'}


def year_of(title):
    m = re.match(r'(\d{4})\b', title)
    return int(m[1]) if m else None


def build_works():
    out = []
    for f in sorted((CACHE / 'html').glob('current-exhibition_*.html')):
        c = car(f)
        y = year_of(c['title'])
        key = f'audrain-{slugify(c["title"])}'
        im = picture(key, c['image'].replace('http://', 'https://') if c['image'] else None)
        desc = short(c['words'])
        if c['notes']: desc = (desc + ' ' if desc else '') + 'Highlights: ' + '; '.join(n.rstrip('.') for n in c['notes']) + '.'
        a = {'id': key, 'title': c['title'], 'artist': maker(c['title']), 'date': str(y) if y else None, 'year': y,
             'medium': 'Automobile', 'type': 'Car',
             'caption': ('Awards: ' + '; '.join(c['awards'])) if c['awards'] else None,
             'creditLine': 'Audrain Automobile Museum collections', 'gallery': 'Exhibition Hall',
             'galleryName': 'Exhibition hall', 'floor': '1',
             'placeNote': f'In “{SHOW}” ({SHOW_DATES}). The museum does not publish where each car stands in the hall.',
             'exhibition': f'{SHOW} ({SHOW_DATES})', 'description': desc,
             'descriptionKind': 'From the Audrain Automobile Museum’s page for this car', 'url': c['url'],
             'image': im, 'imageCredit': im and 'Audrain Automobile Museum'}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    out.sort(key=lambda a: (a.get('year') or 0, a['title']))
    return {'source': 'The Audrain Automobile Museum’s current-exhibition pages (audrainautomuseum.org)',
            'checked': TODAY.isoformat(), 'count': len(out), 'complete': True, 'artworks': out}


def build_guide(works):
    rows = [{k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                               'year': a.get('year'), 'medium': 'Automobile', 'url': a['url'],
                               'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                               'floor': '1'}.items() if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'Audrain Automobile Museum', 'checked': TODAY.isoformat(),
            'source': 'Audrain Automobile Museum website; OpenStreetMap', 'onViewKnown': True,
            'note': f'“More of an art museum than a car museum”: the Audrain can draw on more than 300 rare cars from '
                    f'1899 to today and shows 15-20 at a time in exhibitions that change every few months. On view now: '
                    f'“{SHOW}” ({SHOW_DATES}), {len(rows)} prize-winning cars from Pebble Beach and other concours. '
                    f'Next: “STEAM Power: Stationary, Marine & the Automobile” (January 16 – May 9, 2027).',
            'works': rows}


def main():
    if not (CACHE / 'html' / 'current-exhibition.html').exists():
        raise SystemExit('run tools/harvest_audrain.py first')
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works()
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} cars, {sum("image" in a for a in works["artworks"])} with pictures')


if __name__ == '__main__':
    sys.exit(main())
