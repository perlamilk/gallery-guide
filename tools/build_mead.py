#!/usr/bin/env python3
"""Build the Mead Art Museum (Amherst College) map guide (run: python3 tools/build_mead.py).

    data/mead/floors.json       the gallery floor seen from above (a flat 2D plan)
    data/mead/artworks.json     the works known to be on view now, in the room where they are shown
    data/mead/images/           their pictures, made smaller for phones
    data/guides/Q6803132.json   every Mead work we know of, for the museum page

Where the information comes from
--------------------------------
www.amherst.edu answers robots (and even a normal Mac with curl) with a CAPTCHA page, so the Mead's own pages were
read from Internet Archive copies (web.archive.org, newest copy of each page: home page Oct 17, 2026; current show
Oct 7, 2026; accessibility page Aug 2024). They were saved to .cache/mead/raw/raw/mead (kept out of git) by a run on
Grazi's Mac; INDEX.txt there lists each file and its source.

The map: the Mead publishes no floor plan. The plan here is APPROXIMATE, put together from
  - the building's outline in OpenStreetMap (way 217241847, which also takes in Stirn Auditorium to the south),
  - the architects' first-floor plan of March 15, 1948 (McKim, Mead & White, on Wikimedia Commons, CC BY 4.0):
    the long east gallery with a bay in the middle, the Rotherwas Room at its south end, offices along the west,
    the entrance in the middle of the west side facing James and Stearns Halls, the Stearns Steeple outside,
  - the Mead's accessibility page: all public rooms are on one floor; the Fairchild Gallery is the big room you
    enter; a single restroom is between the Fairchild and Arms Galleries; two larger restrooms (baby changing) and a
    drinking fountain are past the glass door on the right side of the Fairchild Gallery; coat room; power doors
    and a call button at the main entrance; two accessible parking spaces in front; the elevator goes only to
    collection storage, run by staff,
  - the About page ("eight galleries") and the Mead Reimagined release (the Hall Walls hallway).
Which smaller room is which (Arms, teaching gallery, video gallery, the room with the Assyrian reliefs) is our
best guess; the map says so. Coordinates are metres east/north of the OpenStreetMap museum point, times 12.

The works: the Mead owns 20,000+ works, catalogued in the Five College Museums database, whose robots.txt shuts
out AI crawlers, so it is not read. Instead:
  - works pictured or named on the pages of what is on view now: "My beautiful, pitiful age" (Aug 25, 2026 –
    Jan 3, 2027), the Rotherwas Room and its stained glass (always on view), the Assyrian reliefs (always on view);
  - the Collection Highlights pages; Wikimedia Commons categories of the Mead (fetched on Grazi's Mac:
    .cache/mead/raw/raw/mead/commons); Wikidata (CC0) works whose collection is the Mead.
Only on-view works go on the map. The rest are listed on the museum page as part of the collection.
"""
import glob
import html
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'mead'
CACHE = ROOT / '.cache' / 'mead'
RAW = CACHE / 'raw' / 'raw' / 'mead'
MUSEUM = 'Q6803132'
SITE = 'https://www.amherst.edu/museums/mead'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = ('Approximate: OpenStreetMap building outline, the architects’ 1948 first-floor plan (Wikimedia Commons) and '
          'the Mead’s visit and accessibility pages')
K = 12          # pixels per metre


def P(x, y):
    """Metres east/north of the museum point -> map pixels (north up)."""
    return [round((x + 22) * K, 1), round((34 - y) * K, 1)]


def box(x0, y0, x1, y1):
    return [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]


def poly(*pts):
    return [P(x, y) for x, y in pts]


# (id, kind, name, polygon, short label for galleries)
ROOMS = [
    ('Fairchild Gallery', 'gallery', 'Fairchild Gallery (the main gallery, straight ahead from the entrance)',
     poly((0, -12.5), (9.4, -12.5), (9.4, -4), (13.8, -4), (13.8, 3.4), (9.4, 3.4), (9.4, 12.5), (0, 12.5)), 'Fairchild'),
    ('Lobby', 'corridor', 'Lobby · front desk · coat room', box(-5.6, -2.5, 0, 2.6), None),
    ('Arms Gallery', 'gallery', 'Arms Gallery (place approximate)', box(-1, 12.5, 9, 25.8), 'Arms'),
    ('North hall', 'corridor', 'Hall · single restroom · staff elevator', box(-5, 12.5, -1, 25.8), None),
    ('Hall Walls', 'gallery', 'Hall Walls: hallway with a yearly artist installation (place approximate)',
     box(-16.3, 12.2, -5, 19.4), 'Hall Walls'),
    ('North Gallery', 'gallery', 'Gallery (north; room name not published)', box(-11.3, 19.4, -5, 25.8), 'Gallery'),
    ('Teaching Gallery', 'gallery', 'Teaching Gallery (classes; place approximate)', box(-20.4, 19.4, -11.3, 31.7),
     'Teaching'),
    ('Rotherwas Room', 'gallery', 'Rotherwas Room (English paneled room of 1611, always on view)',
     box(2, -26.2, 9.9, -12.5), 'Rotherwas Room'),
    ('South hall', 'corridor', 'Glass door · restrooms · baby changing · drinking fountain', box(-4.2, -18, 2, -12.5), None),
    ('Video Gallery', 'gallery', 'Video Gallery (place approximate)', box(-4.2, -26.2, 2, -18), 'Video'),
    ('Southwest Gallery', 'gallery', 'Gallery (southwest): the Assyrian reliefs (place approximate)',
     poly((-15.7, -13.5), (-4.2, -13.5), (-4.2, -26.2), (-15.7, -26.2)), 'Assyrian reliefs'),
]
CLOSED = [box(-5, 2.6, 0, 12.5), box(-4.2, -12.5, 0, -2.5)]      # offices along the west side (staff only)
SPACES = []  # Stirn Auditorium, joined to the south end, is a separate building: only labelled
DOORS = [
    ('Lobby', 'Fairchild Gallery', (0, 0)), ('Fairchild Gallery', 'Arms Gallery', (5, 12.5)),
    ('Fairchild Gallery', 'North hall', (-0.5, 12.5)), ('North hall', 'Arms Gallery', (-1, 20)),
    ('North hall', 'Hall Walls', (-5, 15.5)), ('North hall', 'North Gallery', (-5, 22.5)),
    ('Hall Walls', 'Teaching Gallery', (-13.5, 19.4)), ('Fairchild Gallery', 'South hall', (1, -12.5)),
    ('Fairchild Gallery', 'Rotherwas Room', (6, -12.5)), ('South hall', 'Video Gallery', (-1, -18)),
    ('South hall', 'Southwest Gallery', (-4.2, -15.5)),
]
AMENITIES = [('entrance', -6.8, 0), ('info', -3, -1.5), ('coat', -3, 1.8), ('restroom', -3, 13.6),
             ('elevator', -3, 24.5), ('restroom', -2.5, -14.2), ('restroom', 0.5, -14.2), ('nursing', -2.5, -16.8),
             ('water', 0.5, -16.8)]
LABELS = [
    ('Main entrance (power doors, call button) · 2 accessible parking spaces in front', 'note', -14, -4.5),
    ('Stearns Steeple (outside)', 'note', -12, 7.5),
    ('All galleries on this one floor · no café or shop', 'note', -2, 36.5),
    ('Stirn Auditorium (next door, own entrance)', 'note', -6, -32),
    ('Rooms other than Fairchild and Rotherwas: places approximate', 'note', -2, -38),
]


def build_floors():
    rooms = [{'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if kind == 'gallery' else {})}
             for rid, kind, name, pl, short in ROOMS + SPACES]
    ids = {r['id'] for r in rooms}
    doors = [{'a': a, 'b': b, 'at': P(x, y), 'width': 10, 'axis': 'o'} for a, b, (x, y) in DOORS]
    for d in doors:
        assert d['a'] in ids and d['b'] in ids, d
    floor = {'id': '1', 'label': 'Gallery Floor', 'order': 1, 'transform': [1, 0, 0],
             'area': 'Entrance · Lobby and coat room · Fairchild Gallery · Rotherwas Room · Arms Gallery · '
                     'Assyrian reliefs · Restrooms',
             'rooms': rooms, 'closed': [{'poly': c} for c in CLOSED],
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS],
             'doors': doors}
    return {'about': 'Built by tools/build_mead.py. The Mead publishes no floor plan: this one is approximate, '
                     'from the building’s outline, the architects’ 1948 plan and the Mead’s visit pages.',
            'source': SOURCE, 'units': 'metres x 12, north up', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------

SHOWS = {
    'whitney': ('Fairchild Gallery', '“My beautiful, pitiful age”: The 20th century through the Thomas P. Whitney '
                'Collection (Aug 25, 2026 – Jan 3, 2027)',
                'Named on the Mead’s page for this show. The page doesn’t name the gallery; the Fairchild, the main '
                'gallery, is our guess.', SITE + '/exhibitions/2026/my-beautiful-pitiful-age'),
    'rotherwas': ('Rotherwas Room', 'The Rotherwas Room and its stained glass (always on view)',
                  'Part of the Rotherwas Room, always on view.', SITE + '/exhibitions/rotherwas-room'),
    'assyrian': ('Southwest Gallery', 'Assyrian reliefs (always on view)',
                 'The Mead says the reliefs are always on view; which room they are in is our guess.',
                 SITE + '/collection/overview/ancient'),
}
WHITNEY = 'Gift of Thomas P. Whitney (Class of 1937)'
GLASS = 'Gift of the Metropolitan Museum of Art'
C = 'commons:'      # picture from the Commons thumbnails saved on the Mac
R = 'raw:'          # picture from the Mead's own pages (archived copies)

# (show, picture, artist, title, date, medium, credit, accession)
SHOW_WORKS = [
    ('whitney', None, 'Isaak Levitan', 'The Steppe', 'late 19th century', 'Pastel on paper mounted on cardboard',
     WHITNEY, 'AC 2001.599'),
    ('whitney', None, 'Naum Gabo', 'Vertical Construction No. 2 (The Waterfall)', '1965–1966',
     'Bronze with stainless steel spring wire', WHITNEY, 'AC 2001.600'),
    ('whitney', None, 'Nicholas Roerich', 'Human Deeds', '1914',
     'Oil pastel, charcoal, and tempera on compressed board', WHITNEY, 'AC 2001.59'),
    ('whitney', 'https://commons.wikimedia.org/wiki/Special:FilePath/'
                'N.Goncharova_-_self-portrait_(c.1907,_Mead_art_museum).jpg?width=800',
     'Natalia Goncharova', 'Self-Portrait', 'ca. 1907', 'Oil on canvas mounted on board', WHITNEY, 'AC 2001.11'),
    ('whitney', None, 'Unknown icon painter (Iaroslavl’ Region, Russia)', 'Icon with the Prophet Elijah',
     'end of 16th century', 'Tempera on panel', WHITNEY, 'AC 2001.582'),
    ('whitney', None, 'Rimma Gerlovina and Valeriy Gerlovin', 'Breathe', '1990', 'Mounted chromogenic print',
     'Gift of Thomas Erben', 'AC 2022.21'),
    ('whitney', C + 'Filonov_-_flight-to-egypt-1918.jpg', 'Pavel Filonov', 'The Flight into Egypt (The Resettlers)',
     '1918', 'Oil on canvas', WHITNEY, 'AC 2001.21'),
    ('whitney', None, 'Boris Orlov', 'Small Three Headed Totem', '1989', 'Enamel on aluminum',
     'Purchase with Amherst Whitney Collection of Russian Art Fund', 'AC 2018.06'),
    ('rotherwas', C + 'Rotherwas_Room_Full_View.jpg', 'Unidentified English makers', 'Rotherwas Room', '1611',
     'Walnut paneling, oak chimneypiece', 'Bequest of Herbert L. Pratt (Class of 1895)', ''),
    ('rotherwas', C + 'Justice_and_Temperance.JPG', 'Unidentified English makers',
     'Chimneypiece: Justice and Temperance', '1611', 'Carved and painted oak',
     'Bequest of Herbert L. Pratt (Class of 1895)', ''),
    ('rotherwas', C + 'Prudence_and_Fortitude.JPG', 'Unidentified English makers',
     'Chimneypiece: Prudence and Fortitude', '1611', 'Carved and painted oak',
     'Bequest of Herbert L. Pratt (Class of 1895)', ''),
    ('rotherwas', R + 'images/exhibitions_stained-glass-rotherwas-room/AC 2018.jpg', 'Caspar Spengler',
     'Heraldic Panel of Hans Jacob Kaffman', '1595',
     'Uncolored glass, vitreous paint, red and blue pot metal glass, silver stain, blue and green enamels', GLASS,
     'AC 2018.205'),
    ('rotherwas', None, 'Unknown maker(s) after Martin Schongauer',
     'Crucifixion with the Virgin and Saint John the Evangelist', 'ca. 1500',
     'Uncolored glass with red, blue, green, and purple pot metal glass; vitreous paint; silver stain', GLASS,
     'AC 2018.234'),
    ('rotherwas', R + 'images/exhibitions_stained-glass-rotherwas-room/AC 2018_2.jpg', 'Unknown maker(s)',
     'Panel of Jacob de Waerder', '1669', 'Uncolored glass, vitreous paint, silver stain, red and blue enamels',
     GLASS, 'AC 2018.206'),
    ('rotherwas', C + 'De_Solers_family_seal.JPG', 'Unknown maker(s)', 'Stained-glass panel: De Solers family arms',
     '16th–17th century', 'Stained glass', GLASS, ''),
    ('rotherwas', C + 'De_la_Barre_family_seal.JPG', 'Unknown maker(s)',
     'Stained-glass panel: De la Barre family arms', '16th–17th century', 'Stained glass', GLASS, ''),
    ('rotherwas', C + 'Whittington_family_seal.JPG', 'Unknown maker(s)',
     'Stained-glass panel: Whittington family arms', '16th–17th century', 'Stained glass', GLASS, ''),
    ('rotherwas', C + 'Yorke_family_seal.JPG', 'Unknown maker(s)', 'Stained-glass panel: Yorke family arms',
     '16th–17th century', 'Stained glass', GLASS, ''),
    ('assyrian', R + 'images/collection_overview_ancient/ancient 2.jpg', 'Assyrian (Neo-Assyrian Empire)',
     'Relief from the palace of Ashurnasirpal II at Nimrud', 'ca. 883–859 BCE', 'Alabaster (gypsum)',
     'Acquired by Amherst College in 1855', ''),
]
CREDIT = {  # picture credits for Commons files with a named photographer
    'Rotherwas_Room_Full_View.jpg': 'Photo Stephen Petegorsky, CC BY-SA 4.0, via Wikimedia Commons',
}

# Collection Highlights pages (not known to be on view)
HIGHLIGHTS = [
    (R + 'images/collection/Sanchez_700.png', 'Juan Sánchez', 'Self-Portrait/Trying to Trace Back to Find Myself',
     '2013', ''),
    (None, 'Frans Snyders', 'Larder with a Servant', 'ca. 1635–1640', ''),
    (None, 'Jamini Roy', 'Untitled (Five Women)', 'ca. 1964–1965', ''),
    (None, 'Jonathan Lyndon Chase', 'Forehead Kiss', '2018', ''),
    (None, 'Toshio Shibata', 'Shimogo Town, Fukushima Prefecture, 1990', '1990', 'Photograph'),
    (R + 'images/collection_overview_ancient/ancient 5.jpg', 'Ancient Greek', 'Silver amphoriskos', '', 'Silver'),
]
ARTISTS = {'Малявин': 'Filipp Malyavin', 'F.Malyavin': 'Filipp Malyavin', 'V. Serov': 'Valentin Serov',
           'Petrov-Vodkin': 'Kuzma Petrov-Vodkin', 'Kuniyasu': 'Utagawa Kuniyasu', 'Unknown author': 'Unknown artist',
           'Anonymous': 'Unknown artist (Low Countries)'}
NOT_WORKS = re.compile(r'Amherst College buildings|Final Plans|Stearns Steeple|rotherwas|Rotherwas Room|family seal|'
                       r'Lower panel|Justice and|Prudence and|3x4|O-77 matte collodion print\.jpg|Portrait de Jérôme',
                       re.I)


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def year_of(date):
    m = re.search(r'(\d{3,4})\s*(BCE)?', date or '')
    if m: return -int(m[1]) if m[2] else int(m[1])
    m = re.search(r'(\d+)(?:st|nd|rd|th) century', date or '')
    return (int(m[1]) - 1) * 100 + 50 if m else None


def record_url(acc):
    """The work's record in the Five College Museums database (a link only; that site is not read here)."""
    if not acc or not acc.startswith('AC '): return None
    return 'https://museums.fivecolleges.edu/detail.php?t=objects&type=ext&id_number=' + urllib.parse.quote(acc)


def picture(key, src):
    """Save a phone-sized JPEG of a picture we already have on disk; remote URLs are kept as they are."""
    if not src: return None
    if src.startswith('http'): return src
    path = RAW / 'commons' / 'thumbs' / src[len(C):] if src.startswith(C) else RAW / src[len(R):]
    if not path.exists(): return None
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(path.read_bytes()))
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/mead/images/{key}.jpg'


def wid(acc, artist, title):
    return 'mead-' + (re.sub(r'[^\w.-]', '', acc.replace('AC ', '')) if acc else norm(artist)[:12] + '-' + norm(title)[:28])


def build_works(floors):
    rooms = {r['id']: r['name'] for r in floors['floors'][0]['rooms']}
    out = []
    for show, img, artist, title, date, medium, credit, acc in SHOW_WORKS:
        room, show_name, how, url = SHOWS[show]
        key = wid(acc, artist, title)
        fname = img[len(C):] if img and img.startswith(C) else ''
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'year': year_of(date), 'medium': medium,
             'accession': acc, 'creditLine': credit, 'gallery': room, 'galleryName': rooms[room], 'floor': '1',
             'placeNote': how, 'exhibition': show_name, 'url': record_url(acc) or url,
             'image': picture(key, img),
             'imageCredit': CREDIT.get(fname) or ('Wikimedia Commons' if (fname or 'commons' in (img or ''))
                                                   else 'Mead Art Museum, Amherst College')}
        if not a['image']: a.pop('imageCredit')
        if fname: a['commonsFile'] = fname
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r[0]: i for i, r in enumerate(ROOMS)}
    out.sort(key=lambda a: (order[a['gallery']], a.get('year') or 0))
    return {'source': 'Mead Art Museum pages (amherst.edu, read from Internet Archive copies) and Wikimedia Commons',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}


def commons_files():
    rows = []
    for f in sorted(glob.glob(str(RAW / 'commons' / 'info-*.json'))):
        for p in json.load(open(f))['query']['pages'].values():
            title = p['title'][5:]
            if NOT_WORKS.search(title): continue
            ii = (p.get('imageinfo') or [{}])[0]
            e = {k: text(str(v.get('value', ''))) for k, v in ii.get('extmetadata', {}).items()}
            name = re.sub(r'\s*label QS:.*', '', e.get('ObjectName', '')).strip()
            name = re.sub(r'^(German|French): .*? (?=[A-Z][a-z])', '', name)
            name = re.sub(r',? (?:by .*|\(\d.*\)|AC \d.*|K\d+.*|, Mead .*)$', '', name).strip() or title
            name = re.sub(r'^[A-Z][\w .-]+ - ', '', name)
            name = re.sub(r'\s*\(circa.*?date QS:.*|, attributed to .*|, c\. \d{4}$|, (?:ca\.|after) \d{4}.*$', '', name)
            name = 'Saint John the Evangelist' if 'Wtewael' in title else name.rstrip('. ')
            date = re.sub(r'\s*date QS:.*', '', e.get('DateTimeOriginal', '')).strip()
            artist = re.sub(r'\s+Unknown author.*|\s*\(.*', '', e.get('Artist', '')).strip()
            artist = ARTISTS.get(artist, artist) or ('Konstantin Korovin' if 'Korovin' in title else 'Unknown artist')
            date = re.sub(r'(\d+) th\b', r'\1th', date)
            acc = re.search(r'AC (?:P\.)?\d{4}\.\d+', title)
            rows.append({'title': name, 'artist': artist, 'date': date, 'accession': acc[0] if acc else '',
                         'image': 'https://commons.wikimedia.org/wiki/Special:FilePath/' +
                                  urllib.parse.quote(title.replace(' ', '_')) + '?width=800',
                         'url': 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(title.replace(' ', '_'))})
    return rows


def wikidata():
    q = '''SELECT ?w ?title ?creator ?date ?img ?acc WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en") }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img }
      OPTIONAL { ?w p:P217 ?s . ?s ps:P217 ?acc . ?s pq:P195 wd:%s } }''' % (MUSEUM, MUSEUM)
    f = CACHE / 'wikidata.json'
    if not f.exists():
        url = 'https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(q)
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('Wikidata did not answer')
        f.write_bytes(out)
    rows = {}
    for b in json.loads(f.read_text())['results']['bindings']:
        v = {k: x['value'] for k, x in b.items()}
        qid = v['w'].rsplit('/', 1)[1]
        r = rows.setdefault(qid, {'qid': qid, 'title': v.get('title') or '', 'artist': set(), 'date': '',
                                  'image': None, 'accession': ''})
        if v.get('creator'): r['artist'].add(v['creator'])
        if v.get('date'): r['date'] = v['date'][:4].lstrip('+')
        if v.get('img') and not r['image']: r['image'] = v['img']
        if v.get('acc', '').startswith('AC'): r['accession'] = v['acc']
    for r in rows.values():
        r['artist'] = ', '.join(sorted(r['artist'])) or 'Unknown artist'
    return [r for r in rows.values() if r['title'] and not re.fullmatch(r'Q\d+', r['title'])]


def build_guide(works):
    rows, seen = [], {}

    def key(t, a): return norm(t)[:30] + norm(a.split(',')[0].split(' ')[-1])[:8]

    def ikey(url):
        if not url or 'FilePath/' not in url and 'File:' not in url: return None
        f = re.split(r'FilePath/|File:', url)[-1].split('?')[0]
        return 'img:' + norm(urllib.parse.unquote(f))[:40]

    def add(row, acc, title, artist, extra=None):
        keys = {k for k in (acc, key(title, artist), ikey(row.get('imageUrl')), extra) if k}
        hit = next((seen[k] for k in keys if k in seen), None)
        if hit is not None:                       # same work from another source: keep its accession number
            if acc and not hit.get('accession'):
                hit['accession'] = acc
                if hit['url'].startswith('https://commons'): hit['url'] = record_url(acc) or hit['url']
            return
        r = {k: v for k, v in row.items() if v not in (None, '')}
        for k in keys: seen[k] = r
        rows.append(r)

    for a in works['artworks']:
        add({'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
             'medium': a.get('medium'), 'accession': a.get('accession'), 'url': a['url'], 'imageUrl': a.get('image'),
             'onView': True, 'gallery': a['gallery'], 'floor': '1'}, a.get('accession'), a['title'], a['artist'],
            ikey('File:' + a['commonsFile']) if a.get('commonsFile') else None)
    for img, artist, title, date, medium in HIGHLIGHTS:
        k = wid('', artist, title)
        add({'id': k, 'title': title, 'artist': artist, 'date': date, 'year': year_of(date), 'medium': medium,
             'url': SITE + '/collection', 'imageUrl': picture(k, img), 'onView': False}, '', title, artist)
    for c in commons_files():
        add({'id': wid(c['accession'], c['artist'], c['title']), 'title': c['title'], 'artist': c['artist'],
             'date': c['date'], 'year': year_of(c['date']), 'accession': c['accession'],
             'url': record_url(c['accession']) or c['url'], 'imageUrl': c['image'], 'onView': False},
            c['accession'], c['title'], c['artist'])
    for w in wikidata():
        img = w['image'].replace('http://', 'https://') + '?width=800' if w['image'] else None
        add({'id': 'mead-' + w['qid'], 'title': w['title'], 'artist': w['artist'], 'date': w['date'],
             'year': year_of(w['date']), 'accession': w['accession'],
             'url': record_url(w['accession']) or f'https://www.wikidata.org/wiki/{w["qid"]}', 'imageUrl': img,
             'onView': False}, w['accession'], w['title'], w['artist'])
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Mead Art Museum', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Mead Art Museum pages (via the Internet Archive), Wikimedia Commons and Wikidata',
            'onViewKnown': True,
            'note': 'The Mead owns more than 20,000 works; its full catalogue is the Five College Museums database. '
                    'This list is what the Mead’s own pages show (the current show, the Rotherwas Room, the Assyrian '
                    'reliefs and collection highlights) plus Mead works on Wikimedia Commons and Wikidata. '
                    'On view means shown in a current show or a permanent installation.',
            'works': rows}


def main():
    if not RAW.exists():
        raise SystemExit(f'missing {RAW}: fetch the mead-raw files first (see the docstring)')
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
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'collection list {len(guide["works"])} ({idx["museums"][MUSEUM]["pictures"]} pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
