#!/usr/bin/env python3
"""Build the Harvard Museum of Natural History map guide (run: python3 tools/harvest_hmnh.py, then this).

    data/hmnh/floors.json       the gallery floor (3rd floor of Harvard's University Museum building), flat 2D
    data/hmnh/artworks.json     the galleries and the specimens, minerals and glass models pictured in them
    data/hmnh/images/           the pictures, made smaller for phones
    data/guides/Q2001855.json   the same, for the museum page

Where the information comes from
--------------------------------
hmnh.harvard.edu answers scripts with 403, so its floor plan page can't be read. The map is traced from the floor plan
the Harvard Museums of Science & Culture print in their wayfinding brochure (July 2023, cached in
.cache/hmnh/wayfinding2023.pdf, page 2, rendered at 150 dpi; coordinates are those pixels minus (200, 100), times 2).
It is a simple diagram: every gallery, the shop and admissions, the main stairs from the Oxford Street entrance, the
elevator, restrooms, the accessible restroom, the water fountain and the route to the ground-level accessible entrance.
Door positions are partly guesses (the diagram shows openings only roughly), so the map says it is approximate.
All galleries are on this one floor; the Peabody Museum of Archaeology & Ethnology is reached through it.

The things in each gallery: photos visitors took in the galleries and shared on Wikimedia Commons (tools/harvest_hmnh.py),
with the photographer and licence. Which gallery a photo belongs to comes from what it shows (GALLERY_RULES below): the
museum's gallery names make most of them clear (minerals and meteorites are in Earth & Planetary Sciences, Blaschka
plants in the Glass Flowers, fossil reptiles in the Dinosaurs/Vertebrate Paleontology hall), and the rest are marked as
placed by guess. Photos are of different years, so a few things may have moved since.
"""
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'hmnh'
CACHE = ROOT / '.cache' / 'hmnh'
MUSEUM = 'Q2001855'
NAME = 'Harvard Museum of Natural History'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def P(x, y):
    # turned a quarter turn clockwise so the long building fits a phone screen (the brochure's left side is at the top)
    return [round((540 - y) * 4, 1), round(x * 4, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# rooms: (id, kind, name, polygon, short label for galleries)
F3 = [
    ('Great Mammal Hall', 'gallery', 'Great Mammal Hall and Birds of the World: whale skeletons overhead, big mammals '
     'and birds from around the world', rect(50, 81, 267, 167), 'Mammal Hall'),
    ('Marine Life', 'gallery', 'Marine Life', rect(67, 167, 136, 250), 'Marine Life'),
    ('New England Forests', 'gallery', 'New England Forests', rect(136, 167, 216, 250), 'N.E. Forests'),
    ('Asia, Central & South America', 'gallery', 'Asia, Central & South America: mammals and birds',
     rect(67, 250, 136, 329), 'Asia & Americas'),
    ('Africa', 'gallery', 'Africa: mammals and birds', rect(136, 250, 216, 328), 'Africa'),
    ('Special Exhibit (west)', 'gallery', 'Special Exhibit gallery (temporary shows)',
     [(102, 329), (166, 329), (166, 369), (240, 369), (240, 411), (102, 411)], 'Special'),
    ('Dinosaurs', 'gallery', 'Dinosaurs and Vertebrate Paleontology: the Kronosaurus, Triceratops, Deinonychus and '
     'early reptiles and amphibians',
     [(37, 386), (102, 386), (102, 411), (155, 411), (155, 485), (37, 485)], 'Dinosaurs'),
    ('Cenozoic Mammals', 'gallery', 'Cenozoic Mammals: fossil mammals after the dinosaurs (Glyptodon, giant ground '
     'sloth, rhinos and early horses)', rect(155, 411, 242, 485), 'Fossil Mammals'),
    ('Elevator Hall', 'corridor', 'Elevator (from the ground-level accessible entrance)', rect(240, 328, 280, 424), None),
    ('Accessible Restroom', 'space', 'Accessible restroom', rect(240, 424, 280, 462), None),
    ('Arthropods', 'gallery', 'Arthropods: Creepy Crawlers and Nature’s Building Blocks (insects, spiders, crabs)',
     rect(280, 328, 370, 397), 'Arthropods'),
    ('Special Exhibit (center)', 'gallery', 'Special Exhibit gallery (temporary shows)', rect(280, 397, 370, 462),
     'Special'),
    ('Sea Creatures in Glass', 'gallery', 'Sea Creatures in Glass: Blaschka glass models of marine invertebrates',
     rect(370, 328, 424, 372), 'Sea Glass'),
    ('Evolution', 'gallery', 'Evolution', rect(370, 372, 424, 462), 'Evolution'),
    ('Glass Flowers', 'gallery', 'The Glass Flowers: the Ware Collection of Blaschka Glass Models of Plants, '
     '4,300 models of 780 species', rect(424, 300, 542, 372), 'Glass Flowers'),
    ('Shop and Admissions', 'space', 'Admissions desk and The Shop at HMNH, at the top of the stairs from the main '
     'entrance', rect(424, 372, 542, 472), None),
    ('Earth & Planetary Sciences', 'gallery', 'Earth & Planetary Sciences: minerals, gems and meteorites (the '
     'Mineralogical & Geological Museum)', rect(542, 328, 692, 459), 'Minerals'),
    ('Restrooms', 'space', 'Restrooms and water fountain', rect(692, 385, 727, 459), None),
    ('Climate Change', 'gallery', 'Climate Change', rect(692, 328, 905, 385), 'Climate Change'),
    ('Accessible Route', 'corridor', 'Outside: path from the main entrance to the ground-level accessible entrance and '
     'its elevator', [(10, 350), (28, 350), (28, 508), (490, 508), (490, 524), (10, 524)], None),
]
PEABODY = [(707, 165), (750, 165), (750, 35), (905, 35), (905, 328), (752, 328), (752, 253), (707, 253)]
F3_CLOSED = [PEABODY, rect(160, 21, 267, 81), rect(166, 329, 240, 369), rect(37, 329, 102, 386)]
F3_DOORS = [
    ('Great Mammal Hall', 'Marine Life', (100, 167)), ('Great Mammal Hall', 'New England Forests', (175, 167)),
    ('Marine Life', 'Asia, Central & South America', (100, 250)), ('New England Forests', 'Africa', (175, 250)),
    ('Asia, Central & South America', 'Africa', (136, 300)), ('Africa', 'Special Exhibit (west)', (151, 328)),
    ('Asia, Central & South America', 'Special Exhibit (west)', (120, 329)),
    ('Special Exhibit (west)', 'Dinosaurs', (128, 411)), ('Special Exhibit (west)', 'Cenozoic Mammals', (200, 411)),
    ('Dinosaurs', 'Cenozoic Mammals', (155, 450)), ('Special Exhibit (west)', 'Elevator Hall', (240, 390)),
    ('Elevator Hall', 'Accessible Restroom', (260, 424)), ('Elevator Hall', 'Arthropods', (280, 350)),
    ('Elevator Hall', 'Special Exhibit (center)', (280, 410)), ('Arthropods', 'Special Exhibit (center)', (325, 397)),
    ('Arthropods', 'Sea Creatures in Glass', (370, 350)), ('Sea Creatures in Glass', 'Evolution', (397, 372)),
    ('Special Exhibit (center)', 'Evolution', (370, 430)), ('Sea Creatures in Glass', 'Glass Flowers', (424, 350)),
    ('Evolution', 'Shop and Admissions', (424, 420)), ('Glass Flowers', 'Shop and Admissions', (483, 372)),
    ('Glass Flowers', 'Earth & Planetary Sciences', (542, 345)),
    ('Shop and Admissions', 'Earth & Planetary Sciences', (542, 400)),
    ('Earth & Planetary Sciences', 'Climate Change', (692, 350)), ('Earth & Planetary Sciences', 'Restrooms', (692, 420)),
]
F3_AMEN = [('elevator', 260, 350), ('restroom-all', 260, 443), ('restroom', 710, 440), ('water', 710, 400),
           ('stairs', 470, 430), ('info', 497, 447), ('shop', 483, 395), ('entrance', 483, 466),
           ('entrance', 19, 365)]
F3_LABELS = [('MAIN ENTRANCE (26 Oxford St), stairs up', 483, 545),
             ('Accessible entrance (ground level)', 19, 330)]
F3_NOTES = [('Classroom B', 213, 50), ('Classroom A', 70, 357),
            ('Peabody Museum of Archaeology & Ethnology (same ticket), through Climate Change', 828, 200)]
LABEL_AT = {}


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def build_floors():
    rr = []
    for rid, kind, name, poly, short in F3:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        if rid in LABEL_AT: r['labelAt'] = P(*LABEL_AT[rid])
        rr.append(r)
    f = {'id': '3', 'label': 'Floor 3 (galleries)', 'order': 0, 'transform': [0.25, 0, 0],
         'area': 'All the galleries: Great Mammal Hall · Dinosaurs · Glass Flowers · Minerals · Arthropods · Climate '
                 'Change · Shop', 'rooms': rr,
         'closed': [{'poly': [P(*q) for q in c]} for c in F3_CLOSED],
         'homeView': [r[0] for r in F3 if r[1] == 'gallery'],
         'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in F3_AMEN],
         'labels': [{'text': t, 'kind': 'area', 'at': P(x, y)} for t, x, y in F3_LABELS],
         'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in F3_NOTES],
         'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 30, 'axis': 'o'} for a, b, p in F3_DOORS]}
    ids = [r['id'] for r in rr]
    assert len(ids) == len(set(ids))
    for d in f['doors']:
        assert d['a'] in ids and d['b'] in ids, d
    for a in f['amenities']:
        assert any(inside(a['at'], r['poly']) for r in rr), a
    return {'about': 'Built by tools/build_hmnh.py. Traced from the floor plan in the Harvard Museums of Science & '
                     'Culture wayfinding brochure (July 2023): every gallery on the third floor, admissions and the '
                     'shop, the stairs from the Oxford Street entrance, the elevator from the ground-level accessible '
                     'entrance, restrooms and the water fountain. The brochure’s plan is a diagram, so walls and doors '
                     'are approximate.',
            'source': 'Harvard Museums of Science & Culture, wayfinding brochure (July 2023)',
            'units': 'pixels of the brochure page at 150 dpi x 4, turned a quarter turn clockwise',
            'approximate': True, 'defaultFloor': '3', 'galleryWord': 'Gallery', 'floors': [f]}


# ---- things in the galleries ---------------------------------------------------------------------------------------

def picture(key, fname):
    raw = CACHE / 'img' / f'{key}.bin'
    failed = CACHE / 'img' / f'{key}.failed'
    if failed.exists(): return None          # Commons refused it twice before; delete the .failed files to retry
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://commons.wikimedia.org/wiki/Special:FilePath/{quote(fname.replace(" ", "_"))}?width=1000'
        out = b''
        for wait in (3, 60):                 # Commons answers 429 when asked too fast: wait and try once more
            out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
            time.sleep(wait)
            if out: break
        if not out:
            failed.write_text('')
            return None
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
    return f'data/hmnh/images/{key}.jpg'


# (regex on file name + description + categories, gallery, kind, sure?)
GALLERY_RULES = [
    (r'(?i)Natural_History_\(DerHexer\)_2012-07-20_\d\d|Seibal|Stela|Peabody_Museum_of_Arch|nutrition_panel|Vegan|JarvisField|Cambridge_of_eighteen|N-W_wing|'
     r'University_Museum|Harvard_Museum_of_Natural_History_(2|-_panoramio|050227|\(54940853196\))\.|'
     r'Harvard_museum_of_natural_history_[12]|Bracelet_\(AM|Word_%22|Word_"|Chevrotain%22|Kronosaurus_scale|'
     r'Kronosaurus_queenslandicus_SW|Wiki_Kronosaurus|'
     r'Beetle_trophic|Australopithecus_afarensis_panel|Thoreaulite.*cropped|Potos_flavus_\(Harvard_University\)_black',
     None, None, True),
    (r'(?i)blaschka.*(invertebrat|marine|sea)|sea_creatures|glass_invertebrat', 'Sea Creatures in Glass', 'Glass model', True),
    (r'(?i)Glass_Flower|Harvard_University_Glass_Flowers|Ware_Collection|Glass_model_of', 'Glass Flowers', 'Glass model', True),
    (r'(?i)meteor', 'Earth & Planetary Sciences', 'Meteorite', True),
    (r'(?i)Minerals_in_the_Harvard|_HMNH\d|HMNH_\d|Welcome_Nugget|Harvard_Museum_of_Natural_History\._[A-Z]|'
     r'Harvard_Mineralogical|Meneghinite|Variscite|Widgiemoolthalite|Pyrite_\(Randolph', 'Earth & Planetary Sciences',
     'Mineral', True),
    (r'(?i)Kronosaurus|Triceratops|Deinonychus|Dimetrodon|Edaphosaur|Archeria|Dinodontosaurus|Exaeretodon|'
     r'Neldasaurus|Homeosaurus|Pterodactyl|Tiktaalik', 'Dinosaurs', 'Fossil', True),
    (r'(?i)Glyptodon|Megalonyx|Teleoceras|Merycochoerus|Heptodon|Anchitherium|Mesohippus|Hypertragulus|Platygonus|'
     r'XXX', 'Cenozoic Mammals', 'Fossil', True),
    (r'(?i)Coleoptera|Beetle|Scolopendra|Triops|Bathynomus|Malacostraca|Mud_crab|Pinchy', 'Arthropods', 'Specimen', False),
    (r'(?i)Natural_History_Museum_2023a', 'Evolution', 'Gallery view', True),
    (r'(?i)Natural_History_Museum_2023b', 'Dinosaurs', 'Gallery view', False),
    (r'(?i)Natural_History_Museum_2023[cf]|Excellent', None, None, True),
    (r'(?i)Bizarre_animals', 'Cenozoic Mammals', 'Fossil', True),
    (r'(?i)Blonde_sloth', 'Asia, Central & South America', 'Specimen', False),
    (r'(?i)Whale_Skeleton|Big_Whale|Baleen|Natural_History_Museum_2023', 'Great Mammal Hall', 'Skeleton', True),
    (r'(?i)Labrador_Duck|Numenius_borealis', 'Great Mammal Hall', 'Specimen', False),
    (r'(?i)Latimeria|Bobtail_squid|Paddlefish|Fish', 'Marine Life', 'Specimen', False),
    (r'(?i)Chrysocyon|Potos_flavus|Dasyprocta|Capromys|Geocapromys|Solenodon|Geoffroy', 'Asia, Central & South America',
     'Specimen', False),
    (r'(?i)Javan_Chevrotain|Echinosorex|Rousettus', 'Asia, Central & South America', 'Specimen', False),
    (r'(?i)Epomophorus|hippo|Hiphop|Horns_and_horns', 'Africa', 'Specimen', False),
    (r'(?i)Perameles', 'Great Mammal Hall', 'Specimen', False),
    (r'(?i)Goliath_frog|Boids|Cat_eyes|O_rly|Bizarre|Excellent|Guffi|Fishlips', 'Great Mammal Hall', 'Specimen', False),
]


def classify(r):
    hay = ' '.join([r['file'], r.get('description', ''), ' '.join(r.get('categories', []))])
    for rx, gal, kind, sure in GALLERY_RULES:
        if re.search(rx, hay):
            return gal, kind, sure
    return 'Great Mammal Hall', None, None


TITLES = {'Guffi': 'Owls', 'O rly': 'Owls', 'Boids': 'Birds', 'Cat eyes': 'Wild cat', 'Crazy-light hippo': 'Hippopotamus',
          'Hiphopotamus': 'Hippopotamus', 'Horns and horns': 'Antelope', 'Blonde sloth': 'Sloth',
          'Beetlemania!': 'Beetles', 'ColeopteraHMNH1': 'Beetles (Coleoptera)', 'Fish eyes': 'Fish', 'Fishlips': 'Fish',
          'Big Whale, Little Whale -63 366-': 'Whale skeletons', 'Big Whale, Little Whale -63 366': 'Whale skeletons',
          'Bizarre animals': 'The evolution of South America’s bizarre animals', 'Pinchy': 'Crab', 'Mud crab': 'Mud crab',
          'Malacostraca': 'Crabs, shrimps and their relatives (Malacostraca)', 'Baleen': 'Whale skeleton and baleen',
          'Teleoceras Harvard, part 1': 'Teleoceras (short-legged rhinoceros)',
          'Teleoceras Harvard, part 2': 'Teleoceras (short-legged rhinoceros), detail',
          'Teleoceras Harvard, part 3': 'Teleoceras (short-legged rhinoceros), detail',
          'Teleoceras Harvard combined': 'Teleoceras (short-legged rhinoceros)',
          '2023a': 'The Evolution gallery',
          '2023b': 'Fossil marine reptile in its case',
          '2023d': 'Great Mammal Hall: the whale skeletons',
          '2023e': 'Great Mammal Hall: the mammal cases',
          'Goliath frog at': 'Goliath frog', '2023g': 'The Glass Flowers gallery', '2023h': 'The mineral gallery',
          'Meteor from Coahuila': 'Coahuila meteorite', 'GlassFlowers1': 'Glass Flowers', 'GlassFlowers4': 'Glass Flowers',
          'Harvard Mineralogical Museum, Harvard University, Cambridge MA': 'The mineral gallery',
          'Widgiemoolthalite,, November 2022': 'Widgiemoolthalite', 'The "Welcome Nugget" Replica': 'Welcome Nugget (replica)',
          'Welcome Nugget': 'Welcome Nugget (replica)', 'Harvard Deinonychus': 'Deinonychus', 'Dimetrodon milleri (1)': 'Dimetrodon milleri',
          'Kronosaurus': 'Kronosaurus', 'Kronosaurus queenslandicus': 'Kronosaurus queenslandicus',
          'Kronosaurus skull': 'Kronosaurus skull', 'Latimeria chalumnae': 'Coelacanth (Latimeria chalumnae)', 'Javan Chevrotain': 'Javan chevrotain'}


def title_of(r, kind):
    t = _title(r, kind)
    t = TITLES.get(t, t)
    if kind == 'Glass model': t = re.sub(r'\s+\d$', '', t)
    return t.replace(',, ', ', ')


def _title(r, kind):
    f = re.sub(r'\.(jpe?g|png)$', '', r['file'], flags=re.I).replace('_', ' ')
    d = r.get('description') or ''
    if kind == 'Mineral':
        m = re.match(r'Harvard Museum of Natural History\. (.+?)(?: \(DerHexer\).*)?$', f)
        if m: return m[1].rstrip('.').replace('. ', ', ', 1).replace('Meteor from Coahuila', 'Coahuila meteorite')
        m = re.match(r'(.+?) HMNH ?\d', f)
        if m: return m[1]
    f = re.sub(r'\s*\((DerHexer|\d{6,}|\d{3,5}|Harvard University|00\d+|\d+-366)\).*$', '', f)
    f = re.sub(r'\s*-?\s*(at the )?Harvard (Museum of )?Natural History( Museum)?(\s*-\s*Sept\. 2008)?', '', f)
    f = re.sub(r'\s*(HMCZ|MCZ|Harvard|HMNH)\s*$', '', f).replace('()', '').strip(' -,.')
    return f or d[:80]


DESCS = {
    'Kronosaurus queenslandicus': 'The Kronosaurus: a 42-foot (13 m) marine reptile skeleton, excavated on a Harvard '
                                  'expedition to Australia in 1931.',
    'Kronosaurus': 'The Kronosaurus, a giant marine reptile from the Early Cretaceous of Australia.',
    'Kronosaurus skull': 'The head of the Kronosaurus, a giant marine reptile from the Early Cretaceous of Australia.',
}


def build_works(floors):
    rooms = {r['id']: r['name'] for r in floors['floors'][0]['rooms']}
    p = CACHE / 'files.json'
    if not p.exists(): raise SystemExit('run tools/harvest_hmnh.py first')
    rows = json.loads(p.read_text())
    works, seen = [], set()
    for r in rows:
        gal, kind, sure = classify(r)
        if gal is None or kind is None: continue
        title = title_of(r, kind)
        key = 'hmnh-' + re.sub(r'[^a-z0-9]+', '-', r['file'].lower().rsplit('.', 1)[0]).strip('-')[:70]
        if key in seen: continue
        seen.add(key)
        img = picture(key, r['file'])
        if not img: continue
        desc = DESCS.get(title, (r.get('description') or '').strip())
        if re.search(r'(?i)harvard university, cambridge, ma|^bos_|366 project|^Day \d+\.|^Interior of the Harvard', desc): desc = DESCS.get(title, '')
        if desc.lower().rstrip('.') in ('harvard museum of natural history', title.lower()): desc = ''
        a = {'id': key, 'title': title, 'artist': kind, 'description': desc[:1200],
             'url': 'https://commons.wikimedia.org/wiki/File:' + quote(r['file'].replace(' ', '_')),
             'image': img, 'gallery': gal, 'galleryName': rooms[gal], 'floor': '3',
             'imageCredit': f"Photo: {r.get('author') or 'Wikimedia Commons'}"
                            f"{', ' + r['license'] if r.get('license') else ''} (Wikimedia Commons)",
             'placeNote': 'Where the museum’s plan puts this kind of display.' if sure else
                          'Placed by guess: the photo doesn’t say which gallery it was taken in.'}
        if r.get('date'): a['date'] = 'photographed ' + r['date'].split(',')[0]
        if not sure: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    used = {Path(a['image']).name for a in works}
    for f in (OUT / 'images').glob('*.jpg'):
        if f.name not in used: f.unlink()
    order = {r['id']: i for i, r in enumerate(floors['floors'][0]['rooms'])}
    works.sort(key=lambda a: (order[a['gallery']], a['artist'], a['title']))
    return {'source': 'Photos from Wikimedia Commons, placed on the HMSC floor plan (2023)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = [{k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'url': a['url'],
             'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'], 'floor': a['floor']}.items()
             if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Wikimedia Commons photos taken in the galleries; floor plan from the HMSC wayfinding brochure',
            'onViewKnown': True,
            'note': 'Harvard’s natural history collections hold over 21 million specimens; a small part is on view. '
                    'The museum’s website and databases can’t be read by this guide, so listed here are things '
                    'visitors photographed in the galleries and shared with a free licence, in the gallery where '
                    'they are shown. Photos are of different years, so a few may have moved.',
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
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} things with pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
