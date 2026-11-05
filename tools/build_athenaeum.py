#!/usr/bin/env python3
"""Build the Boston Athenæum (10½ Beacon Street) map guide (run: python3 tools/build_athenaeum.py).

    data/athenaeum/floors.json     the building's floors seen from above (flat 2D plans)
    data/athenaeum/artworks.json   the works the Athenæum says are shown in a given room
    data/athenaeum/images/         their pictures, made smaller for phones
    data/guides/Q478013.json       all 593 paintings and sculptures the Athenæum publishes online

The works
---------
tools/data/athenaeum_works.tsv is the Athenæum's own "Paintings & Sculpture Online" list (593 records: title, artist,
date, medium, credit line, object number and picture), read on 2026-11-05 from its WordPress API
(bostonathenaeum.org/wp-json/wp/v2/paintings and /artist; the pictures' addresses come from its paintings sitemap).
bostonathenaeum.org answers robots (robots.txt allows everything, crawl delay 10 s) but its Cloudflare wall refuses
cloud machines, so the list was read page by page through a web reader and saved here; the pictures
(wp-content/uploads) do download directly and are cached in .cache/athenaeum/img.
The records say nothing about where a work hangs. Only what the Athenæum itself says is used for the map:
  - the Bayard Henry Long Room holds paintings and sculpture from the permanent collection, among them busts of
    Alexander Hamilton and the Marquis de Lafayette (Harvard Magazine, March 2025, on the reopened building);
  - paintings and statues of George Washington are on the fourth floor, among much of his personal library.
Which Hamilton and Lafayette casts, and which Washington works, are our reading: the map says so.

The map
-------
The Athenæum publishes no floor plan (its free Bloomberg Connects guide has one, but that app refuses outside
readers). The plans here are APPROXIMATE, put together from
  - the building's outline in OpenStreetMap (way 405941805), turned so that Beacon Street is at the top: the front
    doors are on Beacon Street, facing the State House; the back looks over the Granary Burying Ground; the Drum
    (a round stair tower) is at the east end;
  - the Athenæum's accessibility guide: vestibule lift on the left, front desk, Bayard Henry Long Room, Gordon
    Reading Room, Leventhal Living Room (huge windows over the Granary Burying Ground), Norma Jean Calderwood
    Gallery, Coat Room with an all-gender restroom and water fountain, multi-stall restrooms with changing table in
    the hall by the Leventhal Room, Children's Library; elevator 1 on the Beacon Street side (basement to 5),
    elevator 2 on the Granary side (basement to 2); restrooms on floors B, 1, 2, 2G, 3, 4 (none on 5); terraces on
    floors 2 and 5; on 4 the Trustees' Room, the living rooms, the Members' Living Room (two restrooms), a kitchenette
    and phone booths; on 5 the Members' Lounge and the terrace; gallery levels (1G-5G) above each reading room;
  - the visit page: visitors pay for the first floor; a day membership opens all floors; Folio, the bistro, has its
    own door at 14A Beacon Street next door.
Which room is exactly where on each floor is our best reading of those sources; the map says so.
Coordinates are metres along the building (east) and across it (towards Beacon Street), times 12.
"""
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'athenaeum'
CACHE = ROOT / '.cache' / 'athenaeum' / 'img'
MUSEUM = 'Q478013'
SITE = 'https://bostonathenaeum.org'
PAGE = SITE + '/library-collections/special-collections/paintings-sculpture-online/'
TODAY = date.today()
SOURCE = ('Approximate: OpenStreetMap building outline and the Athenæum’s accessibility guide and visit pages '
          '(the Athenæum publishes no floor plan)')
K = 12          # pixels per metre
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def P(u, v):
    """Metres east along the building / north towards Beacon Street -> map pixels (Beacon Street at the top)."""
    return [round((u + 19) * K, 1), round((19 - v) * K, 1)]


def poly(*pts):
    return [P(u, v) for u, v in pts]


# The OpenStreetMap outline (way 405941805), turned 30° so the Beacon Street front runs across the top.
OUTLINE = [(-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (17.9, -5.8), (18.5, -7.0), (21.5, -5.2),
           (22.2, -1.0), (22.4, 0.7), (22.0, 2.4), (21.1, 4.0), (18.8, 5.6), (18.9, 12.7), (-15.2, 15.5),
           (-16.0, 6.9), (-15.6, 2.9)]

# Rooms of the first floor, the floor visitors see: (id, kind, name, polygon, short label for galleries)
FLOOR1 = [
    ('Bayard Henry Long Room', 'gallery', 'Bayard Henry Long Room: paintings and sculpture from the collection',
     poly((-4, -4.7), (10, -5.4), (10, 1.5), (-4, 1.5)), 'Long Room'),
    ('Norma Jean Calderwood Gallery', 'gallery', 'Norma Jean Calderwood Gallery: changing exhibitions',
     poly((10, -5.4), (17.9, -5.8), (18.8, 1.5), (10, 1.5)), 'Calderwood'),
    ('Leventhal Living Room', 'gallery', 'Leventhal Living Room: seating and display cases, windows over the Granary '
     'Burying Ground', poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (-4, 1.5), (-15.4, 1.5)),
     'Leventhal'),
    ('Gordon Reading Room', 'gallery', 'Gordon Reading Room: Special Collections highlights (Re-Reading Special '
     'Collections)', poly((6, 5), (18.8, 5), (18.9, 12.7), (6, 13.6)), 'Gordon'),
    ('Lobby', 'corridor', 'Lobby · front desk · admissions', poly((-3, 5), (6, 5), (6, 13.6), (3, 13.8), (3, 15.0),
                                                               (-3, 15.0)), None),
    ('Hall', 'corridor', 'Hall · elevators · restrooms', poly((-15.4, 1.5), (18.8, 1.5), (18.8, 5), (-15.8, 5),
                                                             (-15.6, 2.9)), None),
]
FLOOR1_SPACES = [
    ('Coat Room', 'space', 'Coat Room and lockers (all-gender restroom, water fountain)',
     poly((-8, 5), (-3, 5), (-3, 15.0), (-8, 15.2)), None),
    ('Children’s Library', 'space', 'Children’s Library', poly((-16.0, 5), (-8, 5), (-8, 15.2), (-15.2, 15.5),
                                                                (-16.0, 6.9)), None),
    ('The Drum', 'space', 'The Drum (round stair tower; not wheelchair accessible)',
     poly((18.8, -5.0), (21.5, -5.2), (22.2, -1.0), (22.4, 0.7), (22.0, 2.4), (21.1, 4.0), (18.8, 5.0)), None),
]
FLOOR1_DOORS = [('Lobby', 'Hall', (1.5, 5)), ('Lobby', 'Coat Room', (-3, 9)), ('Lobby', 'Gordon Reading Room', (6, 9)),
                ('Hall', 'Bayard Henry Long Room', (3, 1.5)), ('Hall', 'Norma Jean Calderwood Gallery', (14, 1.5)),
                ('Hall', 'Leventhal Living Room', (-10, 1.5)), ('Hall', 'Children’s Library', (-12, 5)),
                ('Hall', 'Gordon Reading Room', (12, 5)), ('Hall', 'The Drum', (18.8, 3)),
                ('Bayard Henry Long Room', 'Leventhal Living Room', (-4, -1.5)),
                ('Bayard Henry Long Room', 'Norma Jean Calderwood Gallery', (10, -2))]
FLOOR1_AMENITIES = [('entrance', 0, 16.3), ('elevator', -1.5, 13.8), ('info', 1.5, 8), ('coat', -5.5, 11),
                    ('restroom-all', -5.5, 7), ('water', -6.8, 8.5), ('restroom', -13, 3.3), ('nursing', -10.5, 3.3),
                    ('elevator', 4.5, 5.8), ('elevator', 8, 2.3), ('stairs', 6.3, 3.3), ('stairs', 20, 0)]
FLOOR1_LABELS = [
    ('Entrance', 'note', 0, 18.3),
    ('Beacon Street', 'note', 3, 21),
    ('Granary Burying Ground', 'note', 4, -9.5),
    ('Folio bistro (14A Beacon St)', 'note', -12, 18.3),
    ('Approximate plan', 'note', 3, -12.5),
]

# Upper floors and the basement: members and day members only. (id, label, order, area, rooms, amenities, labels)
MEMBERS = 'Members and day members only'


def reading_floor(fid, label, order, area, rooms, amen, notes):
    return {'id': fid, 'label': label, 'order': order, 'area': area, 'rooms': rooms, 'amenities': amen,
            'labels': notes}


UPPER = [
    reading_floor('B', 'Basement', 0, 'Restrooms · elevators · stairs to the Drum', [
        ('Basement', 'space', 'Basement: staff areas and stacks (not open to visitors)',
         poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (17.9, -5.8), (18.8, 1.5), (-15.6, 1.5),
              (-15.6, 2.9))),
        ('B Hall', 'corridor', 'Basement hall', poly((-16.0, 1.5), (18.8, 1.5), (18.8, 12.7), (-15.2, 15.5),
                                                     (-16.0, 6.9))),
        ('B Drum', 'space', 'The Drum (brick floor, uneven)',
         poly((18.8, -5.0), (21.5, -5.2), (22.2, -1.0), (22.4, 0.7), (22.0, 2.4), (21.1, 4.0), (18.8, 5.0))),
    ], [('restroom', -6, 9), ('restroom', -2, 9), ('elevator', -1.5, 13.8), ('elevator', 4.5, 5.8),
        ('elevator', 8, 2.3), ('stairs', 6.3, 3.3)], [MEMBERS]),
    reading_floor('2', 'Floor 2', 2, 'Reading rooms · Study Center · terrace · restroom', [
        ('Floor 2 Reading Room', 'space', 'Reading room (with a gallery level, 2G, above)',
         poly((-15.6, 2.9), (-15.6, 1.5), (18.8, 1.5), (18.8, 5.6), (18.9, 12.7), (-15.2, 15.5), (-16.0, 6.9))),
        ('Study Center', 'space', 'Study Center: Special Collections by appointment',
         poly((-4.3, -4.6), (17.9, -5.8), (18.8, 1.5), (-4, 1.5))),
        ('Floor 2 Terrace', 'space', 'Terrace (three steps down; over the Granary Burying Ground)',
         poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (-4, 1.5), (-15.6, 1.5), (-15.6, 2.9))),
    ], [('restroom-all', -6, 9), ('elevator', -1.5, 13.8), ('elevator', 4.5, 5.8), ('elevator', 8, 2.3),
        ('stairs', 6.3, 3.3), ('stairs', 15, 11)], [MEMBERS, 'Restroom also on gallery level 2G']),
    reading_floor('3', 'Floor 3', 3, 'Reading room · restroom', [
        ('Floor 3 Reading Room', 'space', 'Reading room (with a gallery level, 3G, above)',
         poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (17.9, -5.8), (18.8, 5.6), (18.9, 12.7),
              (-15.2, 15.5), (-16.0, 6.9), (-15.6, 2.9))),
    ], [('restroom-all', -6, 9), ('elevator', -1.5, 13.8), ('stairs', 6.3, 3.3), ('stairs', 15, 11)], [MEMBERS]),
    reading_floor('4', 'Floor 4', 4, 'Trustees’ Room · living rooms · Members’ Living Room · Washington’s library', [
        ('Trustees’ Room', 'gallery', 'Trustees’ Room', poly((-4.3, -4.6), (8, -5.3), (8, 3), (-4, 3)), 'Trustees'),
        ('Washington Room', 'gallery', 'Living room with George Washington’s library, and paintings and statues of '
         'Washington', poly((8, -5.3), (17.9, -5.8), (18.8, 3), (8, 3)), 'Washington'),
        ('Members’ Living Room', 'space', 'Members’ Living Room (gentle ramp at the door; two restrooms)',
         poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (-4, 3), (-15.6, 3))),
        ('Floor 4 Hall', 'corridor', 'Hall · kitchenette · phone booths',
         poly((-15.6, 3), (18.8, 3), (18.8, 5.6), (18.9, 12.7), (-15.2, 15.5), (-16.0, 6.9))),
    ], [('restroom', -11, -2), ('restroom-all', -6, 9), ('elevator', -1.5, 13.8), ('stairs', 6.3, 4.3),
        ('stairs', 15, 11)], [MEMBERS, 'Kitchenette · phone booths off the hall']),
    reading_floor('5', 'Floor 5', 5, 'Fifth-floor reading room · Members’ Lounge · terrace (no restroom)', [
        ('Fifth Floor Reading Room', 'space', 'The fifth-floor reading room (gallery level 5G above, by stairs only)',
         poly((-4.3, -4.6), (17.9, -5.8), (18.8, 5.6), (18.9, 12.7), (-4, 14))),
        ('Members’ Lounge', 'space', 'Members’ Lounge', poly((-15.6, 2.9), (-4, 2.9), (-4, 14), (-15.2, 15.5),
                                                             (-16.0, 6.9))),
        ('Floor 5 Terrace', 'space', 'Terrace: views over the city, the Granary Burying Ground and the resident '
         'falcons (one step up)', poly((-14.1, -10.0), (-10.2, -8.7), (-10.0, -7.1), (-4.3, -4.6), (-4, 2.9),
                                      (-15.6, 2.9))),
    ], [('elevator', -1.5, 13.0), ('stairs', 6.3, 3.3), ('stairs', 15, 11)],
        [MEMBERS, 'No restroom: use floor 4']),
]
FLOOR_LABEL_AT = (3, -12.5)


def build_floors():
    def mk(spec):
        return [{'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if kind == 'gallery' else {})}
                for rid, kind, name, pl, short in spec]
    rooms = mk(FLOOR1 + FLOOR1_SPACES)
    ids = {r['id'] for r in rooms}
    doors = [{'a': a, 'b': b, 'at': P(u, v), 'width': 12, 'axis': 'o'} for a, b, (u, v) in FLOOR1_DOORS]
    for d in doors:
        assert d['a'] in ids and d['b'] in ids, d
    first = {'id': '1', 'label': 'Floor 1', 'order': 1, 'transform': [1, 0, 0],
             'area': 'Entrance · Lobby · Coat Room · Long Room · Calderwood Gallery · Gordon Reading Room · '
                     'Leventhal Living Room · Children’s Library · Restrooms',
             'rooms': rooms, 'closed': [],
             'amenities': [{'type': t, 'at': P(u, v)} for t, u, v in FLOOR1_AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(u, v)} for t, k, u, v in FLOOR1_LABELS],
             'doors': doors}
    floors = [first]
    for f in UPPER:
        rs = []
        for r in f['rooms']:
            rid, kind, name, pl = r[:4]
            short = {'Trustees’ Room': 'Trustees', 'Washington Room': 'Washington'}.get(rid)
            rs.append({'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if short else {})})
        labels = [{'text': f['labels'][0], 'kind': 'note', 'at': P(*FLOOR_LABEL_AT)}]
        labels += [{'text': t, 'kind': 'note', 'at': P(3, -14.5 - 2 * i)} for i, t in enumerate(f['labels'][1:])]
        labels.append({'text': 'Beacon Street', 'kind': 'note', 'at': P(3, 18.5)})
        floors.append({'id': f['id'], 'label': f['label'], 'order': f['order'], 'transform': [1, 0, 0],
                       'area': f['area'], 'rooms': rs, 'closed': [],
                       'amenities': [{'type': t, 'at': P(u, v)} for t, u, v in f['amenities']],
                       'labels': labels, 'doors': []})
    floors.sort(key=lambda f: f['order'])
    return {'about': 'Built by tools/build_athenaeum.py. The Athenæum publishes no floor plan: these plans are '
                     'approximate, drawn inside the building’s real outline (OpenStreetMap) from the Athenæum’s '
                     'accessibility guide. Beacon Street is at the top.',
            'source': SOURCE, 'units': 'metres x 12, Beacon Street at the top', 'defaultFloor': '1',
            'galleryWord': 'Room', 'floors': floors}


# ---- works ----------------------------------------------------------------------------------------------------

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(when):
    m = re.search(r'\d{4}', when or '')
    return int(m[0]) if m else None


def artists():
    out = {}
    for line in (ROOT / 'tools' / 'data' / 'athenaeum_artists.tsv').read_text().splitlines():
        if line.startswith('#') or not line.strip(): continue
        aid, name = line.split('\t')
        m = re.match(r'(.+?)\s*\((.*)\)\s*(attrib\.)?$', name)
        out[aid] = (m[1] + (' (attributed)' if m[3] else ''), m[2]) if m else (name, '')
    return out


def records():
    who = artists()
    rows = []
    for line in (ROOT / 'tools' / 'data' / 'athenaeum_works.tsv').read_text().splitlines():
        if line.startswith('#') or not line.strip(): continue
        slug, title, aids, when, medium, credit, obj, img = (line.split('\t') + [''] * 8)[:8]
        names = [who[a][0] for a in aids.split(',') if a in who]
        if len(names) > 1 and names[-1] in ('Artist unknown', 'Unknown artist'):
            names = names[:-1]                       # "after Raphael" + "Unknown artist" -> "after Raphael"
        artist = ' and '.join(names) or 'Artist unknown'
        artist = artist[0].upper() + artist[1:]
        life = who[aids.split(',')[0]][1] if aids.split(',')[0] in who else ''
        rows.append({'slug': slug, 'title': title, 'artist': artist, 'life': life,
                     'date': '' if when == 'n.d.' else when, 'medium': medium, 'credit': credit.rstrip('.'),
                     'object': obj, 'img': img, 'kind': 'sculpture' if obj.startswith('UH') else 'painting'})
    return rows


def picture(key, url):
    """Save a phone-sized JPEG of the Athenæum's picture (downloaded once into .cache/athenaeum/img)."""
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/athenaeum/images/{key}.jpg'
    if not url: return None
    f = CACHE / url.split('/')[-1]
    if not f.exists() or f.stat().st_size < 1000:
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['curl', '-s', '-f', '-m', '60', '-A', UA, '-o', str(f), url])
        time.sleep(2)
    if not f.exists(): return None
    try:
        im = Image.open(io.BytesIO(f.read_bytes()))
    except Exception:
        return None
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/athenaeum/images/{key}.jpg'


# What the Athenæum says is shown where (see the notes at the top). Object numbers.
LONG_ROOM = {
    'UH159': 'The Athenæum says busts of Alexander Hamilton and the Marquis de Lafayette stand in the Long Room; it '
             'owns two of each, so which casts are out is our guess.',
    'UH149': 'The Athenæum says busts of Alexander Hamilton and the Marquis de Lafayette stand in the Long Room; it '
             'owns two of each, so which casts are out is our guess.',
}
WASHINGTON = ['UR276', 'UR295', 'UR165', 'UR166', 'UH7', 'UH113', 'UH150', 'UH217']
WASH_NOTE = ('The Athenæum shows paintings and statues of George Washington on the fourth floor, among much of his '
             'personal library (members and day members). These are its Washington works; not all may be out at once.')


def build_works(rows):
    by_obj = {}
    for r in rows: by_obj.setdefault(r['object'], r)
    out = []
    placed = [(o, 'Bayard Henry Long Room', '1', note) for o, note in LONG_ROOM.items()]
    placed += [(o, 'Washington Room', '4', WASH_NOTE) for o in WASHINGTON]
    names = {'Bayard Henry Long Room': 'Bayard Henry Long Room', 'Washington Room': 'Fourth floor: Washington’s library'}
    for obj, room, floor, note in placed:
        r = by_obj[obj]
        key = 'athenaeum-' + r['slug']
        a = {'id': key, 'title': r['title'], 'artist': r['artist'], 'date': r['date'], 'year': year_of(r['date']),
             'medium': r['medium'], 'creditLine': ', '.join(x for x in (r['credit'], f'Boston Athenæum {obj}') if x),
             'gallery': room, 'galleryName': names[room], 'floor': floor, 'placeNote': note,
             'url': PAGE + r['slug'] + '/', 'image': picture(key, r['img']), 'imageCredit': 'Boston Athenæum'}
        if not a['image']: a.pop('imageCredit')
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    return {'source': 'Boston Athenæum, Paintings & Sculpture Online (bostonathenaeum.org)', 'checked': TODAY.isoformat(),
            'count': len(out), 'complete': False, 'artworks': out}


def build_guide(works, rows):
    on = {a['id']: a for a in works['artworks']}
    out = []
    for r in rows:
        key = 'athenaeum-' + r['slug']
        w = {'id': key, 'title': r['title'], 'artist': r['artist'], 'date': r['date'], 'year': year_of(r['date']),
             'medium': r['medium'], 'url': PAGE + r['slug'] + '/', 'imageUrl': on[key].get('image') if key in on
             else (r['img'] or None), 'credit': ', '.join(x for x in (r['credit'], r['object']) if x),
             'onView': key in on}
        if key in on: w.update(gallery=on[key]['gallery'], floor=on[key]['floor'])
        out.append({k: v for k, v in w.items() if v not in (None, '')})
    out.sort(key=lambda w: (not w['onView'], norm(w['artist'].split(' ')[-1]), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Boston Athenæum', 'checked': TODAY.isoformat(),
            'source': 'Boston Athenæum, Paintings & Sculpture Online', 'onViewKnown': False,
            'note': 'These are the 593 paintings and sculptures the Athenæum publishes online: portraits of Bostonians, '
                    'busts and casts bought for its first art gallery in the 1800s, Allan Rohan Crite’s Boston scenes '
                    'and more. Many hang in the reading rooms on the upper floors, which only members and day members '
                    'see. The Athenæum does not say online where each one is, so only the few it names are on the map.',
            'works': out}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    rows = records()
    works = build_works(rows)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, rows)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'collection list {len(guide["works"])} ({idx["museums"][MUSEUM]["pictures"]} pictures)')


if __name__ == '__main__':
    sys.exit(main())
