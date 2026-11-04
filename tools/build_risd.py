#!/usr/bin/env python3
"""Build the RISD Museum map guide (run: python3 tools/build_risd.py [wikidata.json]).

    data/risd/floors.json    five levels seen from above (a flat 2D plan)
    data/risd/artworks.json  works the RISD Museum owns (Wikidata, CC0) in the gallery where they most likely hang

The map: the museum's own "Floor 3 & 4" plan (RISD Museum map, 2020 edition, an image-only PDF) gives the
main gallery level: the Benefit Street entrance, Café Pearl, the Farago Wing, the Radeke Building (Modern and
Contemporary, Prints, Drawings and Photographs, Radeke Garden, Danforth Hall) and, across the bridge, the
Chace Center's special exhibition galleries. Coordinates are pixels of that plan rendered at 90 dpi.

The other levels are not drawn on any map we could reach (risdmuseum.org blocks automated reading, even from
Grazi's Mac). They come from the museum's 2018 section map, which says what is on each floor of each building
and where the elevators, restrooms, café, coat check, lockers and entrances are. Their rooms are laid inside the
same buildings' outlines, so they are approximate; each of those floors says so.

The works: Wikidata says which works the museum owns, not which are on view or where. Each work is put in the
gallery whose subject (from the museum's floor guide) fits its artist, date, country and type best; the work
page says so.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'risd'
MUSEUM = 'Q2148186'
SOURCE = 'RISD Museum map, 2020 edition (Floor 3 & 4 plan) and the 2018 RISD Museum section map'
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# Chace Center (North Main Street side): the same outline on floors 1, 2 and 3
CHACE_LOW = [[918, 610], [1157, 610], [1157, 950], [948, 985], [938, 805], [918, 805]]
CHACE_HIGH = rect(958, 397, 1157, 548)
CHACE_LANDING = rect(918, 397, 958, 548)
CHACE_CORE = rect(918, 548, 1157, 610)
# Radeke Building + Pendleton House (Benefit Street side)
RADEKE_HALL = rect(350, 205, 495, 478)     # stairs and the Radeke elevator, upper floors

# (id, kind, name, poly, short label for galleries)
ROOMS = {
    '1': [
        ('Chace Lobby', 'corridor', 'Chace Lobby · North Main Street entrance', CHACE_LOW, None),
        ('1-core', 'corridor', 'Elevators and restrooms', CHACE_CORE, None),
        ('RISD Works', 'space', 'RISD Works · museum shop', rect(918, 397, 1040, 548), None),
        ('Metcalf Auditorium', 'space', 'Metcalf Auditorium', rect(1040, 397, 1157, 548), None),
    ],
    '2': [
        ('Gelman Gallery', 'gallery', 'Gelman Gallery · RISD student galleries', CHACE_LOW, 'Gelman'),
        ('2-core', 'corridor', 'Elevators and restrooms', CHACE_CORE, None),
        ('2-landing', 'corridor', 'Landing', CHACE_LANDING, None),
        ('Moore Terrace', 'space', 'Moore Terrace', CHACE_HIGH, None),
    ],
    '3': [
        # Benefit Street side, from the 2020 plan
        ('3-lobby', 'corridor', 'Benefit Street entrance · lobby', rect(195, 160, 352, 205), None),
        ('Café Pearl', 'space', 'Café Pearl', rect(74, 205, 307, 354), None),
        ('Paul Scott', 'gallery', 'Decorative Arts and Design · Porcelain Gallery', rect(307, 205, 372, 354),
         'Porcelain'),
        ('Farago Wing', 'gallery', 'Modern and Contemporary · Farago Wing', rect(178, 354, 350, 478), 'Contemporary'),
        ('Farago South', 'gallery', 'Contemporary installations', rect(178, 478, 315, 765), 'Installations'),
        ('3-stair-hall', 'corridor', 'Stairs and elevator', rect(350, 354, 415, 478), None),
        ('3-hall-west', 'corridor', 'Radeke Building hall', rect(415, 205, 495, 330), None),
        ('New Media', 'gallery', 'New Media', rect(415, 330, 495, 478), 'New Media'),
        ('3-restrooms', 'space', 'Restrooms', rect(415, 478, 517, 565), None),
        ('Radeke Garden', 'space', 'Radeke Garden', rect(495, 205, 772, 262), None),
        ('3-hall-north', 'corridor', 'Radeke Building hall', rect(495, 262, 772, 333), None),
        ('Modern and Contemporary', 'gallery', 'Modern and Contemporary', rect(495, 333, 772, 495), 'Modern'),
        ('Fain Gallery', 'gallery', 'Fain Gallery', rect(517, 495, 598, 565), 'Fain'),
        ('Prints and Drawings', 'gallery', 'Prints, Drawings, and Photographs', rect(598, 495, 855, 565), 'Prints'),
        ('Danforth Hall', 'gallery', 'Danforth Hall', rect(772, 108, 855, 410), 'Danforth'),
        ('3-hall-east', 'corridor', 'Hall to the bridge', rect(772, 410, 855, 495), None),
        ('3-bridge', 'corridor', 'Bridge to the Chace Center', rect(855, 397, 918, 452), None),
        # Chace Center level 3
        ('3-landing', 'corridor', 'Chace Center landing', CHACE_LANDING, None),
        ('Chace Gallery', 'gallery', 'Special Exhibitions · Chace Gallery', CHACE_HIGH, 'Exhibitions'),
        ('3-core', 'corridor', 'Elevators and stairs', CHACE_CORE, None),
        ('Chace Gallery South', 'gallery', 'Special Exhibitions · Chace Gallery', CHACE_LOW, 'Exhibitions'),
    ],
    '5': [
        ('Pendleton 5', 'gallery', '18th- and 19th-Century American · Pendleton House', rect(230, 90, 350, 354),
         'American'),
        ('5-hall', 'corridor', 'Stairs and elevator', RADEKE_HALL, None),
        ('European', 'gallery', 'European · Old Masters', rect(772, 205, 855, 495), 'European'),
        ('Grand Gallery', 'gallery', 'European · Grand Gallery', rect(495, 205, 772, 495), 'Grand Gallery'),
        ('Greek and Roman', 'gallery', 'Ancient Greek and Roman', rect(495, 495, 855, 565), 'Greek & Roman'),
    ],
    '6': [
        ('Pendleton 6', 'gallery', '18th- and 19th-Century American · Pendleton House', rect(230, 90, 350, 230),
         'American'),
        ('Decorative Arts', 'gallery', 'Contemporary Decorative Arts and Design', rect(230, 230, 350, 354), 'Design'),
        ('6-hall', 'corridor', 'Stairs and elevator', RADEKE_HALL, None),
        ('Egyptian', 'gallery', 'Ancient Egyptian', rect(495, 205, 640, 495), 'Egyptian'),
        ('Asian', 'gallery', 'Asian', rect(640, 205, 855, 495), 'Asian'),
        ('Costume and Textiles', 'gallery', 'Costume and Textiles · Donghia Study Center', rect(495, 495, 855, 565),
         'Textiles'),
    ],
}

DOORS = {
    '1': [('Chace Lobby', '1-core', (1040, 610)), ('1-core', 'RISD Works', (980, 548)),
          ('1-core', 'Metcalf Auditorium', (1100, 548))],
    '2': [('Gelman Gallery', '2-core', (1040, 610)), ('2-core', '2-landing', (938, 548)),
          ('2-landing', 'Moore Terrace', (958, 470))],
    '3': [('3-lobby', 'Café Pearl', (250, 205)), ('3-lobby', 'Paul Scott', (330, 205)),
          ('Café Pearl', 'Farago Wing', (260, 354)), ('Farago Wing', 'Farago South', (250, 478)),
          ('Farago Wing', '3-stair-hall', (350, 420)), ('Paul Scott', '3-stair-hall', (360, 354)),
          ('3-stair-hall', 'New Media', (415, 400)), ('New Media', '3-hall-west', (455, 330)),
          ('New Media', 'Modern and Contemporary', (495, 410)), ('New Media', '3-restrooms', (465, 478)),
          ('3-hall-west', 'Radeke Garden', (495, 230)), ('3-hall-west', '3-hall-north', (495, 300)),
          ('3-hall-north', 'Modern and Contemporary', (630, 333)), ('3-hall-north', 'Danforth Hall', (772, 300)),
          ('Radeke Garden', 'Danforth Hall', (772, 230)), ('Modern and Contemporary', 'Fain Gallery', (557, 495)),
          ('Modern and Contemporary', 'Prints and Drawings', (700, 495)),
          ('Modern and Contemporary', '3-hall-east', (772, 450)), ('Danforth Hall', '3-hall-east', (813, 410)),
          ('Prints and Drawings', '3-hall-east', (813, 495)), ('3-restrooms', 'Fain Gallery', (517, 530)),
          ('3-hall-east', '3-bridge', (855, 425)), ('3-bridge', '3-landing', (918, 425)),
          ('3-landing', 'Chace Gallery', (958, 470)), ('3-landing', '3-core', (938, 548)),
          ('Chace Gallery', '3-core', (1100, 548)), ('3-core', 'Chace Gallery South', (1040, 610))],
    '5': [('Pendleton 5', '5-hall', (350, 250)), ('5-hall', 'Grand Gallery', (495, 350)),
          ('Grand Gallery', 'European', (772, 350)), ('Grand Gallery', 'Greek and Roman', (630, 495)),
          ('European', 'Greek and Roman', (813, 495)), ('5-hall', 'Greek and Roman', (495, 470))],
    '6': [('Pendleton 6', 'Decorative Arts', (290, 230)), ('Pendleton 6', '6-hall', (350, 218)),
          ('Decorative Arts', '6-hall', (350, 300)), ('6-hall', 'Egyptian', (495, 350)),
          ('Egyptian', 'Asian', (640, 350)), ('Egyptian', 'Costume and Textiles', (560, 495)),
          ('Asian', 'Costume and Textiles', (750, 495))],
}

PURPLE = (300, 180)      # Pendleton House elevator (Benefit Street side)
TEAL = (405, 459)        # Radeke Building elevator
YELLOW = (995, 587)      # Chace Center elevator
AMENITIES = {
    '1': [('entrance', 925, 870), ('info', 1000, 800), ('coat', 960, 760), ('shop', 980, 470),
          ('elevator', *YELLOW), ('stairs', 1140, 590), ('stairs', 1060, 700), ('restroom', 1080, 585)],
    '2': [('elevator', *YELLOW), ('stairs', 1140, 590), ('stairs', 1060, 700), ('restroom', 1080, 585)],
    '3': [('entrance', 250, 165), ('info', 220, 188), ('coat', 270, 192), ('elevator', *PURPLE),
          ('stairs', 340, 185), ('dining', 130, 290),
          ('stairs', 385, 370), ('elevator', *TEAL), ('restroom', 433, 500), ('restroom', 478, 545),
          ('stairs', 840, 300), ('restroom', 938, 475), ('elevator', *YELLOW), ('stairs', 1140, 590)],
    '5': [('elevator', *PURPLE), ('elevator', *TEAL), ('stairs', 385, 370), ('stairs', 340, 215)],
    '6': [('elevator', *PURPLE), ('elevator', *TEAL), ('stairs', 385, 370), ('stairs', 340, 215)],
}
APPROX = 'Layout of this floor is approximate: drawn from the museum’s section map, not a floor plan'
LABELS = {
    '1': [('North Main Street entrance', 'note', 830, 860), ('Chace Plaza', 'place', 830, 920),
          ('Chace Center', 'place', 1040, 380), (APPROX, 'note', 1040, 1010)],
    '2': [('Chace Center', 'place', 1040, 380), ('RISD student galleries', 'note', 1040, 1010), (APPROX, 'note', 1040, 1040)],
    '3': [('Benefit Street entrance', 'note', 250, 130), ('Radeke Building', 'place', 640, 600),
          ('Chace Center', 'place', 1040, 380), ('Bridge', 'note', 886, 470),
          ('North Main Street entrance is on Floor 1', 'note', 830, 860)],
    '5': [('Pendleton House', 'place', 290, 70), ('Radeke Building', 'place', 640, 600), (APPROX, 'note', 560, 640)],
    '6': [('Pendleton House', 'place', 290, 70), ('Radeke Building', 'place', 640, 600), (APPROX, 'note', 560, 640)],
}

FLOORS = [
    ('1', 'Floor 1', 'Chace Center · North Main Street entrance · RISD Works shop · Metcalf Auditorium · coat check', 1),
    ('2', 'Floor 2', 'Chace Center · RISD student galleries (Gelman Gallery) · Moore Terrace', 2),
    ('3', 'Floors 3 & 4', 'Benefit Street entrance · Café Pearl · Modern and Contemporary · Prints, Drawings, and '
                          'Photographs · Radeke Garden · Special Exhibitions (Chace Center)', 3),
    ('5', 'Floor 5', 'European · Grand Gallery · Ancient Greek and Roman · American (Pendleton House)', 5),
    ('6', 'Floor 6', 'Egyptian · Asian · Costume and Textiles · Contemporary Decorative Arts and Design · '
                     'American (Pendleton House)', 6),
]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': poly}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        doors = [{'a': a, 'b': b, 'at': [x, y], 'width': 6, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        amen = [{'type': t, 'at': [x, y]} for t, x, y in AMENITIES[fid]]
        labels = [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in LABELS[fid]]
        ids = {r['id'] for r in rooms}
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_risd.py from the RISD Museum map (Floors 3 & 4, 2020 edition) and the '
                     'museum’s section map (2018). Floors 1, 2, 5 and 6 are approximate. Galleries are rehung '
                     'from time to time, so a room may show other works today.',
            'source': SOURCE, 'units': 'pixels', 'defaultFloor': '3', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

QUERY = """
SELECT ?w ?wLabel ?creatorLabel ?cit ?born ?origin ?inception ?typeLabel ?img ?acc ?matLabel WHERE {
  ?w wdt:P195 wd:%s .
  OPTIONAL { ?w wdt:P170 ?creator . OPTIONAL { ?creator wdt:P27 ?c . ?c rdfs:label ?cit FILTER(lang(?cit)='en') }
             OPTIONAL { ?creator wdt:P569 ?born } }
  OPTIONAL { ?w wdt:P495 ?o . ?o rdfs:label ?origin FILTER(lang(?origin)='en') }
  OPTIONAL { ?w wdt:P571 ?inception }
  OPTIONAL { ?w wdt:P31 ?type }
  OPTIONAL { ?w wdt:P18 ?img }
  OPTIONAL { ?w p:P217 ?st . ?st ps:P217 ?acc . ?st pq:P195 wd:%s }
  OPTIONAL { ?w wdt:P186 ?mat }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}""" % (MUSEUM, MUSEUM)

PLACE_NOTE = ('Gallery guessed from the work’s artist, date, country and type, using the subjects of the RISD '
              'Museum’s floors. Wikidata lists what the museum owns, so this work may not be on view.')
AMERICA = re.compile(r'United States|American|Thirteen Colonies|Province of Massachusetts|Colony', re.I)
ASIA = re.compile(r'Japan|Tokugawa|Edo|Meiji|China|Chinese|Song dynasty|Yuan dynasty|Ming dynasty|Qing dynasty|'
                  r'Tang dynasty|Korea|Joseon|Goryeo|India|Mughal|Nepal|Tibet|Thailand|Vietnam|Cambodia|Indonesia', re.I)
EGYPT = re.compile(r'Egypt', re.I)
CLASSICAL = re.compile(r'Greece|Greek|Roman|Rome|Etrusc|Athens', re.I)
PAPER = re.compile(r'drawing|print|watercolou?r|engraving|etching|woodcut|drypoint|lithograph|photograph|gouache', re.I)
TEXTILE = re.compile(r'textile|tapestry|costume|dress|garment|quilt|kimono|lace|embroider', re.I)
DESIGN = re.compile(r'typewriter|chair|furniture|lamp|vase|ceramic|porcelain|glass|design|model', re.I)
ANCIENT = re.compile(r'situla|archaeolog|amphora|krater|kylix|lekythos|antiquit', re.I)
UNKNOWN_CREATOR = re.compile(r'^(anonymous|unknown|unidentified)', re.I)


def gallery_of(w):
    y, typ = w.get('year', w.get('made')), (w.get('type') or '')
    where = ' '.join(w['cit']) + ' ' + (w.get('origin') or '')
    if EGYPT.search(where): return 'Egyptian'
    if ANCIENT.search(typ) or (y is not None and y < 500 and CLASSICAL.search(where)):
        return 'Greek and Roman'
    if TEXTILE.search(typ): return 'Costume and Textiles'
    if DESIGN.search(typ): return 'Decorative Arts' if (y or 1950) >= 1900 else 'Paul Scott'
    if ASIA.search(where): return 'Asian'
    if PAPER.search(typ): return 'Prints and Drawings'
    if y is None: return None
    if y < 500: return 'Greek and Roman'
    if y >= 1960: return 'Farago Wing'
    if y >= 1900: return 'Modern and Contemporary'
    if AMERICA.search(where): return 'Pendleton 5' if y < 1850 else 'Pendleton 6'
    if y < 1800: return 'European'
    return 'Grand Gallery'


def fetch():
    url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': QUERY})
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)['results']['bindings']


def build_works(floors, rows):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
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
        if v('born') and 'born' not in w:
            m = re.match(r'(-?)0*(\d+)-', v('born'))
            if m: w['born'] = int(m[2]) * (-1 if m[1] else 1)
        if v('typeLabel') and (not w.get('type') or w['type'] in ('painting', 'work of art')): w['type'] = v('typeLabel')
        if v('img'): w['image'] = urllib.parse.unquote(v('img').rsplit('/', 1)[1])
        if v('acc'): w['accession'] = v('acc')
        if v('matLabel'): w['mat'].add(v('matLabel'))
    out, skipped = [], 0
    for w in works.values():
        if w.get('year') is None and w.get('born') is not None:
            w['made'] = w['born'] + 35                                      # no date: the artist's mid-career
        if re.fullmatch(r'Q\d+', w.get('title') or ''): continue           # no English title
        if w.get('type') == 'human': continue                               # a person, not a work
        artist = w.get('artist') or ''
        if UNKNOWN_CREATOR.match(artist) or re.fullmatch(r'Q\d+', artist): w['artist'] = artist = ''
        g = gallery_of(w)
        if not g or g not in rooms:
            skipped += 1
            continue
        floor, gname = rooms[g]
        a = {'id': f'risd-{w["id"]}', 'title': w['title'], 'artist': artist,
             'date': str(w['year']) if w.get('year') is not None else '', 'year': w.get('year'),
             'medium': ', '.join(sorted(w['mat'])).capitalize(), 'accession': w.get('accession', ''),
             'type': (w.get('type') or '').capitalize(), 'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': PLACE_NOTE, 'url': f'https://www.wikidata.org/wiki/{w["id"]}', 'wikidata': w['id']}
        if w.get('image'):
            a['image'] = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(w['image']) + '?width=600'
            a['imageCredit'] = 'Wikimedia Commons'
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    out.sort(key=lambda a: (a['floor'], order[a['gallery']], -('image' in a), a.get('year') or 0))
    doc = {'source': 'Wikidata (CC0), pictures from Wikimedia Commons; galleries guessed from artist, date, country and type',
           'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}
    return doc, skipped


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    rows = json.load(open(sys.argv[1]))['results']['bindings'] if len(sys.argv) > 1 else fetch()
    works, skipped = build_works(floors, rows)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works placed ({sum(1 for a in works["artworks"] if "image" in a)} with pictures), '
          f'{skipped} without a likely gallery')
    for k in sorted(by): print(f'  {k}: {by[k]}')


if __name__ == '__main__':
    main()
