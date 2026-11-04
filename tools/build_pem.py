#!/usr/bin/env python3
"""Build the Peabody Essex Museum map guide (run: python3 tools/build_pem.py [--refresh]).

    data/pem/floors.json    Ground Level, Level 2 and Level 3 seen from above (a flat 2D plan)
    data/pem/artworks.json  works from PEM's own web pages and from Wikidata, in their gallery

The map: PEM's 2024 visitor map (a vector PDF, copy at all-maps.com/wp-content/uploads/2025/05/
Peabody-Essex-Museum-Map-2024.pdf). Rooms are drawn by hand over that map, in the PDF's points (page shown
upright). The PDF stacks the three levels down the page, so Level 2 is moved up 323 points and Level 3 648
points; then the elevators and stairs of each level sit on top of each other, which is how the directions
link floors. Gallery numbers and names are the map's, with two updates from pem.org: Korean Art opened in
302 (May 2025) and the Salem Witch Trials gallery (202) runs through June 2027.

The works:
- pem.org's collection pages ("Highlights from this collection") and the pages of the ongoing gallery
  installations, read politely (one page every 2 seconds, cached in .cache/pem). A work that says "On view
  in the Byrne Family Gallery of Maritime Art" goes in that gallery; a work shown on a gallery's page goes in
  that gallery. Highlights that are not marked on view go in the gallery of their collection, with a note.
- the works Wikidata lists for PEM (data/guides/Q3373790.json, CC0), placed by subject, with a note.
Pictures are PEM's own (pem.org) or from Wikimedia Commons.
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'pem'
CACHE = ROOT / '.cache' / 'pem'
MUSEUM = 'Q3373790'
SOURCE = 'Peabody Essex Museum visitor map, 2024 edition'
SHIFT = {'G': 0, '2': -323, '3': -648}   # lines Level 2 and Level 3 up with the Ground Level


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# (id, kind, name, poly in PDF points, short label for galleries)
ROOMS = {
    'G': [
        ('100', 'gallery', 'Native American and American Art · On This Ground',
         [[22, 61], [78, 61], [81, 120], [86, 200], [85, 243], [22, 243]], 'On This Ground'),
        ('Charter Street hall', 'corridor', 'Charter Street entrance hall',
         [[78, 52], [111, 52], [108, 133], [96, 137], [86, 158], [81, 120]], None),
        ('102', 'space', 'Morse Auditorium', [[111, 52], [147, 55], [142, 136], [108, 133]], None),
        ('103', 'gallery', 'Yin Yu Tang: A Chinese Home',
         [[150, 66], [163, 52], [188, 74], [200, 68], [233, 90], [228, 100], [205, 138], [165, 112], [150, 100]],
         'Yin Yu Tang'),
        ('104', 'gallery', 'Yin Yu Tang: Interpretive Space',
         [[96, 137], [148, 137], [162, 141], [175, 152], [178, 165], [150, 159], [120, 157], [88, 160]],
         'Yin Yu Tang'),
        ('105', 'gallery', 'Chinese Art', [[205, 140], [228, 102], [241, 98], [241, 178], [200, 178], [194, 166]],
         'Chinese Art'),
        ('106', 'space', 'Yin Yu Tang Theater', rect(241, 100, 256, 140), None),
        ('107', 'gallery', 'Yin Yu Tang: Interpretive Space', rect(241, 140, 256, 172), 'Yin Yu Tang'),
        ('Main Atrium', 'corridor', 'Main Atrium · Atrium Café',
         [[88, 160], [120, 157], [178, 165], [200, 182], [218, 186], [218, 248], [140, 248], [140, 232],
          [105, 232], [105, 245], [85, 245], [86, 200]], None),
        ('108', 'gallery', 'Special Exhibitions', rect(222, 188, 262, 247), 'Exhibitions'),
        ('109', 'gallery', 'Art & Nature Center · Special Exhibitions',
         [[217, 252], [262, 252], [262, 290], [201, 290], [201, 266], [217, 266]], 'Art & Nature'),
        ('Museum Shop', 'space', 'Museum Shop', rect(105, 232, 138, 287), None),
        ('Lobby', 'corridor', 'Main entrance lobby · admissions',
         [[72, 245], [105, 245], [105, 300], [100, 302], [100, 347], [80, 347]], None),
        ('Center hall', 'corridor', 'Coatroom, restrooms and elevator',
         [[138, 248], [201, 248], [201, 290], [168, 290], [168, 345], [138, 345], [138, 287]], None),
        ('Museum Shop South', 'space', 'Museum Shop', rect(100, 302, 138, 345), None),
        ('110', 'space', 'Create Space · Studio 2', rect(168, 292, 197, 320), None),
        ('111', 'space', 'Create Space · Studio 1', rect(197, 292, 240, 320), None),
        ('South hall', 'corridor', 'Hall to the Groups Hub', rect(240, 290, 262, 322), None),
        ('114', 'gallery', 'Powerful Figures', rect(262, 178, 300, 220), 'Powerful Figures'),
        ('120', 'gallery', 'Studio Glass', rect(262, 220, 300, 238), 'Studio Glass'),
        ('113', 'gallery', 'The Pod · Art & Nature Center', rect(262, 238, 300, 288), 'The Pod'),
        ('Groups Hub', 'corridor', 'Groups Hub · Groups entrance', rect(262, 288, 312, 332), None),
        ('Garden Atrium', 'corridor', 'Garden Atrium', [[300, 178], [405, 178], [405, 213], [300, 213]], None),
        ('New Wing stairs', 'corridor', 'New Wing stairs', [[300, 213], [319, 213], [306, 332], [292, 332]], None),
        ('G-east elevator', 'corridor', 'East elevator · the only one to Fashion and Design', rect(398, 232, 414, 262), None),
        ('115', 'gallery', 'Vanessa Platacis: Taking Place', rect(352, 105, 390, 150), 'Taking Place'),
        ('116', 'gallery', 'Vanessa Platacis: Taking Place', rect(352, 150, 390, 178), 'Taking Place'),
        ('117', 'gallery', 'Maritime Art · Byrne Family Gallery', [[319, 213], [405, 220], [392, 332], [306, 326]],
         'Maritime Art'),
        ('118', 'space', 'Garden',
         [[392, 158], [480, 175], [478, 215], [466, 215], [460, 268], [410, 262], [407, 213], [395, 178]], None),
    ],
    '2': [
        ('200', 'gallery', 'Yin Yu Tang: Interpretive Space', [[96, 438], [110, 438], [112, 451], [141, 450], [138, 483], [104, 488]],
         'Yin Yu Tang'),
        ('Atrium balcony', 'corridor', 'Balcony over the Main Atrium',
         [[104, 488], [138, 483], [175, 495], [200, 510], [203, 545], [200, 560], [110, 560]], None),
        ('202', 'gallery', 'The Salem Witch Trials 1692', [[198, 500], [233, 433], [243, 433], [243, 510], [200, 510]],
         'Witch Trials'),
        ('208', 'gallery', 'Japanese Art', rect(243, 433, 293, 510), 'Japanese Art'),
        ('209', 'gallery', 'Phillips Library Gallery · Special Exhibitions', rect(293, 452, 309, 478), 'Phillips Library'),
        ('2-restrooms', 'corridor', 'Restrooms', rect(293, 478, 310, 510), None),
        ('210', 'gallery', 'South Asian Art', rect(328, 450, 388, 503), 'South Asian Art'),
        ('211', 'gallery', 'South Asian Art', rect(330, 503, 388, 527), 'South Asian Art'),
        ('203', 'gallery', 'American Art', [[200, 510], [265, 510], [265, 570], [215, 575], [205, 545]], 'American Art'),
        ('207', 'gallery', 'Special Exhibitions', rect(268, 513, 307, 550), 'Special Exhibitions'),
        ('2-hall', 'corridor', 'Hall', [[265, 550], [312, 550], [312, 560], [265, 560]], None),
        ('2-east hall', 'corridor', 'Hall', rect(307, 503, 330, 550), None),
        ('2-north hall', 'corridor', 'Hall', rect(330, 527, 390, 546), None),
        ('206', 'gallery', 'East India Marine Hall · Special Exhibitions', rect(268, 560, 307, 660), 'East India Marine Hall'),
        ('New Wing landing', 'corridor', 'New Wing stairs landing', [[307, 560], [322, 556], [318, 652], [307, 652]], None),
        ('212', 'gallery', 'Asian Export Art · Sean M. Healey Family Gallery',
         [[322, 547], [392, 543], [383, 655], [318, 652]], 'Asian Export Art'),
        ('2-east elevator', 'corridor', 'East elevator · the only one to Fashion and Design', rect(390, 555, 414, 590), None),
        ('2-center', 'corridor', 'Restrooms and elevator', rect(175, 560, 215, 603), None),
        ('201', 'gallery', 'Special Exhibitions',
         [[110, 562], [130, 562], [130, 575], [152, 575], [152, 562], [175, 562], [175, 603], [262, 603],
          [262, 662], [175, 672], [160, 660], [160, 640], [135, 605], [110, 598]], 'Special Exhibitions'),
    ],
    '3': [
        ('300', 'gallery', 'Special Exhibitions', [[26, 712], [72, 712], [80, 780], [83, 888], [34, 888], [26, 870]],
         'Special Exhibitions'),
        ('3-atrium', 'corridor', 'Balcony over the Main Atrium',
         [[78, 712], [110, 712], [110, 784], [140, 782], [195, 810], [218, 838], [218, 878], [150, 876], [85, 876],
          [83, 800]], None),
        ('302', 'gallery', 'Korean Art · Yu Kil-Chun Gallery', rect(242, 758, 290, 835), 'Korean Art'),
        ('303', 'gallery', 'Special Exhibitions', rect(290, 772, 307, 834), 'Special Exhibitions'),
        ('3-hall', 'corridor', 'Hall', rect(218, 835, 265, 846), None),
        ('304', 'gallery', 'Salem Stories', rect(218, 846, 265, 898), 'Salem Stories'),
        ('3-east lobby', 'corridor', 'Elevator lobby · the only elevator to Fashion and Design',
         rect(386, 862, 412, 905), None),
        ('305', 'gallery', 'Fashion and Design · Carl and Iris Barrel Apfel Gallery',
         [[330, 862], [392, 868], [383, 980], [325, 975]], 'Fashion and Design'),
    ],
}

DOORS = {
    'G': [('Charter Street hall', '100', (80, 100)), ('Charter Street hall', '102', (110, 95)),
          ('Charter Street hall', '104', (98, 137)), ('104', 'Main Atrium', (130, 158)),
          ('104', '103', (155, 125)), ('Main Atrium', '100', (85, 200)), ('Main Atrium', '105', (198, 170)),
          ('105', '106', (241, 120)), ('105', '107', (241, 160)), ('Main Atrium', '108', (222, 220)),
          ('Main Atrium', 'Lobby', (95, 245)), ('Main Atrium', 'Museum Shop', (120, 232)),
          ('Main Atrium', 'Center hall', (170, 248)), ('Lobby', 'Museum Shop South', (100, 320)),
          ('Center hall', 'Museum Shop', (138, 265)), ('Center hall', 'Museum Shop South', (138, 320)),
          ('Center hall', '109', (201, 275)), ('Center hall', '110', (180, 292)),
          ('110', '111', (197, 305)), ('111', 'South hall', (240, 305)), ('Center hall', 'South hall', (230, 290)),
          ('South hall', 'Groups Hub', (262, 305)), ('Groups Hub', '113', (280, 288)),
          ('113', '120', (280, 238)), ('120', '114', (280, 220)), ('Main Atrium', '114', (262, 200)),
          ('114', 'Garden Atrium', (300, 195)), ('Groups Hub', 'New Wing stairs', (300, 320)),
          ('New Wing stairs', 'Garden Atrium', (310, 213)), ('New Wing stairs', '117', (312, 270)),
          ('Garden Atrium', '117', (360, 216)), ('Garden Atrium', '116', (370, 178)), ('116', '115', (370, 150)),
          ('Garden Atrium', '118', (405, 195)), ('117', 'G-east elevator', (400, 250))],
    '2': [('200', 'Atrium balcony', (120, 485)), ('Atrium balcony', '201', (140, 562)),
          ('Atrium balcony', '203', (203, 530)), ('Atrium balcony', '2-center', (190, 560)),
          ('2-center', '201', (195, 603)), ('202', '203', (220, 510)), ('202', '208', (243, 480)),
          ('208', '203', (255, 510)), ('208', '209', (293, 465)), ('208', '2-restrooms', (293, 495)),
          ('203', '207', (265, 530)), ('203', '2-hall', (265, 555)), ('2-hall', '206', (285, 560)),
          ('2-hall', '2-east hall', (309, 550)), ('2-east hall', '207', (307, 530)),
          ('2-east hall', '211', (330, 515)), ('211', '210', (360, 503)), ('2-east hall', '2-north hall', (330, 540)),
          ('2-north hall', '212', (360, 545)), ('2-hall', 'New Wing landing', (310, 558)),
          ('New Wing landing', '212', (320, 600)), ('206', 'New Wing landing', (307, 610)), ('206', '201', (265, 630)),
          ('212', '2-east elevator', (391, 572))],
    '3': [('300', '3-atrium', (82, 800)), ('3-atrium', '3-hall', (218, 840)), ('3-hall', '302', (255, 835)),
          ('3-hall', '304', (240, 846)), ('302', '303', (290, 800)), ('3-east lobby', '305', (389, 885))],
}

WEST_ELEV, CENTER_ELEV, EAST_ELEV = (103, 125), (185, 269), (404, 247)
AMENITIES = {   # (type, x, y) on the Ground Level's footing (Level 2/3 points are given before the shift)
    'G': [('entrance', 92, 347), ('entrance', 95, 50), ('entrance', 312, 334), ('info', 137, 168),
          ('info', 86, 296), ('dining', 189, 208), ('shop', 125, 247), ('shop', 118, 317), ('coat', 145, 282),
          ('coat', 152, 316), ('restroom', 153, 262), ('restroom', 242, 312), ('restroom', 282, 166),
          ('nursing', 212, 298), ('elevator', 72, 70), ('elevator', *WEST_ELEV), ('elevator', *CENTER_ELEV),
          ('elevator', *EAST_ELEV), ('stairs', 110, 152), ('stairs', 283, 150), ('stairs', 305, 280),
          ('water', 157, 228)],
    '2': [('elevator', WEST_ELEV[0], WEST_ELEV[1] + 323), ('elevator', CENTER_ELEV[0], CENTER_ELEV[1] + 323),
          ('elevator', EAST_ELEV[0], EAST_ELEV[1] + 323), ('restroom', 300, 490), ('restroom', 192, 578),
          ('stairs', 120, 470), ('stairs', 312, 600), ('stairs', 365, 645), ('water', 195, 563),
          ('info', 140, 573)],
    '3': [('elevator', WEST_ELEV[0], WEST_ELEV[1] + 648), ('elevator', EAST_ELEV[0], EAST_ELEV[1] + 648),
          ('stairs', 120, 795), ('stairs', 360, 970)],
}
LABELS = {
    'G': [('Main Entrance · 161 Essex Street', 'note', 92, 360), ('Charter Street Entrance (open seasonally)', 'note', 95, 38),
          ('Groups Entrance', 'note', 312, 346), ('Garden', 'place', 440, 230)],
    '2': [('Only this elevator goes to Fashion and Design on Level 3', 'note', 430, 600)],
    '3': [('Fashion and Design: take the east elevator (near Maritime Art)', 'note', 400, 1000)],
}
FLOORS = [
    ('G', 'Ground Level', 'Main entrance · Atrium Café · Museum Shop · Native American and American Art · Yin Yu '
                          'Tang · Chinese Art · Maritime Art · Art & Nature Center', 0),
    ('2', 'Level 2', 'American Art · Salem Witch Trials · Japanese Art · South Asian Art · Asian Export Art · '
                     'East India Marine Hall · Special Exhibitions', 2),
    ('3', 'Level 3', 'Korean Art · Salem Stories · Fashion and Design · Special Exhibitions', 3),
]


K = 2   # PDF points x2, so gallery names fit inside the rooms like on the other museums' maps


def pt(x, y, dy):
    return [round(x * K, 1), round((y + dy) * K, 1)]


def shift(poly, dy):
    return [pt(x, y, dy) for x, y in poly]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        dy = SHIFT[fid]
        rooms = []
        for rid, kind, name, poly, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': shift(poly, dy)}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y, dy), 'width': 6 * K, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        amen = [{'type': t, 'at': pt(x, y, dy)} for t, x, y in AMENITIES[fid]]
        labels = [{'text': t, 'kind': k, 'at': pt(x, y, dy)} for t, k, x, y in LABELS[fid]]
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_pem.py from the Peabody Essex Museum visitor map (2024 edition). '
                     'Rooms are drawn over the museum’s map, so walls are approximate. Special exhibitions change '
                     'during the year.',
            'source': SOURCE, 'units': 'half points', 'defaultFloor': 'G', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works from pem.org --------------------------------------------------------------------------------------

PAGES_COLLECTION = ['african-art', 'american-art', 'american-decorative-art', 'asian-export-art', 'chinese-art',
                    'contemporary-art', 'european-art', 'fashion-textiles', 'japanese-art', 'korean-art',
                    'maritime-art-and-history', 'native-american-art', 'natural-history', 'oceanic-art',
                    'phillips-library-collection', 'photography', 'south-asian-art']
# collection page -> gallery for highlights not marked on view (None: no gallery for that collection)
COLLECTION_ROOM = {'african-art': '114', 'american-art': '203', 'american-decorative-art': '100',
                   'asian-export-art': '212', 'chinese-art': '105', 'fashion-textiles': '305', 'japanese-art': '208',
                   'korean-art': '302', 'maritime-art-and-history': '117', 'native-american-art': '100',
                   'oceanic-art': '206', 'phillips-library-collection': '209', 'south-asian-art': '210'}
# ongoing gallery installation pages -> gallery
GALLERY_PAGES = {'american-art-traditions-transformed': '203', 'asian-export-art': '212', 'japanese-art': '208',
                 'maritime-art': '117', 'on-this-ground-being-and-belonging-in-america': '100',
                 'powerful-figures': '114', 'salem-stories': '304', 'south-asian-art': '210', 'studio-glass': '120',
                 'the-salem-witch-trials-1692': '202', 'yu-kil-chun-gallery-of-korean-art-and-culture': '302',
                 'east-india-marine-hall': '206'}
ON_VIEW = [(r'Asian Export', '212'), (r'Maritime', '117'), (r'South Asian', '210'), (r'Japanese', '208'),
           (r'American Art Gallery', '203'), (r'The Pod', '113'), (r'Garden Atrium', 'Garden Atrium'),
           (r'Fashion and Design', '305'), (r'Powerful Figures', '114'), (r'On this Ground', '100'),
           (r'East India Marine', '206'), (r'Ground Level of the New Wing|stairway of the new wing', 'New Wing stairs'),
           (r'Level 2 of the new wing', 'New Wing landing'), (r'Korean', '302'), (r'Chinese Art', '105'),
           (r'Studio Glass', '120'), (r'Salem Stories', '304')]
NOTE_EXACT = 'PEM’s website says this work is on view in this gallery.'
NOTE_ONVIEW = ('PEM’s website says this work is on view; the gallery is the one for its collection area.')
NOTE_PAGE = 'Shown on PEM’s page for this gallery. Galleries are rehung from time to time.'
NOTE_AREA = ('Gallery of this collection area. PEM’s website does not say this work is on view now, '
             'so it may be in storage.')
NOTE_GUESS = ('Gallery guessed from the work’s subject. Wikidata lists what the museum owns, so this work may '
              'not be on view.')


def fetch_page(path, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (path.replace('/', '_') + '.html')
    if f.exists() and not refresh:
        return f.read_text(errors='replace')
    url = 'https://www.pem.org/' + path
    out = subprocess.run(['curl', '-s', '-m', '40', url], capture_output=True, check=False).stdout.decode('utf-8', 'replace')
    f.write_text(out)
    time.sleep(2)                       # polite: one page every 2 seconds
    return out


def text(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s)).split()).replace(' ,', ',').replace(' .', '.')


def year_of(date):
    m = re.search(r'(\d{3,4})', date or '')
    if m:
        y = int(m[1])
        if re.search(r'B\.?C', date): y = -y
        return y
    m = re.search(r'(\d{1,2})(st|nd|rd|th) century', date or '')
    if m:
        return (int(m[1]) - 1) * 100 + 50 * (-1 if re.search(r'B\.?C', date) else 1)
    return None


DATE = r'((?:about|around|circa|ca\.|before|after|early|mid|late|probably)?[\s-]*(?:\d{1,2}(?:st|nd|rd|th)[\s–-]*(?:\d{1,2}(?:st|nd|rd|th))?\s+centur(?:y|ies)|\d{3,4}s?(?:[–-]\d{2,4}s?)?)(?:\s*(?:B\.?C\.?E?|C\.?E\.?|A\.?D\.?))?)'


def parse_caption(cap):
    """'Artist (dates), Title, date. Medium. Credit. Accession.' -> dict (best effort)."""
    cap = re.sub(r'^(?:Installation view[^.]*\.|(?:[A-Z][a-z]+ )?[Dd]etail of )', '', cap).strip()
    cap = re.sub(r'\s*\((?:detail|details)\)', '', cap)
    m = re.match(r'(.+?),\s*' + DATE + r'\.\s*(.*)$', cap)
    if not m: return None
    head, date, rest = m[1], m[2].strip(), m[3]
    parts = [p.strip() for p in re.split(r',\s*(?![^()]*\))', head)]
    if len(parts) < 2: return None
    artist, title = parts[0], ', '.join(parts[1:])
    sent = [s.strip() for s in re.split(r'\.\s+', rest) if s.strip()]
    medium = sent[0].rstrip('.') if sent else ''
    acc = ''
    for s in reversed(sent):
        s = s.rstrip('.')
        if re.fullmatch(r'[A-Z]{0,3}\d[\w.\-]*', s): acc = s; break
    credit = next((s.rstrip('.') for s in sent[1:] if re.search(r'Gift|purchase|Bequest|Collection|Loan|Commissioned', s)), '')
    if re.search(r'Photo|©|Courtesy|^Gift|^Museum purchase|^Bequest', medium) or medium == acc: medium = ''
    return {'artist': artist, 'title': title, 'date': date, 'medium': medium, 'accession': acc, 'credit': credit}


def harvest(refresh=False):
    works = []
    for slug in PAGES_COLLECTION:
        page = fetch_page(f'the-pem-collection/{slug}', refresh)
        mods = {src: cap for src, cap in re.findall(
            r'class="masMod__img" src="([^"]+)".*?masMod__desc"><p>(.*?)</p>', page, re.S)}
        blocks = re.findall(r'<div class="masonry__block grid-item".*?(?=<div class="masonry__block grid-item"|</section>)',
                            page, re.S)
        for b in blocks:
            src = re.search(r'class="masonry__img" src="([^"]+)"', b)
            h5 = re.search(r'<h5>(.*?)</h5>', b, re.S)
            if not src or not h5: continue
            src = src[1]
            heading = text(h5[1])
            author = re.search(r'masonry__author">\s*<p>(.*?)</p>', b, re.S)
            author = text(author[1]) if author else ''
            onview = re.search(r'masonry__onViewDescription">(.*?)</div>', b, re.S)
            onview = text(onview[1]) if onview else ''
            room, note = None, None
            for pat, rid in ON_VIEW:
                if onview and re.search(pat, onview, re.I): room, note = rid, NOTE_EXACT; break
            if not room and COLLECTION_ROOM.get(slug):
                room, note = COLLECTION_ROOM[slug], (NOTE_ONVIEW if 'masonry__onView1' in b else NOTE_AREA)
            cap = text(mods.get(src, ''))
            info = parse_caption(cap) or {}
            m = re.match(r'(.*?),\s*' + DATE + r'\.?\s*$', heading)
            title, date = (m[1], m[2]) if m else (heading.rstrip('.'), '')
            works.append({'title': title.strip(), 'artist': author or info.get('artist', ''), 'date': date,
                          'medium': info.get('medium', ''), 'accession': info.get('accession', ''),
                          'credit': info.get('credit', ''), 'image': src, 'room': room, 'note': note,
                          'onView': onview, 'url': f'https://www.pem.org/the-pem-collection/{slug}', 'area': slug})
    for slug, rid in GALLERY_PAGES.items():
        page = fetch_page(f'exhibitions/{slug}', refresh)
        for src, cap in re.findall(r'class="imageWithCaption__img" src="([^"]+)" alt="([^"]*)"', page):
            info = parse_caption(text(cap))
            if not info: continue
            works.append({**info, 'image': src, 'room': rid, 'note': NOTE_PAGE, 'onView': '',
                          'url': f'https://www.pem.org/exhibitions/{slug}', 'area': slug})
    return works


# ---- works from Wikidata ----------------------------------------------------------------------------------------

SEA = re.compile(r'ship|bark|brig|frigate|harbou?r|sea|whal|schooner|figurehead|captain|marine|port of|wreck|'
                 r'sail|voyage|naval|yacht|clipper|ocean|bay|coast', re.I)
CHINA = re.compile(r'Chin|Canton|Guangzhou|Hong|Macao|porcelain|ceramic|plate|vase|bowl|export', re.I)
WITCH = re.compile(r'witch|1692', re.I)


def wikidata_room(w):
    t = f'{w.get("title", "")} {w.get("type", "")}'
    if WITCH.search(t): return '202'
    if SEA.search(t): return '117'
    if CHINA.search(t): return '212'
    if re.search(r'Japan|Hokusai|Hiroshige|ukiyo', t + ' ' + (w.get('artist') or ''), re.I): return '208'
    if re.search(r'India|Mughal|Hindu', t, re.I): return '210'
    if re.search(r'mask|figure|figurine|earring|club|canoe', t, re.I): return '114'
    y = w.get('year')
    if y and y >= 1950: return '100'
    return '203'


def build_works(floors, pem, wd):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out, seen = [], set()

    def key(title, artist):
        title = re.sub(r',\s*(?:about\s*)?\d{4}\W*$', '', title or '')
        return re.sub(r'\W+', '', title.lower())[:40] + '|' + re.sub(r'\W+', '', (artist or '').lower())[:12]

    # pages that name the exact gallery first, so they win over the "collection area" guesses
    rank = {NOTE_EXACT: 0, NOTE_PAGE: 1, NOTE_ONVIEW: 2, NOTE_AREA: 3}
    for i, w in enumerate(sorted(pem, key=lambda w: rank.get(w['note'], 3))):
        if not w.get('room') or w['room'] not in rooms or not w.get('title'): continue
        k = key(w['title'], w['artist'])
        if k in seen or w['image'] in seen: continue
        seen.add(k); seen.add(w['image'])
        floor, gname = rooms[w['room']]
        aid = 'pem-' + (re.sub(r'[^\w.-]', '', w['accession']) if w.get('accession') else
                        re.sub(r'[^\w]+', '-', Path(urllib.parse.urlparse(w['image']).path).stem)[:48])
        a = {'id': aid, 'title': w['title'], 'artist': w['artist'], 'date': w['date'], 'year': year_of(w['date']),
             'medium': w['medium'], 'accession': w['accession'], 'credit': w.get('credit', ''),
             'gallery': w['room'], 'galleryName': gname, 'floor': floor, 'placeNote': w['note'],
             'url': w['url'], 'image': w['image'], 'imageCredit': 'Peabody Essex Museum'}
        out.append({k2: v for k2, v in a.items() if v not in (None, '')})
    for w in wd:
        k = key(w.get('title'), w.get('artist'))
        if k in seen or re.fullmatch(r'Q\d+', w.get('title') or ''): continue
        seen.add(k)
        g = wikidata_room(w)
        floor, gname = rooms[g]
        a = {'id': f'pem-{w["id"]}', 'title': w['title'], 'artist': w.get('artist', ''),
             'date': str(w['year']) if w.get('year') is not None else '', 'year': w.get('year'),
             'type': (w.get('type') or '').capitalize(), 'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': NOTE_GUESS, 'url': f'https://www.wikidata.org/wiki/{w["id"]}', 'wikidata': w['id']}
        if w.get('image'):
            a['image'] = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(w['image']) + '?width=600'
            a['imageCredit'] = 'Wikimedia Commons'
        out.append({k2: v for k2, v in a.items() if v not in (None, '')})
    ids = {}
    for a in out:                       # ids must be unique
        n = ids.get(a['id'], 0); ids[a['id']] = n + 1
        if n: a['id'] += f'-{n + 1}'
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['placeNote'] != NOTE_EXACT,
                            a.get('year') or 0))
    return {'source': 'Peabody Essex Museum website (pem.org collection and gallery pages) and Wikidata (CC0); '
                      'pictures from pem.org and Wikimedia Commons',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    pem = harvest(refresh='--refresh' in sys.argv)
    wd = json.load(open(ROOT / 'data' / 'guides' / f'{MUSEUM}.json'))['works']
    works = build_works(floors, pem, wd)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    exact = sum(a['placeNote'] in (NOTE_EXACT, NOTE_PAGE, NOTE_ONVIEW) for a in works['artworks'])
    print(f'{works["count"]} works ({exact} in a gallery named by PEM), '
          f'{sum("image" in a for a in works["artworks"])} with pictures')
    for k in sorted(by): print(f'  {k}: {by[k]}')


if __name__ == '__main__':
    main()
