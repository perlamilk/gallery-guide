#!/usr/bin/env python3
"""Build the John F. Kennedy Presidential Library and Museum (Boston) map guide
(run: python3 tools/harvest_jfk.py, then this).

    data/jfk/floors.json       the Entrance Level (with the drive and parking) and the Exhibit Level (with the
                               Pavilion and the lawn by the harbor), seen from above (flat 2D)
    data/jfk/artworks.json     the permanent exhibits and the museum's objects, in the gallery where they likely are
    data/jfk/images/           pictures from Google Arts & Culture, made smaller for phones
    data/guides/Q2007919.json  the same, for the museum page

Where the information comes from
--------------------------------
jfklibrary.org answers 403 to cloud machines, and its robots.txt shuts out AI agents (ClaudeBot, Claude-Web,
anthropic-ai), so this guide does not read the museum's own site, not even its visitor map. The map is APPROXIMATE
and says so:

  - The building: I. M. Pei's published plans of 1979 ("Level 2, Entrance Level" and "Level 1, Ground Floor Exhibit
    Level", reproduced by WikiArquitectura: en.wikiarquitectura.com/wp-content/uploads/2017/04/
    JFK-library-niveles-acceso.jpg, cached in .cache/jfk/). Coordinates here are pixels of that drawing (the Level 1
    drawing sits 65 px right and 868 px down of Level 2), times 2. On it 50 feet are 87 px, so one pixel is about
    0.175 m. North is up and to the left. Level 2 (entrance): the glass lobby between the triangular tower and the
    round theater wing, the theater lobby and Theaters I and II, the bookstore and elevator lobby at the foot of the
    tower, the West Plaza (built over by the Stephen E. Smith Center in 1991). Level 1: the exhibit floor under it
    all, the glass Pavilion (floor on Level 1, open up to the roof), service rooms and restrooms along the south side.
  - The exhibits inside were rebuilt in 1993, so where each one stands is our guess, from visitors' accounts of the
    route (uponarriving.com, 2024; Fodor's; VisitMA): tickets, then the film in Theater One, early-years exhibits in
    the theater lobby, then down to the 1960 campaign (convention, the TV studio of the first debate, election night),
    the inauguration and a White House corridor, the Space Race room, the Cuban Missile Crisis theater, the Attorney
    General's office, the Oval Office, the First Lady's gallery, November 22, 1963 and the legacy galleries, a large
    piece of the Berlin Wall, and out into the Pavilion with its huge flag; special exhibitions and the Kennedy Café
    off the Pavilion. Restrooms and the self-service coat room on the lobby level (the museum's FAQ, as quoted in
    search results).
  - The 2012 addition and the grounds (drive, parking, the lawn by the harbor where JFK's sailboat Victura stands)
    from the same drawings and OpenStreetMap (the café and Victura are mapped there).

The objects: what the museum publishes on Google Arts & Culture (tools/harvest_jfk.py): 28 objects, photographs and
papers, with the museum's own texts. Each is put in the gallery about its subject and says it may not be on view.
"""
import io
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'jfk'
CACHE = ROOT / '.cache' / 'jfk'
MUSEUM = 'Q2007919'
NAME = 'John F. Kennedy Presidential Library and Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
GUESS = '(approximate)'
L1 = (65, 868)                     # where Level 1 sits on the drawing, relative to Level 2


def P(x, y):
    return [round(x * 2, 1), round(y * 2, 1)]


def low(pts):
    """Level 1 drawing pixels -> the shared (Level 2) frame."""
    return [(x - L1[0], y - L1[1]) for x, y in pts]


def arc(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def circle(cx, cy, r, n=24):
    return arc(cx, cy, r, 0, 360, n)[:-1]


CYL = (612, 385, 85)               # the round theater wing on Level 2
PAVILION = [(442, 214), (530, 300), (442, 388), (355, 300)]

# ---- Level 2: Entrance Level ------------------------------------------------------------------------------------

ENTRANCE = [
    ('Lobby', 'space', 'Entrance lobby: tickets and admissions desk, restrooms, self-service coat room',
     [(440, 472), (545, 368), (545, 300), (530, 300), (442, 388)], None),
    ('Theater Lobby', 'gallery', f'Theater lobby: Kennedy’s early years, while you wait for the film {GUESS}',
     [(545, 300), (600, 300), (600, 397), (545, 397)], 'Early Years'),
    ('Theater II', 'gallery', 'Theater II: the introductory film about Kennedy’s life (about 17 minutes)',
     [(600, 300), (612, 300)] + arc(*CYL, -90, 8)[1:] + [(600, 397)], 'Theater II'),
    ('Theater I', 'gallery', 'Theater I: the introductory film about Kennedy’s life. Start here, then go down to '
     'the exhibits', [(545, 397), (696, 397)] + arc(*CYL, 8, 160)[1:], 'Theater I'),
    ('Museum Store', 'space', f'Museum Store and the elevator lobby at the foot of the tower {GUESS}',
     [(273, 302), (440, 302), (440, 472)], None),
    ('Pavilion Overlook', 'space', 'The Pavilion seen from above: its floor is one level down (stairs and elevator)',
     PAVILION, None),
    ('Front Plaza', 'corridor', 'Walk from the drive to the front door',
     [(440, 472), (545, 368), (528, 430), (515, 475), (500, 505), (410, 505), (410, 480)], None),
    ('Drive', 'corridor', 'Entrance drive and drop-off circle', circle(478, 572, 68), None),
    ('Parking', 'space', 'Free parking lot', [(440, 690), (830, 690), (830, 830), (440, 830)], None),
]
ENTRANCE_CLOSED = [
    [(273, 302), (440, 472), (275, 640)],                       # Smith Center (1991), on the old West Plaza
    [(32, 467), (282, 467), (282, 633), (32, 633)],             # archive addition (2012)
]
ENTRANCE_DOORS = [('Front Plaza', 'Lobby', (492, 420)), ('Lobby', 'Theater Lobby', (545, 340)),
                  ('Theater Lobby', 'Theater I', (572, 397)), ('Theater Lobby', 'Theater II', (600, 350)),
                  ('Lobby', 'Museum Store', (440, 430)), ('Lobby', 'Pavilion Overlook', (486, 344)),
                  ('Front Plaza', 'Drive', (470, 505)), ('Drive', 'Parking', (478, 640))]
ENTRANCE_AMEN = [('entrance', 492, 420), ('info', 470, 418), ('restroom', 500, 372), ('coat', 518, 352),
                 ('shop', 395, 395), ('elevator', 345, 330), ('stairs', 400, 322), ('stairs', 652, 445)]
ENTRANCE_LABELS = [('Main entrance ›', 560, 520),
                   ('Smith Center (events)', 320, 520),
                   ('Archives (closed)', 150, 550),
                   ('P · Free parking', 640, 770),
                   ('Approximate map', 700, 640)]

# ---- Level 1: Exhibit Level (drawing pixels of the Level 1 plan, moved into the shared frame by low()) -----------

EXHIBITS = [
    ('Pavilion', 'gallery', 'The Pavilion: the 115-foot glass hall with the great American flag and the view over '
     'Boston Harbor. The museum visit ends here', [(505, 1081), (597, 1167), (505, 1255), (422, 1167)], 'Pavilion'),
    ('Kennedy Café', 'space', f'Kennedy Café, off the Pavilion {GUESS}: open 10 am–4 pm',
     [(597, 1167), (660, 1167), (660, 1215), (600, 1215), (552, 1210)], None),
    ('Campaign 1960', 'gallery', f'The 1960 campaign {GUESS}: the campaign trail, the Democratic convention, the TV '
     'studio of the first Kennedy–Nixon debate and election night',
     [(660, 1168), (690, 1168), (745, 1200), (760, 1250), (745, 1295), (676, 1385), (676, 1428), (600, 1428),
      (600, 1215), (660, 1215)], 'Campaign'),
    ('White House', 'gallery', f'The White House years {GUESS}: the inauguration, the White House corridor, the '
     'Attorney General’s office and the Oval Office',
     [(505, 1255), (552, 1210), (600, 1215), (600, 1330), (440, 1330), (440, 1320)], 'White House'),
    ('Space and Missiles', 'gallery', f'The Space Race and the Cuban Missile Crisis theater {GUESS}',
     [(440, 1330), (600, 1330), (600, 1428), (440, 1428)], 'Space · Cuba'),
    ('Legacy', 'gallery', f'The First Lady, November 22, 1963 and the legacy galleries, with a piece of the Berlin '
     f'Wall before the Pavilion {GUESS}', [(400, 1167), (422, 1167), (505, 1255), (440, 1320), (440, 1428), (400, 1428)],
     'Legacy'),
    ('Special Exhibitions', 'gallery', f'Special exhibitions gallery {GUESS}',
     [(340, 1167), (400, 1167), (400, 1428), (340, 1428)], 'Special'),
    ('Restrooms', 'space', f'Restrooms {GUESS}', [(520, 1428), (575, 1428), (575, 1490), (520, 1490)], None),
]
EXHIBITS_CLOSED = [[(340, 1428), (520, 1428), (520, 1500), (340, 1500)],
                   [(575, 1428), (676, 1428), (676, 1500), (575, 1500)]]
EXHIBITS_DOORS = [('Campaign 1960', 'White House', (600, 1270)), ('White House', 'Space and Missiles', (520, 1330)),
                  ('Space and Missiles', 'Legacy', (440, 1380)), ('White House', 'Legacy', (472, 1288)),
                  ('Legacy', 'Pavilion', (463, 1211)), ('Legacy', 'Special Exhibitions', (400, 1300)),
                  ('Pavilion', 'Kennedy Café', (575, 1188)), ('Space and Missiles', 'Restrooms', (547, 1428))]
EXHIBITS_AMEN = [('dining', 615, 1190), ('restroom', 547, 1455), ('elevator', 410, 1198), ('stairs', 465, 1190),
                 ('stairs', 717, 1313)]
EXHIBITS_LABELS = [('Approximate map', 520, 1525)]

# the outdoors on the harbor side is at Exhibit Level (shared-frame pixels)
LAWN = [(272, 300), (355, 300), (442, 214), (530, 300), (840, 300), (840, 240), (605, 70), (272, 178)]
HARBORWALK = [(272, 178), (605, 70), (840, 240), (840, 222), (605, 52), (272, 160)]
OUT_LABELS = [('Victura', 590, 222), ('Dorchester Bay ›', 420, 115)]


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, home=None):
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [0.25, 0, 0], 'area': area, 'rooms': rr,
         'closed': [{'poly': [P(*q) for q in c]} for c in closed],
         'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': P(x, y)} for t, x, y in labels],
         'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}
    if home: f['homeView'] = home
    return f


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def build_floors():
    ex = [(rid, kind, name, low(poly), short) for rid, kind, name, poly, short in EXHIBITS]
    ex += [('Harbor Lawn', 'space', 'The lawn by the harbor, with Victura, JFK’s sailboat, and the HarborWalk',
            LAWN, None),
           ('HarborWalk', 'corridor', 'Boston HarborWalk along Dorchester Bay', HARBORWALK, None)]
    exd = [(a, b, low([p])[0]) for a, b, p in EXHIBITS_DOORS] + [('Kennedy Café', 'Harbor Lawn', (560, 300)),
                                                                  ('Harbor Lawn', 'HarborWalk', (440, 145))]
    exa = [(t, *low([(x, y)])[0]) for t, x, y in EXHIBITS_AMEN] + [('entrance', 560, 300)]
    exl = [(t, *low([(x, y)])[0]) for t, x, y in EXHIBITS_LABELS] + OUT_LABELS
    floors = [
        floor('1', 'Exhibit Level', 1, 'The permanent exhibits: 1960 campaign · White House years · Space Race and '
              'Cuban Missile Crisis · legacy · the Pavilion · Kennedy Café · special exhibitions (approximate)',
              ex, [low(c) for c in EXHIBITS_CLOSED], exd, exa, exl),
        floor('2', 'Entrance Level', 2, 'Drive and parking · entrance lobby (tickets, restrooms, coat room) · '
              'Theaters I and II and the early-years exhibit · Museum Store (approximate)',
              ENTRANCE, ENTRANCE_CLOSED, ENTRANCE_DOORS, ENTRANCE_AMEN, ENTRANCE_LABELS,
              home=['Lobby', 'Theater I', 'Drive']),
    ]
    for f in floors:
        ids = {r['id'] for r in f['rooms']}
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_jfk.py. Walls and floors are traced from I. M. Pei’s 1979 plans of the '
                     'building. Which exhibit is in which room is approximate: the exhibits were rebuilt in 1993 and '
                     'the museum’s own map could not be read, so they are placed from visitors’ accounts of the route.',
            'source': 'I. M. Pei & Partners, plans of Level 1 and Level 2 (1979, via WikiArquitectura); '
                      'OpenStreetMap; visitors’ accounts of the route',
            'units': 'pixels of the 1979 drawing x 2 (one pixel is about 0.175 m); north is up and to the left',
            'approximate': True, 'defaultFloor': '2', 'galleryWord': 'Gallery', 'floors': floors}


# ---- exhibits and objects ---------------------------------------------------------------------------------------

def picture(key, url):
    if not url: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1)
        if not out: return None
        raw.write_bytes(out)
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            raw.unlink()
            return None
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/jfk/images/{key}.jpg'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


EXHIBIT_NOTE = 'A permanent exhibit. Which room it is in is our guess from visitors’ accounts.'
OBJECT_NOTE = ('Placed in the gallery about its subject. The museum changes what it shows, so this may not be on '
               'view.')

# Permanent exhibits along the route, in order. Texts written for this guide from visitors' accounts.
ROUTE = [
    ('film', 'Theater I', 'Introductory film', 'Start in Theater One: a short film (about 17 minutes) on Kennedy’s '
     'life up to the 1960 campaign, in his own words. Shows run through the day.', None),
    ('early', 'Theater Lobby', 'The early years', 'While you wait for the film: the Kennedy family, Jack’s childhood '
     'illnesses, school days at Choate and Harvard, and his Navy service in the Pacific.', 'LQFBfvA8-6oZtw'),
    ('campaign', 'Campaign 1960', 'The Campaign Trail', 'The 1960 race for the presidency: the primaries, campaign '
     'buttons and posters, and the suitcase Kennedy carried from state to state.', 'EwEXABTK0cbNGw'),
    ('convention', 'Campaign 1960', 'The Democratic National Convention', 'Los Angeles, July 1960: the convention '
     'that nominated Kennedy, and his “New Frontier” acceptance speech.', None),
    ('debate', 'Campaign 1960', 'The Kennedy–Nixon debates', 'The first televised presidential debate, September 26, '
     '1960, with the TV camera and the audio control desk from the CBS studio in Chicago.', None),
    ('election', 'Campaign 1960', 'Election Night', 'November 8, 1960: one of the closest elections in American '
     'history, followed hour by hour.', None),
    ('inauguration', 'White House', 'The Inauguration', 'January 20, 1961: listen to the inaugural address (“Ask not '
     'what your country can do for you…”).', 'rwF-6fb_b0BtJA'),
    ('corridor', 'White House', 'The White House Corridor', 'A corridor styled after the White House, with the '
     'President’s days, his staff and his visitors.', 'dwGhmbkyBcV6tw'),
    ('ag', 'White House', 'The Attorney General’s Office', 'A room modeled on Robert F. Kennedy’s office at the '
     'Justice Department, with his own things, such as his glasses.', None),
    ('oval', 'White House', 'The Oval Office', 'A reproduction of President Kennedy’s Oval Office, with a copy of the '
     'Resolute Desk and his bookends made from cannons of the USS Constitution, and his scrimshaw.', None),
    ('space', 'Space and Missiles', 'The Space Race', 'Kennedy’s goal of the Moon “before this decade is out”, with a '
     'one-eighth scale model of the Gemini capsule given to him in 1962.', 'xwF4jJ6HREHjmA'),
    ('cuba', 'Space and Missiles', 'The Cuban Missile Crisis', 'A small theater shows “To the Brink”, a 14-minute film on '
     'the thirteen days of October 1962, every 20 minutes.', 'YQHTFO-7zTgSPw'),
    ('firstlady', 'Legacy', 'The First Lady', 'Jacqueline Kennedy: her early life, her restoration of the White House '
     'and her televised tour of it, which won an Emmy.', None),
    ('nov22', 'Legacy', 'November 22, 1963', 'A short, dark corridor on the assassination in Dallas, told mostly by the '
     'television news of that day.', None),
    ('legacy', 'Legacy', 'Legacy', 'What followed: the Peace Corps, the space program and the generation Kennedy '
     'inspired. Before the Pavilion, a large section of the Berlin Wall.', None),
    ('pavilion', 'Pavilion', 'The Pavilion', 'I. M. Pei’s glass hall, 115 feet high, with a huge American flag and the '
     'view over Dorchester Bay to Boston. Sit here at the end of the visit.', None),
    ('victura', 'Harbor Lawn', 'Victura', 'Kennedy’s own 25-foot sailboat, which he sailed off Hyannis Port from the '
     'age of 15. It stands on the lawn by the harbor, outside the Pavilion.', None),
]

SUBJECT = [   # (words in an object's title, gallery)
    (r'space|gemini|shepard|glenn|friendship|collier|canaveral|rice univ|spacewalk|aldrin|moon|khrushchev'
     r'|special message|vice president|critiquing', 'Space and Missiles'),
    (r'cuba|briefing board|gnome', 'Space and Missiles'),
    (r'suitcase|press conference|1959', 'Campaign 1960'),
    (r'navy|pt 109|pt-109', 'Special Exhibitions'),
    (r'choate|muckers|portrait from|health records', 'Theater Lobby'),
    (r'.', 'White House'),
]


def gac_rows():
    f = CACHE / 'gac-works.json'
    if not f.exists(): raise SystemExit('run tools/harvest_jfk.py first')
    rows, seen = {}, set()
    for w in json.loads(f.read_text()):
        gid = w['gac'].rsplit('/', 1)[1]
        if gid in rows:
            if w['story'] and not rows[gid]['story']: rows[gid]['story'] = w['story']
            continue
        w['gid'] = gid
        if w['date'] == '1905-05-14': w['date'] = '1961-04-20'     # the museum's page has a typo (the memo is April 20, 1961)
        rows[gid] = w
    return list(rows.values())


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    gac = {w['gid']: w for w in gac_rows()}
    works = []

    def add(a, room, note, guessed=True):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    for i, (key, room, title, text, pic) in enumerate(ROUTE):
        img = None
        if pic and pic in gac:
            img = picture('jfk-gac-' + pic, gac[pic]['image'] and gac[pic]['image'] + '=w1000')
        a = {'id': f'jfk-exhibit-{key}', 'title': title, 'artist': 'Permanent exhibit', 'medium': 'Exhibit',
             'description': text, 'stop': i + 1, 'image': img,
             'imageCredit': f'John F. Kennedy Presidential Library and Museum, via Google Arts & Culture: '
                            f'{gac[pic]["title"]}' if img else None,
             'url': 'https://www.jfklibrary.org/'}
        add(a, room, EXHIBIT_NOTE, guessed=room not in ('Theater I', 'Pavilion', 'Harbor Lawn'))
    for w in gac.values():
        key = 'jfk-gac-' + w['gid']
        room = next(r for pat, r in SUBJECT if re.search(pat, w['title'], re.I))
        creator = w['creator']
        if creator.startswith('John F. Kennedy Presidential Library') or not creator: creator = 'JFK Library collection'
        if creator.startswith('Papers of John F. Kennedy'): creator = 'Papers of John F. Kennedy'
        a = {'id': key, 'title': w['title'], 'artist': creator, 'date': w['date'] or None,
             'year': year_of(w['date']), 'medium': w['medium'] or w['type'] or None,
             'description': (w['text'] or '')[:1500] or None, 'url': w['gac'],
             'image': picture(key, w['image'] and w['image'] + '=w1000'),
             'imageCredit': 'John F. Kennedy Presidential Library and Museum, via Google Arts & Culture'}
        if w['story']: a['story'] = w['story']
        add(a, room, OBJECT_NOTE)
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a.get('stop') or 99, a.get('year') or 0))
    return {'source': 'JFK Library on Google Arts & Culture (objects); visitors’ accounts (exhibits); galleries '
                      'approximate', 'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False,
            'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': a['artist'] == 'Permanent exhibit', 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'JFK Library on Google Arts & Culture, and visitors’ accounts of the permanent exhibits',
            'onViewKnown': False,
            'note': 'The library holds some 24 million documents, 400,000 photographs and thousands of museum '
                    'objects; the museum shows a small part of them in its permanent exhibits. The exhibits are '
                    'listed in the order of the visit; the objects are the ones the museum publishes on Google '
                    'Arts & Culture and may not be on view.',
            'works': rows}


def main():
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
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} exhibits and objects ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
