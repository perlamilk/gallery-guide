#!/usr/bin/env python3
"""Build the ICA Boston map guide (run: python3 tools/harvest_ica.py, then python3 tools/build_ica.py).

    data/ica/floors.json       the four floors seen from above (a flat 2D plan)
    data/ica/artworks.json     the works in the building now, in the gallery where they are shown
    data/guides/Q3152226.json  the whole ICA Collection (about 400 works) for the museum page

The map: the 4th floor, where all the galleries are, is traced from the ICA's own gallery map
(icaboston.org/wp-content/uploads/2023/03/ica-gallery-map.png, 500 x 309 px; coordinates below are those
pixels, doubled when written). The ICA publishes no plan of floors 1-3, so they are drawn from its
descriptions (the lobby tapers to the Holly McGrath Visitor Center with the store behind it facing the water;
the Fineberg Art Wall is on the lobby's east wall; the Art Lab, Common Room, Wine + Coffee Bar and restrooms
are on the 1st floor; the theater fills the 2nd and 3rd floors, main entrance on the 3rd). They are
approximate, and the map says so. Elevators and stairs sit at the same place on every floor, which is how
the directions link floors.

The works: the exhibition pages say which gallery each show is in (90 YEARS in the Bridgitt and Bruce Evans
and Karen and Brian Conway Galleries, To My Best Friend in the Kim and Jim Pallotta Gallery, ...), and
90 YEARS - Beyond the Galleries names a work on each floor. Works pictured on those pages go in that
gallery. To My Best Friend draws on the 50+ works Fotene Demoulas and Tom Coté helped bring into the
collection, so collection works with that credit go in the Pallotta Gallery, with a note. The rest of the
collection is listed on the museum page as not on view.
"""
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_ica import get, text  # noqa: E402  (same polite, cached reader)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'ica'
CACHE = ROOT / '.cache' / 'ica'
MUSEUM = 'Q3152226'
SOURCE = 'ICA gallery map (4th floor) and the ICA’s descriptions of its building'
K = 2


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


GLASS_ELEV, ELEV, STAIRS = (302, 146), (364, 146), (393, 147)

# (id, kind, name, poly in map pixels, label for galleries)
ROOMS = {
    '1': [
        ('Grandstand', 'space', 'Jill Medvedow Grandstand and HarborWalk (outdoors, under the cantilever)',
         rect(108, 24, 178, 262), None),
        ('Wine + Coffee Bar', 'space', 'ICA Wine + Coffee Bar (on the waterfront)', rect(180, 24, 278, 120), None),
        ('Art Lab', 'space', 'Bank of America Art Lab (hands-on art making)', rect(280, 24, 446, 120), None),
        ('ICA Store', 'space', 'ICA Store', rect(180, 122, 278, 200), None),
        ('Lobby', 'gallery', 'State Street Corporation Lobby · Holly McGrath Visitor Center',
         [[280, 122], [428, 122], [428, 190], [446, 190], [446, 240], [180, 240], [180, 202], [280, 202]], 'Lobby'),
        ('Art Wall', 'gallery', 'Sandra and Gerald Fineberg Art Wall', rect(430, 122, 446, 188), 'Art Wall'),
        ('Common Room', 'space', 'Common Room', rect(180, 242, 300, 292), None),
        ('1-services', 'corridor', 'Self-service coat and bag check · restrooms', rect(302, 242, 446, 292), None),
    ],
    '2': [
        ('Theater 2', 'space', 'Barbara Lee Family Foundation Theater (lower level, exit after performances)',
         rect(180, 24, 278, 292), None),
        ('2-lobby', 'corridor', 'Elevator lobby', rect(280, 122, 374, 170), None),
        ('Stairwell', 'gallery', 'Stairwell', rect(376, 122, 410, 172), 'Stairwell'),
        ('2-offices', 'space', 'Education center and offices (staff only)', rect(280, 24, 446, 120), None),
        ('2-offices south', 'space', 'Offices (staff only)', rect(280, 174, 446, 292), None),
    ],
    '3': [
        ('Theater 3', 'space', 'Barbara Lee Family Foundation Theater (main entrance)', rect(180, 24, 278, 292), None),
        ('Third-floor lobby', 'gallery', 'Third-floor lobby', rect(280, 122, 410, 172), '3rd-floor lobby'),
        ('3-offices', 'space', 'Offices (staff only)', rect(280, 24, 446, 120), None),
        ('3-offices south', 'space', 'Offices (staff only)', rect(280, 174, 446, 292), None),
    ],
    '4': [
        ('Founders Gallery', 'gallery', 'John Hancock Founders Gallery (harbor view)',
         [[108, 23], [133, 23], [133, 262], [120, 262]], 'Founders'),
        ('Buttenwieser Gallery', 'gallery', 'Paul and Catherine Buttenwieser Gallery', rect(135, 24, 185, 120),
         'Buttenwieser'),
        ('Demoulas Gallery', 'gallery', 'Fotene Demoulas Gallery', rect(187, 24, 278, 120), 'Demoulas'),
        ('Pallotta Gallery', 'gallery', 'Kim and Jim Pallotta Gallery', rect(280, 24, 446, 120), 'Pallotta Gallery'),
        ('4-restrooms', 'corridor', 'Restrooms and water fountains', rect(135, 122, 185, 168), None),
        ('Mediatheque', 'gallery', 'Poss Family Mediatheque', rect(187, 122, 278, 168), 'Mediatheque'),
        ('4-lobby', 'corridor', '4th floor elevator lobby (gallery stools, pencils)', rect(280, 122, 404, 170), None),
        ('Evans and Conway Galleries', 'gallery', 'Bridgitt and Bruce Evans and Karen and Brian Conway Galleries',
         [[135, 171], [446, 171], [446, 292], [135, 264]], 'Evans and Conway Galleries'),
    ],
}

DOORS = {
    '1': [('Grandstand', 'Lobby', (179, 220)), ('Grandstand', 'Wine + Coffee Bar', (179, 70)),
          ('Lobby', 'ICA Store', (280, 160)), ('Lobby', 'Art Lab', (360, 121)), ('Lobby', 'Art Wall', (429, 160)),
          ('Lobby', 'Common Room', (240, 241)), ('Lobby', '1-services', (370, 241)),
          ('Wine + Coffee Bar', 'Art Lab', (279, 70))],
    '2': [('2-lobby', 'Theater 2', (279, 146)), ('2-lobby', 'Stairwell', (375, 147))],
    '3': [('Third-floor lobby', 'Theater 3', (279, 146))],
    '4': [('4-lobby', 'Pallotta Gallery', (340, 121)), ('4-lobby', 'Evans and Conway Galleries', (340, 170)),
          ('Pallotta Gallery', 'Demoulas Gallery', (279, 95)), ('Demoulas Gallery', 'Buttenwieser Gallery', (186, 95)),
          ('Buttenwieser Gallery', 'Founders Gallery', (134, 80)), ('Founders Gallery', '4-restrooms', (134, 145)),
          ('Founders Gallery', 'Evans and Conway Galleries', (134, 220)),
          ('Evans and Conway Galleries', 'Mediatheque', (250, 170)), ('Demoulas Gallery', 'Mediatheque', (250, 121))],
}

AMENITIES = {
    '1': [('entrance', 446, 215), ('entrance', 180, 220), ('info', 300, 180), ('shop', 229, 160),
          ('dining', 229, 72), ('coat', 330, 266), ('restroom', 400, 266), ('elevator', *GLASS_ELEV),
          ('elevator', *ELEV), ('stairs', *STAIRS)],
    '2': [('elevator', *GLASS_ELEV), ('elevator', *ELEV), ('stairs', *STAIRS)],
    '3': [('elevator', *GLASS_ELEV), ('elevator', *ELEV), ('stairs', *STAIRS)],
    '4': [('elevator', *GLASS_ELEV), ('elevator', *ELEV), ('stairs', *STAIRS), ('restroom', 152, 145),
          ('water', 172, 158)],
}
LABELS = {
    '1': [('Main entrance · 25 Harbor Shore Drive', 'note', 400, 302), ('HarborWalk entrance (harbor side)', 'note', 143, 272),
          ('Floors 1–3 are drawn from the ICA’s descriptions, not a plan: approximate', 'note', 280, 322)],
    '2': [('Theater: main entrance on the 3rd floor', 'note', 230, 312)],
    '3': [],
    '4': [('Harbor view', 'note', 120, 14), ('All the galleries are on this floor', 'note', 290, 312)],
}
FLOORS = [
    ('1', '1st Floor', 'Entrances · Lobby and Visitor Center · ICA Store · Wine + Coffee Bar · Art Lab · '
                       'Fineberg Art Wall · Restrooms · Coat check', 1),
    ('2', '2nd Floor', 'Theater (lower level) · Stairwell installation', 2),
    ('3', '3rd Floor', 'Theater main entrance · Third-floor lobby installation', 3),
    ('4', '4th Floor', 'All the galleries · Founders Gallery over the harbor · Mediatheque · Restrooms', 4),
]


def pt(x, y):
    return [round(x * K, 1), round(y * K, 1)]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(x, y) for x, y in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 6 * K, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_ica.py. The 4th floor, where all the galleries are, is traced from the '
                     'ICA’s gallery map; floors 1–3 are drawn from the ICA’s descriptions of its building, so they '
                     'are approximate. Exhibitions change during the year.',
            'source': SOURCE, 'units': 'half pixels', 'defaultFloor': '4', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ----------------------------------------------------------------------------------------------------

# exhibition page -> room (the page names the gallery)
EXHIBITIONS = {'to-my-best-friend': 'Pallotta Gallery', '90-years': 'Evans and Conway Galleries',
               'leilah-babirye': 'Demoulas Gallery', 'cynthia-daignault': 'Buttenwieser Gallery',
               'caroline-monnet-man-made-land': 'Art Wall', 'my-ica-story': 'Mediatheque'}
SHOW = {'to-my-best-friend': 'To My Best Friend (Jan 23 – Dec 31, 2026)',
        '90-years': '90 YEARS (Oct 15, 2026 – Mar 7, 2027)',
        'leilah-babirye': 'Leilah Babirye: Embaga ya Naki ne Naki (Aug 27, 2026 – Jan 18, 2027)',
        'cynthia-daignault': 'Cynthia Daignault: Valley (Aug 27, 2026 – Jan 18, 2027)',
        'caroline-monnet-man-made-land': 'Caroline Monnet: Man-made Land (Sep 25, 2025 – Mar 21, 2027)',
        '90-years-beyond-the-galleries': '90 YEARS — Beyond the Galleries (Oct 1, 2026 – Mar 7, 2027)'}
# 90 YEARS — Beyond the Galleries: one work on each floor, named on that page (artist, title words, room)
BEYOND = [('Joan Logue', 'Video Portraits', 'Lobby'), ('Jenny Holzer', 'Inflammatory Wall', 'Stairwell'),
          ('Rineke Dijkstra', 'Almerisa', 'Third-floor lobby'), ('Glenn Ligon', 'Rückenfigur', 'Founders Gallery'),
          ('Glenn Ligon', 'Another Country', 'Founders Gallery')]
# named in the text of 90 YEARS as on view
NAMED = [('Yayoi Kusama', 'LOVE IS CALLING', 'Evans and Conway Galleries', '90-years')]

NOTE_SHOW = 'The ICA’s page for {show} shows this work; the page names this gallery.'
NOTE_BEYOND = 'The ICA’s page for 90 YEARS — Beyond the Galleries puts this work here.'
NOTE_TEXT = 'The ICA’s page for {show} names this work; the page names this gallery.'
NOTE_DONOR = ('Given by Fotene Demoulas and Tom Coté. To My Best Friend (until Dec 31, 2026) is drawn from the '
              'works they helped bring into the collection, so this one is probably in it, but the ICA does not '
              'list every work in the show.')


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def installation(slug):
    """The first installation view on a show's page, for shows that are one installation."""
    page = get(f'https://www.icaboston.org/exhibitions/{slug}/', f'ex-{slug}.html')
    for b in re.findall(r'<article class="scald-atom scald-atom-image.*?</article>', page, re.S):
        src = re.search(r'<img[^>]+src="([^"]+)"', b)
        cap = re.search(r'field-name-field-credit.*?<p>(.*?)</p>', b, re.S)
        if src and cap and text(cap[1]).startswith('Installation view'): return src[1]
    return None


# shows that are one installation by one artist: (page, artist, title, date, medium)
INSTALLATIONS = [('cynthia-daignault', 'Cynthia Daignault', 'Valley', '2026',
                  'Multi-panel painting installation of the view up the Merced River in Yosemite'),
                 ('caroline-monnet-man-made-land', 'Caroline Monnet', 'Man-made Land', '2025',
                  'Site-responsive installation: Tyvek, plastic and foil insulation, cut, pieced and sewn')]


def slides(slug):
    page = get(f'https://www.icaboston.org/exhibitions/{slug}/', f'ex-{slug}.html')
    out = []
    for b in re.findall(r'<article class="scald-atom scald-atom-image.*?</article>', page, re.S):
        src = re.search(r'<img[^>]+src="([^"]+)"', b)
        cap = re.search(r'field-name-field-credit.*?<p>(.*?)</p>', b, re.S)
        if not src or not cap: continue
        raw = cap[1]
        em = re.search(r'<em>(.*?)</em>', raw, re.S)
        cap_t = text(raw)
        if not em or re.match(r'Installation view', cap_t): continue
        artist = text(raw[:raw.find('<em>')]).rstrip(', ')
        title = text(em[1])
        if ', ' in artist:                  # "Andy Warhol, Facsimile of <em>Silver Clouds</em>"
            artist, pre = artist.split(', ', 1)
            title = f'{pre} {title}'
        rest = text(raw[raw.find('</em>') + 5:]).lstrip(', ')
        m = re.match(r'([^.]*?\d{4}[^.]*?)\.\s*(.*)$', rest)
        date, tail = (m[1].strip(), m[2]) if m else ('', rest)
        sent = [s.strip() for s in re.split(r'\.\s+', tail) if s.strip()]
        install = bool(sent) and sent[0].startswith('Installation view')
        medium = '' if install or not sent else sent[0].rstrip('.')
        if re.match(r'From the series', medium): medium = sent[1].rstrip('.') if len(sent) > 1 else ''
        credit = next((s.rstrip('.') for s in sent if re.search(r'Gift|gift|Acquired|Courtesy|Collection', s)), '')
        img = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', src[1])          # the full picture, not the carousel crop
        out.append({'artist': artist, 'title': title, 'date': date, 'medium': medium, 'credit': credit,
                    'image': src[1], 'imageFull': img, 'install': install})
    return out


def collection():
    return json.loads((CACHE / 'collection.json').read_text())


def work_id(c):
    return 'ica-' + (re.sub(r'[^\w.-]', '', c['accession']) if c.get('accession') else str(c['wpId']))


def from_collection(c, room, floor, gname, note, show=None):
    a = {'id': work_id(c), 'title': c['title'], 'artist': c['artist'] or c['artists'], 'date': c['date'],
         'year': year_of(c['date']), 'medium': c['medium'], 'dimensions': c.get('dimensions', ''),
         'accession': c['accession'], 'creditLine': c['credit'], 'gallery': room, 'galleryName': gname, 'floor': floor,
         'placeNote': note, 'exhibition': show, 'url': c['url'], 'image': c['image'], 'imageCredit': 'ICA Boston',
         'description': c.get('about', ''), 'descriptionKind': 'Text from the ICA’s website' if c.get('about') else None}
    return {k: v for k, v in a.items() if v not in (None, '')}


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    coll = collection()
    by_key = {}
    for c in coll:
        by_key.setdefault(norm(c['title']) + '|' + norm(c['artist'] or c['artists'])[:10], c)

    def find(artist, title_words):
        t, a = norm(title_words), norm(artist)[:10]
        hits = [c for c in coll if t in norm(c['title']) and norm(c['artist'] or c['artists']).startswith(a[:6])]
        return hits

    placed, out = set(), []

    def add(a):
        if a['id'] in placed: return
        placed.add(a['id'])
        out.append(a)

    for slug, room in EXHIBITIONS.items():
        floor, gname = rooms[room]
        for s in slides(slug):
            hits = find(s['artist'], s['title'])
            if hits:
                for c in hits: add(from_collection(c, room, floor, gname, NOTE_SHOW.format(show=SHOW[slug]), SHOW[slug]))
                continue
            aid = 'ica-' + norm(s['artist'])[:12] + '-' + norm(s['title'])[:28]
            a = {'id': aid, 'title': s['title'], 'artist': s['artist'], 'date': s['date'], 'year': year_of(s['date']),
                 'medium': s['medium'], 'gallery': room, 'galleryName': gname, 'floor': floor,
                 'placeNote': NOTE_SHOW.format(show=SHOW[slug]), 'exhibition': SHOW[slug],
                 'url': f'https://www.icaboston.org/exhibitions/{slug}/', 'image': s['image'],
                 'imageCredit': 'ICA Boston'}
            add({k: v for k, v in a.items() if v not in (None, '')})
    for slug, artist, title, date, medium in INSTALLATIONS:
        room = EXHIBITIONS[slug]
        floor, gname = rooms[room]
        a = {'id': 'ica-' + norm(artist)[:12] + '-' + norm(title)[:28], 'title': title, 'artist': artist, 'date': date,
             'year': year_of(date), 'medium': medium, 'gallery': room, 'galleryName': gname, 'floor': floor,
             'placeNote': NOTE_SHOW.format(show=SHOW[slug]), 'exhibition': SHOW[slug],
             'url': f'https://www.icaboston.org/exhibitions/{slug}/', 'image': installation(slug),
             'imageCredit': 'ICA Boston (installation view)'}
        add({k: v for k, v in a.items() if v not in (None, '')})
    beyond = slides('90-years-beyond-the-galleries')
    show = SHOW['90-years-beyond-the-galleries']
    for artist, words, room in BEYOND:
        floor, gname = rooms[room]
        hits = find(artist, words)
        if hits:
            for c in hits: add(from_collection(c, room, floor, gname, NOTE_BEYOND, show))
            continue
        s = next((s for s in beyond if s['artist'].startswith(artist) and norm(words) in norm(s['title'])), None)
        a = {'id': 'ica-' + norm(artist)[:12] + '-' + norm(words)[:28], 'title': s['title'] if s else words,
             'artist': artist, 'date': s['date'] if s else '', 'year': year_of(s['date']) if s else None,
             'medium': s['medium'] if s else '', 'gallery': room,
             'galleryName': gname, 'floor': floor, 'placeNote': NOTE_BEYOND, 'exhibition': show,
             'url': 'https://www.icaboston.org/exhibitions/90-years-beyond-the-galleries/',
             'image': s['image'] if s else None, 'imageCredit': 'ICA Boston' if s else None}
        add({k: v for k, v in a.items() if v not in (None, '')})
    for artist, words, room, slug in NAMED:
        floor, gname = rooms[room]
        for c in find(artist, words):
            add(from_collection(c, room, floor, gname, NOTE_TEXT.format(show=SHOW[slug]), SHOW[slug]))
    floor, gname = rooms['Pallotta Gallery']
    for c in coll:
        if re.search(r'Fotene Demoulas', c['credit'] or '') and re.search(r'Cot[ée]', c['credit'] or ''):
            add(from_collection(c, 'Pallotta Gallery', floor, gname, NOTE_DONOR, SHOW['to-my-best-friend']))

    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a['placeNote'] == NOTE_DONOR, a.get('year') or 0))
    return {'source': 'ICA Boston website (icaboston.org collection and exhibition pages); pictures from icaboston.org',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}


def build_guide(works):
    """The whole collection for the museum page: works in the building now are on view, the rest are not."""
    on = {a['id']: a for a in works['artworks']}
    rows = []
    for c in collection():
        wid = work_id(c)
        a = on.get(wid)
        w = {'id': wid, 'title': c['title'], 'artist': c['artist'] or c['artists'], 'date': c['date'],
             'year': year_of(c['date']), 'medium': c['medium'], 'accession': c['accession'], 'url': c['url'],
             'imageUrl': c['image'], 'onView': bool(a)}
        if a: w.update(gallery=a['gallery'], floor=a['floor'])
        rows.append({k: v for k, v in w.items() if v not in (None, '')})
    for a in works['artworks']:            # works on loan for a show are on view too, though not in the collection
        if not any(r['id'] == a['id'] for r in rows):
            rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'),
                         'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                         'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                         'floor': a['floor']}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Institute of Contemporary Art, Boston', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'ICA Boston website (icaboston.org)', 'onViewKnown': True,
            'note': 'The ICA Collection as listed on icaboston.org, plus works on loan to current shows. '
                    'On view means shown in one of the current exhibitions.',
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
    print(f'{works["count"]} works in the building, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'collection {len(guide["works"])} ({idx["museums"][MUSEUM]["pictures"]} pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
