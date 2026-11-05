#!/usr/bin/env python3
"""Build the New England Air Museum (Windsor Locks, CT) map guide (run: python3 tools/build_neam.py).

    data/neam/floors.json     the hangars and grounds from above, and the mezzanine (flat 2D)
    data/neam/artworks.json   the aircraft, exhibits and engines, each in a hangar
    data/guides/Q7007140.json the same, plus the aircraft in storage and the engine collection, for the museum page

The museum's pages (neam.org, a Shopify site; robots.txt allows them) and OpenStreetMap are read once into
.cache/neam, 3 seconds apart.

The map
-------
NEAM hands out a paper map at the desk but publishes none online. The plan here is drawn from:
  - OpenStreetMap (ODbL, api.openstreetmap.org/api/0.6/map): the outlines of the Military Hangar (way 167257109),
    the Civil Aviation Hangar (1287255447), the B-29 Hangar (1287255448), the Restoration Hangar (167259457), the
    Storage Hangar (152293833), the entrance canopy (1349336876), the parking lot (152293836), the outdoor aircraft
    (C-7A, A-3B, HU-16E) and Perimeter Road. These are true to scale.
  - the museum's own words (neam.org/pages/visit): three exhibit hangars on more than one floor, most exhibits on the
    ground floor, an elevator next to each mezzanine, a small dining area with vending machines, picnic tables in the
    outside yard, outdoor "Restoration Park" closed in winter; and on aircraft pages, which hangar a plane is in
    (ZNPK-28 and CBY-3 "Civilian Hangar"; K-225, A-10, F-104C "Military Hangar").
  - a visitor's walk-through (A. Epplett, Feb 2026): admission counter in the lobby, then the Military Hangar
    (CH-54, A-26, F-100), a hallway with New England Women in Aviation, a small room with the Kosciuszko Squadron,
    the Civil Aviation Hangar (Electra, CBY-3, R-3, VS-44, DC-3, PT-17, HH-52A), the Space & Observation Mezzanine
    (Silas Brooks basket, space toilet; the B-29 seen from it), the B-29 Hangar with the Tuskegee Airmen exhibit, and
    outside the K-16B and an HU-25A.
Where the lobby, shop, restrooms, vending and mezzanine are inside each hangar, and the hangar of every plane the
museum doesn't place, is our best reading: the map and each plane say so.
Coordinates are metres east / north of 41.9475 N, 72.6910 W, times K.
"""
import html
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'neam'
CACHE = ROOT / '.cache' / 'neam'
MUSEUM = 'Q7007140'
NAME = 'New England Air Museum'
SITE = 'https://neam.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
K = 4            # map units per metre
LAT0, LON0 = 41.9475, -72.6910
OSM_BBOX = '-72.6985,41.9435,-72.6855,41.9505'


def get(url, dest):
    dest = CACHE / dest
    if not (dest.exists() and dest.stat().st_size > 500):
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '120', '-A', UA, url], capture_output=True).stdout
        time.sleep(3)
        if not out: raise SystemExit(f'could not read {url}')
        dest.write_bytes(out)
    return dest.read_text(encoding='utf-8', errors='ignore')


def P(x, y):
    """Metres east / north of the museum's middle -> map units (north up)."""
    return [round((x + 160) * K, 1), round((130 - y) * K, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def clip(poly, box):
    """The part of poly inside the rectangle box (Sutherland-Hodgman; the box is convex)."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
             (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))]
    out = list(poly)
    for inside_, cut in edges:
        src, out = out, []
        for i, cur in enumerate(src):
            prev = src[i - 1]
            if inside_(cur):
                if not inside_(prev): out.append(cut(prev, cur))
                out.append(cur)
            elif inside_(prev):
                out.append(cut(prev, cur))
    pts = []
    for p in out:
        p = (round(p[0], 2), round(p[1], 2))
        if not pts or p != pts[-1]: pts.append(p)
    return pts


def band(pts, half):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        left.append((x - dy / n * half, y + dx / n * half)); right.append((x + dy / n * half, y - dx / n * half))
    return left + right[::-1]


def osm():
    raw = get(f'https://api.openstreetmap.org/api/0.6/map?bbox={OSM_BBOX}', 'osm.xml')
    r = ET.fromstring(raw)
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in r.iter('node')}
    c = math.cos(math.radians(LAT0))

    def xy(p): return (round((p[1] - LON0) * 111320 * c, 1), round((p[0] - LAT0) * 110540, 1))
    ways = {}
    for w in r.iter('way'):
        pts = [xy(nodes[n.get('ref')]) for n in w.findall('nd') if n.get('ref') in nodes]
        if len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
        ways[w.get('id')] = pts
    return ways


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def build_floors():
    w = osm()
    MIL, CIV, B29 = w['167257109'], w['1287255447'], w['1287255448']
    road = [p for p in w['186873021'] if -170 < p[0] < 90]
    yard = [(-76, 39), (-39.3, 36), (-24, 52), (-25, 57), (-66, 62), (-70, 66), (-70, 80), (-81, 81), (-78, 39)]
    G = [
        ('Perimeter Road', 'corridor', 'Perimeter Road: from Route 75, the museum is at no. 36 on the north side of '
         'Bradley Airport', band(road, 4), None),
        ('Parking', 'space', 'Free parking (accessible spaces next to the entrance)', w['152293836'], None),
        ('Entrance', 'corridor', 'Entrance under the canopy, from the parking lot', w['1349336876'], None),
        ('Lobby', 'space', 'Lobby: admission counter (tickets, maps, wheelchairs to borrow, simulator passes), museum '
         'shop, restrooms and the small dining area with vending machines', clip(MIL, (-44, -70, -25, -18)), None),
        ('Military Hangar', 'gallery', 'Military Hangar: warplanes and helicopters, the Kaman exhibit and the 416th '
         'Bombardment Group Memorial', clip(MIL, (-25, -70, 46, -18)), 'Military'),
        ('Hallway', 'gallery', 'Hallway to the Civil Aviation Hangar: New England Women in Aviation',
         clip(CIV, (-1, -23, 8, -6.6)), 'Hallway'),
        ('Kosciuszko Room', 'gallery', 'A small room for The Kosciuszko Squadron: Defenders of Freedom, 1919–1946',
         clip(CIV, (-24, -6.6, -8, 3)), 'Kosciuszko'),
        ('Civil Aviation Hangar', 'gallery', 'Civil Aviation Hangar (the main hangar, 1984): airliners, racers, '
         'flying boats, pioneers and the first helicopters', clip(CIV, (-8, -6.6, 50, 45)), 'Civil'),
        ('Civil West', 'gallery', 'Civil Aviation Hangar, west side (under the Space & Observation Mezzanine)',
         clip(CIV, (-24, 3, -8, 45)), 'Civil'),
        ('B-29 Link', 'corridor', 'Passage to the B-29 Hangar', clip(B29, (-41.5, 2.5, -21.5, 12)), None),
        ('B-29 Hangar', 'gallery', 'B-29 Hangar: the 58th Bomb Wing Memorial (B-29 “Jack’s Hack”) and the Tuskegee '
         'Airmen exhibit', clip(B29, (-81, -13, -39, 39)), 'B-29'),
        ('Yard', 'space', 'Outside yard: picnic tables in fair weather', yard, None),
        ('Restoration Park', 'gallery', 'Restoration Park: fewer than a dozen planes outdoors, waiting for '
         'restoration. Weather permitting; closed in winter', [(-148, 58), (-82, 54), (-80, 81), (-78, 118),
                                                                   (-96, 113), (-113, 113), (-134, 106), (-147, 104)],
         'Outdoors'),
        ('Restoration Hangar', 'space', 'Restoration Hangar (1989): the volunteers’ workshop, 11,200 sq ft (staff '
         'only)', w['167259457'], None),
        ('Storage Hangar', 'space', 'Storage Hangar (2010): planes in storage (not open to visitors)', w['152293833'],
         None),
    ]
    G_DOORS = [('Parking', 'Entrance', (-57, -36)), ('Entrance', 'Lobby', (-42.6, -36.5)),
               ('Lobby', 'Military Hangar', (-25, -42)), ('Military Hangar', 'Hallway', (3.5, -21.8)),
               ('Hallway', 'Civil Aviation Hangar', (4.2, -6.6)), ('Civil Aviation Hangar', 'Kosciuszko Room',
                                                                   (-8, -2)),
               ('Civil Aviation Hangar', 'Civil West', (-8, 20)), ('Kosciuszko Room', 'Civil West', (-15, 3)),
               ('Civil West', 'B-29 Link', (-22.2, 7)), ('B-29 Link', 'B-29 Hangar', (-40.5, 7)),
               ('B-29 Hangar', 'Yard', (-58, 37.2)), ('Yard', 'Restoration Park', (-79, 60)),
               ('Parking', 'Perimeter Road', (0, -88))]
    G_AMEN = [('entrance', -50, -36), ('info', -36, -36), ('shop', -36, -28), ('restroom', -38, -50),
              ('restroom-all', -32, -50), ('dining', -35, -60), ('elevator', -12, 8), ('stairs', -12, 12),
              ('elevator', -36, -24)]
    G_LABELS = [('Free parking', -100, -45), ('Bradley International Airport ↓', 0, -110),
                ('Approximate rooms inside the real hangar outlines (no plan is published)', -40, 128),
                ('Outdoor aircraft: closed in winter', -115, 50)]
    M = [
        ('Space & Observation Mezzanine', 'gallery', 'Space & Observation Mezzanine above the Civil Aviation Hangar: '
         'Apollo & Beyond (spacesuits), the Silas Brooks balloon basket; look down on the B-29 and the hangar floor',
         clip(CIV, (-24, 3, -8, 45)), 'Mezzanine'),
        ('Hangar below', 'space', 'Civil Aviation Hangar below (open to the roof)', clip(CIV, (-8, -6.6, 50, 45)),
         None),
    ]
    M_DOORS = [('Space & Observation Mezzanine', 'Hangar below', (-8, 25))]
    M_AMEN = [('elevator', -12, 8), ('stairs', -12, 12)]
    M_LABELS = [('Mezzanine level: approximate', 20, 50), ('B-29 Hangar ← (seen from the mezzanine)', -58, 15)]

    def floor(fid, label, order, area, rooms, doors, amen, labels):
        rr = []
        for rid, kind, name, poly, short in rooms:
            assert len(poly) >= 3, rid
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short
            rr.append(r)
        return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area, 'rooms': rr,
                'closed': [], 'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
                'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
                'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 14, 'axis': 'o'} for a, b, p in doors]}
    floors = [
        floor('G', 'Hangars', 0, 'Entrance · Lobby · Military, Civil Aviation and B-29 Hangars · outdoor aircraft',
              G, G_DOORS, G_AMEN, G_LABELS),
        floor('M', 'Mezzanine', 1, 'Space & Observation Mezzanine (Civil Aviation Hangar)', M, M_DOORS, M_AMEN,
              M_LABELS),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_neam.py. The New England Air Museum publishes no map online (a paper map '
                     'is handed out at the desk). The hangars, parking and outdoor planes are traced from '
                     'OpenStreetMap, true to scale; the lobby, shop, restrooms, vending and the mezzanine inside them '
                     'are placed from the museum’s own descriptions and are approximate.',
            'source': 'OpenStreetMap (hangar outlines) and the New England Air Museum’s visit and aircraft pages; '
                      'rooms inside the hangars approximate',
            'units': f'metres x {K}, north up', 'approximate': True, 'defaultFloor': 'G', 'galleryWord': 'Hangar',
            'floors': floors}


# ---- the collection -----------------------------------------------------------------------------------------------

def text_of(s):
    s = re.sub(r'(?s)<(script|style|noscript)[^>]*>.*?</\1>', '', s)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', s))
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    i = [k for k, l in enumerate(lines) if l == 'Cart']
    j = [k for k, l in enumerate(lines) if l == 'Quick Links']
    return lines[(i[-1] + 1 if i else 0):(j[0] if j else len(lines))]


def page(slug):
    return get(f'{SITE}/pages/{slug}', f'pages/{slug}.html')


def img(name, width=800):
    """A picture on the museum's Shopify CDN, at a phone-friendly width."""
    stem, ext = name.rsplit('.', 1)
    return f'https://neam.org/cdn/shop/files/{stem}.{ext}?width={width}'


def paragraphs(slug, n=3):
    out = []
    for l in text_of(page(slug)):
        if len(l) > 90 and not l.isupper() and 'click' not in l.lower() and 'donat' not in l.lower():
            out.append(l)
        if len(out) == n: break
    return '\n\n'.join(out)


# key: (hangar, guessed?, year built, type, featured page, words)
# Hangars the museum or the visitor walk-through names are not guessed; the others are our guess by subject.
AIRCRAFT = {
    'ATLAS': ('Civil Aviation Hangar', True, '2012', 'Human-powered helicopter', None,
              'A section of AeroVelo’s Atlas, the human-powered helicopter that won the AHS Sikorsky Prize in 2013 '
              'by hovering for 64 seconds and climbing to 3.3 m, pedalled by one rider. The full rotor spanned '
              'nearly 50 m.'),
    'AH-1S ‘TOWCOBRA’': ('Military Hangar', True, '1970s', 'Helicopter', None,
                         'The Bell AH-1 Cobra was the first purpose-built attack helicopter, with a slim two-seat '
                         'body: gunner in front, pilot behind. The AH-1S carried TOW anti-tank missiles.'),
    "UH-1B 'IROQUOIS'": ('Military Hangar', True, '1962', 'Helicopter', None,
                         'The “Huey”, the helicopter of the Vietnam War, carrying troops, wounded and supplies. This '
                         'UH-1B is serial 62-02550.'),
    'XI': ('Civil Aviation Hangar', True, '1909 design', 'Pioneer aircraft', None,
           'The Blériot XI: in this kind of monoplane Louis Blériot made the first flight across the English Channel '
           'on July 25, 1909.'),
    "B-29A 'SUPERFORTRESS'": ('B-29 Hangar', False, '1945', 'Bomber', 'boeing-b-29-superfortress', None),
    "CBY-3 'LOADMASTER'": ('Civil Aviation Hangar', False, '1945', 'Transport', 'brunelli', None),
    'PUSHER': ('Civil Aviation Hangar', True, 'replica', 'Pioneer aircraft', None,
               'A home-built replica of a Curtiss pusher, with the engine and propeller behind the pilot, the way '
               'Glenn Curtiss built his early planes from 1910.'),
    "'HERRING'": ('Civil Aviation Hangar', True, 'replica', 'Glider', None,
                  'A replica of the biplane hang glider that Octave Chanute and Augustus Herring flew over the dunes '
                  'of Lake Michigan in 1896: its trussed wings inspired the Wright brothers.'),
    "C-7A 'CARIBOU'": ('Restoration Park', False, '1962', 'Transport', None,
                       'A de Havilland Canada twin-engine transport that could land on short, rough strips; used by '
                       'the US Army and Air Force in Vietnam. Serial 62-4188. Outdoors (in Restoration Park).'),
    "A-3B 'SKYWARRIOR'": ('Restoration Park', False, '1950s', 'Bomber', None,
                          'The Douglas A-3 Skywarrior, the heaviest plane ever flown routinely from aircraft carriers '
                          '(sailors called it “the Whale”). Serial 142246. Outdoors (in Restoration Park).'),
    "A-26C 'INVADER'": ('Military Hangar', False, '1944', 'Bomber', None,
                        'The Douglas A-26 “Reida Rae” (43-22499) flew 39 combat missions with the 416th Bombardment '
                        'Group in Europe in 1944–45, including the Battle of the Bulge: the centrepiece of the 416th '
                        'Bombardment Group Memorial.'),
    'DC-3': ('Civil Aviation Hangar', False, '1930s', 'Airliner', None,
             'The airliner that made air travel pay: the Douglas DC-3 first flew in 1935 and carried most of the '
             'world’s air passengers by the end of the decade. The museum’s volunteers are restoring this one (it '
             'flew for Eastern Air Lines). VIP tours go inside.'),
    "A-10A 'THUNDERBOLT II'": ('Military Hangar', False, '1970s', 'Attack aircraft', 'x-a-10', None),
    "RB-57A 'CANBERRA'": ('Military Hangar', True, '1953', 'Reconnaissance aircraft', None,
                          'The Martin B-57, an American-built version of the British English Electric Canberra jet '
                          'bomber; the RB-57A took reconnaissance photos. Serial 52-1488.'),
    'ZNPK-28 BLIMP CONTROL CAR': ('Civil Aviation Hangar', False, '1942', 'Airship', 'goodyear-znpk-28-blimp-control-car',
                                  None),
    "R-1 'SUPER SPORTSTER'": ('Civil Aviation Hangar', True, 'replica', 'Racing aircraft', None,
                              'A replica of the Gee Bee R-1, the stubby racer built by the Granville Brothers of '
                              'Springfield, Massachusetts: Jimmy Doolittle won the 1932 Thompson Trophy in it.'),
    "F6F-5K 'HELLCAT'": ('Military Hangar', True, '1944', 'Fighter', None,
                         'Grumman’s Navy fighter of World War II, credited with more enemy planes shot down than any '
                         'other American type. This one (79192) was later made into a radio-controlled target '
                         'drone (F6F-5K).'),
    "FM-2 'WILDCAT'": ('Military Hangar', True, '1944', 'Fighter', None,
                       'The Wildcat held the line for the US Navy early in World War II; the FM-2 was built by '
                       'Eastern Aircraft (General Motors) for small escort carriers. Serial 74120.'),
    "HU-16E 'ALBATROSS'": ('Restoration Park', False, '1950s', 'Flying boat', None,
                           'Grumman’s amphibian flying boat, flown by the Coast Guard for search and rescue at sea. '
                           'Outdoors, in Restoration Park, under restoration.'),
    "LNB-4 'PARASOL'": ('Civil Aviation Hangar', True, '1930s', 'Light aircraft', None,
                        'The Heath Parasol was sold as a kit or as plans in the 1930s, so anyone could build a plane '
                        'at home.'),
    "OH-6A 'CAYUSE'": ('Military Hangar', True, '1960s', 'Helicopter', None,
                       'The Hughes “Loach” (light observation helicopter), small and fast, flew scouting missions in '
                       'Vietnam.'),
    'K-225': ('Military Hangar', False, '1949', 'Helicopter', 'kaman', None),
    'HOK-1': ('Military Hangar', False, '1950s', 'Helicopter', None,
              'A Kaman helicopter for the Marine Corps, with two intermeshing rotors (no tail rotor), designed by '
              'Charles Kaman in Bloomfield, Connecticut. Part of the Kaman exhibit.'),
    "SH-F 'SEASPRITE'": ('Military Hangar', True, '1980s', 'Helicopter', None,
                         'The Kaman SH-2F Seasprite flew from Navy frigates and destroyers to hunt submarines. '
                         'Serial 161905.'),
    "LC-DW 30 'SOLUTION'": ('Civil Aviation Hangar', True, '1930', 'Racing aircraft', None,
                            'Laird’s “Solution” won the first Thompson Trophy race in 1930, flown by Speed Holman.'),
    "10-A 'ELECTRA'": ('Civil Aviation Hangar', False, '1935', 'Airliner', 'lockheed-10-a-electra', None),
    "TV-2 'Shooting Star'": ('Military Hangar', True, '1950s', 'Jet trainer', None,
                             'The Navy’s version of the Lockheed T-33, the two-seat jet trainer in which a generation '
                             'of pilots learned to fly jets. Serial 138048, restored by the museum’s volunteers.'),
    'R-3': ('Civil Aviation Hangar', False, '1933', 'Racing aircraft', None,
            'The Keith Rider R-3, rebuilt as the Marcoux-Bromberg Special: a racer of the Golden Age of air racing '
            'in the 1930s.'),
    "F-15 'Eagle'": ('Military Hangar', True, '1985', 'Fighter', None,
                     'An F-15C Eagle donated by the 104th Fighter Wing of the Massachusetts Air National Guard at '
                     'Barnes Airport in 2024. Serial 85-101.'),
    "F-100A 'SUPER SABRE'": ('Military Hangar', False, '1954', 'Fighter', None,
                             'The first US Air Force fighter to fly faster than sound in level flight. You can sit in '
                             'its cockpit. Serial 52-5761.'),
    'P-51D RACER': ('Civil Aviation Hangar', True, '1945', 'Racing aircraft', None,
                    'A World War II P-51D Mustang (44-72400) later set up as an air racer.'),
    'FLIGHTSTAR MC': ('Civil Aviation Hangar', True, '1980s', 'Ultralight', None,
                      'An ultralight built in Connecticut by Pioneer, for flying just for fun.'),
    'LNE-1 GLIDER': ('Civil Aviation Hangar', True, '1940s', 'Glider', None,
                     'A training glider built in Deep River, Connecticut, by Pratt, Read & Company for the Navy in '
                     'World War II. See the Silent Wings exhibit on glider pilots.'),
    "P-47D 'THUNDERBOLT'": ('Military Hangar', True, '1945', 'Fighter', None,
                            'Republic’s heavy fighter-bomber of World War II, powered by a Pratt & Whitney Double Wasp '
                            'engine made in Connecticut. This one (45-49458, “Norma”) honours the 57th Fighter '
                            'Group.'),
    "HH-52A (S-62A) 'SEAGUARD'": ('Civil Aviation Hangar', False, '1960s', 'Helicopter', None,
                                  'A Sikorsky Coast Guard rescue helicopter with a boat hull, so it could land on '
                                  'water. Serial 1428. Docents sometimes open it.'),
    "R-4B 'HOVERFLY'": ('Civil Aviation Hangar', True, '1944', 'Helicopter', None,
                        'The first helicopter built in numbers anywhere, by Sikorsky in Stratford, Connecticut, from '
                        'Igor Sikorsky’s VS-300. Serial 43-46503.'),
    "S-39B 'JUNGLE GYM'": ('Civil Aviation Hangar', True, '1930', 'Flying boat', None,
                           'A small Sikorsky amphibian of 1930, flown on expeditions; built in Bridgeport, '
                           'Connecticut.'),
    'S-51 EXECUTIVE TRANSPORT': ('Civil Aviation Hangar', True, '1940s', 'Helicopter', None,
                                 'The Sikorsky S-51 was the first helicopter sold to businesses and airlines; this '
                                 'one was fitted out for executives.'),
    "VS-44A 'EXCAMBIAN'": ('Civil Aviation Hangar', False, '1942', 'Flying boat', 'sikorsky-vs-44a-excambian', None),
    "CH-54B (S-64) 'TARHE' SKYCRANE": ('Military Hangar', False, '1970', 'Helicopter', None,
                                       'The Sikorsky Skycrane, a flying crane that could lift tanks, bridges and '
                                       'other helicopters; used in Vietnam. Serial 69-18465.'),
    "PT-17 (MODEL 75) 'KAYDET'": ('Civil Aviation Hangar', False, '1940s', 'Trainer', None,
                                  'The Stearman biplane on which most American pilots of World War II learned to '
                                  'fly.'),
    "XF4U-4 'CORSAIR'": ('Military Hangar', True, '1944', 'Fighter', None,
                         'A test version of the Vought Corsair, the gull-winged Navy fighter built in Stratford, '
                         'Connecticut. Serial 80759.'),
}
EXTRA_AIRCRAFT = [   # outside, seen by visitors in 2026 but not in the museum's list
    ('k-16b', 'Kaman K-16B', 'Kaman Aircraft', '1959', 'Experimental aircraft', 'Restoration Park', False,
     'K-16B_Preservation_Aug_2022-1.jpg',
     'A 1959 Navy prototype built from a Grumman Goose hull to test vertical takeoff and landing with tilting wings. It '
     'never made a free flight. Outdoors, being preserved by the museum.'),
]

# id, title, hangar, guessed?, page, picture, words (None = read from the page)
EXHIBITS = [
    ('women', 'New England Women in Aviation', 'Hallway', False, 'new-england-women-in-aviation', 'Asset-3a.jpg',
     'An exhibit (2022) honouring New England women who overcame barriers in flight, from early pilots to astronauts '
     'such as Maine’s Jessica Meir; Amelia Earhart among them. Being expanded in 2026.'),
    ('kosciuszko', 'The Kosciuszko Squadron: Defenders of Freedom, 1919–1946', 'Kosciuszko Room', False,
     'the-kosciuszko-squadron', 'Kosciuszko_Squadron_Exhibit.jpg',
     'American volunteers led by Merian C. Cooper flew for Poland in 1919–20; in 1940 the squadron, by then all Polish, '
     'fought in the Battle of Britain. Original artifacts and interactive screens, made with Central Connecticut State '
     'University (2021); signs in English and Polish.'),
    ('58th', '58th Bomb Wing Memorial', 'B-29 Hangar', False, '58th-bomb-wing-wwii-memorial', 'b29_58.jpg',
     'The first unit to take the B-29 into combat, from India and China in 1944 and then Tinian. Nose art, a route map '
     'and the veterans’ stories around “Jack’s Hack”.'),
    ('tuskegee', 'The Tuskegee Airmen: Their Untold Stories', 'B-29 Hangar', False, 'tuskegee-airmen',
     'Members_of_the_Army_Air_Force_332nd_Fighter_Group_in_a_briefing_room_Ramitelli_Italy.jpg',
     'Made with the children of Tuskegee Airmen: their parents’ stories of the war and after. The “Red Tails” flew '
     '1,578 missions and won more than 850 medals. Opened 2023.'),
    ('416th', '416th Bombardment Group Memorial', 'Military Hangar', False, '416th-bombardment-group-memorial',
     'EXHIBIT_416th_Bombardment_Group_Light_Memorial.jpg',
     'Around the A-26 Invader “Reida Rae”, which flew 39 combat missions with the 416th in Europe, from D-Day to the '
     'Battle of the Bulge.'),
    ('57th', '57th Fighter Group WWII Memorial', 'Military Hangar', True, '57th-fighter-group-wwii-memorial',
     'fighter-group.jpg', 'A memorial to the 57th Fighter Group, which flew P-40s and P-47 Thunderbolts in North '
     'Africa and Italy in World War II.'),
    ('kaman', 'Kaman: A Legacy of Innovation', 'Military Hangar', False, 'enhanced-kaman-exhibit',
     'NEAM_Exhibits-26.jpg',
     'The story of Charles Kaman and his Bloomfield, Connecticut company: a 3D hologram of how his inventions cut '
     'vibration, an interactive kiosk and an augmented-reality scavenger hunt (2018).'),
    ('apollo', 'Apollo & Beyond: A Connecticut Company’s Contributions to Spaceflight', 'Space & Observation Mezzanine',
     False, 'apollo-era-emu', 'NEAM_Exhibits-75.jpg',
     'Hamilton Standard of Windsor Locks made the life-support backpacks worn on the Moon and the spacesuit systems '
     'used on the Space Station. Two full spacesuits (EMUs) and an Apollo-era suit worn by James Irwin; also the '
     'zero-gravity toilet used on the International Space Station.'),
    ('brooks', 'Silas Brooks Balloon Basket', 'Space & Observation Mezzanine', False, 'silas-brooks-balloon-basket',
     'EXHIBIT_Silas_Brooks_Balloon_Basket.jpg',
     'Built and flown in the 1870s by Silas Brooks of Plymouth, Connecticut: the oldest surviving American-built '
     'aircraft.'),
    ('blanchard', 'Blanchard Balloon Basket Replica', 'Space & Observation Mezzanine', True, None,
     None, 'Built and flown in 1993 to mark 200 years since Jean-Pierre Blanchard made the first manned flight in '
     'America, in Philadelphia in 1793.'),
    ('pw', 'Pratt & Whitney Innovators', 'Civil Aviation Hangar', True, 'pratt-whitney-innovators',
     '20211229_154429.jpg',
     'A century of Pratt & Whitney, founded in Hartford in 1925: the Wasp radial engine and the people who built the '
     'company. New exhibit.'),
    ('sikorsky', 'Through the Eyes of Igor Sikorsky', 'Civil Aviation Hangar', True, 'igor-silkorsky-memorial-exhibit',
     'exhibit_1.jpg',
     'Igor Sikorsky, from Kyiv to Connecticut: flying boats like the VS-44A, and the VS-300 of 1939, the first practical '
     'helicopter. A short film plays near the Excambian.'),
    ('silent-wings', 'Silent Wings', 'Civil Aviation Hangar', True, 'silent-wings', 'Silent_Wings.jpg',
     'The glider pilots of World War II, and the two Connecticut firms that built gliders: Pratt Read of Deep River '
     'and Ludington-Griswold of Old Saybrook.'),
    ('spencer', 'Percival H. Spencer', 'Civil Aviation Hangar', True, None, 'percival.jpg',
     'Artifacts of Connecticut inventor and aviation pioneer Percival Spencer, who flew his own glider in 1910 and later '
     'designed amphibians, among them the Republic Seabee.'),
    ('tornado', '8 Minutes: Bradley Air Museum & the 1979 Tornado', 'Lobby', True, 'windsor-locks-tornado',
     'windsor.jpg',
     'On October 3, 1979 a tornado struck the museum, then the Bradley Air Museum on Route 75: of 30 planes outdoors '
     'only 4 escaped serious damage. How the museum rebuilt here.'),
    ('simulator', 'F/A-18 Hornet flight simulator', 'Military Hangar', True, 'simulator', 'F-18_Hornet.png',
     'Fly a fighter jet: free flight, carrier takeoffs and landings. Ages 12 and up; extra charge, book a pass at the '
     'front desk. Usually Tue, Thu, Sat and Sun 10 am–3 pm.'),
]

ENGINES = [   # featured on neam.org (pictures); slug, title, maker, picture
    ('wright-brothers-engine-engine-17', 'Wright Brothers Engine #17', 'Wright brothers', 'Wright_Brothers_Engine_17.jpg'),
    ('smith-aircraft-engine', 'Smith Aircraft Engine', 'Smith', 'Smith_Aircraft_Engine.jpg'),
    ('pratt-whitney-r-1340-wasp-model-a', 'Pratt & Whitney R-1340 Wasp Model A', 'Pratt & Whitney',
     'Prat_Whitney_Wasp_Model_A.jpg'),
    ('wright-1820-45-cyclone', 'Wright R-1820-45 Cyclone', 'Wright Aeronautical', 'Wright_Cyclone.jpg'),
    ('general-electric-j-31', 'General Electric J-31', 'General Electric', 'GE_J_31.jpg'),
    ('pratt-whitney-j58', 'Pratt & Whitney J58', 'Pratt & Whitney', 'Pratt_Whitney_J58.jpg'),
]


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


SPECIAL = {'XI': 'Blériot XI', 'PUSHER': 'Curtiss Pusher (Bunce replica)', "'HERRING'": 'Chanute-Herring Glider (replica)',
           'ATLAS': 'AeroVelo Atlas (section)', "SH-F 'SEASPRITE'": 'SH-2F “Seasprite”'}


def nice(title):
    """"CBY-3 'LOADMASTER'" -> 'CBY-3 “Loadmaster”'."""
    t = title.strip()
    if t in SPECIAL: return SPECIAL[t]
    t = re.sub(r"['‘]([^'’]+)['’]", r'“\1”', t)
    return re.sub(r'(?<![-\w])([A-Z]{3,})(?![-\w])', lambda x: x.group(1).title(), t)


def year(date):
    m = re.search(r'1[89]\d\d|20[0-2]\d', date or '')
    return int(m.group()) if m else None


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    listing = page('aircraft')
    works, rows = [], []

    def add(a, guessed, note=None):
        name, fl = names[a['gallery']]
        a.update(galleryName=name, floor=fl, imageCredit='New England Air Museum (neam.org)')
        if guessed:
            a['placeGuessed'] = True
            a['placeNote'] = note or 'The museum doesn’t say which hangar it is in: our guess by subject.'
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    seen = set()
    for m in re.finditer(r'<a class="acc_square">.*?src="([^"]+)".*?<strong>(.*?)</strong></p>\s*<span[^>]*>(.*?)'
                         r'</span>', listing, re.S):
        raw, maker = html.unescape(m.group(2)).strip(), html.unescape(m.group(3)).strip()
        if raw not in AIRCRAFT: raise SystemExit(f'new aircraft on neam.org: {raw!r} ({maker})')
        room, guessed, date, typ, slug, words = AIRCRAFT[raw]
        seen.add(raw)
        pic = re.sub(r'_530x350_crop_center', '', m.group(1).split('/files/')[1].split('?')[0])
        title = nice(raw)
        if slug:
            words = paragraphs(slug)
        add({'id': 'neam-' + slugify(raw), 'title': title, 'artist': maker, 'date': date, 'year': year(date),
             'type': typ, 'description': words, 'url': f'{SITE}/pages/{slug}' if slug else f'{SITE}/pages/aircraft',
             'image': img(pic), 'gallery': room}, guessed)
    missing = set(AIRCRAFT) - seen
    if missing: raise SystemExit(f'gone from neam.org: {sorted(missing)}')
    for key, title, maker, date, typ, room, guessed, pic, words in EXTRA_AIRCRAFT:
        add({'id': 'neam-' + key, 'title': title, 'artist': maker, 'date': date, 'year': year(date), 'type': typ,
             'description': words, 'url': f'{SITE}/pages/restoration-program', 'image': img(pic), 'gallery': room},
            guessed)
    for key, title, room, guessed, slug, pic, words in EXHIBITS:
        if slug: page(slug)
        add({'id': 'neam-x-' + key, 'title': title, 'artist': 'Exhibit', 'type': 'Exhibit', 'description': words,
             'url': f'{SITE}/pages/{slug}' if slug else f'{SITE}/pages/exhibits-displays',
             'image': img(pic) if pic else None, 'gallery': room}, guessed)
    for slug, title, maker, pic in ENGINES:
        add({'id': 'neam-e-' + slug, 'title': title, 'artist': maker, 'type': 'Engine',
             'description': paragraphs(slug, 2), 'url': f'{SITE}/pages/{slug}', 'image': img(pic),
             'gallery': 'Civil Aviation Hangar'}, True,
            'The museum shows engines around the hangars but doesn’t say where each one is: our guess.')
    for w in works:
        rows.append({k: v for k, v in {'id': w['id'], 'title': w['title'], 'artist': w['artist'], 'date': w.get('date'),
                                       'year': w.get('year'), 'url': w['url'], 'imageUrl': w.get('image'),
                                       'onView': True, 'gallery': w['gallery'], 'floor': w['floor']}.items() if v})
    # the rest of the collection: aircraft in storage, the engine collection (no pictures, not said to be on view)
    store = re.search(r'Aircraft In Storage(.*?)EXPLORE ENGINES', listing, re.S)
    for t in re.findall(r'\+\s*([^<]+)', store.group(1) if store else ''):
        t = html.unescape(t).strip()
        rows.append({'id': 'neam-s-' + slugify(t) + ('-2' if 'neam-s-' + slugify(t) in {r['id'] for r in rows} else ''),
                     'title': nice(t) + ' (in storage)', 'artist': t.split(' ')[0], 'url': f'{SITE}/pages/aircraft',
                     'onView': False})
    eng = page('our-engines')
    feat = {e[1].lower() for e in ENGINES}
    for t in dict.fromkeys(html.unescape(x).strip() for x in re.findall(r'\+\s*([^<]{4,80})<', eng)):
        if not re.search(r'[A-Za-z]{3}', t) or t.lower() in feat: continue
        t = t.replace('Motor + Company', 'Motor Company')
        rows.append({'id': 'neam-en-' + slugify(t), 'title': t, 'artist': 'Engine', 'url': f'{SITE}/pages/our-engines',
                     'onView': False})
    print(f'{len(works)} on the map, {len(rows)} on the museum page')
    return works, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, rows = build_works(floors)
    checked = time.strftime('%Y-%m-%d')
    source = 'New England Air Museum (neam.org): aircraft, exhibit and engine pages'
    (OUT / 'artworks.json').write_text(json.dumps({'source': source, 'checked': checked, 'count': len(works),
                                                   'complete': True, 'artworks': works},
                                                  ensure_ascii=False, separators=(',', ':')))
    guide = {'museum': MUSEUM, 'name': NAME, 'checked': checked, 'source': source, 'onViewKnown': True,
             'note': 'On view: the aircraft the museum lists as on display in its three hangars and outside, its '
                     'exhibits and featured engines. The museum also lists the aircraft in storage and its engine '
                     'collection (without pictures); those are marked not on view.',
             'works': rows}
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False,
                                                                         separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(rows), 'pictures': sum(bool(w.get('imageUrl')) for w in rows),
                              'onView': sum(bool(w.get('onView')) for w in rows), 'galleries': True,
                              'checked': checked, 'source': source}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
