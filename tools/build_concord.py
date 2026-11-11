#!/usr/bin/env python3
"""Build the Concord Museum (Concord, MA) map guide (run: python3 tools/build_concord.py).

    data/concord/floors.json       the First and Second Floors, seen from above (flat 2D)
    data/concord/artworks.json     what is on view, placed in its gallery
    data/concord/images/           pictures, made smaller for phones
    data/guides/Q5158830.json      the same list, plus collection objects that may be in storage, for the museum page

Where the information comes from
--------------------------------
The rooms are traced from the museum's own floor plans in its Bloomberg Connects guide (read in the app on Nov 11
2026; run with --floors-only to redraw the map and move the saved works without downloading again). Coordinates are
pixels of the first-floor plan picture; up() fits the second-floor picture onto it. One room name on the first floor
was hidden in our copy ("To Set the World …"); it is shown as the Transcendentalist authors gallery, its subject on
the museum's What's On page. The older galleries' ids are moved to the plan's rooms by MOVED.

Works: concord.emuseum.com (the museum's online collection) disallows Claude's crawlers in robots.txt, so it is not
read. Objects come from Wikimedia Commons: Daderot's photos of December 2014 (public domain / CC0), Clare Richardson's
2012 Thoreau furniture photos and Lparker04's July 2026 photos, each placed in the gallery whose subject matches it
(approximate). Many of Daderot's photos show the 2014-15 show "Behind Closed Doors: Asleep in New England"; those
objects are listed on the museum page as collection objects, not placed on the map. Current shows and the gallery
pictures come from concordmuseum.org (WordPress; robots.txt asks for 10 s between requests).
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
OUT = ROOT / 'data' / 'concord'
CACHE = ROOT / '.cache' / 'concord'
MUSEUM = 'Q5158830'
NAME = 'Concord Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://concordmuseum.org/'
WHATS_ON = SITE + 'whats-on/'
UP = SITE + 'wp-content/uploads/'
COMMONS = 'Wikimedia Commons'
TODAY = date.today()
X0, Y0, U = 0, 60, 1.6      # map units = (pixel of the museum's first-floor plan - origin) x 1.6


def P(x, y):
    return [round((x - X0) * U, 1), round((y - Y0) * U, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def up(pts):
    """Second-floor plan pixels -> first-floor plan pixels (the two pictures differ a little in scale)."""
    return [((x + 46) / 1.062, (y + 36.8) / 1.12) for x, y in pts]


# ---- First Floor (traced from the museum's own plan in its Bloomberg Connects guide) -----------------------------
FIRST = [
    # id, kind, name shown, polygon, short label
    ('Emerson’s Study', 'gallery', 'Emerson’s Study', rect(135, 175, 250, 268), 'Emerson’s Study'),
    ('Thoreau Gallery', 'gallery', 'Thoreau Gallery: his flute, spyglass, bed and tools', rect(65, 268, 185, 370),
     'Thoreau Gallery'),
    ('Thoreau’s Desk', 'gallery', 'Thoreau’s Desk', rect(185, 268, 258, 355), 'Thoreau’s Desk'),
    ('Poetry Passageway', 'corridor', 'Poetry Passageway', rect(35, 370, 195, 410), None),
    ('Stairs West 1', 'corridor', 'Stairs to the 2nd floor', rect(195, 355, 258, 425), None),
    ('Getting a Living', 'gallery', 'Getting a Living: farms, work and the town’s people', rect(65, 410, 185, 490),
     'Getting a Living'),
    ('Thomas Dugan Gallery', 'gallery', 'Thomas Dugan Gallery: the farmer Thomas Dugan and the silversmith’s shop',
     rect(185, 425, 265, 490), 'Thomas Dugan'),
    ('1775 Period Room', 'gallery', '1775 Period Room: a family on the eve of April 19', rect(135, 490, 260, 630),
     '1775 Period Room'),
    ('1720 Period Room', 'gallery', '1720 Period Room: a magistrate’s parlor', rect(265, 465, 380, 560),
     '1720 Period Room'),
    ('Transcendentalist Authors', 'gallery', 'Celebrated Transcendentalist Authors',
     [(258, 225), (360, 222), (365, 310), (258, 315)], 'Authors'),
    ('Incorporating Concord', 'gallery', '1600’s Gallery: Incorporating Concord',
     [(360, 222), (470, 200), (480, 228), (460, 300), (365, 310)], '1600’s Gallery'),
    ('Elevator hall', 'corridor', 'Elevator and ramp', [(428, 135), (600, 105), (612, 205), (480, 228), (470, 200),
                                                        (440, 205)], None),
    ('At the Center of Revolution', 'gallery', 'Concord: At the Center of Revolution (introductory gallery)',
     [(480, 228), (612, 205), (610, 345), (488, 345), (460, 300)], 'At the Center of Revolution'),
    ('Musketaquid Gallery', 'gallery', 'People of Musketaquid: Indigenous history and art',
     [(600, 108), (697, 108), (697, 345), (610, 345), (612, 205)], 'People of Musketaquid'),
    ('Courtyard', 'space', 'Courtyard', [(258, 315), (365, 310), (460, 300), (488, 345), (488, 455), (380, 455),
                                         (380, 465), (265, 465), (265, 425), (258, 425)], None),
    ('Brooke Hall', 'corridor', 'Brooke Hall', [(488, 345), (697, 345), (697, 455), (575, 455), (575, 560),
                                                 (488, 560)], None),
    ('Restrooms', 'space', 'Restrooms (accessible, with changing table)', rect(380, 455, 488, 560), None),
    ('Lobby', 'corridor', 'Main Entrance · coat rack', rect(410, 560, 575, 640), None),
    ('Gateway', 'space', 'Admission Desk and Museum Shop', rect(575, 455, 697, 630), None),
]
FIRST_CLOSED = []
FIRST_DOORS = [('Emerson’s Study', 'Thoreau’s Desk', (220, 268)), ('Thoreau Gallery', 'Thoreau’s Desk', (185, 300)),
               ('Thoreau Gallery', 'Poetry Passageway', (125, 370)), ('Poetry Passageway', 'Getting a Living', (125, 410)),
               ('Poetry Passageway', 'Stairs West 1', (195, 390)), ('Thoreau’s Desk', 'Stairs West 1', (225, 355)),
               ('Stairs West 1', 'Thomas Dugan Gallery', (225, 425)), ('Getting a Living', 'Thomas Dugan Gallery', (185, 455)),
               ('Getting a Living', '1775 Period Room', (160, 490)), ('Thomas Dugan Gallery', '1720 Period Room', (265, 478)),
               ('1775 Period Room', '1720 Period Room', (262, 540)), ('Thoreau’s Desk', 'Transcendentalist Authors', (258, 290)),
               ('Transcendentalist Authors', 'Incorporating Concord', (362, 265)),
               ('Incorporating Concord', 'Elevator hall', (455, 205)),
               ('Elevator hall', 'At the Center of Revolution', (530, 215)),
               ('Elevator hall', 'Musketaquid Gallery', (606, 160)),
               ('At the Center of Revolution', 'Musketaquid Gallery', (611, 280)),
               ('At the Center of Revolution', 'Brooke Hall', (550, 345)), ('Musketaquid Gallery', 'Brooke Hall', (650, 345)),
               ('1720 Period Room', 'Restrooms', (380, 510)), ('Brooke Hall', 'Restrooms', (488, 500)),
               ('Brooke Hall', 'Lobby', (530, 560)), ('Brooke Hall', 'Gateway', (575, 520)), ('Lobby', 'Gateway', (575, 600))]
FIRST_AMEN = [('entrance', 505, 635), ('info', 640, 560), ('shop', 640, 600), ('coat', 450, 605),
              ('restroom', 405, 490), ('restroom-all', 435, 490), ('nursing', 465, 490), ('elevator', 528, 145),
              ('stairs', 225, 405), ('stairs', 660, 480)]
FIRST_LABELS = []
FIRST_NOTES = [('Main Entrance', 505, 665)]

# ---- Second Floor ----------------------------------------------------------------------------------------------
SECOND = [
    ('April 19, 1775', 'gallery', 'April 19, 1775 (Paul Revere’s lantern)', up(rect(25, 272, 148, 532)),
     'April 19, 1775'),
    ('Concord Minute Man', 'gallery', 'The Concord Minute Man', up(rect(148, 272, 232, 368)), 'Minute Man'),
    ('Stairs West 2', 'corridor', 'Stairs to the 1st floor', up(rect(148, 368, 232, 440)), None),
    ('Revolution at Home', 'gallery', 'The Revolution at Home', up(rect(148, 440, 232, 532)), 'Revolution at Home'),
    ('Midnight Ride Passageway', 'corridor', 'Midnight Ride Passageway',
     up([(205, 242), (430, 222), (445, 262), (360, 292), (232, 292), (232, 272), (205, 272)]), None),
    ('Elevator hall 2', 'corridor', 'Elevator', up([(425, 120), (600, 80), (585, 200), (445, 212)]), None),
    ('The Work of Art', 'gallery', 'The Work of Art: clocks, furniture, needlework and silver',
     up([(445, 212), (585, 200), (600, 322), (490, 345), (460, 262), (445, 262), (430, 222)]), 'The Work of Art'),
    ('History Learning Center', 'space', 'The History Learning Center (open by appointment only)',
     up([(600, 80), (630, 205), (652, 315), (600, 322), (585, 200)]), None),
    ('Passage 2', 'corridor', 'Hall to the Special Exhibit Gallery', up(rect(490, 345, 522, 530)), None),
    ('Stairs East 2', 'corridor', 'Stairs to the 1st floor', up(rect(522, 470, 700, 530)), None),
    ('Special Exhibit Gallery', 'gallery', 'Special Exhibit Gallery (Wallace Kane Gallery)',
     up(rect(402, 530, 702, 662)), 'Special Exhibit Gallery'),
]
SECOND_CLOSED = []
SECOND_DOORS = [(a, b, up([p])[0]) for a, b, p in [
    ('April 19, 1775', 'Concord Minute Man', (148, 320)), ('April 19, 1775', 'Stairs West 2', (148, 404)),
    ('April 19, 1775', 'Revolution at Home', (148, 486)), ('Stairs West 2', 'Concord Minute Man', (190, 368)),
    ('Stairs West 2', 'Revolution at Home', (190, 440)), ('Concord Minute Man', 'Midnight Ride Passageway', (218, 272)),
    ('Midnight Ride Passageway', 'The Work of Art', (440, 245)), ('The Work of Art', 'Elevator hall 2', (520, 206)),
    ('The Work of Art', 'History Learning Center', (592, 260)), ('The Work of Art', 'Passage 2', (506, 340)),
    ('Passage 2', 'Special Exhibit Gallery', (506, 530)), ('Passage 2', 'Stairs East 2', (522, 500)),
    ('Stairs East 2', 'Special Exhibit Gallery', (610, 530))]]
SECOND_AMEN = [(t, *up([(x, y)])[0]) for t, x, y in [('elevator', 533, 120), ('stairs', 193, 422), ('stairs', 655, 520)]]
SECOND_LABELS = []
SECOND_NOTES = []

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
         'doors': [{'a': a, 'b': b, 'at': P(*at), 'width': 16, 'axis': 'o'} for a, b, at in doors]}
    for a in f['amenities']:
        assert any(inside(a['at'], r['poly']) for r in rooms), (fid, a)
    return f


def build_floors():
    floors = [
        floor('1', 'First Floor', 0, 'Main Entrance, Admission Desk and Museum Shop, Brooke Hall, restrooms, '
              'elevator; At the Center of Revolution, People of Musketaquid, the 1600’s Gallery, Emerson’s Study, '
              'Thoreau, Getting a Living, Thomas Dugan, the 1720 and 1775 Period Rooms', FIRST, FIRST_CLOSED,
              FIRST_DOORS, FIRST_AMEN, FIRST_LABELS, FIRST_NOTES),
        floor('2', 'Second Floor', 1, 'April 19, 1775 (Paul Revere’s lantern), The Concord Minute Man, The Revolution '
              'at Home, the Midnight Ride Passageway, The Work of Art, the Special Exhibit Gallery', SECOND,
              SECOND_CLOSED, SECOND_DOORS, SECOND_AMEN, SECOND_LABELS, SECOND_NOTES),
    ]
    return {'about': 'Built by tools/build_concord.py. Rooms traced from the Concord Museum’s own floor plans in its '
                     'Bloomberg Connects guide (Nov 2026).',
            'source': 'Concord Museum floor plans in its Bloomberg Connects guide (Nov 2026)',
            'units': 'plan pixels x 1.6, north up', 'defaultFloor': '1',
            'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def fetch(url, dest, pause=3):
    if dest.exists() and dest.stat().st_size > 3000: return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 20, 60, 120):
        time.sleep(wait or pause)
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.stat().st_size > 3000: return True
        dest.unlink(missing_ok=True)
    return False


def picture(key, src):
    """src: a Commons file name, or ('site', path under wp-content/uploads/)."""
    if not src: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/concord/images/{key}.jpg'
    if dest.exists(): return rel
    raw = CACHE / 'img' / (key + '.bin')
    if isinstance(src, tuple):
        ok = fetch(UP + src[1], raw, pause=10)                     # concordmuseum.org: Crawl-delay 10
    else:
        ok = fetch('https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(src) + '?width=1000',
                   raw)
    if not ok:
        print(f'  no picture: {src}')
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(raw.read_bytes()))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return rel


# ---- Commons objects -----------------------------------------------------------------------------------------------
# Daderot's file names read "Title, place, date, materials - Concord Museum - Concord, MA - DSC0xxxx.JPG".
# PLACE: a piece of the file name -> the gallery it is shown in (by subject: APPROXIMATE). Objects not listed here
# are collection objects (many from the 2014-15 show Behind Closed Doors), shown on the museum page only.
PLACE = [
    ('Native American artifacts', 'Musketaquid Gallery'),
    ('Deed, 1649', 'Incorporating Concord'), ('Joined cupboard', 'Incorporating Concord'),
    ('Cradle, Massachusetts, 1665', 'Incorporating Concord'), ('Money scales', 'Incorporating Concord'),
    ('Hourglass, England, 1659', 'Incorporating Concord'), ('Interior door, New England, 1600s', 'Incorporating Concord'),
    ('Charger, London', 'Incorporating Concord'), ('Jug, Germany', 'Incorporating Concord'),
    ("Ralph Waldo Emerson's study", 'Emerson’s Study'),
    ('Ralph Waldo Emerson by Daniel Chester French', 'Emerson’s Study'),
    ('Desk at Walden Pond', 'Thoreau’s Desk'),
    ('Furniture from the house at Walden. Bedstead', 'Thoreau Gallery'),
    ('Furniture from the house at Walden. Chair and desk', 'Thoreau’s Desk'),
    ('Rocking chair at Walden Pond', 'Thoreau Gallery'), ('Flute owned by Henry David Thoreau', 'Thoreau Gallery'),
    ('Spyglass owned', 'Thoreau Gallery'), ('Snowshoes and spyglass', 'Thoreau Gallery'),
    ('Surveying chain', 'Thoreau Gallery'), ('Drafting tools owned', 'Thoreau Gallery'),
    ('T-square owned', 'Thoreau Gallery'), ('Straight-edge owned', 'Thoreau Gallery'),
    ('Pencil, perhaps made by Henry', 'Thoreau Gallery'), ('Sheet of uncut William Munroe pencil labels',
                                                              'Thoreau Gallery'),
    ('Cash box, labels, and pencils', 'Thoreau Gallery'), ('Box for geological specimens', 'Thoreau Gallery'),
    ('Aeolian harp', 'Thoreau Gallery'), ('Birch tree tap', 'Thoreau Gallery'),
    ('Last pen owned by Henry', 'Thoreau Gallery'), ('Henry David Thoreau by Walton Ricketson', 'Thoreau Gallery'),
    ('Cell Lock', 'Thoreau Gallery'), ('Thoreau Family Furniture (01)', 'Thoreau Gallery'),
    ('Looking glass owned by Sophia Thoreau', 'Thoreau Gallery'), ('Thoreau fire bucket', 'Thoreau Gallery'),
    ('Copper Tea Kettle', 'At the Center of Revolution'),
    ('Tell about the party', 'Transcendentalist Authors'),
    ('The Bloody Massacre', 'April 19: The Alarm'), ('Revere Lantern', 'April 19: The Alarm'),
    ('Old North Bridge diorama', 'April 19: North Bridge'), ('Beam end from Old North Bridge', 'April 19: North Bridge'),
    ('Peg from Old North Bridge', 'April 19: North Bridge'), ('Pair of pistols owned by Major John Buttrick', 'April 19: North Bridge'),
    ('Naval cutlass owned by Col. James Barrett', 'April 19: North Bridge'), ('Powder horn, owned by Amos Barrett',
                                                                        'April 19: North Bridge'),
    ("Powder horn, engraved 'Jonathan Gardner", 'April 19: Road to Boston'),
    ('The Concord Minuteman of 1775', 'April 19: Road to Boston'), ('Dance card, Grand Centennial', 'April 19: Road to Boston'),
    ('Ribbons, Grand Centennial', 'April 19: Road to Boston'),
    ('Period room, c. 1725', '1720 Period Room'),
    ('A View of the Town of Concord', 'Life in Concord'), ('Muskets and rifles from shop of Alvan Pratt', 'Life in Concord'),
    ('Barrett fire bucket', 'Life in Concord'), ('Uncle Tom and Eva', 'Life in Concord'),
    ('Asparagus cutter', 'Life in Concord'), ('Milk pail', 'Life in Concord'),
    ('Rocking chair, Allen Chair Company', 'Life in Concord'), ('Concord Souvenir China', 'Life in Concord'),
    ("Ebenezer Rockwood Hoar's dinner for President Grant", 'Life in Concord'),
    ('Model 1832 Artillery Sword', 'Life in Concord'), ('Autobiography by William Munroe', 'Life in Concord'),
    ('Household inventory, Concord', 'Life in Concord'), ('Plate, Concord, c. 1780', 'Life in Concord'),
    ('Creampot, Samuel Bartlett', 'Milldam and Farm'), ('Strainer, Samuel Bartlett', 'Milldam and Farm'),
    ('Teaspoons, Samuel Bartlett', 'Milldam and Farm'), ('Flagon marked by Samuel Bartlett', 'Milldam and Farm'),
    ('Footed cup, marked by Samuel Bartlett', 'Milldam and Farm'), ('Silver by Samuel Bartlett', 'Milldam and Farm'),
    ('Chest-on-chest, attributed to Joseph Hosmer', 'Gross Family Gallery'),
    ("High chest, Barrett's Mill Shop", 'Gross Family Gallery'),
    ('High chest owned by William Emerson', 'Gross Family Gallery'),
    ('High chest, Concord, 1760', 'Gross Family Gallery'), ('High chest, Concord, 1770', 'Gross Family Gallery'),
    ('Eight-day clock by Nathaniel Munroe', 'Gross Family Gallery'),
    ('Eight-Day Clock, Daniel Munroe & William Munroe', 'Gross Family Gallery'),
    ('Timepiece by Daniel Munroe', 'Gross Family Gallery'), ('Patent timepiece by Lemuel Curtis', 'Gross Family Gallery'),
    ('Longcase clock by Nathaniel Edwards', 'Gross Family Gallery'),
    ('Marking sampler, Adeline Hunt', 'Gross Family Gallery'), ('Marking sampler, Sarah A. Stow', 'Gross Family Gallery'),
    ('Cann marked by Jacob Hurd', 'Gross Family Gallery'), ('Caudle cup, marked by John Coney', 'Gross Family Gallery'),
]
SKIP = ('Concord Museum (Concord, MA)', 'Concord Museum Exterior', 'Museo Concord', 'Cambridge Turnpike',
        'Annie Leibovitz', 'Furniture from the house at Walden.jpg', 'Concord Museum items', 'Clockworks, unidentified',
        'Unidentified mirror', 'Lantern hung in the Old North Church', 'Lantern flashed from belfry',
        'Jonathan Gardner Powder horn 1776 at the Concord', 'Furniture at Walden Pond owned', 'Thoreau Family Furniture (02)',
        'Mugs for children')
NOTES = {   # a few words more where the file name says little
    'Revere Lantern': ('Lantern from Paul Revere’s ride', 'Boston', 'about 1775', 'Tin, glass',
                       'One of the two lanterns hung in the steeple of Christ Church (the Old North Church) in Boston on '
                       'the night of April 18, 1775: “one if by land, two if by sea.” The signal told the riders the '
                       'Regulars were crossing the river to march on Concord.'),
    'Cell Lock': ('Lock from Thoreau’s jail cell', 'Concord', '1840s', 'Iron',
                  'The lock from the Middlesex County jail where Thoreau spent a night in July 1846 for refusing to pay '
                  'his poll tax, in protest against slavery and the war with Mexico: the night behind his essay '
                  '“Civil Disobedience.”'),
    'Copper Tea Kettle': ('Louisa May Alcott’s tea kettle', None, '1862', 'Copper',
                          'The kettle Louisa May Alcott used while she worked as a Union Army nurse in Washington, '
                          'D.C., during the Civil War. One of the fourteen “iconic artifacts” in the introductory '
                          'gallery.'),
    "Ralph Waldo Emerson's study": ('Ralph Waldo Emerson’s study', 'Concord', 'as it was in 1882', None,
                                    'The furniture, books and pictures of Emerson’s study, moved from his house across '
                                    'the road and arranged as they were when he died in 1882. Emerson wrote here for '
                                    'almost fifty years; a touch screen tells who came to visit him.'),
    'Desk at Walden Pond': None, 'Native American artifacts': ('Stone tools of Musketaquid', 'Concord area',
                                                               'up to 12,000 years old', 'Stone',
                                                               'Stone points and tools found in Concord, the land the '
                                                               'Native people called Musketaquid. The gallery shows '
                                                               '600 of them in a glass wall arranged in a Native '
                                                               'design.'),
    'Furniture from the house at Walden. Bedstead': ('Thoreau’s bed from Walden Pond', 'Concord', '1845–47', 'Wood',
                                                     'The bed Henry David Thoreau slept in at his cabin by Walden Pond.'),
    'Furniture from the house at Walden. Chair and desk': ('Thoreau’s chair and desk from Walden Pond', 'Concord',
                                                           '1845–47', 'Painted wood',
                                                           'The desk and chair from the one-room cabin where Thoreau '
                                                           'wrote the first drafts of Walden.'),
    'Thoreau Family Furniture (01)': ('Thoreau family furniture', 'Concord', '1800s', 'Wood',
                                      'A work table, painted side chair and desk from the Thoreau family house.'),
    'Period room, c. 1725': ('1720 Period Room', 'Concord', 'about 1720–1725', None,
                             'A parlor of the 1720s, where a wealthy magistrate welcomed visitors, with its furniture '
                             'and woodwork.'),
}


DATE = re.compile(r'^(?:[A-Z][a-z]+ \d{1,2} )?(?:c\. |about |after |early |mid |late |mid to late )?'
                  r'(?:\d{4}(?:-\d{4})?s?|1[6-9]00s|\d{2}th century)(?: printing)?$')
MAKER = re.compile(r'\b(?:made by|marked by|attributed to|attrib to|by) ([A-Z][A-Za-z.&\' ]+?(?:,? Jr\.)?)'
                   r'(?: \(?\d{4}-\d{4}\)?)?(?: shop| and | with|,|$)')


def parse(fname):
    """-> title, maker, place, date, medium, caption (the whole description, cleaned)."""
    base = fname[5:] if fname.startswith('File:') else fname
    base = re.sub(r'\.(jpe?g|png)$', '', base, flags=re.I)
    base = re.split(r',?\s*-?\s*Concord Museum|\s*at the Concord Mass Museum', base)[0].strip(' -,')
    base = re.sub(r',? (?:view \d|\d of \d)\b', '', base)
    base = re.sub(r'\b([A-Z][a-z]+ \d{1,2}), (\d{4})', r'\1 \2', base)          # "April 19, 1875"
    parts = [p.strip() for p in base.split(', ')]
    di = next((i for i, p in enumerate(parts) if i and DATE.match(p)), None)
    title, place, when, medium = parts[0], None, None, None
    if di is not None:
        when = parts[di]
        medium = ', '.join(parts[di + 1:]) or None
        if di > 1:
            place = parts[di - 1]
            title = ', '.join(parts[:di - 1])
    m = MAKER.search(base)
    maker = m.group(1).strip() if m and 'owned by' not in base[:m.start() + 9] else None
    caption = base.replace(' attrib ', ' attributed ')
    return title, maker, place, when, medium, caption


def credit_of(meta):
    a = re.sub(r'<[^>]+>', '', meta.get('Artist') or '').replace('MyName (Daderot)', 'Daderot').strip()
    lic = meta.get('LicenseShortName') or ''
    return f'photo by {a} ({"public domain" if lic in ("Public domain", "CC0") else lic}), via {COMMONS}'


def commons_objects():
    files = json.load(open(CACHE / 'commons.json'))
    meta = json.load(open(CACHE / 'commons-meta.json'))
    seen, objs = set(), []
    for _, f in sorted(files, key=lambda c: c[1]):
        if f in seen: continue
        seen.add(f)
        if any(s in f for s in SKIP): continue
        title, maker, place, when, medium, caption = parse(f)
        room = next((r for k, r in PLACE if k in f), None)
        note = next((v for k, v in NOTES.items() if k in f), None)
        text = None
        if note:
            title, place, when, medium, text = note
        key = re.sub(r'[^a-z0-9]+', '-', (title + ' ' + (when or '') + ' ' + (medium or '')).lower()).strip('-')[:56]
        if any(o['key'] == key for o in objs): continue      # another view of the same object
        m = meta.get(f, {})
        desc = re.sub(r'<[^>]+>', '', m.get('ImageDescription') or '').strip()
        if not text and desc and not desc.startswith(('Exhibit in the Concord Museum', 'Concord Museum items')) \
                and len(desc) > 40:
            text = desc
        if not text and caption != title:
            text = caption + '.'
        objs.append({'key': key, 'file': f[5:], 'title': title, 'maker': maker, 'place': place, 'date': when,
                     'medium': medium, 'text': text, 'room': room, 'credit': credit_of(m)})
    return objs


# ---- shows and galleries -------------------------------------------------------------------------------------------
# (key, gallery, title, maker, date, medium, text, picture, url, credit, temporary (from, to) or None)
SHOWS = [
    ('dion', 'Wallace Kane Gallery', 'Mark Dion: Eccentric Collectors Like Us', 'Exhibition',
     'Oct 9, 2026 – Mar 7, 2027', None,
     'The artist Mark Dion turns the special-exhibition gallery into a cabinet of curiosities inspired by Cummings E. '
     'Davis, the eccentric Concord collector whose objects started the museum: quirky portraits and engravings, '
     'weathervanes, a barber’s sign and dozens of objects rarely or never shown before. Instead of labels you get a '
     'Field Guide, and a hands-on installation invites you into the work of collecting.',
     ('site', '2026/09/Dion-and-Davis.png'), SITE + 'event/mark-dion-eccentric-collectors-like-us/',
     'Concord Museum', ('2026-10-09', '2027-03-07')),
    ('family-trees', 'Lyceum', 'Family Trees: A Celebration of Children’s Literature', 'Holiday installation',
     'Nov 21, 2026 – Jan 3, 2027', None,
     'Dozens of story trees decorated by local volunteers, each bringing a picture book to life, with a scavenger hunt '
     'and books to read together. The trees fill the museum; where exactly they stand is not on the map. Special '
     'ticket prices apply while it is on, and the museum also opens on Mondays in December.',
     ('site', '2026/10/Family-Trees-2026-1024x647.png'), SITE + 'event/family-trees-2026/', 'Concord Museum',
     ('2026-11-21', '2027-01-03')),
    ('paddle-strong', 'Musketaquid Gallery', 'Chemacheg Menuhki: Paddle Strong', 'Brittney Peauwe Wunnepog Walley (Nipmuc), '
     'co-curator', None, None,
     'Regional Indigenous history and contemporary textile arts, with a fibre basket woven by Walley: a celebration '
     'of the continued presence and resilience of Indigenous communities today.',
     ('site', '2025/02/Paddle-Strong-1732-x-1100.png'), WHATS_ON + '#ongoing-exhibitions', 'Concord Museum', None),
    ('musketaquid', 'Musketaquid Gallery', 'Musketaquid Gallery', 'Gallery', None, None,
     'The history and contemporary art of the Indigenous communities who have shaped this region for 12,000 years. '
     'Its centrepiece is a glass wall of 600 stone tools arranged in a Native design.',
     ('site', '2025/01/tile-image_ongoing-exhibitions_musketaquid-gallery.png'), WHATS_ON + '#ongoing-exhibitions',
     'Concord Museum', None),
    ('center-of-revolution', 'At the Center of Revolution', 'Concord: At the Center of Revolution', 'Introductory gallery',
     'since 2019', None,
     'Fourteen iconic objects that give a first “brush” with Concord’s history, from Louisa May Alcott’s Civil War tea '
     'kettle to Abner Hosmer’s powder horn: the place to start your visit.', None,
     'https://www.discoverconcordma.com/articles/517-concord-museum-unveils-an-innovative-new-experience', None, None),
    ('authors', 'Transcendentalist Authors', 'Celebrated Transcendentalist Authors', 'Galleries', None, None,
     'The world of Concord’s writers: the Alcotts, Hawthorne, Emerson and Thoreau, their friendships, their social '
     'world and their political activism.',
     ('site', '2025/01/tile-image_ongoing-exhibitions_celebrated-transcendentalist-authors.png'),
     WHATS_ON + '#ongoing-exhibitions', 'Concord Museum', None),
    ('thoreau-desk', 'Thoreau’s Desk', 'Thoreau’s desk', 'Henry David Thoreau', '1838', 'Painted pine',
     'The plain green desk Thoreau used at Walden Pond, where he wrote much of Walden and A Week on the Concord and '
     'Merrimack Rivers. Stand in front of it for a media presentation drawn from his own words. The museum has the '
     'world’s largest collection of Thoreau’s belongings.',
     'Desk at Walden Pond owned by Henry David Thoreau, Concord, 1838, painted pine - Concord Museum - Concord, MA - '
     'DSC05629.JPG', WHATS_ON + '#ongoing-exhibitions', None, None),
    ('april-19', 'April 19: The Alarm', 'April 19, 1775', 'Galleries', 'since 2020', None,
     'Three galleries on the day the American Revolution began, hour by hour, with dozens of objects that witnessed '
     'it, starting with the lantern from Paul Revere’s ride.',
     ('site', '2025/01/tile-image_ongoing-exhibitions_april-19-1775.png'), WHATS_ON + '#ongoing-exhibitions',
     'Concord Museum', None),
    ('period-1775', '1775 Period Room', '1775 Period Room', 'Period room', None, None,
     'A Concord home on the night before April 19, 1775, as a family secretly prepares for rebellion.',
     ('site', '2026/07/Emerson-study-1700-x-1132-2.png'), WHATS_ON + '#ongoing-exhibitions', 'Concord Museum', None),
    ('period-1720', '1720 Period Room', '1720 Period Room (museum photo)', 'Period room', None, None,
     'A wealthy magistrate’s parlor of the 1720s, set for welcoming visitors.',
     ('site', '2026/07/Emerson-study-1700-x-1132-1.png'), WHATS_ON + '#ongoing-exhibitions', 'Concord Museum', None),
    ('life-in-concord', 'Life in Concord', 'Life in Concord', 'Galleries', None, None,
     'Life in Concord over time through its people’s things, tools and creations: abolition and social justice, '
     'farming and the environment, free and enslaved African Americans, women and children.',
     ('site', '2025/01/tile-image_ongoing-exhibitions_life-in-concord.png'), WHATS_ON + '#ongoing-exhibitions',
     'Concord Museum', None),
    ('milldam', 'Milldam and Farm', 'The silversmith’s shop and Thomas Dugan’s farm', 'Galleries', None, None,
     'A silversmith at work in his shop on the Milldam, Concord’s main street, and Thomas Dugan, a Black yeoman farmer '
     'who was born enslaved in Virginia and owned his own farm in Concord in the 1820s.', None,
     SITE + 'online-exhibition/thomas-dugan-yeoman-of-concord/', None, None),
]
WHERE = {
    'Lyceum': 'Family Trees fills the museum; it is shown here in Brooke Hall, by the entrance.',
}
APPROX = 'In this gallery, as the museum’s own floor plan names it.'


# galleries of the earlier, approximate map -> the rooms on the museum's own plan
MOVED = {'Wallace Kane Gallery': 'Special Exhibit Gallery', 'Lyceum': 'Brooke Hall',
         'April 19: The Alarm': 'April 19, 1775', 'April 19: North Bridge': 'April 19, 1775',
         'April 19: Road to Boston': 'April 19, 1775', 'Life in Concord': 'Getting a Living',
         'Milldam and Farm': 'Thomas Dugan Gallery', 'Gross Family Gallery': 'The Work of Art'}


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    rooms.update({old: rooms[new] for old, new in MOVED.items()})
    works, extra = [], []
    for key, room, title, maker, when, medium, text, pic, url, credit, span in SHOWS:
        if span and date.fromisoformat(span[1]) < TODAY: continue          # closed
        fl, gname = rooms[room]
        img = picture(f'concord-{key}', pic)
        cred = None
        if img:
            cred = credit if isinstance(pic, tuple) else 'photo by Daderot (public domain), via ' + COMMONS
        a = {'id': f'concord-{key}', 'title': title, 'artist': maker, 'date': when, 'medium': medium,
             'description': text if not span or date.fromisoformat(span[0]) <= TODAY
             else f'Opens {when.split(" – ")[0]}. ' + text,
             'gallery': MOVED.get(room, room), 'galleryName': gname, 'floor': fl, 'placeNote': WHERE.get(room, APPROX),
             'url': url, 'image': img, 'imageCredit': cred}
        if span: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    for o in commons_objects():
        if 'Desk at Walden Pond' in o['file']: continue        # it has its own entry (Thoreau's desk)
        img = picture(f'concord-{o["key"]}', o['file'])
        desc = o['text'] or ', '.join(x for x in (o['place'], o['date']) if x) or None
        a = {'id': f'concord-{o["key"]}', 'title': o['title'], 'artist': o['maker'] or o['place'] or 'Concord Museum',
             'date': o['date'], 'medium': o['medium'], 'description': desc,
             'url': SITE, 'image': img, 'imageCredit': o['credit'] if img else None}
        if o['room']:
            fl, gname = rooms[o['room']]
            a.update(gallery=MOVED.get(o['room'], o['room']), galleryName=gname, floor=fl,
                     placeNote='Placed in the gallery for its subject (approximate): the museum’s online '
                               'catalogue can’t be read by this guide, and its galleries change.')
            works.append({k: v for k, v in a.items() if v not in (None, '', [])})
        else:
            extra.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return ({'source': 'Concord Museum: What’s On and exhibition pages; objects photographed in the museum, from '
                       'Wikimedia Commons',
             'checked': TODAY.isoformat(), 'count': len(works), 'complete': False, 'artworks': works}, extra)


def build_guide(works, extra):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in extra]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': on,
                     'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': TODAY.isoformat(),
            'source': 'Concord Museum What’s On pages; Wikimedia Commons (Daderot, Clare Richardson, Lparker04)',
            'onViewKnown': False,
            'note': 'The Concord Museum’s online catalogue (concord.emuseum.com) asks AI tools not to read it, so this '
                    'list is its galleries and current shows plus objects photographed in the museum and shared on '
                    'Wikimedia Commons. Objects marked on view are placed in the gallery for their subject, which is '
                    'approximate; the others were photographed in 2014 (many for a special show) and may be in '
                    'storage.',
            'works': rows}


def floors_only(floors):
    """Move the saved works onto the redrawn map (no downloads)."""
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    path = OUT / 'artworks.json'
    works = json.loads(path.read_text())
    for a in works['artworks']:
        g = MOVED.get(a['gallery'], a['gallery'])
        a['gallery'], (a['floor'], a['galleryName']) = g, rooms[g]
        if a.get('placeNote', '').startswith('Approximate: the museum publishes'): a['placeNote'] = APPROX
        if a['id'] == 'concord-family-trees': a['placeNote'] = WHERE['Lyceum']
    path.write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    gpath = ROOT / 'data' / 'guides' / f'{MUSEUM}.json'
    guide = json.loads(gpath.read_text())
    for w in guide['works']:
        if w.get('gallery'): w['gallery'] = MOVED.get(w['gallery'], w['gallery']); w['floor'] = rooms[w['gallery']][0]
    gpath.write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    if sys.argv[1:2] == ['--floors-only']: return floors_only(floors)
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
