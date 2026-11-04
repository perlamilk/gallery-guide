#!/usr/bin/env python3
"""Build the Clark Art Institute map guide (run: python3 tools/build_clark.py [wikidata.json]).

    data/clark/floors.json    three levels seen from above (a flat 2D plan)
    data/clark/artworks.json  works the Clark owns (Wikidata, CC0) in the gallery where they most likely hang

The map: the Clark's own visitor map (clarkart.edu, "A-4547 8.5x14 Gallery Closure map 8-26.pdf", Aug 2021),
already drawn flat. The rooms below are its walls' coordinates in PDF points; doors are the gaps in the walls.
The main level holds three buildings joined indoors: the Clark Center (main entrance, admissions, store), the
Museum Building (galleries 1-20, reached by the walkway along the reflecting pool) and the Manton Research
Center (British art, works on paper, library), reached from gallery 18. The PDF draws the Clark Center's lower
level and the Museum Building's upper level as small insets; they are shifted (LOWER_SHIFT, UPPER_SHIFT) so
their elevators sit over the main-level elevators they belong to.

The works: Wikidata says which works the Clark owns, not which are on view or where. Each work is put in the
gallery whose subject (the map's gallery list) fits its artist, date and country best; the work page says so.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'clark'
MUSEUM = 'Q1465805'
SOURCE = ('https://www.clarkart.edu/getmedia/614f36ad-9b91-4807-819f-6266fbafd90d/'
          'A-4547-8-5x14-Gallery-Closure-map_8-26.pdf')
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'

LOWER_SHIFT = (263.9, -60.7)    # lower-level inset -> under the Clark Center (elevator over elevator)
UPPER_SHIFT = (-186.0, -133.0)  # upper-level inset -> over gallery 1's elevator in the Museum Building


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# Gallery subjects, from the map's gallery list
GALLERY = {
    '1': 'American Art 1850–1900', '2': 'Impressionist Paintings', '3': 'European and American Art 1850–1900',
    '4': 'Sculpture', '5': 'European Decorative Arts 1700–1800', '6': 'European Art 1800–1850',
    '7': 'Special Installations', '8': 'European Art 1550–1650', '9': 'European Art 1450–1600',
    '10': 'European Art 1300–1500', '11': 'European Art 1700–1850', '12': 'Pastels',
    '13': 'European Art 1850–1900', '14': 'Edgar Degas', '15': 'Alfred Stevens', '16': 'European Art 1850–1900',
    '17': 'European Decorative Arts and Paintings', '18': 'Impressionist Paintings', '19': 'European Art 1800–1900',
    '20': 'European Silver 1500–1850',
}
MUSEUM_ROOMS = {   # Museum Building galleries, wall centre lines
    '14': rect(636.3, 206.65, 656.0, 229.8), '13': rect(656.0, 206.65, 701.4, 229.8),
    '12': rect(701.4, 206.65, 719.6, 229.8), '10': rect(719.6, 206.65, 756.9, 229.8),
    '7': rect(756.9, 206.65, 775.3, 229.8), '6': rect(775.3, 206.65, 854.1, 229.8),
    '5': rect(854.1, 206.65, 880.95, 243.6), '11': rect(681.4, 174.9, 710.55, 206.65),
    '9': rect(710.55, 174.9, 766.0, 206.65), '8': rect(766.0, 174.9, 793.5, 206.65),
    '1': rect(636.3, 229.8, 701.4, 295.15), '2': rect(701.4, 229.8, 793.5, 295.15),
    '3': [[793.5, 229.8], [854.1, 229.8], [854.1, 243.6], [854.1, 280.8], [854.1, 295.15], [793.5, 295.15]],
    '4': rect(854.1, 243.6, 886.1, 280.8), '20': rect(854.1, 280.8, 880.95, 318.3),
    '15': rect(636.3, 295.15, 656.0, 318.3), '16': rect(656.0, 295.15, 701.4, 318.3),
    '18': rect(701.4, 295.15, 793.5, 318.3), '19': rect(793.5, 295.15, 854.1, 318.3),
    '17': rect(681.4, 318.3, 738.5, 351.3),
}

FLOOR_ROOMS = {
    '1': [
        # Clark Center
        ('Conforti Pavilion', 'space', 'Michael Conforti Pavilion · Events', rect(263.1, 141.2, 369.7, 178.0)),
        ('1-entrance', 'corridor', 'Main entrance', rect(369.7, 149.7, 392.7, 162.7)),
        ('Admissions', 'corridor', 'Admissions · Clark Center', rect(392.7, 141.2, 452.1, 178.0)),
        ('Museum Store', 'space', 'Museum Store', rect(452.1, 141.2, 503.0, 178.0)),
        ('1-walkway', 'corridor', 'Walkway to the Museum Building',
         [[480.9, 178.0], [503.0, 178.0], [530.6, 197.0], [548.6, 197.0], [600.2, 239.8], [600.2, 247.0],
          [549.8, 209.8], [533.0, 206.7]]),
        # Museum Building
        ('Museum Pavilion', 'corridor', 'Museum Pavilion · Museum Building entrance',
         [[600.2, 206.7], [629.0, 206.7], [629.0, 238.0], [636.3, 238.0], [636.3, 286.6], [629.0, 286.6],
          [629.0, 318.2], [600.2, 318.2]]),
        # Manton Research Center
        ('1-manton-hall', 'corridor', 'Passage to the Manton Research Center', rect(738.5, 318.3, 758.8, 450.6)),
        ('Study Center', 'space', 'Manton Study Center for Works on Paper', rect(699.3, 375.5, 738.5, 413.6)),
        ('Thaw Gallery', 'gallery', 'Eugene V. Thaw Gallery for Works on Paper', rect(692.8, 413.6, 738.5, 451.2)),
        ('Manton Gallery', 'gallery', 'Manton Gallery for British Art', rect(758.8, 413.6, 784.6, 450.6)),
        ('Reading Room', 'corridor', 'Reading Room · Manton admissions', rect(666.9, 451.2, 774.6, 496.7)),
        ('Auditorium', 'space', 'Auditorium', rect(616.0, 368.5, 677.0, 431.4)),
        ('1-manton-lobby', 'corridor', 'Manton lobby', rect(660.4, 431.4, 692.8, 451.2)),
        ('1-manton-restrooms', 'space', 'Restrooms', rect(643.6, 439.3, 660.4, 451.2)),
        ('Library', 'space', 'Library', rect(631.6, 496.7, 784.7, 560.0)),
    ],
    '0': [
        ('Special Exhibition Gallery', 'gallery', 'Special Exhibition Gallery · Clark Center',
         [[42.5, 202.1], [58.4, 202.1], [58.4, 141.6], [145.0, 192.5], [145.0, 202.1], [115.6, 202.1],
          [115.6, 240.1], [42.5, 240.1]]),
        ('0-lobby', 'corridor', 'Lower lobby',
         [[115.6, 202.1], [192.3, 202.6], [192.3, 215.6], [224.0, 215.6], [224.0, 240.1], [115.6, 240.1]]),
        ('0-restrooms', 'space', 'Restrooms', rect(192.3, 202.6, 224.0, 215.6)),
        ('Café 7', 'space', 'Café 7', rect(224.0, 202.9, 248.2, 240.1)),
    ],
    '2': [
        ('Glass Study Gallery', 'gallery', 'Lauzon Glass Study Gallery', rect(833.9, 356.6, 856.6, 392.4)),
        ('2-landing', 'corridor', 'Landing', rect(856.6, 356.6, 880.7, 397.0)),
        ('American Decorative Arts', 'gallery', 'Burrows Gallery of American Decorative Arts',
         [[880.7, 356.7], [925.7, 356.7], [925.7, 436.9], [880.7, 436.9]]),
    ],
}
SHORT = {'Thaw Gallery': 'Thaw', 'Manton Gallery': 'British Art', 'Special Exhibition Gallery': 'Exhibitions',
         'Glass Study Gallery': 'Glass', 'American Decorative Arts': 'American'}

DOORS = {
    '1': [('Conforti Pavilion', '1-entrance', (369.7, 156.0)), ('1-entrance', 'Admissions', (392.7, 156.0)),
          ('Admissions', 'Museum Store', (452.1, 164.0)), ('Museum Store', '1-walkway', (492.0, 178.0)),
          ('1-walkway', 'Museum Pavilion', (600.2, 243.4)), ('Museum Pavilion', '1', (636.3, 262.0)),
          # Museum Building, from the gaps in the PDF's walls
          ('14', '13', (656.0, 219.0)), ('13', '12', (701.4, 218.8)), ('13', '11', (696.7, 206.7)),
          ('13', '1', (675.9, 229.8)), ('10', '9', (724.5, 206.7)), ('7', '6', (775.3, 219.0)),
          ('6', '5', (854.1, 226.1)), ('6', '8', (780.0, 206.7)), ('6', '3', (830.2, 229.8)),
          ('5', '4', (866.9, 243.6)), ('11', '9', (710.5, 191.1)), ('9', '8', (766.0, 191.1)),
          ('1', '2', (701.4, 271.6)), ('1', '16', (675.9, 295.1)), ('2', '3', (793.5, 253.4)),
          ('3', '4', (854.1, 262.3)), ('3', '19', (811.8, 295.1)), ('4', '20', (867.0, 280.8)),
          ('19', '20', (854.1, 298.6)), ('15', '16', (656.0, 306.2)), ('16', '18', (701.4, 306.3)),
          ('16', '17', (696.7, 318.3)), ('18', '19', (793.5, 306.4)), ('18', '17', (724.4, 318.3)),
          ('12', '10', (719.6, 218.0)), ('10', '7', (756.9, 218.0)),
          ('18', '1-manton-hall', (748.7, 318.3)),
          # Manton
          ('1-manton-hall', 'Thaw Gallery', (738.5, 437.0)), ('1-manton-hall', 'Manton Gallery', (758.8, 440.0)),
          ('1-manton-hall', 'Reading Room', (748.7, 450.9)), ('Thaw Gallery', 'Study Center', (704.0, 413.6)),
          ('Thaw Gallery', 'Reading Room', (705.0, 451.2)), ('Reading Room', '1-manton-lobby', (680.0, 451.2)),
          ('1-manton-lobby', 'Auditorium', (670.0, 431.4)), ('1-manton-lobby', '1-manton-restrooms', (660.4, 445.0)),
          ('Reading Room', 'Library', (700.0, 496.7))],
    '0': [('Special Exhibition Gallery', '0-lobby', (115.6, 205.0)), ('0-lobby', '0-restrooms', (208.0, 215.6)),
          ('0-lobby', 'Café 7', (224.0, 228.0))],
    '2': [('Glass Study Gallery', '2-landing', (856.6, 375.0)), ('2-landing', 'American Decorative Arts', (880.7, 365.0))],
}

AMENITIES = {
    '1': [('entrance', 381.0, 149.7), ('info', 420.0, 166.0), ('shop', 476.0, 162.0), ('elevator', 428.7, 134.4),
          ('stairs', 438.0, 170.0), ('elevator', 274.5, 148.5), ('stairs', 285.0, 167.0),
          ('info', 614.5, 268.0), ('elevator', 675.8, 251.0), ('stairs', 676.0, 261.6), ('restroom', 676.0, 274.0),
          ('entrance', 666.9, 472.0), ('entrance', 774.6, 473.0), ('info', 740.0, 474.0),
          ('elevator', 754.0, 421.0), ('stairs', 744.5, 392.0), ('elevator', 672.0, 435.5),
          ('restroom', 652.0, 445.0), ('restroom-all', 696.0, 398.0), ('coat', 681.0, 401.0),
          ('elevator', 673.0, 502.0)],
    '0': [('elevator', 164.8, 195.1), ('stairs', 172.0, 232.0), ('coat', 184.0, 209.0), ('restroom', 201.0, 209.0),
          ('restroom-all', 215.0, 209.0), ('dining', 236.0, 225.0)],
    '2': [('elevator', 862.0, 385.0), ('stairs', 875.0, 385.0), ('stairs', 895.0, 434.0)],
}
LABELS = {
    '1': [('Fernández Terrace', 'place', 455.0, 215.0), ('Reflecting Pool', 'place', 520.0, 255.0),
          ('Parking lot 1 · South Street', 'note', 440.0, 100.0), ('Entrance · Museum Building', 'note', 600.0, 200.0),
          ('Clark Center', 'place', 380.0, 128.0), ('Museum Building', 'place', 760.0, 165.0),
          ('Manton Research Center', 'place', 700.0, 570.0), ('Parking lot 2', 'note', 800.0, 560.0),
          ('Walking trails · Lunder Center at Stone Hill', 'note', 640.0, 520.0)],
    '0': [('Café 7 and coat check are one floor below the main entrance', 'note', 175.0, 250.0)],
    '2': [('Above the Museum Building', 'note', 880.0, 450.0)],
}

FLOORS = [
    ('0', 'Lower Level', 'Clark Center · Special Exhibition Gallery · Café 7 · Coat check · Restrooms', 0, LOWER_SHIFT),
    ('1', 'Main Level', 'Clark Center entrance · Museum Building galleries 1–20 · Manton Research Center', 1, (0, 0)),
    ('2', 'Upper Level', 'American Decorative Arts · Glass Study Gallery', 2, UPPER_SHIFT),
]


def shift(points, dx, dy):
    return [[round(x + dx, 1), round(y + dy, 1)] for x, y in points]


def build_floors():
    floors = []
    for fid, label, area, order, (dx, dy) in FLOORS:
        rooms = []
        if fid == '1':
            for gid, poly in MUSEUM_ROOMS.items():
                r = {'id': gid, 'kind': 'gallery', 'name': f'Gallery {gid} · {GALLERY[gid]}', 'label': gid,
                     'poly': poly}
                if gid == '1': r['labelAt'] = [650.0, 262.0]   # clear of the stairs, elevator and restrooms
                rooms.append(r)
        for rid, kind, name, poly in FLOOR_ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': shift(poly, dx, dy)}
            if kind == 'gallery': r['label'] = SHORT.get(rid, rid)
            rooms.append(r)
        doors = [{'a': a, 'b': b, 'at': [round(x + dx, 1), round(y + dy, 1)], 'width': 4.5, 'axis': 'o'}
                 for a, b, (x, y) in DOORS[fid]]
        amen = [{'type': t, 'at': [round(x + dx, 1), round(y + dy, 1)]} for t, x, y in AMENITIES[fid]]
        labels = [{'text': t, 'kind': k, 'at': [round(x + dx, 1), round(y + dy, 1)]} for t, k, x, y in LABELS[fid]]
        ids = {r['id'] for r in rooms}
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_clark.py from the Clark Art Institute visitor map (2021 edition). '
                     'Galleries are rehung from time to time, so a room may show other works today.',
            'source': SOURCE, 'units': 'pdf-points', 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

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

PLACE_NOTE = ('Gallery guessed from the work’s artist, date and country, using the subjects on the Clark’s map. '
              'Wikidata lists what the Clark owns, so this work may not be on view.')
AMERICA = re.compile(r'United States|American', re.I)
BRITAIN = re.compile(r'United Kingdom|Great Britain|England|Scotland|Ireland|Wales', re.I)
IMPRESSIONISTS = {'Pierre-Auguste Renoir', 'Claude Monet', 'Camille Pissarro', 'Alfred Sisley', 'Édouard Manet',
                  'Berthe Morisot', 'Gustave Caillebotte', 'Mary Cassatt', 'Henri de Toulouse-Lautrec',
                  'Paul Gauguin', 'Vincent van Gogh', 'Paul Cézanne', 'Georges Seurat', 'Armand Guillaumin',
                  'Eugène Louis Boudin', 'Stanislas Lépine', 'Jean-Louis Forain', 'Pierre Bonnard', 'Édouard Vuillard'}
BARBIZON = {'Jean-Baptiste Camille Corot', 'Jean-François Millet', 'Théodore Rousseau', 'Constant Troyon',
            'Charles-François Daubigny', 'Narcisse Virgilio Díaz de la Peña', 'Jules Dupré', 'Henri Harpignies',
            'Charles Jacque', 'Gustave Courbet'}
ACADEMIC = {'William-Adolphe Bouguereau', 'Jean-Léon Gérôme', 'Lawrence Alma-Tadema', 'Giovanni Boldini',
            'Raimundo de Madrazo y Garreta', 'Ernest Meissonier', 'Jean-Louis-Ernest Meissonier', 'Alexandre Cabanel',
            'Jean-Jacques Henner', 'Mariano Fortuny', 'Félix Ziem', 'Alexandre-Gabriel Decamps'}
PAPER = re.compile(r'drawing|print|watercolou?r|engraving|etching|woodcut|drypoint|lithograph|photograph', re.I)
UNKNOWN_CREATOR = re.compile(r'^(anonymous|unknown|unidentified)', re.I)


def gallery_of(w):
    y, artist, typ = w.get('year'), w.get('artist') or '', w.get('type') or ''
    where = ' '.join(w['cit']) + ' ' + (w.get('origin') or '')
    if artist == 'Edgar Degas': return '14'
    if artist == 'Alfred Stevens': return '15'
    if 'pastel' in typ or any('pastel' in m for m in w['mat']): return '12'
    if PAPER.search(typ): return 'Thaw Gallery'
    if typ == 'sculpture': return '4'
    if AMERICA.search(where) and not BRITAIN.search(where): return '1'
    if BRITAIN.search(where): return 'Manton Gallery'
    if artist == 'Pierre-Auguste Renoir': return '2'
    if artist in IMPRESSIONISTS: return '18'
    if artist in BARBIZON: return '19'
    if artist in ACADEMIC: return '3'
    if y is None: return None
    if y < 1450: return '10'
    if y < 1550: return '9'
    if y < 1700: return '8'
    if y < 1800: return '11'
    if y < 1850: return '6'
    if y < 1870: return '13'
    if y < 1900: return '16'
    return '18'


def fetch():
    url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': QUERY})
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    with urllib.request.urlopen(req, timeout=120) as r:
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
        if v('typeLabel') and (not w.get('type') or w['type'] == 'painting'): w['type'] = v('typeLabel')
        if v('img'): w['image'] = urllib.parse.unquote(v('img').rsplit('/', 1)[1])
        if v('acc'): w['accession'] = v('acc')
        if v('matLabel'): w['mat'].add(v('matLabel'))
    out, skipped = [], 0
    for w in works.values():
        if re.fullmatch(r'Q\d+', w.get('title') or ''): continue           # no English title
        artist = w.get('artist') or ''
        if UNKNOWN_CREATOR.match(artist) or re.fullmatch(r'Q\d+', artist): w['artist'] = artist = ''
        g = gallery_of(w)
        if not g or g not in rooms:
            skipped += 1
            continue
        floor, gname = rooms[g]
        a = {'id': f'clark-{w["id"]}', 'title': w['title'], 'artist': artist,
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
    doc = {'source': 'Wikidata (CC0), pictures from Wikimedia Commons; galleries guessed from artist, date and country',
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
    for k in sorted(by, key=lambda k: (len(k), k)): print(f'  {k}: {by[k]}')


if __name__ == '__main__':
    main()
