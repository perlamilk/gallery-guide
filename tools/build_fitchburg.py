#!/usr/bin/env python3
"""Build the Fitchburg Art Museum (Fitchburg, MA) map guide (run: python3 tools/build_fitchburg.py).

    data/fitchburg/floors.json     the First, Second and Third Floors seen from above (flat 2D)
    data/fitchburg/artworks.json   the works on view that the museum publishes, in their galleries
    data/fitchburg/images/         their pictures, made smaller for phones
    data/guides/Q5455423.json      the same, for the museum page

First run tools/harvest_fitchburg.py: it reads the museum's pages, its visitor map and the FESTIVAL catalogue into
.cache/fitchburg.

The map
-------
Traced from the museum's own visitor map (VisitorMapStandard, January 2026, scale 1:400, on the Visit page): the
Harlan K. and Elsie D. Simonds Building (entrance, lobby, Community Gallery, restrooms, coat check, Ansin and Nadine
Martel Galleries downstairs; the big upstairs galleries) and the older Merriam Parkway Building, joined on the second
floor by the bridge that is the Harris Gallery. Coordinates are pixels of that map (halved in the output). The three floors are printed one
above the other, so each is moved to line up with the floor above at the elevators (the map draws the shafts).
The map is kept as the museum prints it: north is down and to the right (its compass), Elm Street and the courtyard
are between the two buildings.
The map names the rooms but not what is in them; that comes from the museum's exhibition pages, its 2025 gallery map
(which coloured the rooms by show) and the FESTIVAL catalogue ("the visitor enters through an array of masks extending
down a corridor-like gallery that opens up into the Merriam Parkway galleries"; a learning lounge between Ceremonial
Life and the galleries of Ritual and Domestic Life). Which of the two Doyle rooms holds Ritual and which Domestic Life
is our guess, and so is the room of each Kaleidoscope work: the works say so.
"""
import html
import io
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_fitchburg import CACHE, get, SITE  # noqa: E402  (cached, polite fetch)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'fitchburg'
MUSEUM = 'Q5455423'
NAME = 'Fitchburg Art Museum'
SOURCE = 'Fitchburg Art Museum: visitor map (January 2026), exhibition pages and the FESTIVAL catalogue'
CATALOG = CACHE / 'files' / 'FAM-FESTIVAL-Catalog-FINAL.pdf'
CATALOG_URL = f'{SITE}/wp-content/uploads/2026/07/FAM-FESTIVAL-Catalog-FINAL.pdf'
PRESS = CACHE / 'files' / 'Kaleidoscope_NewPressRelease.pdf'
PX_PER_M = 18.3          # the map's scale bar: 40 feet = 223 pixels
# each floor's shift onto the Second Floor's frame (elevators line up)
SHIFT = {'1': (2, -812), '2': (0, 0), '3': (3, 842)}
K = 0.5                  # half size (about 9 units a metre), like the other flat maps
ORIGIN = (700, 900)      # the Second Floor's top-left corner, so coordinates start near 0


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- First Floor ---------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
F1 = [
    ('Lobby', 'corridor', 'Lobby: main entrance and reception desk (ask here for directions; couches to rest)',
     [(1180, 1750), (1295, 1750), (1295, 2155), (1158, 2122), (1158, 2062), (1132, 2062), (1132, 1892),
      (1180, 1892)], None),
    ('Community Gallery', 'gallery', 'Community Gallery (Galería de la Comunidad): 80 feet of wall for local schools '
     'and community groups, a new show most months', rect(882, 1835, 1180, 1892), 'Community'),
    ('Restrooms', 'space', 'Restrooms (men’s and women’s, with accessible stalls), in the first-floor hallway',
     rect(995, 1750, 1148, 1835), None),
    ('Coat Check', 'space', 'Coat check (large bags and umbrellas stay here: they aren’t allowed in the galleries)',
     rect(1148, 1750, 1180, 1835), None),
    ('Ansin Gallery', 'gallery', 'The Ronald M. Ansin Gallery',
     [(883, 1892), (1132, 1892), (1132, 2060), (905, 2060), (883, 2052)], 'Ansin'),
    ('West Hall', 'corridor', 'Hall to the elevator and the Nadine Martel Gallery',
     [(727, 1730), (878, 1730), (878, 1750), (933, 1750), (933, 1835), (882, 1835), (882, 1852), (727, 1852)], None),
    ('Martel Gallery', 'gallery', 'The Nadine Martel Gallery: Discover Ancient Egypt (temporarily closed)',
     [(335, 1720), (550, 1720), (550, 1730), (727, 1730), (727, 1885), (637, 1885), (637, 1972), (335, 1972)],
     'Martel'),
    ('Courtyard', 'space', 'Courtyard on Elm Street between the two buildings (landscaped; Thurston, the big red '
     'figure, stands here)', [(1300, 1790), (1788, 1790), (1788, 2125), (1975, 2125), (1975, 2250), (1300, 2200)],
     None),
    ('Merriam Stair Hall', 'corridor', 'Merriam Parkway Building, ground floor: the stairs down from the '
     'Second Floor (the map also draws steps out to the courtyard; directions keep you inside)', rect(1788, 1910, 1867, 1983), None),
    ('Merriam Restrooms', 'space', 'Restrooms in the Merriam Parkway Building (ground floor)',
     rect(1867, 1910, 1975, 1983), None),
    ('Art Place on Elm', 'space', 'Art Place on Elm (the museum’s neighbouring building; not part of the galleries)',
     [(1975, 2125), (2068, 2125), (2068, 2080), (2165, 2150), (2165, 2392), (1975, 2392)], None),
]
F1_CLOSED = [rect(933, 1750, 995, 1835), [(727, 1852), (882, 1852), (882, 2055), (727, 2020)],
             [(905, 2062), (1158, 2062), (1158, 2120)], [(335, 1972), (637, 1972), (637, 2127), (395, 2127)],
             rect(1788, 1715, 2068, 1910), rect(1975, 1910, 2068, 1983), rect(1788, 1983, 2068, 2125),
             rect(2068, 1805, 2138, 2048)]
F1_DOORS = [('Lobby', 'Courtyard', (1295, 1985)), ('Lobby', 'Community Gallery', (1180, 1865)),
            ('Community Gallery', 'Coat Check', (1164, 1835)), ('Community Gallery', 'Restrooms', (1035, 1835)),
            ('Community Gallery', 'Ansin Gallery', (1000, 1892)), ('Lobby', 'Ansin Gallery', (1132, 1950)),
            ('Community Gallery', 'West Hall', (900, 1843)), ('West Hall', 'Martel Gallery', (727, 1755)),
            ('Merriam Stair Hall', 'Merriam Restrooms', (1867, 1946)),
            ('Courtyard', 'Art Place on Elm', (1975, 2180))]
F1_AMEN = [('entrance', 1285, 1985), ('info', 1215, 1985), ('coat', 1164, 1800), ('restroom', 1035, 1790),
           ('restroom', 1110, 1790), ('elevator', 763, 1815), ('stairs', 1270, 1800), ('stairs', 1828, 1950),
           ('restroom', 1920, 1945)]
F1_LABELS = [('Main entrance, 185 Elm Street: automatic doors, about 20 feet from the drop-off; free parking in the '
              'Elm Street lot (accessible spaces by the entrance) and the Merriam Parkway courtyard lot', 1540, 2290),
             ('Harlan K. & Elsie D. Simonds Building', 800, 2230), ('Merriam Parkway Building', 1930, 1660)]
F1_NOTES = [('Staff only', 790, 1960)]

# ---- Second Floor --------------------------------------------------------------------------------------------------
F2 = [
    ('Elevator Gallery', 'gallery', 'Elevator Gallery (by the elevator)',
     [(727, 955), (845, 955), (845, 1080), (765, 1060), (727, 1050)], 'Elevator'),
    ('Simonds Gallery', 'gallery', 'The John S. Simonds Gallery',
     [(845, 970), (1048, 970), (1048, 1050), (980, 1050), (980, 1114), (845, 1080)], 'Simonds'),
    ('Cookman Mezzanine', 'gallery', 'The Robert R. Cookman Jr. Mezzanine (stairs down to the lobby)',
     [(1048, 970), (1292, 970), (1292, 1025), (1165, 1050), (1048, 1050)], 'Mezzanine'),
    ('Center Hall', 'corridor', 'Hall between the upstairs galleries',
     [(980, 1050), (1165, 1050), (1292, 1025), (1292, 1123), (1035, 1123), (1035, 1327), (925, 1310), (975, 1113),
      (980, 1114)], None),
    ('Sinon Gallery', 'gallery', 'The Margaret Simonds Sinon Gallery', [(765, 1060), (975, 1113), (925, 1310),
                                                                           (720, 1265)], 'Sinon'),
    ('Wallace Gallery', 'gallery', 'The George R. Wallace III Gallery', rect(1035, 1123, 1330, 1285), 'Wallace'),
    ('Simonds Learning Lounge', 'space', 'Learning Lounge (Salón de Aprendizaje): hands-on art making, books and '
     'videos for families', [(1035, 1285), (1292, 1285), (1292, 1378), (1035, 1327)], None),
    ('Harris Gallery', 'gallery', 'The Zaydee D. and Mason D. Harris Gallery: the bridge to the Merriam Parkway '
     'Building (step-free)', rect(1292, 977, 1790, 1028), 'Harris'),
    ('Crocker Gallery', 'gallery', 'The Bigelow and Barbara Cushing Crocker Gallery', rect(1790, 948, 2068, 1080),
     'Crocker'),
    ('Merriam Learning Lounge', 'space', 'Learning Lounge (Salón de Aprendizaje) for FESTIVAL: touchable African art, '
     'videos of artists at work, books, a map of Africa and a mancala game', rect(1790, 1080, 2068, 1182), None),
    ('Doyle Gallery West', 'gallery', 'The Louise I. Doyle Gallery (west room)', rect(1790, 1182, 1945, 1358),
     'Doyle W'),
    ('Doyle Gallery East', 'gallery', 'The Louise I. Doyle Gallery (east room)', rect(1945, 1182, 2068, 1358),
     'Doyle E'),
    ('Merriam East Hall', 'corridor', 'Merriam Parkway Building hall: stairs and elevator',
     rect(2068, 1038, 2138, 1280), None),
]
F2_CLOSED = [[(727, 1050), (765, 1060), (720, 1265)]]
F2_DOORS = [('Elevator Gallery', 'Simonds Gallery', (845, 1010)), ('Elevator Gallery', 'Sinon Gallery', (755, 1057)),
            ('Simonds Gallery', 'Cookman Mezzanine', (1048, 1010)), ('Simonds Gallery', 'Center Hall', (1015, 1050)),
            ('Cookman Mezzanine', 'Center Hall', (1100, 1050)), ('Center Hall', 'Sinon Gallery', (950, 1215)),
            ('Center Hall', 'Wallace Gallery', (1035, 1200)), ('Center Hall', 'Simonds Learning Lounge', (1035, 1305)),
            ('Wallace Gallery', 'Simonds Learning Lounge', (1180, 1285)),
            ('Cookman Mezzanine', 'Harris Gallery', (1292, 1000)), ('Harris Gallery', 'Crocker Gallery', (1790, 1000)),
            ('Crocker Gallery', 'Merriam Learning Lounge', (1920, 1080)),
            ('Merriam Learning Lounge', 'Doyle Gallery West', (1870, 1182)),
            ('Merriam Learning Lounge', 'Doyle Gallery East', (2005, 1182)),
            ('Doyle Gallery West', 'Doyle Gallery East', (1945, 1285)),
            ('Merriam Learning Lounge', 'Merriam East Hall', (2068, 1132))]
F2_AMEN = [('elevator', 765, 1003), ('stairs', 1262, 995), ('stairs', 1825, 1150), ('stairs', 2103, 1060),
           ('elevator', 2099, 1260)]
F2_LABELS = [('Original entrance, 25 Merriam Parkway (closed) →', 2000, 1420),
             ('Harlan K. & Elsie D. Simonds Building', 1000, 1440), ('Merriam Parkway Building', 1930, 900)]
F2_NOTES = []

# ---- Third Floor (Merriam Parkway Building only) -------------------------------------------------------------------
F3 = [
    ('Rockwell Gallery', 'gallery', 'The Marjorie Doyle Rockwell Gallery', rect(1790, 95, 2065, 340), 'Rockwell'),
    ('Merriam Upper Hall', 'corridor', 'Merriam Parkway Building hall: stairs and elevator',
     rect(2065, 190, 2137, 440), None),
]
F3_CLOSED = [rect(1790, 340, 2065, 500)]
F3_DOORS = [('Rockwell Gallery', 'Merriam Upper Hall', (2065, 245))]
F3_AMEN = [('stairs', 1825, 290), ('stairs', 2102, 213), ('elevator', 2096, 418)]
F3_LABELS = [('Merriam Parkway Building, top floor', 1930, 30)]
F3_NOTES = []


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes):
    dx, dy = SHIFT[fid]

    def P(x, y): return [round((x + dx - ORIGIN[0]) * K, 1), round((y + dy - ORIGIN[1]) * K, 1)]

    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'walkScale': round(1 / (PX_PER_M * K * 0.35), 3),
            'area': area, 'rooms': rr,
            'closed': [{'poly': [P(*q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
            'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    floors = [
        floor('1', 'First Floor', 1, 'Main entrance · Lobby · Coat check · Restrooms · Community Gallery · Ansin '
              'Gallery · Nadine Martel Gallery · Courtyard', F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS, F1_NOTES),
        floor('2', 'Second Floor', 2, 'Kaleidoscope (Simonds Building) · Harris Gallery bridge · FESTIVAL (Merriam '
              'Parkway Building) · Learning Lounges', F2, F2_CLOSED, F2_DOORS, F2_AMEN, F2_LABELS, F2_NOTES),
        floor('3', 'Third Floor', 3, 'Marjorie Doyle Rockwell Gallery (Merriam Parkway Building)', F3, F3_CLOSED,
              F3_DOORS, F3_AMEN, F3_LABELS, F3_NOTES),
    ]
    floors[0]['homeView'] = ['Lobby', 'Ansin Gallery', 'Martel Gallery', 'Community Gallery']
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_fitchburg.py, traced from the Fitchburg Art Museum’s own visitor map '
                     '(January 2026, scale 1:400) and kept as the museum prints it: north is down and to the right. '
                     'The Simonds Building (entrance, lobby, galleries) and the Merriam Parkway Building are joined '
                     'on the Second Floor by the Harris Gallery bridge. What is in each room comes from the museum’s '
                     'exhibition pages, its 2025 gallery map and the FESTIVAL catalogue.',
            'source': 'Fitchburg Art Museum visitor map (January 2026, fitchburgartmuseum.org/visit)',
            'units': 'half-pixels of the museum’s map (about 9 per metre), Second Floor frame', 'defaultFloor': '1',
            'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------------

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def save_picture(key, im):
    dest = OUT / 'images' / f'{key}.jpg'
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/fitchburg/images/{key}.jpg'


def picture(key, url):
    if not url: return None
    if (OUT / 'images' / f'{key}.jpg').exists(): return f'data/fitchburg/images/{key}.jpg'
    raw = get(url, CACHE / 'img' / f'{key}.bin', delay=1.5)
    if not raw: return None
    try:
        return save_picture(key, Image.open(io.BytesIO(raw)))
    except Exception:
        (CACHE / 'img' / f'{key}.bin').unlink()
        return None


def page(slug_):
    return (CACHE / 'pages' / f'{slug_}.html').read_text(errors='replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def page_text(slug_, start, n=1200):
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page(slug_), flags=re.S)
    s = clean(re.sub(r'<[^>]+>', ' ', t))
    i = s.find(start)
    s = s[i:] if i >= 0 else s
    s = re.split(r'\s(?:HOURS Wednesday|Carousel Image|Homepage Image|Artist Talk:|Kaleidoscope exhibition webpage)', s)[0]
    if len(s) > n: s = s[:s.rfind('. ', 0, n) + 1]
    return s


# FESTIVAL: the catalogue's checklist. Sections -> rooms (Masquerade is the Harris Gallery bridge, per the catalogue;
# Ceremonial Life is the first Merriam room; the Ritual / Domestic split of the two Doyle rooms is our guess).
SECTIONS = [(1, 'Masquerade', 'Harris Gallery', False), (44, 'Ceremonial Life', 'Crocker Gallery', True),
            (90, 'Ritual Life', 'Doyle Gallery West', True), (147, 'Domestic Life', 'Doyle Gallery East', True)]
FEST_DATES = 'April 3, 2025 – December 13, 2026'
FEST_URL = f'{SITE}/festival-a-celebration-of-african-art/'
CREDIT = re.compile(r'^(Gift|Museum purchase|Sinon|General Collection|Bequest|Purchase|Promised|Doyle|Director|'
                    r'Transfer|Lent|Loan|On loan|Anonymous|Collection of|Fitchburg Art Museum|Partial gift)', re.I)
ACC = re.compile(r'\b((?:19|20)\d{2}\.\d+(?:\.\d+)?(?:\s?[a-z](?:-[a-z])?\b)?)')
DATEISH = re.compile(r'(century|\b1[0-9]{3}\b|\b20[0-2][0-9]\b|circa|c\. ?\d|before|undated|BCE|CE\b|n\.d\.)', re.I)
LIG = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}


def cell_lines(page_, box):
    """Lines in a checklist cell as (regular text, italic text) runs."""
    c = page_.crop(box).dedupe_chars()
    out = []
    for ln in c.extract_text_lines(return_chars=True):
        runs = []
        for ch in ln['chars']:
            it = 'It' in ch['fontname'] or 'Italic' in ch['fontname']
            t = LIG.get(ch['text'], ch['text'])
            if runs and runs[-1][0] == it: runs[-1][1] += t
            else: runs.append([it, t])
        # pdfplumber drops spaces between chars; rebuild from the line text instead when possible
        out.append({'text': clean(ln['text']), 'runs': runs, 'top': ln['top']})
    return out


def split_runs(line):
    """Map the italic runs back onto the line's spaced text."""
    text, pos, parts = line['text'], 0, []
    for it, t in line['runs']:
        core = t.replace(' ', '')
        j, k, n = pos, pos, 0
        while k < len(text) and n < len(core):
            if text[k] != ' ': n += 1
            k += 1
        parts.append((it, text[j:k]))
        pos = k
    if pos < len(text) and parts: parts[-1] = (parts[-1][0], parts[-1][1] + text[pos:])
    return [(it, s) for it, s in parts if s.strip()]


def parse_cell(lines):
    lines = [l for l in lines if not re.match(r'^Object\s+\d+$', l['text'])]
    artist, title, rest, seen_it = [], [], [], False
    for l in lines:
        tail = []
        for it, s in split_runs(l):
            if it:
                title.append(s.strip())
                seen_it = True
            elif not seen_it:
                artist.append(s.strip())
            else:
                tail.append(s.strip())
        if tail: rest.append(' '.join(tail))
    # the title's line may end ", 2013" (a date after the italic title)
    date = ''
    if rest and rest[0].startswith(','):
        date = rest.pop(0).lstrip(', ').strip()
    elif rest and DATEISH.search(rest[0]) and not CREDIT.match(rest[0]):
        date = rest.pop(0)
    i = next((k for k, r in enumerate(rest) if CREDIT.match(r) or re.search(r'\bFund\b', r) or ACC.search(r)),
             len(rest))
    medium = ' '.join(rest[:i]).rstrip('.')
    j = next((k for k in range(i, len(rest)) if ACC.search(rest[k])), None)
    credit = ' '.join(rest[i:(j + 1) if j is not None else len(rest)])
    prov = ' '.join(rest[(j + 1):]) if j is not None else ''
    acc = ACC.findall(credit)
    a = clean(' '.join(artist)).replace(' ,', ',')
    return {'artist': a, 'title': clean(' '.join(title)).rstrip(','), 'date': date, 'medium': medium,
            'credit': credit, 'accession': acc[-1] if acc else None, 'provenance': prov}


# Checklist entries the parser above reads wrongly (no italic title, a broken line, an odd accession number)
FIX = {
    18: {'artist': 'Bidjogo Artist, Bissagos Islands, Guinea Bissau', 'title': 'Bull Mask (dugn’be)',
         'date': 'Late 19th to early 20th century', 'medium': 'Wood, horns, enamel paint, fiber twine',
         'credit': 'Gift of Lillian Montalto Bohlen, 2023.323', 'accession': '2023.323',
         'provenance': 'Purchased from Jeremiah Cole, Atlanta, GA, 2002. Cole was the son of African art dealer '
                       'Talibi Kaba (Guinea).'},
    90: {'accession': '2016.54'},
    93: {'accession': 'T.1.2021', 'medium': 'Terra cotta'},
    97: {'title': 'Processional Cross (qäqwami mäsqäl)', 'date': 'Late 19th to early 20th century',
         'medium': 'Cast copper alloy with high silver content'},
    200: {'medium': 'Plastic and glass beads, twine, cowry shells, colonial era coins',
          'credit': 'Gift of Simon Gregory and Family'},
}


def festival():
    import pdfplumber
    pdf = pdfplumber.open(str(CATALOG))
    rows = []
    for pi in range(50, 78):                 # the checklist spreads (catalogue pages 96–153)
        pg = pdf.pages[pi]
        for col in range(4):
            for row in range(2):
                cx, cy = 22 + col * 396, (60, 322)[row]
                imgs = [im for im in pg.images if cx - 15 <= im['x0'] < cx + 150 and cy - 5 <= im['top'] < cy + 60
                        and im['x1'] - im['x0'] < 400]
                x0 = (imgs[0]['x1'] + 4) if imgs else cx + 150
                lines = cell_lines(pg, (x0, cy, min(pg.width, cx + 394), cy + 262))
                head = next((l for l in lines if re.match(r'^Object\s+\d+$', l['text'])), None)
                if not head: continue
                n = int(head['text'].split()[1])
                if pi == 77 and col == 0 and row == 0 and n == 210: n = 211      # the catalogue numbers it 210 twice
                lines = [l for l in lines if l['top'] > head['top']]
                p = parse_cell(lines)
                p.update(FIX.get(n, {}))
                p.update(n=n, img=(imgs[0]['x0'], imgs[0]['top'], imgs[0]['x1'], imgs[0]['bottom']) if imgs else None,
                         page=pi)
                rows.append(p)
    rows.sort(key=lambda r: r['n'])
    works = []
    for r in rows:
        sec = [s for s in SECTIONS if s[0] <= r['n']][-1]
        key = f"fam-{slug(r['accession'] or 'object-' + str(r['n']))}"
        img = None
        if r['img']:
            dest = OUT / 'images' / f'{key}.jpg'
            if dest.exists():
                img = f'data/fitchburg/images/{key}.jpg'
            else:
                pg = pdf.pages[r['page']]
                x0, t, x1, b = r['img']
                box = (max(0, x0), max(0, t), min(pg.width, x1), min(pg.height, b))
                img = save_picture(key, pg.crop(box).to_image(resolution=300).original)
        artist = re.sub(r'\s*,\s*', ', ', r['artist']).strip(', ')
        culture = re.match(r'^(.*?)\s+(?:Artist|Blacksmith|bronze caster|Bronze Caster|Potter|Weaver|Carver)s?\b',
                           artist)
        desc = ', '.join(x for x in [r['title'], r['date'], r['medium']] if x) + '. ' + r['credit']
        if r['provenance']: desc += ' ' + r['provenance']
        desc += f' FESTIVAL: A Celebration of African Art, object {r["n"]} ({sec[1]}).'
        works.append({'id': key, 'title': r['title'] or f'Object {r["n"]}', 'artist': artist, 'date': r['date'],
                      'medium': r['medium'], 'accession': r['accession'], 'culture': culture.group(1) if culture else None,
                      'type': sec[1], 'description': desc.strip(), 'url': FEST_URL, 'image': img,
                      'imageCredit': 'Fitchburg Art Museum, FESTIVAL catalogue (photo Sarah Harper)' if img else None,
                      '_room': sec[2], '_guess': sec[3], '_n': r['n']})
    return works


# Kaleidoscope: the works the museum's press release names (with its pictures)
KALEIDO = [
    ('Eleanor Norcross', 'My Studio', '1891', 'Oil on canvas', 'Norcross Collection, 1942.1', 'kimg-1'),
    ('Ansel Adams', 'Cape Cod', '', 'Gelatin silver print', 'Gift of Gale Simonds Hurd and William B. Hurd Jr., in '
     'memory of their mother Janet Simonds Short, 1999.5', 'kimg-2'),
    ('Anna Hyatt Huntington', 'Yawning Tiger', '1917', 'Bronze', 'Doyle Collection Fund and the Director’s Fund, '
     '2009.12', 'kimg-3'),
    ('Georgia O’Keeffe', 'Untitled (Pink Camellia)', '1935', 'Pastel on paper', 'Gift of Margaret Simonds Sinon, '
     '1992.1', 'kimg-4'),
    ('Greg Girard', 'Six Hundred Things (Pinghu Lu)', '2005', 'Chromogenic print', 'Gift of Dr. Anthony Terrana, '
     '2018.72', 'kimg-5'),
]
KALEIDO_URL = f'{SITE}/kaleidoscope/'
KALEIDO_DATES = 'February 21, 2026 – July 3, 2027'
KALEIDO_NOTE = ('Kaleidoscope fills the big upstairs galleries of the Simonds Building, hung salon-style; the museum '
                'doesn’t say which room each work is in, so the room is our guess.')


def press_images():
    """The pictures embedded in the Kaleidoscope press release, in page order (0 is the banner)."""
    from pypdf import PdfReader
    out = []
    for pg in PdfReader(str(PRESS)).pages:
        for im in pg.images:
            out.append(im)
    return out


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', []) and not k.startswith('_')})

    def show(key, title, dates, slug_, start, img_url, room, guessed, note, temporary=True):
        a = {'id': key, 'title': title, 'artist': 'Exhibition', 'date': dates, 'url': f'{SITE}/{slug_}/',
             'description': page_text(slug_, start), 'image': picture(key, img_url)}
        if temporary: a['temporary'] = True
        if a['image']: a['imageCredit'] = 'Fitchburg Art Museum (fitchburgartmuseum.org)'
        add(a, room, guessed, note)

    up = f'{SITE}/wp-content/uploads'
    # First Floor
    show('fam-show-heirlooms', 'Elisa H. Hamilton: Heirlooms', 'September 26, 2026 – September 19, 2027',
         'elisa-h-hamilton-heirlooms', 'Heirlooms presents', f'{up}/2026/07/MendingLines_EHH-scaled.jpg',
         'Ansin Gallery', True, 'A show on view now; the museum doesn’t say which gallery, so this room (the one its '
         '2025 map gives to single-artist shows) is our guess.')
    for t, f in [('Mending Lines', '2026/07/MendingLines_EHH-scaled.jpg'),
                 ('Layered Lives', '2026/10/LayeredLives_EHH-scaled.jpg')]:
        key = f'fam-hamilton-{slug(t)}'
        a = {'id': key, 'title': t, 'artist': 'Elisa H. Hamilton', 'date': '2026',
             'medium': 'Acrylic, gouache, black gesso and oil pastel on paper', 'description': f'Elisa Hamilton, {t}, '
             '2026, acrylic, gouache, black gesso, and oil pastel on paper. Courtesy of the artist. In Heirlooms: '
             'abstract works on paper drawn from a quilt made by the artist’s great-grandmother.',
             'url': f'{SITE}/elisa-h-hamilton-heirlooms/', 'loan': True, 'image': picture(key, f'{up}/{f}')}
        if a['image']: a['imageCredit'] = 'Fitchburg Art Museum (fitchburgartmuseum.org)'
        add(a, 'Ansin Gallery', True, 'In Heirlooms (to September 19, 2027); the gallery is our guess.')
    a = {'id': 'fam-show-community', 'title': 'Community Gallery: Creative Discoveries (November 2026)',
         'artist': 'Exhibition', 'date': 'November 2026; December 2026: Spanish American Center',
         'url': f'{SITE}/community-gallery/', 'temporary': True,
         'description': 'The Community Gallery is an 80-foot space for local schools, non-profits and creative groups '
                        'from Fitchburg, Leominster and Central Massachusetts, with a new show most months. November '
                        '2026: the Creative Discoveries program at FAM. December 2026: the Spanish American Center.'}
    add(a, 'Community Gallery', False, 'In the Community Gallery, the hallway past the lobby.')
    show('fam-show-egypt', 'Discover Ancient Egypt (temporarily closed)', 'Paused', 'discover-ancient-egypt',
         'Designed to appeal', f'{up}/2019/01/DiscoverAncientEgypt-1.jpeg', 'Martel Gallery', True,
         'The museum’s 2025 map puts Discover Ancient Egypt in this wing; it is temporarily closed.', temporary=False)
    a = {'id': 'fam-kornfeld-thurston', 'title': 'Thurston', 'artist': 'Douglas Kornfeld', 'date': '2015',
         'medium': 'Painted steel', 'url': f'{SITE}/thurston/',
         'description': 'A giant, bright red steel figure commissioned by FAM in 2015 to tower over the museum’s '
                        'courtyard on Elm Street. Students of Montachusett Regional Vocational Technical School built '
                        'and painted it under the artist’s supervision; a schools essay contest gave it its name.',
         'image': picture('fam-kornfeld-thurston', f'{up}/2021/05/50613701561_680c6794aa_k.jpg')}
    if a['image']: a['imageCredit'] = 'Fitchburg Art Museum (fitchburgartmuseum.org)'
    add(a, 'Courtyard', False, 'Outdoors, in the courtyard on Elm Street.')
    a = {'id': 'fam-sosa-bodega', 'title': 'La bodega de mis sueños (The bodega of my dreams)',
         'artist': 'Gabriel Sosa', 'date': '2023', 'medium': 'Mixed-media installation', 'url': f'{SITE}/la-bodega-de-mis-suenos/',
         'description': page_text('la-bodega-de-mis-suenos', 'In this inaugural', 900),
         'image': picture('fam-sosa-bodega', f'{up}/2023/08/20230717_AM5662-scaled.jpg')}
    if a['image']: a['imageCredit'] = 'Fitchburg Art Museum (photo Aníbal Martel)'
    add(a, 'Courtyard', True, 'Outdoors, on the museum’s façade where an old storefront was; the museum doesn’t say '
        'which wall, so look around the outside of the buildings.')
    # Second Floor: Kaleidoscope
    show('fam-show-kaleidoscope', 'Kaleidoscope: 100 Years of Collecting for Our Community', KALEIDO_DATES,
         'kaleidoscope', 'Kaleidoscope is the second', f'{up}/2026/02/Artboard-1-1.jpg', 'Sinon Gallery', True,
         KALEIDO_NOTE)
    pics = press_images()
    for (artist, title, date, medium, credit, ref) in KALEIDO:
        key = f"fam-{slug(ACC.findall(credit)[-1])}"
        img = None
        if (OUT / 'images' / f'{key}.jpg').exists(): img = f'data/fitchburg/images/{key}.jpg'
        else:
            n = int(ref.split('-')[1])
            try: img = save_picture(key, pics[n].image)
            except Exception as e: print('no picture for', title, e)
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'medium': medium,
             'accession': ACC.findall(credit)[-1], 'url': KALEIDO_URL, 'image': img,
             'description': f'{artist}, {title}{", " + date if date else ""}, {medium.lower()}. {credit}. In '
                            f'Kaleidoscope ({KALEIDO_DATES}), over 500 works from the collection hung salon-style.'}
        if img: a['imageCredit'] = 'Fitchburg Art Museum (Kaleidoscope press release)'
        room = 'Simonds Gallery' if artist == 'Eleanor Norcross' else 'Sinon Gallery'
        add(a, room, True, KALEIDO_NOTE + (' The show opens with the founder Eleanor Norcross’s own art and '
                                           'collection.' if artist == 'Eleanor Norcross' else ''))
    # Second Floor: FESTIVAL
    show('fam-show-festival', 'FESTIVAL: A Celebration of African Art', FEST_DATES,
         'festival-a-celebration-of-african-art', 'FESTIVAL: A Celebration of African Art at the Fitchburg Art Museum is',
         f'{up}/2025/02/Festival_Yoruba-Artist_Beaded-Crown.jpg', 'Harris Gallery', False,
         'FESTIVAL begins with the masks along the Harris Gallery bridge and fills the Merriam Parkway Building’s '
         'galleries (to December 13, 2026).')
    for w in festival():
        if w['_room'] == 'Harris Gallery':
            note = ('In FESTIVAL (to December 13, 2026): Masquerade, the array of masks along the Harris Gallery '
                    'bridge into the Merriam Parkway Building.')
        elif w['_room'] == 'Crocker Gallery':
            note = ('In FESTIVAL (to December 13, 2026): Ceremonial Life, in the first Merriam Parkway room past the '
                    'bridge (the room is our reading of the catalogue).')
        else:
            note = (f'In FESTIVAL (to December 13, 2026): {w["type"]}, in the Doyle Gallery past the Learning '
                    'Lounge; which of its two rooms is our guess.')
        add(w, w['_room'], w['_guess'], note)
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['artist'] != 'Exhibition'))
    return {'source': SOURCE, 'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False,
            'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'],
                     'date': a.get('date'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': True, 'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'), 'source': SOURCE, 'onViewKnown': True,
            'note': 'The Fitchburg Art Museum has over 7,000 works and no online catalogue yet (it is taking a full '
                    'inventory). Listed here is what it publishes about the shows on view now: every object in '
                    'FESTIVAL: A Celebration of African Art (from its catalogue, until December 13, 2026), the works '
                    'its Kaleidoscope press release names (500+ works upstairs to July 2027), Heirlooms, and the '
                    'public art outside.',
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
    print(f'{works["count"]} works on the map ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
