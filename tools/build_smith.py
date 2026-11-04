#!/usr/bin/env python3
"""Build the Smith College Museum of Art (SCMA, Northampton) map guide (run: python3 tools/build_smith.py).

    data/smith/floors.json       the four floors seen from above (a flat 2D plan)
    data/smith/artworks.json     the works known to be in the building now, in the gallery where they are shown
    data/smith/images/           their pictures, made smaller for phones
    data/guides/Q14715853.json   every SCMA work we know of, for the museum page

The map is traced from the museum's own map (scma.smith.edu/sites/default/files/SCMA_General_Map_for_Website_0.jpg,
linked as "map of the museum" on scma.smith.edu/visit). Coordinates below are pixels of that image shrunk to
850 x 1400 (a third of its size); floors are lined up on the elevator. Red hatched rooms on that map (Mellon
Classroom, two rooms on the 2nd floor) are not open to visitors. The museum names only some rooms, so the
2nd floor's east room is left unnamed. There is no café in the museum.

The works: SCMA owns more than 29,000 works, listed in the Five College Museums database
(museums.fivecolleges.edu). That site's robots.txt shuts out AI crawlers, so it is not read here. Instead:
  - the museum's own pages for each current show (scma.smith.edu/art/on-view/current), which picture works and,
    for most shows, say which gallery the show is in;
  - the museum's Highlights pages (scma.smith.edu/art/highlights), with links to each work's record;
  - Wikidata (CC0): works whose collection is SCMA, with Wikimedia Commons pictures.
Works pictured on a show's page go in that show's gallery. Highlights and Wikidata works are listed on the museum
page as part of the collection, not placed on the map, because the museum doesn't say whether they are on view.
"""
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
OUT = ROOT / 'data' / 'smith'
CACHE = ROOT / '.cache' / 'smith'
MUSEUM = 'Q14715853'
SITE = 'https://scma.smith.edu'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'SCMA museum map (scma.smith.edu/visit, “map of the museum”)'
K = 1


def get(url, name):
    """Read a page once, politely, and keep it in .cache/smith."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1)
        if not out: raise SystemExit(f'could not read {url}')
        f.write_bytes(out)
    return f.read_text(errors='replace')


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# elevator on each floor (map pixels); floors are moved so these line up with the 1st floor's
ELEV = {'LL': (551, 1290), '1': (560, 940), '2': (563, 622), '3': (577, 322)}
STAIRS = {'LL': (425, 1250), '1': (440, 900), '2': (450, 580), '3': (466, 284)}

# (id, kind, name, poly in map pixels, label for galleries)
ROOMS = {
    'LL': [
        ('Art After 1950', 'gallery', 'Art After 1950', rect(424, 1060, 757, 1186), 'Art After 1950'),
        ('Teaching Gallery', 'gallery', 'Teaching Gallery', rect(332, 1060, 422, 1186), 'Teaching Gallery'),
        ('Asian Art Gallery', 'gallery', 'Asian Art Gallery',
         [[666, 1188], [757, 1188], [757, 1145], [800, 1145], [800, 1318], [666, 1318]], 'Asian Art'),
        ('LL-hall', 'corridor', 'Talk Back Space and stair hall', rect(386, 1188, 532, 1270), None),
        ('Video & New Media Gallery', 'gallery', 'Video & New Media Gallery', rect(386, 1272, 507, 1340), 'New Media'),
        ('LL-restrooms', 'corridor', 'Artist-designed restrooms · elevator',
         [[533, 1188], [664, 1188], [664, 1318], [533, 1318]], None),
    ],
    '1': [
        ('Special Exhibitions', 'gallery', 'Special Exhibitions', rect(322, 718, 622, 838), 'Special Exhibitions'),
        ('Mellon Classroom', 'closed', 'Mellon Classroom (classes only)',
         [[212, 717], [320, 717], [320, 900], [283, 900], [283, 807], [212, 807]], None),
        ('Overlook', 'space', 'Open to the Lower Level: look down into the galleries below', rect(624, 718, 748, 838), None),
        ('1-hall', 'corridor', 'Stair hall', rect(322, 840, 578, 918), None),
        ('1-elevator', 'corridor', 'Elevator', rect(543, 920, 578, 966), None),
        ('Lobby', 'corridor', 'Lobby · information desk',
         [[580, 840], [748, 840], [748, 966], [676, 966], [676, 904], [580, 904]], None),
        ('Gift Shop', 'space', 'SCMA Shop', rect(580, 906, 674, 966), None),
        ('Coatroom', 'corridor', 'Coatroom · lockers · strollers · wheelchairs', rect(750, 786, 800, 904), None),
        ('Vestibule', 'corridor', 'Entrance vestibule', rect(750, 906, 800, 966), None),
    ],
    '2': [
        ('Art Before 1800', 'gallery', 'Art Before 1800 · Ancient World Gallery',
         [[454, 410], [482, 410], [482, 398], [673, 398], [673, 410], [748, 410], [748, 473], [797, 473], [797, 548],
          [682, 548], [682, 524], [454, 524]], 'Art Before 1800'),
        ('Nixon Gallery', 'gallery', 'Nixon Gallery: Works on Paper', rect(335, 410, 452, 522), 'Nixon Gallery'),
        ('East room', 'gallery', 'Gallery (east room)', rect(684, 550, 797, 645), 'Gallery'),
        ('Cunningham Center', 'space', 'Cunningham Center for the Study of Prints, Drawings and Photographs '
                                       '(by appointment)', rect(105, 410, 238, 566), None),
        ('2-closed north', 'closed', 'Not open to visitors', rect(240, 410, 333, 566), None),
        ('2-closed south', 'closed', 'Not open to visitors', rect(212, 590, 338, 640), None),
        ('2-hall', 'corridor', 'Stair hall',
         [[212, 568], [335, 568], [335, 526], [545, 526], [545, 600], [340, 600], [340, 588], [212, 588]], None),
        ('2-restrooms', 'corridor', 'Restrooms · baby changing · elevator', rect(547, 526, 680, 644), None),
    ],
    '3': [
        ('Worlds in Process', 'gallery', 'Worlds in Process: Art from the SCMA Collection',
         [[137, 113], [321, 113], [321, 61], [399, 61], [399, 113], [498, 113], [498, 98], [681, 98], [681, 113],
          [753, 113], [753, 178], [799, 178], [799, 289], [753, 289], [753, 226], [137, 226]], 'Worlds in Process'),
        ('3-hall', 'corridor', 'Stair hall',
         [[360, 228], [560, 228], [560, 252], [595, 252], [595, 345], [560, 345], [560, 298], [360, 298]], None),
    ],
}

DOORS = {
    'LL': [('Teaching Gallery', 'Art After 1950', (423, 1115)), ('LL-hall', 'Teaching Gallery', (410, 1187)),
           ('LL-hall', 'Art After 1950', (515, 1187)), ('LL-hall', 'Video & New Media Gallery', (440, 1271)),
           ('LL-hall', 'LL-restrooms', (532, 1262)), ('Art After 1950', 'Asian Art Gallery', (712, 1187))],
    '1': [('1-hall', 'Special Exhibitions', (420, 839)), ('1-hall', '1-elevator', (560, 919)),
          ('1-hall', 'Lobby', (579, 870)), ('Lobby', 'Gift Shop', (630, 905)), ('Lobby', 'Overlook', (690, 839)), ('Lobby', 'Coatroom', (749, 870)),
          ('Lobby', 'Vestibule', (749, 940))],
    '2': [('2-hall', 'Nixon Gallery', (400, 525)), ('2-hall', 'Art Before 1800', (520, 525)),
          ('Nixon Gallery', 'Art Before 1800', (453, 505)), ('2-hall', '2-restrooms', (546, 560)),
          ('2-hall', 'Cunningham Center', (225, 567)), ('Art Before 1800', 'East room', (740, 549))],
    '3': [('3-hall', 'Worlds in Process', (370, 227)), ('3-hall', 'Worlds in Process', (540, 227))],
}

AMENITIES = {
    'LL': [('elevator', *ELEV['LL']), ('stairs', *STAIRS['LL']), ('restroom', 648, 1240), ('restroom', 648, 1300)],
    '1': [('entrance', 780, 968), ('elevator', *ELEV['1']), ('stairs', *STAIRS['1']), ('info', 713, 920),
          ('shop', 629, 925), ('coat', 775, 815)],
    '2': [('elevator', *ELEV['2']), ('stairs', *STAIRS['2']), ('restroom', 614, 555), ('restroom', 614, 622),
          ('nursing', 643, 555), ('nursing', 643, 622)],
    '3': [('elevator', *ELEV['3']), ('stairs', *STAIRS['3'])],
}
LABELS = {
    'LL': [('Accessible restrooms on this floor and the 2nd', 'note', 600, 1355)],
    '1': [('Mellon Classroom', 'note', 252, 760), ('Entrance · 20 Elm Street at Bedford Terrace (ramp and power door)', 'note', 680, 990),
          ('No café in the museum', 'note', 420, 990)],
    '2': [],
    '3': [],
}
FLOORS = [
    ('LL', 'Lower Level', 'Art After 1950 · Asian Art Gallery · Video & New Media Gallery · Teaching Gallery · '
                          'Artist-designed restrooms', 0),
    ('1', '1st Floor', 'Entrance · Lobby · SCMA Shop · Coatroom and lockers · Special Exhibitions', 1),
    ('2', '2nd Floor', 'Art Before 1800 · Ancient World · Nixon Gallery: Works on Paper · Cunningham Center · '
                       'Restrooms and baby changing', 2),
    ('3', '3rd Floor', 'Worlds in Process: Art from the SCMA Collection · Painting Nature', 3),
]


def pt(x, y):
    return [round(x * K, 1), round(y * K, 1)]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms, closed = [], []
        for rid, kind, name, poly, short in ROOMS[fid]:
            if kind == 'closed':                    # red hatched on the museum's map: not open to visitors
                closed.append({'poly': [pt(x, y) for x, y in poly]})
                continue
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(x, y) for x, y in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 8, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        ex, ey = ELEV[fid]
        fx, fy = ELEV['1']
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order,
                       'transform': [1, round((fx - ex) * K, 1), round((fy - ey) * K, 1)],
                       'rooms': rooms, 'closed': closed,
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_smith.py, traced from the Smith College Museum of Art’s own museum map. '
                     'Shows change during the year.',
            'source': SOURCE, 'units': 'pixels of the museum map at 850 x 1400', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': floors}


# ---- works ----------------------------------------------------------------------------------------------------

# show page -> (room, show name, how we know the room)
SHOWS = {
    'composingcolor': ('Special Exhibitions', 'Composing Color: Paintings by Alma Thomas from the Smithsonian American '
                       'Art Museum (Jul 24, 2026 – Jan 10, 2027)',
                       'A loan exhibition from the Smithsonian; SCMA’s page doesn’t name the gallery, but loan shows '
                       'are in Special Exhibitions on the 1st floor.'),
    'CocoFuscoTheEmptyPlaza': ('Video & New Media Gallery', 'Coco Fusco: The Empty Plaza/La Plaza Vacía '
                               '(Aug 31, 2026 – Feb 26, 2027)', 'SCMA’s page: “On view in the New Media Gallery on the '
                                                                 'Lower Level.”'),
    'craftingworlds': ('Asian Art Gallery', 'Crafting Worlds: Japanese Decorative Arts from the 18th through 21st '
                       'Centuries (Oct 17, 2025 – Feb 7, 2027)', 'SCMA’s programs for this show are on the Lower '
                                                                  'Level, home of the Asian Art Gallery.'),
    'beyondthefloatingworld': ('Nixon Gallery', 'Beyond the Floating World: Viewing Japanese Prints with Smith Faculty '
                               '(Oct 9, 2026 – Apr 4, 2027)',
                               'SCMA’s page doesn’t name the gallery. 35 prints: probably the Nixon Gallery for works '
                               'on paper, possibly the Asian Art Gallery.'),
    'paintingnature': ('Worlds in Process', 'Painting Nature: 19th-century American and French Landscapes (ongoing)',
                       'SCMA’s page: “Located on the Third Floor in the Ketcham Gallery as part of Worlds in '
                       'Process.”'),
    'worlds-process-art-scma-collection': ('Worlds in Process', 'Worlds in Process: Art from the SCMA Collection '
                                           '(ongoing)', 'SCMA’s page for the 3rd-floor collection installation '
                                                        'pictures this work. Works rotate, so it may have moved.'),
}
PATH = {'composingcolor': '/composingcolor', 'beyondthefloatingworld': '/beyondthefloatingworld'}

# Works pictured on each show page, as captioned there: (show, image, artist, title, date, medium, credit, accession)
SHOW_WORKS = [
    ('composingcolor', '2026-06/1978.40.3%20%282%29_0.png', 'Alma Thomas', 'The Eclipse', '1970',
     'Acrylic on canvas', 'Smithsonian American Art Museum, Gift of the artist', 'SAAM 1978.40.3'),
    ('composingcolor', '2026-05/2_Alma%20Thomas%20Light%20Blue%20Nursery.jpeg', 'Alma Thomas', 'Light Blue Nursery',
     '1966', 'Acrylic on canvas', 'Smithsonian American Art Museum, Gift of the artist', 'SAAM 1970.324'),
    ('composingcolor', '2026-05/3_Alma%20Thomas%20Celestial%20Fantasy.jpeg', 'Alma Thomas', 'Celestial–Fantasy',
     '1973', 'Acrylic on canvas', 'Smithsonian American Art Museum, Bequest of the artist', 'SAAM 1980.36.11'),
    ('composingcolor', '2026-05/4_Alma%20Thomas_Delightful%20Song%20by%20Red%20Dahlia.jpeg', 'Alma Thomas',
     'Delightful Song by Red Dahlia', '1976', 'Acrylic on canvas',
     'Smithsonian American Art Museum, Bequest of the artist', 'SAAM 1980.36.4'),
    ('composingcolor', '2026-05/5Alma%20Thomas_White%20Roses%20Sing%20and%20Sing_0.jpeg', 'Alma Thomas',
     'White Roses Sing and Sing', '1976', 'Acrylic on canvas',
     'Smithsonian American Art Museum, Bequest of the artist', 'SAAM 1980.36.3'),
    ('composingcolor', '2026-05/6_Alma%20Thomas%20Red%20Abstraction%202.jpeg', 'Alma Thomas', 'Red Abstraction',
     '1960', 'Oil on canvas', 'Smithsonian American Art Museum, Gift of the artist', 'SAAM 1978.40.1'),
    # SCMA's own Alma Thomas hangs with the Smithsonian loans for this show (press release, July 2026)
    ('composingcolor', '2023-10/Thomas_WIP_Slideshow%20copy.jpg', 'Alma Thomas', 'Morning in the Bowl of Night', '1973',
     'Acrylic on canvas', 'Purchased with the Hillyer Tryon Mather Fund; the Madeleine H. Russell, class of 1937, '
     'Fund; the Kathleen Compton Sherrerd, class of 1954, Acquisition Fund for American Art; and the Dorothy C. '
     'Miller, class of 1925, Fund', 'SC 2018.23'),
    ('CocoFuscoTheEmptyPlaza', '2026-08/Coco%20Fusco_0.png', 'Coco Fusco', 'The Empty Plaza / La Plaza Vacía', '2012',
     'Single-channel video', 'Purchased with funds from the Contemporary Associates, Smith College Museum of Art', ''),
    ('craftingworlds', '2025-09/peaches.png', 'Unidentified artists (Japanese, Edo period)', 'Dish with peaches design',
     '18th century', 'Porcelain with underglaze blue and celadon glaze (Nabeshima type)',
     'Gift of John C. Weber in honor of Julia Meech, class of 1963', ''),
    ('craftingworlds', '2025-09/whirlpool.png', 'Monden Kōgyoku', 'Undulation', '2006', 'Timber bamboo',
     'Gift of Valerie and Charles Diker (Valerie Tishman, class of 1959)', ''),
    ('craftingworlds', '2025-09/kyoto.png', 'Tsuboi Asuka', 'Women of Kyoto', '2006',
     'Stoneware with clay slip and enamel', 'Anonymous gift of a member of the Smith class of 1965', ''),
    ('craftingworlds', '2025-09/shell-vessel.png', 'Koike Shōko', 'Shell Vessel', '1999', 'Glazed stoneware',
     'Anonymous gift of a member of the Smith class of 1965', ''),
    ('craftingworlds', '2026-06/SCMA%20Peaches%20plate%20for%20website.png', 'Unknown Japanese artist',
     'Dish with design of peaches and bellflowers, Nabeshima ware', '18th century',
     'Porcelain with blue underglaze and celadon glaze', 'Gift of John C. Weber in honor of Julia Meech, class of 1963',
     ''),
    ('beyondthefloatingworld', '2026-08/Seated%20person%20in%20Kimono%20.png', 'Sekino Jun’ichirō', 'Bin-gata', '1975',
     'Woodblock print in eleven colors on cream paper', 'Gift of Lucio and Joan Noto', ''),
    ('beyondthefloatingworld', '2026-09/Three%20People%20on%20a%20Train.png', 'Koizumi Kishio',
     'Subway in Spring (Haru no chikatetsu), from 100 Views of Great Tokyo in the Shōwa Era', '',
     'Woodcut printed in color on cream paper', 'Gift of Julia Meech, class of 1963, in honor of Samuel C. Morse', ''),
    ('beyondthefloatingworld', '2026-09/Triptych%202.png', 'Utagawa Kuniyoshi',
     'Geisha by the Sumida River, from Popular Customs of the Present Age (Tōsei fūzoku konomi)', '1830s',
     'Woodcut printed in color on paper', 'The Margaret Rankin Barker – Isaac Ogden Rankin Collection. Gift of Mr. and '
     'Mrs. James Barker (Margaret Clark Rankin, class of 1908)', ''),
    ('beyondthefloatingworld', '2026-08/Men%20on%20Boat%20for%20website.png', 'Ogata Gessan',
     'Our Army Crosses the Yalu River on the Pontoon Bridge and Drives Back the Enemy Forces to Finally Occupy '
     'Jiuliancheng', '1904', 'Woodcut printed in color on thin cream paper',
     'The Margaret Rankin Barker – Isaac Ogden Rankin Collection. Gift of Mr. and Mrs. James Barker (Margaret Clark '
     'Rankin, class of 1908)', ''),
    ('beyondthefloatingworld', '2026-08/Beast%20for%20website.png', 'Attributed to Utagawa Yoshiiku', 'Ōtsu-e',
     'Late 19th century', 'Woodcut printed in color on paper', 'Bequest of Henry L. Seaver', ''),
    ('paintingnature', '2026-07/Monet_The%20Seine-Website.png', 'Claude Monet', 'The Seine at Bougival', '1869',
     'Oil on canvas', 'Purchased', ''),
    ('paintingnature', '2026-07/SCMA_Gifford_Lake%20Nemi.png', 'Sanford Robinson Gifford', 'Lake Nemi', 'ca. 1856–57',
     'Oil on canvas', 'Gift of Andrea Henderson Fahnestock, class of 1980, in memory of her husband, George Andrew '
     'Hambrecht (Yale ’67)', ''),
    ('paintingnature', '2026-07/Attributed%20to%20Victor%20de%20Grailly%20copy_0_0.png',
     'Attributed to Victor de Grailly', 'The Ox Bow of the Connecticut River from Mount Holyoke', 'ca. 1840',
     'Oil on canvas', 'Purchased', ''),
    ('worlds-process-art-scma-collection', '2023-10/Elmer%20WIP%20SLideshow%20copy.jpg', 'Edwin Romanzo Elmer',
     'Mourning Picture', '1890', 'Oil on canvas', 'Purchased', 'SC 1953.129'),
    ('worlds-process-art-scma-collection', '2023-10/Rooster_WIP_Slideshow%20copy.jpg', 'Unrecorded Fon artist',
     'Rooster', '20th century', 'Bronze', 'Gift of the Herman Copen Trust', 'SC 2002.12.30'),
    ('worlds-process-art-scma-collection', '2023-10/Callender_WIP_Slideshow.jpg', 'Alexis Callender',
     'Where Everything is Made From Within', '2019', 'Oil, acrylic, and graphite on canvas',
     'Purchased with the Dorothy C. Miller, class of 1925, Fund', 'SC 2022.30.1'),
    ('worlds-process-art-scma-collection', '2023-10/Heddle%20Pulley%20copy.jpg', 'Unrecorded Baule artist',
     'Heddle Pulley', '20th century', 'Carved wood', 'Gift of Mr. and Mrs. Raymond L. Myrer', 'SC 1960.46'),
    ('worlds-process-art-scma-collection', '2023-10/Guillebaud_WIP_Slideshow.jpg', 'Amile-Ursule Guillebaud',
     'Portrait of the Artist, Seated at Her Easel', 'ca. 1820–1845', 'Oil on canvas',
     'Purchased with a gift from Peter Soriano and Nina Munk, class of 1988, and the Museum Acquisitions Fund',
     'SC 2019.5'),
    ('worlds-process-art-scma-collection', '2023-10/Bankston_WIP_Slideshow.jpg', 'John Bankston', 'Unmasked', '2005',
     'Oil on linen', 'Gift of Rena G. Bransten, class of 1954', 'SC 2007.30.2'),
    ('worlds-process-art-scma-collection', '2023-10/Barthe_WIP_Slideshow%20copy.jpg', 'Richmond Barthé',
     'The Negro Looks Ahead', '1944 (cast ca. 1979)', 'Bronze', 'Purchased with the Kathleen Compton Sherrerd, class '
     'of 1954, Acquisition Fund for American Art, and the Museum Acquisitions Fund', 'SC 2022.14'),
    ('worlds-process-art-scma-collection', '2023-10/Bellow_WIP.jpg', 'George Wesley Bellows', 'Pennsylvania Excavation',
     '1907', 'Oil on canvas', 'Gift of Mary Gordon Roberts, class of 1960, in honor of her 50th reunion', 'SC 2010.11'),
    ('worlds-process-art-scma-collection', '2023-10/Bell_WIP.jpg', 'Vanessa Bell', 'Landscape with Haystack, Asheham',
     '1912', 'Oil on board', 'Purchased with the gift of Anne Holden Kieckhefer, class of 1952 in honor of Ruth '
     'Chandler Holden, class of 1926', 'SC 1989.23'),
    ('worlds-process-art-scma-collection', '2023-10/White%20glazed%20jog_WIP%20copy.jpg', 'Artist unknown (Iranian)',
     'Jug', 'late 12th century', 'Pierced and glazed stonepaste with blue paint',
     'Gift of Elinor Lander Horwitz, class of 1950', 'SC 2016.29.27'),
    ('worlds-process-art-scma-collection', '2023-10/Bod_WIP%20copy.jpg', 'Artist unknown (India)',
     'Bodhisattva, probably Avalokiteśvara Padmapāṇi', 'Pala period, c. 10th–11th century', 'Stone',
     'Gift of Mr. and Mrs. Stanley Marcus', 'SC 1963.81'),
]


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    if m: return int(m[1])
    m = re.search(r'(\d+)(?:st|nd|rd|th)[–-]?(?:\d+(?:st|nd|rd|th))? century', date or '')
    return (int(m[1]) - 1) * 100 + 50 if m else None


def record_url(acc):
    """The work's record in the Five College Museums database (a link only; that site is not read here)."""
    if not acc or not acc.startswith('SC '): return None
    return 'https://museums.fivecolleges.edu/detail.php?t=objects&type=ext&id_number=' + urllib.parse.quote(acc)


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
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
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/smith/images/{key}.jpg'


def wid(acc, artist, title):
    return 'scma-' + (re.sub(r'[^\w.-]', '', acc.replace('SC ', '')) if acc else norm(artist)[:12] + '-' + norm(title)[:28])


def highlights():
    """Works on scma.smith.edu/art/highlights (4 pages): the newest acquisitions and selected artworks."""
    out = {}
    for p in range(4):
        page = get(f'{SITE}/art/highlights?page={p}', f'highlights-{p}.html')
        for row in re.split(r'<(?:div|li) class="[^"]*views-row[^"]*">', page)[1:]:
            a = re.search(r'id_number=([^"&]+)"[^>]*>(.*?)</a>', row, re.S)
            if not a: continue
            acc = urllib.parse.unquote_plus(html.unescape(a[1])).strip()
            f = lambda name: text((re.search(rf'field-{name}"><(?:span|div) class="field-content">(.*?)</(?:span|div)>',
                                             row, re.S) or [None, ''])[1])
            img = re.search(r'<img[^>]+src="([^"]+)"', row)
            out.setdefault(acc, {'accession': acc, 'title': text(a[2]), 'artist': f('artist'),
                                 'date': f('artwork-date'), 'medium': f('artwork-materials'),
                                 'credit': f('credit-line'), 'image': SITE + img[1] if img else None})
    return list(out.values())


def wikidata():
    q = '''SELECT ?w ?title ?creator ?date ?img ?acc ?material WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en") }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img }
      OPTIONAL { ?w p:P217 ?s . ?s ps:P217 ?acc . ?s pq:P195 wd:%s }
      OPTIONAL { ?w wdt:P186 ?m . ?m rdfs:label ?material FILTER(lang(?material)="en") } }''' % (MUSEUM, MUSEUM)
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
                                  'image': None, 'accession': '', 'medium': set()})
        if v.get('creator'): r['artist'].add(v['creator'])
        if v.get('material'): r['medium'].add(v['material'])
        if v.get('date'): r['date'] = v['date'][:4].lstrip('+')
        if v.get('img'): r['image'] = v['img']
        if v.get('acc'): r['accession'] = v['acc'] if v['acc'].startswith('SC') else 'SC ' + v['acc']
    for r in rows.values():
        r['artist'] = ', '.join(sorted(r['artist'])) or 'Unknown artist'
        r['medium'] = ', '.join(sorted(r['medium']))
    return [r for r in rows.values() if r['title'] and not re.fullmatch(r'Q\d+', r['title'])]


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out = []
    for show, img, artist, title, date, medium, credit, acc in SHOW_WORKS:
        room, show_name, how = SHOWS[show]
        floor, gname = rooms[room]
        key = wid(acc, artist, title)
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'year': year_of(date), 'medium': medium,
             'accession': acc, 'creditLine': credit, 'gallery': room, 'galleryName': gname, 'floor': floor,
             'placeNote': how, 'exhibition': show_name,
             'url': record_url(acc) or SITE + PATH.get(show, f'/art/exhibitions/{show}'),
             'image': picture(key, f'{SITE}/sites/default/files/{img}'),
             'imageCredit': 'Smith College Museum of Art' if not acc.startswith('SAAM') else
                            'Smithsonian American Art Museum, via SCMA'}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    return {'source': 'Smith College Museum of Art website (scma.smith.edu exhibition pages); pictures from '
                      'scma.smith.edu', 'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False,
            'artworks': out}


def build_guide(works):
    """Every SCMA work we know of: shows (on view), highlights and Wikidata (collection, on view not known)."""
    rows, seen = [], set()
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
        seen.add(a.get('accession') or a['id'])
        seen.add(norm(a['title']) + norm(a['artist'])[:8])
    for h in highlights():
        if h['accession'] in seen: continue
        seen.add(h['accession']); seen.add(norm(h['title']) + norm(h['artist'])[:8])
        key = wid(h['accession'], h['artist'], h['title'])
        rows.append({k: v for k, v in {'id': key, 'title': h['title'], 'artist': h['artist'], 'date': h['date'],
                     'year': year_of(h['date']), 'medium': h['medium'], 'accession': h['accession'],
                     'url': record_url(h['accession']), 'imageUrl': picture(key, h['image']),
                     'onView': False}.items() if v not in (None, '')})
    for w in wikidata():
        if (w['accession'] and w['accession'] in seen) or norm(w['title']) + norm(w['artist'])[:8] in seen: continue
        seen.add(w['accession']); seen.add(norm(w['title']) + norm(w['artist'])[:8])
        img = None
        if w['image']:
            img = w['image'].replace('http://', 'https://') + '?width=800'
        rows.append({k: v for k, v in {'id': 'scma-' + w['qid'], 'title': w['title'], 'artist': w['artist'],
                     'date': w['date'], 'year': year_of(w['date']), 'medium': w['medium'],
                     'accession': w['accession'], 'url': record_url(w['accession']) or
                     f'https://www.wikidata.org/wiki/{w["qid"]}', 'imageUrl': img,
                     'onView': False}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Smith College Museum of Art', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'SCMA website (scma.smith.edu) and Wikidata', 'onViewKnown': True,
            'note': 'SCMA owns more than 29,000 works; its full catalogue is the Five College Museums database. '
                    'This list is what the museum’s own pages show (current shows and highlights) plus the SCMA works '
                    'in Wikidata. On view means pictured on the page of a current show.',
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
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'collection list {len(guide["works"])} ({idx["museums"][MUSEUM]["pictures"]} pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
