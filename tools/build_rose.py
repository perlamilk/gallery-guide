#!/usr/bin/env python3
"""Build the Rose Art Museum (Brandeis University, Waltham, MA) map guide (run: python3 tools/build_rose.py).

    data/rose/floors.json      the Entrance Level and the Lower Level seen from above (flat 2D)
    data/rose/artworks.json    the shows on view now and the permanent installations, in their galleries
    data/rose/images/          their pictures, made smaller for phones
    data/guides/Q7367636.json  the same plus two collection highlights, for the museum page

The pages come from .cache/rose, filled by tools/harvest_rose.py --wayback. brandeis.edu refuses robots (from the
cloud and from a home connection alike), so the harvest reads the Internet Archive's copies of the Rose's pages; the
cache was carried over on the branch claude/rose-cache (cat rose-cache.tgz.part-* | tar xz -C .cache). The Rose's
online catalogue (rosecollection.brandeis.edu) closes itself to robots and is not used.

The map
-------
The Rose publishes no floor plan. The plan here is APPROXIMATE, drawn inside the building's real outline:
  - OpenStreetMap way 42505155 (ODbL), turned 24 degrees so its walls are square, with the front door (facing Chris
    Burden's Light of Reason on the Rose circle) at the bottom: the 1961 Rose building by Harrison & Abramovitz in the
    middle (its skylit roof shows on aerial photos), the 1974 addition to the right, and Graham Gund's glass-fronted
    Lois Foster Wing (2001, about 5,000 sq ft) across the back.
  - the museum's own words: the reception desk is "in the Fineberg gallery" (so the Gerald S. and Sandra Fineberg
    Gallery is the entrance hall of the Rose building) with the coat closet and free lockers "at the museum entrance";
    the Lower Rose Gallery is downstairs, reached by the stair opening "on the first floor of the Rose building", and
    has restrooms; the accessible entrance with power doors and the elevator are "on the right side of the building",
    reached from the ramp left of the front steps; the elevator serves all public areas; accessible restrooms with
    baby changing are "on the museum's second floor in the Lois Foster Wing", "outside of the Lois Foster Wing", by
    "the vestibule before the Foster Wing"; the Foster Wing stairwell (with seating) runs between the floors, and "the
    hallway outside the Lower Rose Gallery in the Lois Foster Wing" is the quiet space; Mark Dion's Undisciplined
    Collector is in "a small ground-floor gallery"; the Mildred S. Lee Gallery holds Yinka Shonibare's darkened
    installation.
Which room is where inside each part of the building is our best reading of those sources; the map says so.
Coordinates are metres in the building's turned frame (x to the right, y down, front door at y = 42.4), times K.
"""
import html
import io
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'rose'
OUT = ROOT / 'data' / 'rose'
MUSEUM = 'Q7367636'
NAME = 'Rose Art Museum'
SITE = 'https://www.brandeis.edu/rose'
SOURCE = 'Rose Art Museum: exhibition, visit and accessibility pages (brandeis.edu/rose, read from the Internet ' \
         'Archive); approximate plan'
CREDIT = 'Rose Art Museum, Brandeis University (brandeis.edu/rose)'
K = 16          # pixels per metre


def P(x, y):
    return [round((x + 40) * K, 1), round((y + 4) * K, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Outline (OSM way 42505155, turned): Foster Wing x -36.1..0, y 0..17.2; Rose building x -19.9..-5.6, y 17.2..42.4;
# 1974 addition x -5.6..31, y 15.3..36.5.
ROSE = rect(-19.9, 17.2, -5.6, 42.4)
VEST = rect(-19.9, 13, 0, 17.2)
STAIR = rect(-8, 0, -4, 13)

# ---- Entrance Level ------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
F2 = [
    ('Fineberg Gallery', 'gallery', 'Gerald S. and Sandra Fineberg Gallery: the entrance hall of the 1961 Rose '
     'building, with the reception desk, the coat closet and lockers, and the stair down to the Lower Rose', ROSE,
     'Fineberg'),
    ('Foster Vestibule', 'corridor', 'Vestibule before the Lois Foster Wing (large-print binders)', VEST, None),
    ('Lois Foster Wing', 'gallery', 'Lois Foster Wing: Graham Gund’s glass-fronted gallery (2001)',
     [(-36.1, 0), (-8, 0), (-8, 13), (-19.9, 13), (-19.9, 17.2), (-36.1, 17.2)], 'Foster Wing'),
    ('Foster Stairwell', 'corridor', 'Lois Foster Wing stairwell, with benches: stairs between the two floors',
     STAIR, None),
    ('Restrooms', 'space', 'Restrooms: accessible, with baby changing, gender-neutral', rect(-4, 0, 0, 13), None),
    ('Side Hall', 'corridor', 'Hall from the accessible entrance (power doors) and the elevator', rect(-5.6, 26, 8, 36.5),
     None),
    ('Undisciplined Collector', 'gallery', 'Mark Dion: The Undisciplined Collector (a 1961 collector’s den you can '
     'walk into)', rect(-5.6, 17.2, 3, 26), 'Dion'),
    ('Lee Gallery', 'gallery', 'Mildred S. Lee Gallery', rect(8, 15.3, 31, 36.5), 'Lee'),
    ('Light of Reason', 'gallery', 'Outdoors: Chris Burden’s Light of Reason on the lawn by the Rose circle (free '
     'parking)', rect(-26, 42.4, 8, 56), 'Light of Reason'),
]
F2_CLOSED = [rect(3, 15.3, 8, 26)]
F2_DOORS = [('Fineberg Gallery', 'Foster Vestibule', (-12.7, 17.2)), ('Foster Vestibule', 'Lois Foster Wing', (-14, 13)),
            ('Foster Vestibule', 'Foster Stairwell', (-6, 13)), ('Foster Vestibule', 'Restrooms', (-2, 13)),
            ('Fineberg Gallery', 'Side Hall', (-5.6, 31)), ('Side Hall', 'Lee Gallery', (8, 31)),
            ('Side Hall', 'Undisciplined Collector', (-1, 26)), ('Fineberg Gallery', 'Light of Reason', (-12.7, 42.4))]
F2_AMEN = [('entrance', -12.7, 41.4), ('info', -12.7, 37.5), ('coat', -17.6, 39.5), ('stairs', -12.7, 27),
           ('entrance', 0, 35.5), ('elevator', 4.5, 33), ('restroom', -2, 4), ('restroom-all', -2, 8.5),
           ('stairs', -6, 6.5)]
F2_LABELS = [('Accessible entrance: ramp from the left of the front steps', 4, 39.5),
             ('Approximate plan: the Rose publishes none', 0, -2.5)]
F2_NOTES = [('Offices', 5.5, 20.5)]

# ---- Lower Level ---------------------------------------------------------------------------------------------------
F1 = [
    ('Lower Rose Gallery', 'gallery', 'Lower Rose Gallery: under the Fineberg, down the stair from the entrance',
     rect(-19.9, 21.5, -5.6, 42.4), 'Lower Rose'),
    ('Lower Rose Restrooms', 'space', 'Restrooms in the Lower Rose Gallery (doors without power assist)',
     rect(-19.9, 17.2, -13, 21.5), None),
    ('Foster Hallway', 'corridor', 'Hallway outside the Lower Rose Gallery, in the Lois Foster Wing: a quiet space',
     rect(-19.9, 13, 0, 17.2), None),
    ('Lower Foster Stairwell', 'corridor', 'Lois Foster Wing stairwell, with benches', STAIR, None),
    ('Elevator Lobby', 'corridor', 'Elevator', rect(-5.6, 28, 0, 36.5), None),
]
F1_CLOSED = [rect(-36.1, 0, -8, 13), rect(-36.1, 13, -19.9, 17.2), rect(-4, 0, 0, 13), rect(-13, 17.2, -5.6, 21.5),
             rect(0, 15.3, 31, 36.5), rect(-5.6, 17.2, 0, 28)]
F1_DOORS = [('Lower Rose Gallery', 'Foster Hallway', (-9, 21.5)), ('Foster Hallway', 'Lower Foster Stairwell', (-6, 13)),
            ('Lower Rose Gallery', 'Lower Rose Restrooms', (-16.5, 21.5)),
            ('Lower Rose Gallery', 'Elevator Lobby', (-5.6, 32))]
F1_AMEN = [('stairs', -12.7, 27), ('restroom', -16.5, 19.3), ('elevator', -2.8, 33), ('stairs', -6, 6.5)]
F1_LABELS = [('Lower Level (approximate plan): storage and offices in the grey parts', -6, -2.5)]
F1_NOTES = []


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes):
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area, 'rooms': rr,
            'closed': [{'poly': [P(*q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
            'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    floors = [
        floor('L', 'Lower Level', 0, 'Lower Rose Gallery · restrooms · quiet hallway · Foster Wing stairwell',
              F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS, F1_NOTES),
        floor('1', 'Entrance Level', 1, 'Entrance · reception desk · lockers · Fineberg Gallery · Lois Foster Wing · '
              'Lee Gallery · Mark Dion’s den · restrooms', F2, F2_CLOSED, F2_DOORS, F2_AMEN, F2_LABELS, F2_NOTES),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_rose.py. The Rose publishes no floor plan: this one is approximate, drawn '
                     'inside the building’s real outline (OpenStreetMap) from the museum’s visit, accessibility and '
                     'exhibition pages. The front door, facing Light of Reason, is at the bottom.',
            'source': 'Approximate: OpenStreetMap building outline and the Rose’s visit, accessibility and exhibition '
                      'pages',
            'units': 'metres x 16, front door at the bottom', 'approximate': True, 'defaultFloor': '1',
            'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------------

INDEX = None


def cached(url):
    """Local file for a cached page or picture (from the harvest index), or None."""
    global INDEX
    if INDEX is None: INDEX = json.loads((CACHE / 'index.json').read_text())
    f = INDEX['images'].get(url) or (INDEX['pages'].get(url) or {}).get('file')
    return CACHE / f if f and (CACHE / f).exists() else None


def picture(key, src):
    """src: a brandeis.edu picture URL from the harvest, or a Path. Returns the guide's picture path or None."""
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/rose/images/{key}.jpg'
    f = src if isinstance(src, Path) else cached(src)
    if not f: return None
    try:
        im = Image.open(io.BytesIO(f.read_bytes()))
    except Exception:
        return None
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/rose/images/{key}.jpg'


def page_text(path):
    """The main text of a cached Rose page (after the breadcrumb, before the footer)."""
    f = cached(f'{SITE}/{path}')
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', f.read_text(errors='replace'), flags=re.S)
    s = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
    s = s.split('Home / ', 1)[-1]
    return re.split(r' (?:Current Exhibitions Upcoming Exhibitions|Visit the Rose Subscribe|View Gallery)', s)[0]


def paragraph(path, start, n=900):
    s = page_text(path)
    i = s.find(start)
    s = s[i:] if i >= 0 else s
    if len(s) > n: s = s[:s.rfind('. ', 0, n) + 1]
    return s


IMG = f'{SITE}/exhibitions/2026'
# (key, room, title, artist, date, description, page, picture, extra fields)
SHOWS = [
    ('rose-show-gribbon', 'Lois Foster Wing', 'Jenna Gribbon: Entwined', 'Exhibition', 'August 19, 2026 – January 3, 2027',
     None, 'exhibitions/2026/jenna-gribbon.html', CACHE / 'extra' / 'gribbon_bww.jpg',
     {'imageCredit': 'Jenna Gribbon, Examinationscape, 2021 (detail). Tia Collection. © Jenna Gribbon. Press image of '
                     'the Rose Art Museum (via BroadwayWorld)'}),
    ('rose-show-chromaform', 'Fineberg Gallery', 'ChromaForm', 'Exhibition', 'August 19, 2026 – June 6, 2027',
     None, 'exhibitions/2026/chromaform.html', f'{IMG}/chromaform-images/chromaform-hero-1.jpg',
     {'imageCredit': 'Leon Polk Smith, George Washington Bridge #2, 1979. Rose Art Museum, gift of Mr. Gerald '
                     'Lennard, 2000.83. ' + CREDIT}),
    ('rose-show-shonibare', 'Lee Gallery', 'Yinka Shonibare: Sanctuary', 'Exhibition', 'February 11, 2026 – January 3, 2027',
     None, 'exhibitions/2026/yinka-shonibare.html', f'{IMG}/yinka-shonibare-images/sanctuary-city-hero.jpg',
     {'imageCredit': 'Yinka Shonibare, Sanctuary City, 2024, installation view at Serpentine South. Photo © Jo '
                     'Underhill. ' + CREDIT}),
    ('rose-show-enlighten', 'Lower Rose Gallery', 'En/Lighten: Material & Metaphor', 'Exhibition',
     'August 19, 2026 – June 6, 2027',
     'Light as a physical thing and as a symbol, from the Rose’s collection and loans: works made with incandescent '
     'bulbs, neon, fluorescent tubes, scrolling LED text and video monitors by Dan Basen, Christian Boltanski, Dan '
     'Flavin, Felix Gonzalez-Torres, Jenny Holzer, Alfredo Jaar, Joseph Kosuth, Bruce Nauman, Nam June Paik and Mary '
     'Weatherford. The show begins outdoors with Chris Burden’s Light of Reason. Co-curated by Gannit Ankori and Chad '
     'Sirois.', None, f'{SITE}/lightofreason/images/light-of-reason.jpg',
     {'imageCredit': 'Chris Burden, Light of Reason, 2014, where the show begins. ' + CREDIT,
      'url': 'https://felixgonzalez-torresfoundation.org/exhibitions/enlighten-material-and-metaphor'}),
]
SHOW_TEXT = {
    'exhibitions/2026/jenna-gribbon.html': 'The Rose Art Museum is proud',
    'exhibitions/2026/chromaform.html': 'ChromaForm explores',
    'exhibitions/2026/yinka-shonibare.html': 'Yinka Shonibare: Sanctuary presents',
}
PERMANENT = [
    ('rose-2015-6', 'Undisciplined Collector', 'The Undisciplined Collector', 'Mark Dion', '2015',
     'exhibitions/2015/dion.html', f'{SITE}/exhibitions/2015/images/dion-thumb-2.jpg',
     {'accession': '2015.6', 'medium': 'Room-sized installation: a wood-paneled den furnished as in 1961',
      'imageCredit': 'Mark Dion, The Undisciplined Collector, 2015. Rose Art Museum Special Fund, 2015.6. ' + CREDIT}),
]
DION = ('A wood-paneled room furnished with the trappings of a 1961 collector’s den, the year the Rose was founded: '
        'books, furniture and objects from the collections of Brandeis University, which visitors can walk into. It '
        'is the museum’s introduction to the history of collecting at Brandeis. Rose Art Museum Special Fund, 2015.6.')
LIGHT = ('rose-2014-3', 'Light of Reason', 'Chris Burden', '2014',
         'Twenty-four antique cast-iron Victorian street lamps and concrete benches in three branches that fan out '
         'from the museum’s entrance, made for the Rose and Brandeis. The three branches come from the three torches, '
         'hills and Hebrew letters of the university seal; the title from Louis D. Brandeis: “If we would guide by the '
         'light of reason, we must let our minds be bold.” The lamps go on at sunset and off at sunrise. Rose Art '
         'Museum Acquisition Fund, gift of Monroe and Edith Geller and Russian Sale Gift, 2014.3.')


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []

    def add(a, room, note, guessed=True):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})

    for key, room, title, artist, date, desc, path, pic, extra in SHOWS:
        if desc is None: desc = paragraph(path, SHOW_TEXT[path])
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'description': desc,
             'url': f'{SITE}/{path}' if path else None, 'temporary': True, 'image': picture(key, pic)}
        a.update(extra)
        if not a['image']: a.pop('imageCredit', None)
        add(a, room, f'The museum puts this show in the {room}; where that room is on this plan is our best '
            'reading of the museum’s pages.')
    for key, room, title, artist, date, path, pic, extra in PERMANENT:
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'description': DION,
             'url': f'{SITE}/{path}', 'image': picture(key, pic)}
        a.update(extra)
        add(a, room, 'A permanent installation in a small ground-floor gallery; its place on this plan is our guess.')
    key, title, artist, date, desc = LIGHT
    a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'accession': '2014.3', 'description': desc,
         'medium': '24 restored cast-iron street lamps, concrete benches', 'url': f'{SITE}/lightofreason/index.html',
         'image': picture(key, f'{SITE}/exhibitions/2021/light-of-reason-images/light-of-reason-735x735.jpg'),
         'imageCredit': 'Chris Burden, Light of Reason, 2014. © Chris Burden. ' + CREDIT, 'outdoor': True}
    add(a, 'Light of Reason', 'Outdoors, on the lawn in front of the main entrance (the Rose circle).', guessed=False)
    return {'source': SOURCE, 'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False,
            'artworks': works}


EXTRA = [
    ('rose-1964-162', 'Elegy to the Spanish Republic, No. 58', 'Robert Motherwell', '1957–1961',
     'Oil on canvas. Gift of Julian J. and Joachim Jean Aberbach, N.Y., 1964.162', 'collection/index.html',
     f'{SITE}/collection/images/motherwell-collection-site.jpg'),
    ('rose-2019-9', 'Supreme Quality', 'Betye Saar', '1998',
     'Mixed media on vintage washboard and tub. Mortimer and Sara Hays Acquisition Fund, 2019.9', 'collection/index.html',
     f'{SITE}/_blocks/permanent-collection/images/betye-saar-2019.9.jpg'),
]


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'],
                     'date': a.get('date'), 'medium': a.get('accession'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': True, 'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    for key, title, artist, date, medium, path, pic in EXTRA:
        rows.append({'id': key, 'title': title, 'artist': artist, 'date': date, 'medium': medium,
                     'url': f'{SITE}/{path}', 'imageUrl': picture(key, pic), 'onView': False})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'), 'source': SOURCE, 'onViewKnown': True,
            'note': 'The Rose has more than 9,000 works, strongest in American art of the 1960s and 1970s, and shows '
                    'them in changing exhibitions. Its online catalogue can’t be read by this guide. Listed here are '
                    'the shows on view now and the permanent installations, in the rooms of an approximate plan, plus '
                    'two collection highlights that may be in storage.',
            'works': rows}


def main():
    if not (CACHE / 'index.json').exists():
        print('No .cache/rose: run tools/harvest_rose.py --wayback (or unpack the claude/rose-cache branch) first')
        return 1
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    for a in works['artworks']:
        print(f"  {a['floor']} {a['gallery']:<24} {a['title'][:40]:<40} {'pic' if a.get('image') else 'NO PIC'}")
    print(f"{works['count']} on the map, {len(guide['works'])} in the guide")


if __name__ == '__main__':
    sys.exit(main())
