#!/usr/bin/env python3
"""Build data/met/floors.json: The Met Fifth Avenue, every floor, from The Met's own indoor map
(maps.metmuseum.org by Living Map; fetched and merged by tools/met_map_src.py into .cache/met/indoor.json).

Rooms, galleries with their numbers, corridors, restrooms, elevators, stairs, cafés, stores, coat checks,
information and ticket desks, water fountains and entrances are where The Met's map puts them. The plan is
turned like The Met's printed map: Fifth Avenue along the bottom, Central Park at the top.
Doorways come from the map's door and threshold lines (the two rooms on either side of each)."""
import json, math, os, re, collections
from shapely.geometry import shape, Point, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '.cache', 'met', 'indoor.json')
OUT = os.path.join(ROOT, 'data', 'met', 'floors.json')

LAT0, LON0 = 40.779448, -73.963517
BEARING = math.radians(-61)       # The Met's own map is turned this way: Fifth Avenue at the bottom
U = 2.0                           # frame units per meter
M_LAT = 111_132.0
M_LON = 111_320.0 * math.cos(math.radians(LAT0))

FLOORS = {   # Living Map floor id -> (our id, label, order, what is there)
    1: ('G', 'Ground Floor', 0, 'Ruth and Harold D. Uris Center for Education, 81st Street entrance, The Costume Institute, Robert Lehman Collection ground floor, The Eatery'),
    2: ('1', 'Floor 1', 1, 'Fifth Avenue entrance and the Great Hall · Egyptian Art and the Temple of Dendur · Greek and Roman Art · Arms and Armor · Medieval Art · The American Wing · Michael C. Rockefeller Wing · Modern and Contemporary Art · European Sculpture and Decorative Arts · Robert Lehman Wing'),
    3: ('1M', 'Floor 1 Mezzanine', 2, 'Etruscan and Cycladic Art · American Wing mezzanine (Luce Center, ceramics) · Modern and Contemporary Art mezzanine'),
    4: ('2', 'Floor 2', 3, 'European Paintings 1250–1800 · 19th and Early 20th Century European Paintings and Sculpture · Asian Art · Islamic Art · Ancient West Asia and Cyprus · Musical Instruments · Drawings, Prints and Photographs · The American Wing'),
    5: ('3', 'Floor 3', 4, 'Chinese decorative arts and the Chinese Treasury · Arts of Tibet and Nepal · early American period rooms'),
    6: ('4', 'Floor 4', 5, 'Patrons Lounge and coat check'),
    7: ('5', 'Floor 5', 6, 'The Iris and B. Gerald Cantor Roof Garden (seasonal) and its bar'),
}
DEFAULT = '1'

AMENITY = {   # (class, type) -> our icon
    ('circulation', 'lift'): 'elevator', ('restroom', 'toilet'): 'restroom',
    ('circulation', 'escalator'): 'stairs', ('tourism', 'information'): 'info', ('facility', 'tickets'): 'info',
    ('facility', 'reception'): 'info', ('facility', 'cloakroom'): 'coat', ('food_and_drink', 'restaurant'): 'dining',
    ('food_and_drink', 'cafe'): 'dining', ('food_and_drink', 'bar'): 'dining', ('retail', 'shop'): 'shop',
    ('facility', 'drinking_water'): 'water', ('restroom', 'changing_room'): 'nursing',
    ('emergency', 'defibrillator'): 'emergency', ('circulation', 'entrance'): 'entrance',
}
SPACE = {('food_and_drink', 'restaurant'), ('food_and_drink', 'cafe'), ('food_and_drink', 'bar'),
         ('retail', 'shop'), ('education', 'library'), ('education', 'classroom'), ('event_space', 'auditorium'),
         ('facility', 'cloakroom'), ('restroom', 'toilet')}
CORRIDOR = {('building', 'corridor'), ('building', 'vista'), ('circulation', 'stairs'), ('circulation', 'steps'),
            ('circulation', 'lift'), ('circulation', 'escalator'), ('facility', 'tickets')}
CLOSED = {('building', 'back_of_house'), ('building', 'structure')}


def xy(lon, lat):
    e = (lon - LON0) * M_LON
    n = (lat - LAT0) * M_LAT
    up = n * math.cos(BEARING) + e * math.sin(BEARING)
    right = e * math.cos(BEARING) - n * math.sin(BEARING)
    return right * U, -up * U


def proj(g):
    def ring(cs):
        return [xy(*c) for c in cs]
    t = g['type']
    if t == 'Polygon':
        return Polygon(ring(g['coordinates'][0]), [ring(h) for h in g['coordinates'][1:]])
    if t == 'MultiPolygon':
        return MultiPolygon([Polygon(ring(p[0]), [ring(h) for h in p[1:]]) for p in g['coordinates']])
    if t == 'LineString':
        return LineString(ring(g['coordinates']))
    if t == 'MultiLineString':
        return unary_union([LineString(ring(c)) for c in g['coordinates']])
    if t == 'Point':
        return Point(xy(*g['coordinates']))
    return shape(g)


def polys(g, tol=0.25):
    """Our rooms are simple polygons (with holes): split multipolygons, drop slivers, simplify."""
    g = g.buffer(0).simplify(tol, preserve_topology=True)
    parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
    out = []
    for p in sorted([p for p in parts if p.geom_type == 'Polygon' and p.area > 2 * U * U], key=lambda p: -p.area):
        out.append(p)
    return out


def r1(v):
    return round(v, 1)


def coords(ring):
    cs = [[r1(x), r1(y)] for x, y in ring.coords[:-1]]
    return cs


def gallery_ids(p):
    """Gallery numbers of a room: '137', or 'Galleries 964-965' → ['964', '965']."""
    name = p.get('name') or ''
    sub = p.get('popup_subheader') or ''
    if re.fullmatch(r'\d{2,3}[a-z]?', name):
        return [name]
    m = re.search(r'Galler(?:y|ies) (\d{3})(?:\s*[-–&]\s*(\d{3}))?', sub) or re.search(r'Galler(?:y|ies) (\d{3})(?:\s*[-–&]\s*(\d{3}))?', name)
    if not m:
        return []
    a = int(m.group(1)); b = int(m.group(2) or a)
    return [f'{n:03d}' for n in range(a, b + 1)] if b - a < 10 else [m.group(1), m.group(2)]


def tidy(s):
    return re.sub(r'\s+', ' ', (s or '').replace('’', '’')).strip()


def main():
    feats = json.load(open(SRC))
    by_floor = collections.defaultdict(list)
    points = {}
    for f in feats:
        p = f['props']
        if p.get('location_name') != 'The Met Fifth Avenue' or p.get('floor_id') not in FLOORS:
            continue
        g = proj(f['geometry'])
        by_floor[p['floor_id']].append((p, g))
        if p.get('geom_type') == 'DISPLAY_POINT':
            points[(p['floor_id'], p['geom_id'])] = g

    floors = []
    for fid, (our, label, order, area) in FLOORS.items():
        items = by_floor[fid]
        rooms, closed, amen, labels, notes = [], [], [], [], []
        used = collections.Counter()
        sections = [(tidy(p['name']), g) for p, g in items
                    if (p.get('class'), p.get('type')) == ('building', 'section') and g.geom_type.endswith('Polygon')]

        def section_at(pt):
            best = None
            for n, g in sections:
                if g.contains(pt) and (best is None or g.area < best[1].area):
                    best = (n, g)
            return best[0] if best else None

        # the floor itself and back-of-house areas: grey, under everything
        for p, g in items:
            ct = (p.get('class'), p.get('type'))
            if ct == ('building', 'floor') or ct in CLOSED:
                for q in polys(g, 0.4):
                    c = {'poly': coords(q.exterior)}
                    if ct == ('building', 'floor'):
                        c['z'] = -1
                        if q.interiors:
                            c['holes'] = [coords(h) for h in q.interiors]
                    closed.append(c)

        def add_room(p, g, kind, rid, name, extra=None):
            ps = polys(g)
            for i, q in enumerate(ps):
                k = rid if i == 0 else f'{rid} ({i + 1})'
                used[k] += 1
                if used[k] > 1:
                    k = f'{k} #{used[k]}'
                r = {'id': k, 'kind': kind, 'name': name, 'poly': coords(q.exterior)}
                if q.interiors:
                    r['holes'] = [coords(h) for h in q.interiors if Polygon(h).area > 4]
                    if not r['holes']:
                        del r['holes']
                dp = points.get((fid, p.get('geom_id')))
                if i == 0 and dp is not None and q.contains(dp):
                    r['labelAt'] = [r1(dp.x), r1(dp.y)]
                elif not q.contains(q.centroid):
                    rp = q.representative_point()
                    r['labelAt'] = [r1(rp.x), r1(rp.y)]
                if extra and i == 0:
                    r.update(extra)
                rooms.append((r, q))

        for p, g in items:
            if not g.geom_type.endswith('Polygon'):
                continue
            ct = (p.get('class'), p.get('type'))
            closed_now = p.get('closed') is True
            if ct in (('tourism', 'gallery'), ('event_space', 'exhibition')):
                ids = gallery_ids(p)
                if not ids:
                    continue
                title = tidy(p.get('popup_header'))
                gen = not title or re.fullmatch(r'Gallery \d+\w?', title)
                name = f'Gallery {ids[0]}' if gen else f'Gallery {"–".join([ids[0], ids[-1]]) if len(ids) > 1 else ids[0]}: {title}'
                if ct == ('event_space', 'exhibition'):
                    name += ' (special exhibitions)'
                if closed_now:
                    name += ' (closed for now)'
                extra = {'label': ids[0]}
                if len(ids) > 1:
                    extra['aliases'] = ids[1:]
                add_room(p, g, 'gallery', ids[0], name, extra)
            elif ct in SPACE:
                n = tidy(p.get('popup_header') or p.get('name')) or ct[1].title()
                if ct == ('restroom', 'toilet'):
                    n = tidy(p.get('name')) or 'Restroom'
                if closed_now:
                    n += ' (closed for now)'
                add_room(p, g, 'space', n, n)
            elif ct in CORRIDOR:
                n = tidy(p.get('name'))
                if ct == ('circulation', 'lift'):
                    n = n or 'Elevator'
                elif ct in (('circulation', 'stairs'), ('circulation', 'steps')):
                    n = 'Stairs'
                elif ct == ('circulation', 'escalator'):
                    n = 'Escalator'
                elif ct == ('facility', 'tickets'):
                    n = 'Ticket desk'
                elif ct == ('building', 'vista'):
                    n = 'Balcony over the court below'
                if not n:
                    n = section_at(g.representative_point()) or 'Corridor'
                    if n == 'The Great Hall':
                        n = 'The Great Hall'
                    elif n != 'Corridor':
                        n = f'Corridor, {n}'
                add_room(p, g, 'corridor', n, n)

        # icons
        for p, g in items:
            ct = (p.get('class'), p.get('type'))
            t = AMENITY.get(ct)
            if ct == ('circulation', 'arrow') and 'main_entrance' in (p.get('icon_id') or ''):
                t = 'entrance'
            if ct in (('circulation', 'stairs'),) and g.geom_type.endswith('Polygon'):
                t = 'stairs'
            if not t:
                continue
            if fid == 1 and '82nd Street' in (p.get('name') or ''):
                continue           # the Fifth Avenue doors are on Floor 1; the ground-floor layer repeats them
            if g.geom_type.endswith('Polygon'):
                dp = points.get((fid, p.get('geom_id')))
                if dp is not None:
                    continue           # its display point carries the icon
                pt = g.representative_point()
            elif g.geom_type == 'Point':
                pt = g
            else:
                continue
            if t == 'restroom' and 'Accessible' in (p.get('name') or ''):
                t = 'restroom-all'
            a = {'type': t, 'at': [r1(pt.x), r1(pt.y)]}
            nm = tidy(p.get('name'))
            if nm and t in ('entrance', 'dining', 'shop', 'info', 'coat'):
                a['name'] = nm + (' (closed for now)' if p.get('closed') is True else '')
            amen.append(a)
        # one icon per spot
        seen, keep = set(), []
        for a in amen:
            k = (a['type'], round(a['at'][0] / 6), round(a['at'][1] / 6))
            if k in seen:
                continue
            seen.add(k); keep.append(a)
        amen = keep

        # wing names
        for n, g in sections:
            dp = None
            for p, gg in items:
                if (p.get('class'), p.get('type')) == ('building', 'section') and tidy(p.get('name')) == n and gg.geom_type == 'Point':
                    dp = gg
            pt = dp or g.representative_point()
            labels.append({'text': n, 'kind': 'area', 'at': [r1(pt.x), r1(pt.y)]})
        # landmark works on The Met's map (Temple of Dendur...) are found through the works list instead

        # doorways: each door/threshold line joins the rooms on its two sides
        walk = [(r, q) for r, q in rooms]
        tree = STRtree([q for r, q in walk])
        def room_at(pt):
            best = None
            for i in tree.query(pt):
                r, q = walk[i]
                if q.contains(pt) and (best is None or q.area < best[1].area):
                    best = (r, q)
            return best[0] if best else None

        doors, pairs = [], set()
        for p, g in items:
            if (p.get('class'), p.get('type')) not in (('building', 'door'), ('building', 'threshold')):
                continue
            segs = list(g.geoms) if hasattr(g, 'geoms') else [g]
            for s in segs:
                if s.length < 0.6 * U:
                    continue
                (x0, y0), (x1, y1) = s.coords[0], s.coords[-1]
                L = math.hypot(x1 - x0, y1 - y0) or 1
                nx, ny = -(y1 - y0) / L, (x1 - x0) / L
                m = s.interpolate(0.5, normalized=True)
                a = room_at(Point(m.x + nx * 1.2 * U, m.y + ny * 1.2 * U))
                b = room_at(Point(m.x - nx * 1.2 * U, m.y - ny * 1.2 * U))
                if not a or not b or a['id'] == b['id']:
                    continue
                k = (min(a['id'], b['id']), max(a['id'], b['id']), round(m.x / 8), round(m.y / 8))
                if k in pairs:
                    continue
                pairs.add(k)
                axis = 'h' if abs(x1 - x0) >= abs(y1 - y0) else 'v'
                doors.append({'a': a['id'], 'b': b['id'], 'at': [r1(m.x), r1(m.y)], 'width': r1(min(s.length, 6 * U)), 'axis': axis})

        # rooms that touch along an open side with no door line (wide openings): link them too, unseen
        linked = {(d['a'], d['b']) for d in doors} | {(d['b'], d['a']) for d in doors}
        walls = unary_union([g for p, g in items if (p.get('class'), p.get('type')) in (('building', 'wall'), ('building', 'partition'))] or [LineString()])
        wall_zone = walls.buffer(0.25 * U)
        grown = [q.buffer(0.3 * U) for r, q in walk]
        gtree = STRtree(grown)
        for i, (ra, qa) in enumerate(walk):
            for j in gtree.query(grown[i]):
                if j <= i:
                    continue
                rb, qb = walk[j]
                if (ra['id'], rb['id']) in linked or not grown[i].intersects(grown[j]):
                    continue
                shared = grown[i].intersection(grown[j])
                if shared.area < (2.5 * U) * (0.6 * U):
                    continue
                open_part = shared.difference(wall_zone)
                if open_part.area < (2.0 * U) * (0.6 * U):
                    continue
                c = open_part.representative_point()
                doors.append({'a': ra['id'], 'b': rb['id'], 'at': [r1(c.x), r1(c.y)], 'width': 8, 'axis': 'h', 'implicit': True})
                linked |= {(ra['id'], rb['id']), (rb['id'], ra['id'])}

        out_rooms = [r for r, q in rooms]
        floors.append({**({'partial': True} if our in ('1M', '3', '4') else {}), 'id': our, 'label': label, 'order': order, 'transform': [1, 0, 0], 'walkScale': round(1 / U / 0.35, 3),
                       'area': area, 'rooms': out_rooms, 'closed': closed, 'amenities': amen, 'labels': labels,
                       'notes': notes, 'doors': doors})
        print(our, len(out_rooms), 'rooms', sum(r['kind'] == 'gallery' for r in out_rooms), 'galleries', len(doors), 'doors', len(amen), 'icons')

    floors.sort(key=lambda f: f['order'])
    # Fifth Avenue and the park, on the main floor
    main = next(f for f in floors if f['id'] == '1')
    xs = [p[0] for r in main['rooms'] for p in r['poly']]; ys = [p[1] for r in main['rooms'] for p in r['poly']]
    main['labels'] += [
        {'text': 'FIFTH AVENUE ↓ (main entrance at 82nd Street)', 'kind': 'area', 'at': [r1((min(xs) + max(xs)) / 2), r1(max(ys) + 30)]},
        {'text': 'CENTRAL PARK', 'kind': 'area', 'at': [r1((min(xs) + max(xs)) / 2), r1(min(ys) - 30)]},
    ]
    data = {
        'about': 'Built by tools/build_met_map.py from The Met’s own indoor map (maps.metmuseum.org, made by Living Map): '
                 'every floor of The Met Fifth Avenue with its numbered galleries, corridors, restrooms, elevators, stairs, '
                 'cafés, stores, coat checks, information and ticket desks, water fountains and entrances where The Met puts them. '
                 'Turned like The Met’s printed map, with Fifth Avenue at the bottom. Openings between rooms come from the '
                 'map’s door lines; a few are inferred where two rooms meet with no wall.',
        'source': 'The Metropolitan Museum of Art, interactive map (maps.metmuseum.org, Living Map), November 2026',
        'units': f'{U:g} units per meter; Fifth Avenue is at the bottom',
        'approximate': False,
        'defaultFloor': DEFAULT,
        'galleryWord': 'Gallery',
        'floors': floors,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
