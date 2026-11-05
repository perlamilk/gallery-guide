#!/usr/bin/env python3
"""Build the Eric Carle Museum of Picture Book Art (Amherst) map guide (run: python3 tools/build_carle.py).

    data/carle/floors.json      the museum's one floor seen from above (a flat 2D plan)
    data/carle/artworks.json    the works the Carle shows online for its shows on view now, in their galleries
    data/carle/images/          their pictures, made smaller for phones
    data/guides/Q5386237.json   every work we know of, for the museum page

First run tools/harvest_carle.py: it reads the Carle's exhibition and collection pages into .cache/carle.

The map
-------
The Carle publishes no floor plan (its visit pages say only that everything is on one level). The plan here is
APPROXIMATE, put together from
  - the building's outline in OpenStreetMap (way 893989994), which matches the roofs on Esri World Imagery,
  - the landscape architects' plan of the courtyard and Bobbie's Meadow (Mantle Landscape Architecture, 2019):
    the Art Studio is the south end of the west wing, the Great Hall runs along the north side of the courtyard
    with doors onto a terrace, the Carle Café is in the south end of the east wing with its own terrace, the main
    entrance is a double-door vestibule on the west side where the drive and drop-off are,
  - OpenStreetMap's point for The Carle Bookshop (in the west wing, by the lobby) and its door to the meadow path,
  - the Carle's pages: West Gallery (Eric Carle), Central and East Galleries; Reading Library (with its own small
    show); Art Studio; auditorium; power-assist doors at the main entrance and the gallery entrance, and a door
    with a paved path out to Bobbie's Meadow; restrooms (men, women, all-gender, all with changing tables);
    "the café is down the opposite hall from the library" (a visitor's review).
Which room is exactly where inside each wing is our best reading of those sources; the map says so.
Coordinates are metres east/north of the OpenStreetMap museum point (42.3211, -72.533), times 12.
"""
import html
import io
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_carle import get  # noqa: E402  (cached, polite fetch)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'carle'
CACHE = ROOT / '.cache' / 'carle'
MUSEUM = 'Q5386237'
SITE = 'https://carlemuseum.org'
TODAY = date.today()
SOURCE = ('Approximate: OpenStreetMap building outline, the landscape architects’ courtyard plan and the Carle’s '
          'visit and accessibility pages')
K = 12          # pixels per metre


def P(x, y):
    """Metres east/north of the museum point -> map pixels (north up)."""
    return [round((x + 46) * K, 1), round((42 - y) * K, 1)]


def poly(*pts):
    return [P(x, y) for x, y in pts]


# (id, kind, name, polygon, short label for galleries)
ROOMS = [
    ('West Gallery', 'gallery', 'West Gallery (Eric Carle’s own art)',
     poly((-40, 2.2), (-15, 2.0), (-15, 20.4), (-39.1, 21.6)), 'West'),
    ('Central Gallery', 'gallery', 'Central Gallery', poly((-15, 8), (21, 8), (21.1, 18.9), (-15, 20.4)), 'Central'),
    ('East Gallery', 'gallery', 'East Gallery', poly((25, -0.8), (34.6, -0.6), (38.8, -0.8), (39.6, 18.1), (25, 18.7)),
     'East'),
    ('Reading Library', 'gallery', 'Reading Library (picture books to read, and a small show)',
     poly((-17, -26), (-11, -26), (-10.2, -8), (-17, -8)), 'Reading Library'),
    ('Lobby', 'corridor', 'Lobby · admissions desk', poly((-30.2, -8), (-10.2, -8), (-10, 2), (-29.6, 1.8)), None),
    ('Great Hall', 'corridor', 'The Great Hall (seating, windows onto the courtyard)',
     poly((-10.4, -11.5), (7.3, -12.3), (7.5, -7.2), (19.4, -7.8), (19.6, -1), (21, -1), (21, 8), (-15, 8), (-15, 2),
          (-10, 2)), None),
    ('West hall', 'corridor', 'Hall to the Art Studio', poly((-21, -26), (-17, -26), (-17, -8), (-21, -8)), None),
    ('East hall', 'corridor', 'East hall · restrooms · to the auditorium', poly((21, -1), (25, -0.8), (25, 18.7),
                                                                              (21.1, 18.9)), None),
]
SPACES = [
    ('Bookshop', 'space', 'The Carle Bookshop', poly((-30.6, -26), (-21, -26), (-21, -8), (-30.2, -8)), None),
    ('Art Studio', 'space', 'Art Studio (make art, open to everyone)',
     poly((-31.2, -40.6), (-12.2, -41.4), (-11.9, -37.4), (-11, -26), (-30.6, -26)), None),
    ('Carle Café', 'space', 'Carle Café (eating area, vending machine; bring your own food)',
     poly((18.6, -25.5), (37.2, -26.3), (38, -8.1), (34.3, -7.9), (34.6, -0.6), (25, -0.8), (21, -1), (19.6, -1),
          (19.4, -7.8)), None),
    ('Auditorium', 'space', 'Auditorium (films, talks, storytime; hearing loop)',
     poly((21.1, 18.9), (39.6, 18.1), (42.6, 18), (42.8, 24), (39.6, 24.2), (40.2, 37.8), (22, 38.6)), None),
]
DOORS = [
    ('Lobby', 'Great Hall', (-10.1, -3)), ('Lobby', 'Bookshop', (-25.5, -8)), ('Lobby', 'West hall', (-19, -8)),
    ('Lobby', 'Reading Library', (-13.5, -8)), ('Lobby', 'West Gallery', (-22, 2)),
    ('West hall', 'Art Studio', (-19, -26)), ('West hall', 'Bookshop', (-21, -17)),
    ('Great Hall', 'West Gallery', (-15, 5)), ('Great Hall', 'Central Gallery', (3, 8)),
    ('Great Hall', 'East hall', (21, 3.5)), ('Great Hall', 'Carle Café', (19.5, -4.5)),
    ('East hall', 'East Gallery', (25, 9)), ('East hall', 'Auditorium', (23, 18.8)), ('East hall', 'Carle Café', (23, -0.9)),
]
AMENITIES = [('entrance', -32, -3), ('info', -22, -3.5), ('shop', -26, -17), ('dining', 29, -15),
             ('entrance', -5, -12.6), ('entrance', -12.2, -38.5), ('entrance', 28, -26.8),
             ('restroom', 23, 3), ('restroom-all', 23, 6.5), ('nursing', 23, 10)]
LABELS = [
    ('Main entrance (power-assist doors) · drop-off, free parking with 4 accessible spaces to the west', 'note', -44, -4.5),
    ('Courtyard', 'note', 4, -19),
    ('Doors to the courtyard terrace and the paved path to Bobbie’s Meadow', 'note', 2, -15),
    ('Bobbie’s Meadow: orchard and meadow walk (outside, south)', 'note', 4, -47),
    ('Café terrace (outside)', 'note', 28, -29.5),
    ('Everything is on this one floor · places inside each wing approximate', 'note', 0, 43),
]
AREA = 'Entrance · Lobby · Bookshop · Reading Library · Art Studio · Great Hall · West, Central and East Galleries · ' \
       'Café · Auditorium · Restrooms'


def build_floors():
    rooms = [{'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if kind == 'gallery' else {})}
             for rid, kind, name, pl, short in ROOMS + SPACES]
    ids = {r['id'] for r in rooms}
    doors = [{'a': a, 'b': b, 'at': P(x, y), 'width': 10, 'axis': 'o'} for a, b, (x, y) in DOORS]
    for d in doors:
        assert d['a'] in ids and d['b'] in ids, d
    floor = {'id': '1', 'label': 'Museum Floor', 'order': 1, 'transform': [1, 0, 0], 'area': AREA,
             'rooms': rooms, 'closed': [],
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS],
             'doors': doors}
    return {'about': 'Built by tools/build_carle.py. The Carle publishes no floor plan: this one is approximate, from '
                     'the building’s outline, the landscape architects’ courtyard plan and the Carle’s visit pages.',
            'source': SOURCE, 'units': 'metres x 12, north up', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------

ABBR = re.compile(r'(?:\b(?:Mrs|Mr|Dr|St|Jr|Sr|Inc|Co|ca|no|vol)|\b[A-Z])$')
CREDIT = re.compile(r'^(Gift|Museum [Pp]urchase|Purchase|Purchased|Collection|Courtesy|Bequest|Private|Lent|Loan|'
                    r'The Morgan|Mead Art|Smith College|Promised)')
MONTHS = 'January February March April May June July August September October November December'.split()


def sentences(text):
    """Split a caption into sentences without breaking at Mrs. / W. / ca. and the like."""
    out, start = [], 0
    for m in re.finditer(r'\.\s+(?=[A-Z“"(©])', text):
        if ABBR.search(text[start:m.start()]): continue
        out.append(text[start:m.start() + 1].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [s for s in out if s]


def to_date(s):
    m = re.match(r'(?:Sept?|[A-Z][a-z]+)\.? (\d{1,2}), (\d{4})', s.strip())
    if not m: return None
    mon = s.strip()[:3]
    month = next(i for i, n in enumerate(MONTHS, 1) if n.startswith(mon))
    return date(int(m[2]), month, int(m[1]))


def parse(caption):
    """'Artist, Illustration for Book by X (Publisher). Credit. © 1994 Holder.' -> fields (None if not a work)."""
    text = caption.replace(' ', ' ').replace(' ,', ',')
    view = re.findall(r'On view ((?:[A-Z][a-z]+\.? \d{1,2}, \d{4})) to ((?:[A-Z][a-z]+\.? \d{1,2}, \d{4}))', text)
    text = re.sub(r'^On view [^:]*:\s*', '', text)
    text = re.split(r'\s+On view ', text)[0].strip()
    parts = sentences(text)
    if not parts: return None
    head, rest = parts[0], parts[1:]
    copy = next((i for i, s in enumerate(rest) if s.startswith('©') or 'Public domain' in s), None)
    if copy is None and '©' in head:                    # "Faith Ringgold, Tar Beach 2, 1990. © Faith Ringgold. ..."
        copy = -1
    credit_bits = list(dict.fromkeys(s for i, s in enumerate(rest) if i != copy and CREDIT.match(s)))[:2]
    if not credit_bits and rest and copy != 0 and not rest[0].startswith('©'):
        credit_bits = rest[:1]
    credit = ' '.join(credit_bits)
    copyright_ = rest[copy] if copy is not None and copy >= 0 else ''
    if not credit and not copyright_ and not CREDIT.match(rest[0] if rest else ''): return None
    m = re.match(r'(.+?), (.+)$', head)
    if not m or ' for ' in m[1] or len(m[1]) > 90: return None
    if any(w[0].islower() and w not in ('de', 'van', 'von', 'and', 'la', 'le', 'du', 'band', 'of')
           for w in re.sub(r'\(.*?\)', '', m[1]).split()):
        return None                                     # a sentence of a biography, not "Artist, Title"
    artist, title = m[1].strip(), m[2].strip().rstrip('.')
    d = re.search(r',\s*((?:ca\.\s*)?\d{4}(?:[–-]\d{1,4})?(?: \(print \d{4}\))?|n\. ?d)\.?$', title)
    when = ''
    if d:
        when, title = re.sub(r'n\. ?d', '', d[1]), title[:d.start()].strip()
    if not when:
        y = re.search(r'©\s*(\d{4})', copyright_ or credit or text)
        when = y[1] if y else ''
    title = re.split(r'\.\s+(?=Collection|Gift|Courtesy)', title)[0]
    title = re.sub(r'\s+', ' ', title).replace('T he ', 'The ')
    medium = ''
    book = re.match(r'(?:Alternate |Variant |Unpublished |Book dummy sketch |Book pages |Woodcut block )?'
                    r'[Ii]llustration (?:for|on) (.+?)(?: by .*| \(.*| collected by .*| gathered .*)?$', title)
    return {'artist': artist, 'title': title, 'date': when, 'credit': credit, 'copyright': copyright_.rstrip('.'),
            'book': book[1].strip() if book else None, 'medium': medium,
            'view': [(to_date(a), to_date(b)) for a, b in view]}


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(when):
    m = re.search(r'\d{4}', when or '')
    return int(m[0]) if m else None


def img_url(src):
    return src if src.startswith('http') else SITE + src


def picture(key, src):
    """Save a phone-sized JPEG of a picture from the Carle's site (cached download)."""
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/carle/images/{key}.jpg'
    f = get(img_url(src), binary=True)
    if not f: return None
    try:
        im = Image.open(io.BytesIO(Path(f).read_bytes()))
    except Exception:
        return None
    im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/carle/images/{key}.jpg'


def fmt_dates(d):
    """'September 19, 2026 - September 5, 2027' -> 'Sep 19, 2026 – Sep 5, 2027'."""
    return re.sub(r'\b([A-Z][a-z]{2})[a-z]+\b', r'\1', d or '').replace(' - ', ' – ')


def show_open(dates):
    a, b = [s.strip() for s in dates.split(' - ')]
    end = to_date(b)
    start = to_date(a if re.search(r'\d{4}', a) else f'{a}, {end.year}')
    return start, end


# Reading Library show: its page names books, not artists with captions, so the three pictured books are typed here.
ENTWINED = [
    ('Michaela Goade (Tlingit)', 'Illustration for Berry Song', '2022', 'Little, Brown and Company', 'Berry Song'),
    ('Carly Lake', 'Illustration for Waa’aka’: The Bird Who Fell in Love with the Sun by Cindi M. Alvitre', '2020',
     'Heyday', 'Waa’aka’'),
    ('Madelyn Goodnight', 'Illustration for Rock Your Mocs by Laurel Goodluck', '2023', 'Heartdrum', 'Rock Your Mocs'),
]


def build_works(floors, harvest):
    rooms = {r['id']: r['name'] for r in floors['floors'][0]['rooms']}
    out, skipped, seen_titles = [], [], {}
    for ex in harvest['exhibitions']:
        start, end = show_open(ex['dates'])
        room = ex['room']
        # On the map: shows open today, and a show opening within three weeks in a gallery that is between shows
        if end < TODAY or (start > TODAY and (start - TODAY).days > 21):
            skipped.append(ex['title']); continue
        if (end - TODAY).days < 7 and any(        # closes this week and the next show there is already listed
                o['room'] == room and show_open(o['dates'])[0] > TODAY for o in harvest['exhibitions']):
            skipped.append(ex['title'] + ' (closes this week)'); continue
        show = f'{ex["title"]} ({fmt_dates(ex["dates"])})'
        how = (f'Pictured on the Carle’s page for this show, which is in the {room}.' if start <= TODAY else
               f'Opens {fmt_dates(ex["dates"].split(" - ")[0])}: until then the {room} is closed between shows.')
        items = ex['works']
        if ex['room'] == 'Reading Library':
            rows = [{'artist': a, 'title': t, 'date': d, 'credit': '', 'copyright': f'© {d} {a}' if d else '',
                     'book': b, 'view': [], 'src': w['src']} for (a, t, d, pub, b), w in zip(ENTWINED, items)]
        else:
            rows = []
            captions = [re.sub(r'^On view [^:]*:\s*', '', w['caption']) for w in items]
            for i, w in enumerate(items):
                if 'interior_feature_image' in w['src'] and any(
                        c[:60] == captions[i][:60] for c in captions[i + 1:]):
                    continue                            # the page's banner repeats a picture shown again below
                p = parse(w['caption'])
                if p: rows.append({**p, 'src': w['src']})
        for p in rows:
            if p['view'] and not any(a and b and a <= TODAY <= b for a, b in p['view']):
                continue                                    # a later rotation of the show
            base = norm(p['artist'])[:14] + '-' + norm(p['book'] or p['title'])[:28]
            n = seen_titles[base] = seen_titles.get(base, 0) + 1
            key = 'carle-' + base + (f'-{n}' if n > 1 else '')
            title = p['title'] + (f' ({n})' if n > 1 else '')
            note = how
            if p['view'] and p['view'][0][1] and p['view'][0][1] < end:
                note += f' This work is on view until {p["view"][0][1].strftime("%b %-d, %Y")}.'
            a = {'id': key, 'title': title, 'artist': p['artist'], 'date': p['date'], 'year': year_of(p['date']),
                 'creditLine': ' '.join(x for x in (p['credit'], p['copyright']) if x), 'gallery': room,
                 'galleryName': rooms[room], 'floor': '1', 'placeNote': note, 'exhibition': show, 'url': ex['url'],
                 'image': picture(key, p['src']), 'imageCredit': 'The Eric Carle Museum of Picture Book Art'}
            if not a['image']: a.pop('imageCredit')
            out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r[0]: i for i, r in enumerate(ROOMS)}
    out.sort(key=lambda a: (order[a['gallery']], a['exhibition']))
    return {'source': 'The Eric Carle Museum’s exhibition pages (carlemuseum.org)', 'checked': TODAY.isoformat(),
            'count': len(out), 'complete': False, 'artworks': out}, skipped


def build_guide(works, harvest):
    rows, seen = [], set()
    for a in works['artworks']:
        rows.append({'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': '1', 'credit': a.get('creditLine')})
        seen.add(norm(a['title'] + a['artist']) + norm(a.get('image', '')))
    pics = set()
    for page in harvest['collection']:
        for w in page['works']:
            p = parse(w['caption'])
            if not p: continue
            pic = re.sub(r'\?.*', '', w['src'].split('/')[-1])
            if pic in pics: continue
            pics.add(pic)
            key = 'carle-c-' + re.sub(r'[^\w-]', '', pic.rsplit('.', 1)[0])[:40]
            rows.append({'id': key, 'title': p['title'], 'artist': p['artist'], 'date': p['date'],
                         'year': year_of(p['date']), 'url': page['url'], 'imageUrl': img_url(w['src']),
                         'onView': False, 'credit': ' '.join(x for x in (p['credit'], p['copyright']) if x)})
    rows = [{k: v for k, v in r.items() if v not in (None, '')} for r in rows]
    rows.sort(key=lambda w: (not w['onView'], norm(w['artist'].split(' ')[-1]), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Eric Carle Museum of Picture Book Art', 'checked': TODAY.isoformat(),
            'source': 'The Eric Carle Museum’s exhibition, Collection Highlights and Featured Artists pages',
            'onViewKnown': True,
            'note': 'The Carle’s permanent collection has more than 9,000 objects by more than 250 artists, mostly '
                    'fragile works on paper that are shown in rotating exhibitions, so most are not on view. It has no '
                    'public collection database yet. This list is what the Carle shows online: the works pictured for '
                    'its current shows (many of them loans) and its Collection Highlights and Featured Artists pages.',
            'works': rows}


def main():
    hv = CACHE / 'harvest.json'
    if not hv.exists():
        raise SystemExit('run tools/harvest_carle.py first')
    harvest = json.loads(hv.read_text())
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, skipped = build_works(floors, harvest)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, harvest)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'collection list {len(guide["works"])} ({idx["museums"][MUSEUM]["pictures"]} pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')
    print('  not on the map now:', '; '.join(skipped))


if __name__ == '__main__':
    sys.exit(main())
