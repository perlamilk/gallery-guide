#!/usr/bin/env python3
"""Build the Fuller Craft Museum (Brockton, MA) map guide (run tools/harvest_fuller.py first, then this).

    data/fuller/floors.json       the First and Second Floors, seen from above (flat 2D)
    data/fuller/artworks.json     what is on view, placed in its gallery
    data/fuller/images/           pictures, made smaller for phones
    data/guides/Q5508243.json     the same list plus the rest of the digital archive, for the museum page

Where the information comes from
--------------------------------
Map: the museum's own "Museum Map + Rules" brochure (fullercraft.org/wp-content/uploads/2023/06/
MuseumMapBrochure_Updated_Final.pdf, linked from Plan Your Visit), traced by hand from the page rendered at 200 dpi.
Coordinates here are pixels of that picture, in the brochure's own orientation (not north up: the building sits on
a slope by Upper Porter Pond, turned about 45 degrees). The brochure draws the two floors apart; the Second Floor is
moved down 448 px so its stairs sit over the First Floor's. The main entrance, front desk and Museum Shop are on the
Second (upper) Floor; the accessible Education Entrance, the restrooms, the Lounge and most galleries are on the First.
The brochure's orange blocks have no name and are drawn as closed. Facts from the Plan Your Visit page: no café
(snacks at the shop; bring lunch to the Lounge or the patio), bags are checked at the front desk, lift/elevator,
restrooms (with all-gender) on the first floor, free parking, accessible parking at the lower lot by the Education
Entrance.

Works: the museum's Digital Archive (collections.fullercraft.org, Proficio) through tools/harvest_fuller.py. Its
"On Display" field names the gallery for the works in The Vessel (Lampos Gallery), Fiber Forward ("Education
Gallery"), the Great Room and the Interior Courtyard. The other current shows come from fullercraft.org's WordPress
API (robots.txt allows all); except Agency (the Atrium Gallery, said on its page) their galleries are not published,
so those are guesses and the map says so. Outdoor sculptures: the museum's Outdoor Sculpture Guide brochure (2023):
Patio, Courtyard, Front Inner and Outer Circles, Education Entrance.
"""
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'fuller'
CACHE = ROOT / '.cache' / 'fuller'
MUSEUM = 'Q5508243'
NAME = 'Fuller Craft Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://fullercraft.org/'
UP = SITE + 'wp-content/uploads/'
ARCHIVE = 'http://collections.fullercraft.org/'
ARCHIVE_PAGE = SITE + 'proficio-archive/'
TODAY = date.today()
U = 0.5
F2 = (540, 28)        # Second Floor brochure crop -> First Floor frame


def P(x, y):
    return [round(x * U, 1), round(y * U, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def up(pts, d=F2):
    return [(x + d[0], y + d[1]) for x, y in pts]


# ---- First Floor (brochure crop at 200 dpi, origin 180,500) ----------------------------------------------------------
FIRST = [
    ('Great Room', 'gallery', 'Great Room', rect(408, 65, 688, 258), 'Great Room'),
    ('Atrium Gallery', 'gallery', 'Atrium Gallery', rect(408, 258, 688, 320), 'Atrium'),
    ('Walkway', 'corridor', 'Glass walkway across the courtyard', rect(688, 272, 945, 305), None),
    ('Courtyard', 'space', 'Interior Courtyard (outdoors, with seating)', rect(722, 310, 895, 452), None),
    ('Stairs West', 'corridor', 'Stairs to the Second Floor', rect(618, 320, 688, 395), None),
    ('West Hall', 'corridor', 'Hall to the restrooms and the education wing',
     [(425, 320), (455, 320), (455, 550), (385, 550), (385, 395), (425, 395)], None),
    ('All-Gender Restroom', 'space', 'All-gender accessible restroom', rect(373, 322, 425, 395), None),
    ('Restrooms', 'space', 'Restrooms', rect(285, 395, 385, 480), None),
    ('Community Gallery', 'gallery', 'Community Gallery (education wing; the museum calls it the Education Gallery)',
     rect(35, 550, 455, 602), 'Community Gallery'),
    ('Ceramic Studio', 'space', 'Ceramic Studio (classes)', rect(35, 602, 160, 740), None),
    ('Community Studio', 'space', 'Community Studio (classes and family activities)', rect(160, 602, 285, 740), None),
    ('Education Entrance', 'space', 'Accessible & Education Entrance', rect(308, 602, 430, 745), None),
    ('Education Walk', 'space', 'Outside the Education Entrance: lower parking lot (accessible parking)',
     rect(300, 745, 430, 900), None),
    ('Middle Hall', 'corridor', 'Hall', rect(455, 550, 690, 602), None),
    ('Lampos Gallery', 'gallery', 'Lampos Gallery', rect(690, 530, 945, 602), 'Lampos'),
    ('Tarlow Gallery', 'gallery', 'Tarlow Gallery', rect(785, 602, 940, 740), 'Tarlow'),
    ('East Hall', 'corridor', 'Hall with benches', rect(945, 550, 1190, 602), None),
    ('Barstow Gallery', 'gallery', 'Barstow Gallery', rect(1065, 602, 1190, 740), 'Barstow'),
    ('Stone Gallery', 'gallery', 'Stone Gallery', rect(1068, 320, 1190, 550), 'Stone'),
    ('Keith Gallery', 'gallery', 'Keith Gallery', rect(1068, 255, 1190, 320), 'Keith'),
    ('Lounge', 'space', 'Museum Lounge: seating; bring your own lunch (no café)', rect(945, 115, 1068, 320), None),
    ('Patio', 'space', 'Patio by the pond (outdoors; picnic welcome)', rect(1195, 110, 1310, 330), None),
]
FIRST_CLOSED = [rect(285, 65, 373, 395), rect(455, 320, 618, 550), rect(618, 395, 690, 550), rect(945, 320, 1068, 550),
                rect(722, 112, 895, 272), rect(455, 602, 785, 900), rect(940, 602, 1065, 740), rect(690, 740, 1190, 900)]
FIRST_DOORS = [('Great Room', 'Atrium Gallery', (550, 258)), ('Atrium Gallery', 'Stairs West', (650, 320)),
               ('Atrium Gallery', 'Walkway', (688, 288)), ('Atrium Gallery', 'West Hall', (440, 320)),
               ('West Hall', 'All-Gender Restroom', (425, 360)), ('West Hall', 'Restrooms', (385, 437)),
               ('West Hall', 'Community Gallery', (420, 550)), ('Community Gallery', 'Middle Hall', (455, 576)),
               ('Community Gallery', 'Ceramic Studio', (98, 602)), ('Community Gallery', 'Community Studio', (222, 602)),
               ('Community Gallery', 'Education Entrance', (340, 602)),
               ('Education Entrance', 'Education Walk', (370, 745)), ('Middle Hall', 'Lampos Gallery', (690, 576)),
               ('Lampos Gallery', 'East Hall', (945, 576)), ('Lampos Gallery', 'Tarlow Gallery', (862, 602)),
               ('East Hall', 'Barstow Gallery', (1128, 602)), ('East Hall', 'Stone Gallery', (1128, 550)),
               ('Stone Gallery', 'Keith Gallery', (1128, 320)), ('Keith Gallery', 'Lounge', (1068, 288)),
               ('Lounge', 'Walkway', (945, 288)), ('Walkway', 'Courtyard', (808, 305)),
               ('Keith Gallery', 'Patio', (1192, 288))]
FIRST_AMEN = [('restroom', 335, 437), ('restroom-all', 399, 358), ('stairs', 640, 340), ('stairs', 1128, 350),
              ('elevator', 1080, 338), ('entrance', 370, 700), ('dining', 1005, 230)]
FIRST_LABELS = [('Upper Porter Pond side', 1250, 80), ('Lower parking lot', 365, 930)]
FIRST_NOTES = [('Accessible entrance: rear of the building, by the lower lot', 365, 960)]

# ---- Second Floor (brochure crop at 200 dpi, origin 720,80, moved by F2) ---------------------------------------------
SECOND = [
    ('D. Tarlow Gallery', 'gallery', 'D. Tarlow Gallery (the long upper hall)', up(rect(45, 240, 470, 295)), 'D. Tarlow'),
    ('Stairs Upper', 'corridor', 'Stairs to the First Floor', up(rect(75, 295, 155, 380)), None),
    ('Entrance Hall', 'space', 'Main entrance and front desk (admission by donation; check large bags here)',
     up([(470, 240), (655, 240), (655, 380), (525, 380), (525, 295), (470, 295)]), None),
    ('Museum Shop', 'space', 'Museum Shop (also snacks and drinks)', up(rect(470, 190, 655, 240)), None),
    ('Front Inner Circle', 'space', 'Front Inner Circle: sculpture by the entrance drive (outdoors)',
     up(rect(665, 180, 780, 350)), None),
    ('Front Outer Circle', 'space', 'Front Outer Circle: sculpture around the front lawn (outdoors)',
     up(rect(780, 140, 900, 390)), None),
]
SECOND_CLOSED = [up(rect(45, 30, 160, 240)), up(rect(400, 85, 655, 190))]
SECOND_DOORS = [('D. Tarlow Gallery', 'Stairs Upper', up([(115, 295)])[0]),
                ('D. Tarlow Gallery', 'Entrance Hall', up([(470, 268)])[0]),
                ('Entrance Hall', 'Museum Shop', up([(560, 240)])[0]),
                ('Entrance Hall', 'Front Inner Circle', up([(658, 262)])[0]),
                ('Front Inner Circle', 'Front Outer Circle', up([(780, 262)])[0])]
SECOND_AMEN = [('entrance', *up([(640, 262)])[0]), ('info', *up([(590, 262)])[0]), ('coat', *up([(615, 280)])[0]),
               ('shop', *up([(560, 215)])[0]), ('stairs', 640, 340), ('stairs', 1128, 350), ('elevator', 1080, 338)]
SECOND_LABELS = [('Front parking lot →', *up([(840, 420)])[0])]
SECOND_NOTES = [('Main entrance from the front lot (455 Oak Street)', *up([(760, 110)])[0])]


def inside(p, pg):
    x, y = p
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area_text, spec, closed, doors, amen, labels, notes):
    rooms = []
    for rid, kind, name, pg, short in spec:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in pg]}
        if short: r['label'] = short
        rooms.append(r)
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), fid
    for a, b, at in doors:
        assert a in ids and b in ids, (fid, a, b)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area_text,
         'rooms': rooms, 'closed': [{'poly': [P(*q) for q in c]} for c in closed],
         'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': P(x, y)} for t, x, y in labels],
         'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in notes],
         'doors': [{'a': a, 'b': b, 'at': P(*at), 'width': 14, 'axis': 'o'} for a, b, at in doors]}
    for a in f['amenities']:
        assert any(inside(a['at'], r['poly']) for r in rooms), (fid, a)
    return f


def build_floors():
    floors = [
        floor('1', 'First Floor', 0, 'Great Room, Atrium, Lampos, Tarlow, Barstow, Stone and Keith Galleries, the '
              'Community Gallery, restrooms, Lounge, Interior Courtyard, patio, Accessible & Education Entrance',
              FIRST, FIRST_CLOSED, FIRST_DOORS, FIRST_AMEN, FIRST_LABELS, FIRST_NOTES),
        floor('2', 'Second Floor (entrance level)', 1, 'Main entrance and front desk, Museum Shop, D. Tarlow Gallery, '
              'outdoor sculpture on the front lawn', SECOND, SECOND_CLOSED, SECOND_DOORS, SECOND_AMEN, SECOND_LABELS,
              SECOND_NOTES),
    ]
    return {'about': 'Built by tools/build_fuller.py from the Fuller Craft Museum’s own Museum Map brochure (2023), '
                     'drawn in the brochure’s orientation (not north up). You come in on the upper (Second) floor from '
                     'the front lot; the galleries, restrooms and Lounge are downstairs. Outdoor sculpture areas come '
                     'from the museum’s Outdoor Sculpture Guide; their places around the building are approximate.',
            'source': 'Fuller Craft Museum: Museum Map + Rules brochure, Plan Your Visit page, Outdoor Sculpture Guide',
            'units': 'brochure pixels at 200 dpi x 0.5 (about 0.13 m)', 'approximate': False, 'defaultFloor': '2',
            'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def fetch(url, dest, pause=1.5):
    if dest.exists() and dest.stat().st_size > 2000: return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 20, 60):
        time.sleep(wait or pause)
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.exists() and dest.stat().st_size > 2000: return True
        dest.unlink(missing_ok=True)
    return False


def picture(key, url, size=1000):
    if not url: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/fuller/images/{key}.jpg'
    if dest.exists(): return rel
    raw = CACHE / 'img' / (key + '.bin')
    if not fetch(url, raw):
        print(f'  no picture: {url}')
        return None
    try:
        im = Image.open(io.BytesIO(raw.read_bytes()))
        im.load()
    except Exception as e:
        print(f'  bad picture {url}: {e}')
        return None
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert('RGB')
    im.thumbnail((size, size))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=78, optimize=True, progressive=True)
    return rel


def archive_image(r):
    p = (r.get('FullImage') or '').replace('\\', '/').lstrip('/')
    if not p: return None
    if p.endswith('.jp'): p += 'g'                                   # the archive cuts some names short
    return ARCHIVE + 'FullImages/' + urllib.parse.quote(p)


# ---- shows ---------------------------------------------------------------------------------------------------------
# (key, gallery, title, maker, (from, to), WordPress slug, picture under wp-content/uploads, gallery known?)
SHOWS = [
    ('agency', 'Atrium Gallery', 'Molly Hatch: Agency', 'Molly Hatch', ('2026-10-17', '2028-10-01'),
     'molly-hatch-agency', '2026/08/MH-web-header.png', True),
    ('vessel', 'Lampos Gallery', 'The Vessel', 'From the permanent collection', ('2026-05-23', '2027-05-02'),
     'the-vessel', '2026/04/Lugo-Melting-Pot-II-front-WH-scaled.jpg', True),
    ('fiber-forward', 'Community Gallery', 'Fiber Forward: The Judith Stern Weisman Collection', 'Gift of Judith Stern '
     'Weisman', ('2025-10-25', '2026-12-06'), 'fiber-forward-the-judith-stern-weisman-collection',
     '2025/12/FiberForward.png', True),
    ('maeda', 'Keith Gallery', 'Stories on the Planet: Asagi Maeda', 'Asagi Maeda', ('2026-06-27', '2026-11-08'),
     'stories-on-the-planet-asagi-maeda', '2025/12/asagi.png', False),
    ('forest', 'Stone Gallery', 'Forest of Here: Jeila Gueramian', 'Jeila Gueramian', ('2026-04-18', '2027-03-28'),
     'forest-of-here-jeila-gueramian', '2025/11/1.png', False),
    ('more-clay', 'Barstow Gallery', 'MORE CLAY! The Power of Repetition', 'Curated by Rebecca Cross',
     ('2026-03-28', '2027-02-07'), 'more-clay-the-power-of-repetition', '2025/11/2.png', False),
    ('geranium', 'Atrium Gallery', 'Geranium and Lotus Flowers', 'Daina Shobrys', ('2026-05-09', '2026-10-29'),
     'geranium-and-lotus-flowers', '2026/05/GeraniumCloseup.jpg', False),
]
GUESS = ('The museum doesn’t publish which gallery this show is in, so its place on the map is a guess. Ask at the '
         'front desk.')


def fmt(d):
    d = date.fromisoformat(d)
    return f'{d:%b} {d.day}, {d.year}'


def show_text(slug):
    exh = {e['slug']: e for e in json.load(open(CACHE / 'exhall.json'))}
    html = exh[slug]['content']['rendered']
    paras = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', p)).strip() for p in re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)]
    import html as H
    paras = [H.unescape(p) for p in paras if len(p) > 60]
    return ' '.join(paras[:2])


# ---- outdoor sculpture (Outdoor Sculpture Guide, 2023) --------------------------------------------------------------
# collection objects (CAT_NBR -> area) and brochure-only works (area, title, artist, date, text)
OUTDOOR_CAT = {'1968.1': 'Patio', '2009.18': 'Front Outer Circle', '2020.5': 'Front Outer Circle',
               '2020.4.1': 'Front Outer Circle', '2020.4.2': 'Front Outer Circle', '2013.11': 'Front Inner Circle',
               '2016.14': 'Front Inner Circle', '2025.10.22': 'Courtyard'}
OUTDOOR_TEXT = {
    '1968.1': 'The first acquisition of the Brockton Art Center – Fuller Memorial (now Fuller Craft Museum). The bronze '
              'form echoes Rodin and the Art Nouveau.',
    '2009.18': 'Many straight lines of red cedar make one flowing, double-curved form, named after Daedalus, the father '
               'of Icarus.',
    '2020.5': 'Murray Dewart’s sculpture has muscular forms and captivating materials: grace, serenity, strength.',
    '2020.4.1': 'Inspired by the artist watching two sticks of butter melt into each other in the microwave.',
    '2020.4.2': 'Paul Meneses rolls, bends and cuts steel to suggest energy and the potential for movement.',
    '2013.11': 'From Joseph Wheelwright’s series of faces carved into large pieces of granite.',
    '2016.14': 'Shown at Framingham’s Danforth Museum before it came to the Fuller in 2017.',
}
OUTDOOR_EXTRA = [
    ('Patio', 'Blossom, Butterfly Maiden and Scamp', 'Tommy Simpson', '2001',
     'Three works on loan from the multimedia artist, listed left to right.'),
    ('Patio', 'Just Sitting', 'Linda Hoffman', '2018',
     'Five small seated figures rooted in the artist’s Zen meditation practice, placed so the sky reflects in the '
     'water around them.'),
    ('Patio', 'St. Francis', 'Alfred Duca', '1958', 'Bronze; a gift from the Stephen and Sybil Stone Foundation in 1971.'),
    ('Courtyard', 'Poetic Pause', 'Jim Cole', '1992', 'A gift from Charles and Maples Stamm in 2015.'),
    ('Front Outer Circle', 'Sight', 'Paul Meneses', '2016',
     'Made to contrast and coexist with the outdoors; the rust that forms on it protects the work.'),
    ('Front Outer Circle', 'Sanctuary', None, 'about 2005',
     'A memorial to Jennifer Atkinson, the museum’s curator and director until her death in 2003.'),
    ('Front Outer Circle', 'Glace Bay', 'George Greenamyer', '1974',
     'Heavy, dark and full of wheels, it celebrates the Industrial Revolution; named after a Nova Scotia coal town.'),
    ('Front Inner Circle', 'Work Tools Memorial', None, '2007',
     'A memorial to Joe Beasly Riley, a Brockton resident and friend of the museum.'),
    ('Education Walk', 'Stoneworks', 'David Phillips', '1978',
     'Boulders rearranged as sculpture, recalling Zen stone gardens.'),
]
OUTDOOR_NOTE = ('Placed from the museum’s Outdoor Sculpture Guide (2023); outdoor areas are drawn approximately '
                'around the building.')


def name_of(artist):
    """'Allen, Shelley Muzylowski' -> 'Shelley Muzylowski Allen'."""
    a = (artist or '').strip()
    if ';' in a: return ' and '.join(name_of(x) for x in a.split(';'))
    m = re.match(r'^([^,]+), ([^,]+)$', a)
    return f'{m.group(2)} {m.group(1)}' if m else a or None


def clean(s):
    s = re.sub(r'<br\s*/?>', ' ', s or '')
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('__', '× ').replace('" ×', '" ×')
    return re.sub(r'\s+', ' ', s).strip() or None


def where_on(r):
    """-> (gallery id or None, note) from the archive's On Display field."""
    u = r.get('USER1') or ''
    if 'The Vessel' in u: return 'Lampos Gallery', None
    if 'Fiber Fo' in u: return 'Community Gallery', None
    if u.strip() == 'Great Room': return 'Great Room', None
    if 'Interior Courtyard' in u: return 'Courtyard', None
    if 'On Loan' in u or 'Again and Again' in u: return None, clean(u)
    return None, None


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    objs = json.load(open(CACHE / 'objects.json'))
    exhibits = json.load(open(CACHE / 'exhibits.json'))
    in_show = {rid: 'Lampos Gallery' for rid in exhibits.get('The Vessel', [])}
    in_show.update({rid: 'Community Gallery' for rid in exhibits.get('Fiber Forward', [])})
    works, extra = [], []

    def add(a, room, note):
        if room:
            fl, gname = rooms[room]
            a.update(gallery=room, galleryName=gname, floor=fl, placeNote=note)
            works.append({k: v for k, v in a.items() if v not in (None, '', [])})
        else:
            extra.append({k: v for k, v in a.items() if v not in (None, '', [])})

    for key, room, title, maker, (d0, d1), slug, pic, known in SHOWS:
        if date.fromisoformat(d1) < TODAY: continue
        text = show_text(slug)
        when = f'{fmt(d0)} – {fmt(d1)}'
        if date.fromisoformat(d0) > TODAY: text = f'Opens {fmt(d0)}. ' + text
        img = picture(f'fuller-show-{key}', UP + pic)
        a = {'id': f'fuller-show-{key}', 'title': title, 'artist': maker, 'date': when, 'medium': 'Exhibition',
             'description': text, 'url': SITE + f'exhibitions/{slug}/', 'image': img,
             'imageCredit': 'Fuller Craft Museum' if img else None, 'temporary': True}
        add(a, room, None if known else GUESS)

    for rid, r in sorted(objs.items(), key=lambda kv: kv[1].get('CAT_NBR', '')):
        cat = r.get('CAT_NBR', '')
        if 'Myron' in (r.get('USER1') or ''): room, note = None, 'Off view for repairs (Myron the duck).'
        elif cat in OUTDOOR_CAT: room, note = OUTDOOR_CAT[cat], OUTDOOR_NOTE
        elif rid in in_show: room, note = in_show[rid], None
        else:
            room, note = where_on(r)
        img = picture(f'fuller-{re.sub(r"[^0-9a-z]+", "-", cat.lower()).strip("-") or rid}', archive_image(r),
                      size=1000 if room else 500)
        label = clean(r.get('ExhibitLbl'))
        desc = OUTDOOR_TEXT.get(cat) or label
        bits = [x for x in (clean(r.get('CATEG_2')), clean(r.get('WEIGHT')), clean(r.get('CREDIT_LINE'))) if x]
        if not desc: desc = '. '.join(bits) + '.' if bits else None
        elif bits: desc += ' (' + '; '.join(bits) + ')'
        if note and not room: desc = (note + ' ' + (desc or '')).strip()
        photo = clean(r.get('USER2'))
        a = {'id': f'fuller-{rid}', 'title': clean(r.get('CAT_NAM')) or 'Untitled', 'artist': name_of(r.get('ARTIST')),
             'date': clean(r.get('CATEG_16')), 'medium': clean(r.get('MATERIAL')), 'description': desc,
             'accession': cat, 'url': ARCHIVE_PAGE, 'image': img,
             'imageCredit': (f'Fuller Craft Museum, photo by {photo}' if photo else 'Fuller Craft Museum') if img else None}
        add(a, room, note if room else None)

    for i, (room, title, artist, when, text) in enumerate(OUTDOOR_EXTRA):
        add({'id': f'fuller-outdoor-{i}', 'title': title, 'artist': artist or 'Fuller Craft Museum', 'date': when,
             'medium': 'Outdoor sculpture', 'description': text, 'url': SITE + 'plan-your-visit/'}, room, OUTDOOR_NOTE)

    return ({'source': 'Fuller Craft Museum: Digital Archive (On Display field and exhibitions), current exhibition '
                       'pages, Outdoor Sculpture Guide',
             'checked': TODAY.isoformat(), 'count': len(works), 'complete': False, 'artworks': works}, extra)


def build_guide(works, extra):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in extra]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': on, 'gallery': a.get('gallery'), 'floor': a.get('floor')}.items()
                     if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': TODAY.isoformat(),
            'source': 'Fuller Craft Museum Digital Archive (collections.fullercraft.org) and fullercraft.org',
            'onViewKnown': True,
            'note': 'Everything in the museum’s online Digital Archive (983 objects), with the works the archive marks on display placed in their gallery, plus the '
                    'current shows and the outdoor sculpture.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, extra = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, extra)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} on view ({sum("image" in a for a in works["artworks"])} with pictures), '
          f'{len(extra)} more in the collection list')


if __name__ == '__main__':
    sys.exit(main())
