#!/usr/bin/env python3
"""Build the MIT Museum (Cambridge, MA) map guide (run: python3 tools/build_mit.py).

    data/mit/floors.json       the First, Second and Third Floors, seen from above (flat 2D)
    data/mit/artworks.json     what is on view, placed in its gallery
    data/mit/images/           pictures, made smaller for phones
    data/guides/Q6716306.json  the same list for the museum page

Where the information comes from
--------------------------------
The map is the museum's own visitor floor map: "MITMus_Floor_maps_0924.pdf" (three pages, First, Second and Third
Floor, Adobe Illustrator, May 2025), on the museum's file server (mit-museum-cms-files--production.s3.us-east-2
.amazonaws.com). It names every gallery and shows the restrooms, water fountains, elevator, grand stair, Exchange
stair, store, lobby and entrances. Coordinates here are pixels of those pages drawn at 100 dpi (1100 x 850 px), x 2.
The walls and room shapes match the architects' plans (Höweler + Yoon, "Plan Level 2" and "Plan Level 3" on
howeleryoon.com), which give the scale: the building is about 57 m (186 ft) across. So the rooms are not guesses.

What the museum's map does NOT settle: shows change with the museum's "seasons" (TIME 2025-26, OCEANS from Sept 2026),
and the May 2025 map names the shows of that time (Optiker, Gene Cultures, Cosmograph, Sensable Cities). The OCEANS
booklet (Sept 2026, same file server) gives the galleries for its shows: Sensing Oceans in the Henri A. Termeer
Gallery (the 2022 press release puts Gene Cultures, which the map shows in the big west gallery of the Second Floor,
in the Termeer Gallery), Crochet Coral Reef in the "Exchange Gallery" (taken to be the gallery beside The Exchange on
the Second Floor: APPROXIMATE), and Water Lines in the Kurtz Photography Gallery. Where the Starship Enterprise model
and Split | Second are shown is a guess, and the works say so.

mitmuseum.mit.edu itself sits behind a Vercel bot check that refuses curl and WebFetch, so its pages were not read.
Objects come from Wikimedia Commons: photos taken in the new building (Daderot's DSC09xxx series, public domain,
and "Interior of the MIT Museum 2025-10-19"), each placed in the gallery the museum's descriptions put it in.
"""
import io
import json
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'mit'
CACHE = ROOT / '.cache' / 'mit'
MUSEUM = 'Q6716306'
NAME = 'MIT Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
FILES = 'https://mit-museum-cms-files--production.s3.us-east-2.amazonaws.com/'
MAP_PDF = FILES + 'MITMus_Floor_maps_0924.pdf'
OCEANS_PDF = FILES + 'Theme-Booklets/OCEAN_Booklet-DIGITAL.pdf?v=1789480045'
SITE = 'https://mitmuseum.mit.edu/'
K = 2                     # map units are map-page pixels (100 dpi) x 2
S = 0.35                  # transform: map units -> app units
WALK = 0.106              # walking: 0.037 m a unit / 0.35 m a router point
COMMONS = 'Wikimedia Commons'
TODAY = date.today()


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- First Floor ---------------------------------------------------------------------------------------------------
FIRST = [
    # id, kind, name shown, polygon, short label
    ('Lobby', 'space', 'Lobby (free to enter)',
     [(383, 580), (796, 580), (820, 787), (480, 787), (480, 653), (383, 653)], None),
    ('Museum Store', 'space', 'MIT Museum Store', [(622, 360), (767, 343), (794, 580), (622, 580)], None),
    ('Restrooms 1', 'space', 'Restrooms', rect(440, 520, 560, 580), None),
]
FIRST_CLOSED = [
    [(62, 163), (750, 195), (767, 340), (614, 357), (614, 580), (560, 580), (560, 520), (440, 520), (440, 580),
     (383, 580), (383, 787), (62, 787)],            # the rest of the building (not the museum)
    rect(390, 653, 475, 787),                       # staff offices
]
FIRST_DOORS = [('Lobby', 'Museum Store', (700, 578)), ('Lobby', 'Restrooms 1', (520, 578))]
FIRST_AMEN = [('entrance', 795, 625), ('info', 700, 640), ('shop', 705, 470), ('restroom', 463, 550),
              ('restroom', 531, 550), ('elevator', 446, 613), ('stairs', 599, 735)]
FIRST_LABELS = [('MUSEUM ENTRANCE ←', 900, 625), ('Kendall/MIT Red Line station and Main Street', 880, 700),
                ('314 Main Street building (not the museum)', 220, 380)]
FIRST_NOTES = [('Grand stair up to the Second Floor', 599, 670), ('Admission desk', 700, 680)]

# ---- Second Floor --------------------------------------------------------------------------------------------------
SECOND = [
    ('Termeer Gallery', 'gallery', 'Henri A. Termeer Gallery: Sensing Oceans (until Feb 21, 2027)',
     rect(63, 158, 237, 575), 'Sensing Oceans'),
    ('Essential MIT', 'gallery', 'Brit J. and Alex d’Arbeloff Gallery: Essential MIT', rect(63, 581, 368, 787),
     'Essential MIT'),
    ('Exchange Gallery', 'gallery', 'Exchange Gallery: Crochet Coral Reef (until Feb 14, 2027)',
     rect(244, 158, 357, 313), 'Coral Reef'),
    ('The Exchange', 'space', 'The Exchange: the Lee Family Exchange stair, seats for talks, up to the Third Floor',
     rect(364, 158, 552, 313), None),
    ('Maker Hub', 'gallery', 'Maker Hub: hands-on drop-in activities (free with admission)', rect(566, 158, 657, 313),
     'Maker Hub'),
    ('Learning Lab North', 'space', 'Learning Lab (Ulf B. Heide Education Suite)',
     [(660, 158), (790, 158), (800, 313), (660, 313)], None),
    ('Learning Lab', 'space', 'Learning Lab (Ulf B. Heide Education Suite)',
     [(660, 318), (801, 318), (812, 475), (660, 475)], None),
    ('Event Room', 'space', 'Event Room (Phillip A. Sharp Room): open for programs and events',
     [(659, 600), (820, 600), (833, 787), (659, 787)], None),
    ('Hall 2 North', 'corridor', 'Hall by The Exchange', rect(237, 313, 659, 387), None),
    ('Hall 2 West', 'corridor', 'Hall and elevator', [(237, 387), (406, 387), (406, 573), (475, 573), (475, 653),
                                                     (368, 653), (368, 578), (237, 578)], None),
    ('Hall 2 East', 'corridor', 'Hall', rect(625, 387, 659, 653), None),
    ('Grand Stair 2', 'corridor', 'Top of the grand stair: Made to Measure display case',
     [(368, 653), (659, 653), (659, 787), (368, 787)], None),
    ('Restrooms 2', 'space', 'Restrooms and water fountain', rect(406, 387, 625, 572), None),
]
SECOND_CLOSED = [rect(285, 387, 368, 572),        # exhibition wall case
                 [(659, 482), (812, 482), (820, 594), (659, 594)],   # staff offices
                 rect(475, 572, 625, 637)]        # service core
SECOND_DOORS = [('Hall 2 West', 'Termeer Gallery', (237, 480)), ('Hall 2 North', 'Termeer Gallery', (237, 345)),
                ('Hall 2 West', 'Essential MIT', (300, 580)), ('Grand Stair 2', 'Essential MIT', (368, 720)),
                ('Hall 2 North', 'Exchange Gallery', (300, 313)), ('Hall 2 North', 'The Exchange', (420, 313)),
                ('Hall 2 North', 'Maker Hub', (610, 313)), ('Maker Hub', 'Learning Lab North', (659, 240)),
                ('Hall 2 East', 'Learning Lab', (659, 420)), ('Grand Stair 2', 'Event Room', (659, 700)),
                ('Hall 2 North', 'Hall 2 West', (320, 387)), ('Hall 2 North', 'Hall 2 East', (642, 387)),
                ('Hall 2 West', 'Grand Stair 2', (387, 653)), ('Hall 2 East', 'Grand Stair 2', (642, 653)),
                ('Hall 2 North', 'Restrooms 2', (557, 387))]
SECOND_AMEN = [('stairs', 540, 735), ('stairs', 483, 236), ('elevator', 440, 605), ('restroom', 477, 484),
               ('restroom', 513, 484), ('water', 527, 408)]
SECOND_LABELS = []
SECOND_NOTES = [('Grand stair down to the lobby', 540, 770), ('Exchange stair up to the Third Floor', 483, 290),
                ('Made to Measure', 555, 645)]

# ---- Third Floor ---------------------------------------------------------------------------------------------------
THIRD = [
    ('Lee Family Exchange', 'space', 'Yuchun and Agustina Lee Family Exchange: top of the Exchange stair, media wall',
     rect(364, 158, 563, 313), None),
    ('Exchange Landing', 'corridor', 'Exchange landing', rect(563, 158, 632, 313), None),
    ('Gruber Gallery', 'gallery', 'Martin J. and Eleanor C. Gruber Gallery: changing exhibitions',
     [(632, 158), (790, 158), (801, 313), (680, 313), (680, 288), (632, 288)], 'Gruber'),
    ('AI: Mind the Gap', 'gallery', 'AI: Mind the Gap',
     [(632, 288), (680, 288), (680, 318), (801, 318), (818, 572), (632, 572)], 'AI'),
    ('Exchange Hall', 'corridor', 'Hall by the Exchange (a changing display)', rect(358, 313, 632, 387), None),
    ('Hall 3 West', 'corridor', 'Hall and elevator', [(358, 387), (406, 387), (406, 573), (475, 573), (475, 655),
                                                     (358, 655)], None),
    ('Restrooms 3', 'space', 'Restrooms and water fountain', rect(406, 387, 625, 572), None),
    ('Thorp Collections Gallery', 'gallery', 'Edward O. Thorp Collections Gallery: MIT Collects',
     [(364, 655), (482, 655), (482, 578), (710, 578), (710, 787), (364, 787)], 'MIT Collects'),
    ('Kurtz Gallery', 'gallery', 'Ronald A. and Carol S. Kurtz Photography Gallery',
     [(715, 578), (818, 578), (833, 787), (715, 787)], 'Kurtz'),
    ('Collections Workshop', 'space', 'Ann Chase Allen Collections Workshop (classes; visible from the gallery)',
     rect(244, 655, 358, 787), None),
]
THIRD_CLOSED = [[(62, 158), (358, 158), (358, 650), (237, 650), (237, 787), (62, 787)],   # staff offices
                rect(475, 572, 625, 578)]
THIRD_DOORS = [('Lee Family Exchange', 'Exchange Hall', (460, 313)), ('Exchange Landing', 'Exchange Hall', (595, 313)),
               ('Lee Family Exchange', 'Exchange Landing', (563, 240)), ('Exchange Landing', 'Gruber Gallery', (632, 230)),
               ('Exchange Hall', 'AI: Mind the Gap', (632, 350)), ('Exchange Hall', 'Hall 3 West', (380, 387)),
               ('Exchange Hall', 'Restrooms 3', (557, 387)), ('Hall 3 West', 'Thorp Collections Gallery', (385, 655)),
               ('AI: Mind the Gap', 'Thorp Collections Gallery', (670, 575)),
               ('AI: Mind the Gap', 'Kurtz Gallery', (760, 575)), ('Thorp Collections Gallery', 'Kurtz Gallery', (712, 700)),
               ('Thorp Collections Gallery', 'Collections Workshop', (361, 720)),
               ('Gruber Gallery', 'AI: Mind the Gap', (740, 316))]
THIRD_AMEN = [('stairs', 503, 236), ('elevator', 440, 605), ('restroom', 477, 484), ('restroom', 513, 484),
              ('water', 527, 408)]
THIRD_LABELS = []
THIRD_NOTES = [('Exchange stair down to the Second Floor', 503, 290)]


def pt(x, y):
    return [round(x * K, 1), round(y * K, 1)]


def poly(q):
    return [pt(x, y) for x, y in q]


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
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': poly(pg)}
        if short: r['label'] = short
        rooms.append(r)
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), fid
    for a, b, at in doors:
        assert a in ids and b in ids, (fid, a, b)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [S, 0, 0], 'walkScale': WALK, 'area': area_text,
         'rooms': rooms, 'closed': [{'poly': poly(c)} for c in closed],
         'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': pt(x, y)} for t, x, y in labels],
         'notes': [{'text': t, 'kind': 'note', 'at': pt(x, y)} for t, x, y in notes],
         'doors': [{'a': a, 'b': b, 'at': pt(*at), 'width': 16, 'axis': 'o'} for a, b, at in doors]}
    for a in f['amenities']:
        if not any(inside(a['at'], r['poly']) for r in rooms):
            print(f'  note: {label} {a["type"]} at {a["at"]} is outside the rooms (routes use the nearest room)')
    return f


def build_floors():
    floors = [
        floor('1', 'First Floor', 0, 'Lobby and Museum Store (free to enter), restrooms; the grand stair and the '
              'elevator go up to the galleries', FIRST, FIRST_CLOSED, FIRST_DOORS, FIRST_AMEN, FIRST_LABELS,
              FIRST_NOTES),
        floor('2', 'Second Floor', 1, 'Essential MIT, Sensing Oceans, Crochet Coral Reef, The Exchange, the Maker Hub '
              'and Learning Labs', SECOND, SECOND_CLOSED, SECOND_DOORS, SECOND_AMEN, SECOND_LABELS, SECOND_NOTES),
        floor('3', 'Third Floor', 2, 'AI: Mind the Gap, MIT Collects, the Gruber and Kurtz Galleries, the Collections '
              'Workshop', THIRD, THIRD_CLOSED, THIRD_DOORS, THIRD_AMEN, THIRD_LABELS, THIRD_NOTES),
    ]
    return {'about': 'Built by tools/build_mit.py. Rooms, restrooms, stairs and elevator traced from the MIT Museum’s '
                     'own visitor floor maps (May 2025), which match the architects’ plans. Shows change by season: '
                     'which gallery holds the Crochet Coral Reef, the Starship Enterprise model and Split | Second is '
                     'approximate.',
            'source': 'MIT Museum, visitor floor maps (MITMus_Floor_maps_0924.pdf, 2025); Höweler + Yoon, Plan Level 2 '
                      'and Plan Level 3',
            'units': 'pixels of the museum’s floor-map pages at 100 dpi, x 2 (0.037 m a unit)',
            'approximate': False, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def commons_url(name, width=1000):
    return 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(name) + f'?width={width}'


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 5000: return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 20, 60, 120):
        time.sleep(wait or 2)
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.stat().st_size > 5000: return True
        dest.unlink(missing_ok=True)
    return False


def booklet_image(n):
    """Picture n (as pdfimages numbers them) from the museum's OCEANS booklet."""
    pdf = CACHE / 'oceans.pdf'
    if not fetch(OCEANS_PDF, pdf): return None
    out = CACHE / 'oceans'
    if not out.exists():
        out.mkdir(parents=True)
        subprocess.run(['pdfimages', '-j', str(pdf), str(out / 'i')], capture_output=True)
    f = out / f'i-{n:03d}.jpg'
    return f if f.exists() else None


def picture(key, src):
    """src: a Commons file name, or ('booklet', n)."""
    if not src: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/mit/images/{key}.jpg'
    if dest.exists(): return rel
    if isinstance(src, tuple):
        raw = booklet_image(src[1])
        if not raw: return None
    else:
        raw = CACHE / 'img' / (key + '.bin')
        if not fetch(commons_url(src), raw):
            print(f'  no picture (Commons busy): {src}')
            return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(raw.read_bytes())).convert('RGB')
    im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return rel


# ---- what is on view ------------------------------------------------------------------------------------------------
OCEANS = 'https://mitmuseum.mit.edu/oceans'
DAD = 'photo by Daderot (public domain)'
EMIT = 'Essential MIT: the experimental culture of the MIT community, told through its research. '
AIG = ('AI: Mind the Gap: what machines can and cannot do, from Claude Shannon’s game-playing machines to today’s '
       'robots and neural networks. ')
COLL = ('MIT Collects: hundreds of objects from the museum’s collection of about 1.5 million, in lit glass cases along '
        'a 90-foot wall, arranged by topic. ')
MEAS = ('Made to Measure: a case of measuring instruments from the collection, at the top of the grand stair. ')
# (key, gallery, title, maker, date, medium, text, picture, source url, credit, temporary (from, to) or None)
ON_VIEW = [
    ('echelman', 'Lobby', 'Remembering the Future', 'Janet Echelman', 'since Sept 17, 2025', 'Knotted fiber net',
     'A colored aerial sculpture of knotted fibre that floats through the lobby and over the grand stair, made '
     'during Echelman’s residency at MIT’s Center for Art, Science & Technology. You can see it from the lobby and from '
     'the stairs to the Second Floor.', 'Interior of the MIT Museum 2025-10-19 2.jpg', SITE,
     'photo of the grand stair, Oct 2025', None),
    ('store', 'Museum Store', 'MIT Museum Store', 'Store', None, None,
     'Books, kits, puzzles and MIT gifts. Free to enter; it keeps longer hours than the galleries.', None, SITE, None,
     None),
    # Second Floor
    ('sensing-oceans', 'Termeer Gallery', 'Sensing Oceans', 'Exhibition', 'Sept 28, 2026 – Feb 21, 2027', None,
     'How people and sea creatures sense the ocean: early oceanographic instruments, current MIT research and art by '
     'the collective Marshmallow Laser Feast, including Seeing Echoes in the Mind of the Whale and Plankton Temple. '
     'Part of the museum’s OCEANS season.', ('booklet', 9), OCEANS,
     'Marshmallow Laser Feast, Plankton Temple, 2025; photo courtesy of the artist, from the museum’s OCEANS booklet',
     ('2026-09-28', '2027-02-21')),
    ('coral-reef', 'Exchange Gallery', 'Crochet Coral Reef', 'Margaret Wertheim and Christine Wertheim',
     'Aug 14, 2026 – Feb 14, 2027', 'Crocheted yarn and other fibres; folded paper',
     'Hand-crocheted corals by the Institute For Figuring and thousands of makers around the world: the hyperbolic '
     'shapes of real reef creatures, a lesson in geometry and a warning about climate change. With folded-paper '
     'sculptures by MIT’s Erik and Martin Demaine that find the same curves in paper.', ('booklet', 6), OCEANS,
     'Crochet Coral Reef, Museum Frieder Burda; photo Richard Nielsen, from the museum’s OCEANS booklet',
     ('2026-08-14', '2027-02-14')),
    ('enterprise', 'Exchange Gallery', 'Starship Enterprise model', 'Star Trek: The Original Series', '1964',
     '33-inch studio model',
     'The restored 33-inch model of the starship Enterprise made for the 1964 Star Trek pilot, lent by the Roddenberry '
     'family for its first showing on the East Coast. Shown near the Crochet Coral Reef, with a board on its story.',
     None, 'https://mitmuseum.mit.edu/announcements/the-original-starship-enterprise-model-lands-at-mit-museum', None,
     ('2026-09-30', '2027-03-28')),
    ('essential-mit', 'Essential MIT', 'Essential MIT', 'Exhibition', 'since 2022', None,
     EMIT + 'Hands-on stations on space, climate, health and more; the museum’s opening exhibition in the new building.',
     'Interior of the MIT Museum 2025-10-19 1.jpg', SITE, 'photo Oct 2025', None),
    ('ligo', 'Essential MIT', 'LIGO 1.5 m prototype', 'Rainer Weiss and team, MIT', 'about 1980',
     'Vacuum tube, mirrors, laser optics',
     EMIT + 'An early test version of the laser interferometer Rainer Weiss designed to catch gravitational waves. LIGO '
     'first heard two black holes merging in 2015, and Weiss shared the 2017 Nobel Prize.',
     'LIGO 1.5m prototype, c. 1980, view 1 - MIT Museum - Cambridge, MA - DSC09051.jpg', SITE, DAD, None),
    ('squeezer', 'Essential MIT', 'Squeezer (optical parametric oscillator)', 'MIT LIGO Laboratory', '2011', None,
     EMIT + 'Used in the first tests of “squeezed light” at the LIGO observatory in Hanford: a quantum trick that '
     'lowers noise so the detectors can hear fainter gravitational waves.',
     'Squeezer device (optical parameter oscillator), used in 2011 in initial experiments with squeezed light at the '
     'Hanford LIGO observatory - MIT Museum - Cambridge, MA - DSC09057.jpg', SITE, DAD, None),
    ('voyager', 'Essential MIT', 'Plasma Science Experiment, flight spare for Voyager 1 and 2', 'MIT', '1970s', None,
     EMIT + 'The spare of the instrument MIT built to measure the solar wind on the Voyager probes, which are still '
     'sending data from interstellar space.',
     'Plasma science experiment, flight spare for Voyager 1 and 2, view 1 - MIT Museum - Cambridge, MA - DSC09043.jpg',
     SITE, DAD, None),
    ('glove', 'Essential MIT', 'Scalable tactile glove', 'MIT CSAIL', '2019', 'Knitted glove with 548 sensors',
     EMIT + 'A cheap glove covered in pressure sensors that taught a neural network to recognise objects by touch.',
     'Scalable tactile glove, 2019 - MIT Museum - Cambridge, MA - DSC09084.jpg', SITE, DAD, None),
    ('cooling-tower', 'Essential MIT', 'Cooling-tower water capture prototype', 'MIT', None, None,
     EMIT + 'A lab-scale model of a system that catches the water lost as plumes from power-plant cooling towers.',
     'Labscale cooling tower water capture prototype - MIT Museum - Cambridge, MA - DSC09038.jpg', SITE, DAD, None),
    ('jenga', 'Essential MIT', 'Jenga-playing robot', 'MIT', '2019', None,
     EMIT + 'A robot arm that learned to play Jenga by feel as well as by sight, pushing blocks gently and sensing when '
     'they resist.', 'Jenga-playing robot - MIT Museum - Cambridge, MA - DSC09079.jpg', SITE, DAD, None),
    ('made-to-measure', 'Grand Stair 2', 'Made to Measure', 'Display', None, None,
     MEAS + 'Instruments that measure heat, humidity, strain, electricity and distance, and the Smoot: the unit Oliver '
     'Smoot’s classmates used to measure the Harvard Bridge in 1958.', None, SITE, None, None),
    ('maser', 'Grand Stair 2', 'Ammonia maser', 'James Gordon', '1955', None,
     MEAS + 'One of the first masers, the microwave ancestor of the laser, built by James Gordon (MIT class of 1949) '
     'with Charles Townes at Columbia.',
     'Ammonia maser by James Gordon, 1955 - MIT Museum - Cambridge, MA - DSC09173.jpg', SITE, DAD, None),
    ('kelvin-balance', 'Grand Stair 2', 'Kelvin’s electric balance', 'after William Thomson, Lord Kelvin', 'about 1890',
     None, MEAS + 'A precise balance that weighs the pull between two coils to measure an electric current.',
     'Kelvin\'s Electric Balance, c. 1890 - MIT Museum - Cambridge, MA - DSC09200.jpg', SITE, DAD, None),
    ('theodolite', 'Grand Stair 2', 'Transit theodolite', 'Heller & Brightly', '1886', None,
     MEAS + 'A surveyor’s instrument for measuring angles, of the kind MIT civil engineering students learned on.',
     'Transit theodolite, Heller & Brightly, 1886 - MIT Museum - Cambridge, MA - DSC09212.jpg', SITE, DAD, None),
    ('ph-meter', 'Grand Stair 2', 'Model G pH meter', 'Beckman', 'about 1937–1956', None,
     MEAS + 'Arnold Beckman’s acidity meter, the first of its kind sold commercially, which began the business of '
     'electronic lab instruments.', 'Model G pH meter, Beckman, c. 1937-1956 - MIT Museum - Cambridge, MA - DSC09205.jpg',
     SITE, DAD, None),
    ('maker-hub', 'Maker Hub', 'Maker Hub', 'Hands-on space', None, None,
     'Drop-in activities every day, led by museum staff and free with admission: build, tinker and test ideas. The '
     'Learning Labs next door hold workshops for groups.', None, SITE, None, None),
    # Third Floor
    ('split-second', 'Gruber Gallery', 'Split | Second', 'Exhibition', 'Feb 19, 2026 – Jan 4, 2027', None,
     'Part of the TIME season: instruments and artworks in four sections, Earth Time, Mechanical Time, Electric Time '
     'and Atomic Time, on how we have measured ever smaller slices of a second.', None, SITE, None,
     ('2026-02-19', '2027-01-04')),
    ('ai', 'AI: Mind the Gap', 'AI: Mind the Gap', 'Exhibition', 'since 2022', None,
     AIG + 'Train a robot, watch a neural network think in real time, and write a poem together with an AI.',
     None, SITE, None, None),
    ('kismet', 'AI: Mind the Gap', 'Kismet', 'Cynthia Breazeal, MIT Artificial Intelligence Laboratory',
     '1997–2000', None,
     AIG + 'A robot head with eyebrows, ears and lips that read people’s faces and voices and answered with its own '
     'expressions: one of the first “social robots”.', 'Kismet, 1997-2000 - MIT Museum - Cambridge, MA - DSC09093.jpg',
     SITE, DAD, None),
    ('theseus', 'AI: Mind the Gap', 'Theseus', 'Claude and Betty Shannon', '1950', 'Maze, magnetic mouse, relays',
     AIG + 'A mechanical mouse that finds its way through a maze and remembers the route: one of the first machines '
     'that learned. Claude Shannon, the father of information theory, built it with his wife Betty.',
     'Theseus (1950), Betty and Claude Shannon, MIT Museum.jpg', SITE, None, None),
    ('nimwit', 'AI: Mind the Gap', 'Nimwit', 'Claude Shannon', 'about 1953', 'Relays and lights',
     AIG + 'A machine that plays the game of Nim, and nearly always wins.',
     'Nimwit by Claude Shannon, Nim-playing machine, c. 1953, view 1 - MIT Museum - Cambridge, MA - DSC09104.jpg',
     SITE, DAD, None),
    ('endgame', 'AI: Mind the Gap', 'Endgame', 'Claude Shannon', 'about 1950', None,
     AIG + 'A small machine that plays the end of a chess game: Shannon also wrote the first paper on how a computer '
     'could play chess.', 'Endgame by Claude Shannon, c. 1950 - MIT Museum - Cambridge, MA - DSC09087.jpg', SITE, DAD,
     None),
    ('wc-fields', 'AI: Mind the Gap', 'W. C. Fields juggling machine', 'Claude Shannon', 'early 1980s', None,
     AIG + 'A little figure that bounce-juggles three balls on a drum, named after the comedian who started as a '
     'juggler. Shannon was a keen juggler himself.',
     'W. C. Fields (bounce juggling machine) by Claude Shannon - MIT Museum, early 1980s - Cambridge, MA - DSC09099.jpg',
     SITE, DAD, None),
    ('red-black', 'AI: Mind the Gap', 'Red-Black', 'Claude Shannon', 'about 1951', None,
     AIG + 'Another of Shannon’s game-playing machines.',
     'Red-Black by Claude Shannon, game-playing machine, c. 1951 - MIT Museum - Cambridge, MA - DSC09108.jpg', SITE, DAD,
     None),
    ('mit-collects', 'Thorp Collections Gallery', 'MIT Collects', 'Exhibition', 'since 2022', None,
     COLL + 'Its sections include Modeling Everything, A Sequence of Actions (early computing), Technology and the '
     'Dream (the Black experience at MIT) and Totally Useless Things.',
     'Interior of the MIT Museum 2025-10-19 5.jpg', SITE, 'photo Oct 2025', None),
    ('whirlwind', 'Thorp Collections Gallery', 'Whirlwind computer (part)', 'MIT Servomechanisms Laboratory',
     '1945–1951', 'Vacuum tubes, magnetic-core memory',
     COLL + 'A section of Whirlwind, the first computer fast enough to work in real time; it led to magnetic-core '
     'memory and the SAGE air-defence network.', 'Interior of the MIT Museum 2025-10-19 6.jpg', SITE,
     'photo Oct 2025', None),
    ('differential-analyzer', 'Thorp Collections Gallery', 'Integrator unit of the Differential Analyzer',
     'Vannevar Bush with Harold Hazen', '1928–1931', None,
     COLL + 'Part of Vannevar Bush’s room-sized mechanical computer, which solved equations with turning shafts and '
     'wheels.', 'Integrator Unit, Differential Analyzer, by Vannevar Bush with Harold Hazen, 1928-1931 - MIT Museum - '
     'Cambridge, MA - DSC09127.jpg', SITE, DAD, None),
    ('apollo-gnc', 'Thorp Collections Gallery', 'Apollo Primary Guidance, Navigation and Control System (Block II '
     'prototype)', 'MIT Instrumentation Laboratory', '1961–1969', None,
     COLL + 'MIT designed the computer and guidance that flew the Apollo spacecraft to the Moon. This prototype of the '
     'command module’s system includes the Apollo Guidance Computer.',
     'Prototype Block II Primary Guidance, Navigation and Control System (PGNCS), Apollo Command Module 1961-1969 - '
     'MIT Museum - Cambridge, MA - DSC09133.jpg', SITE, DAD, None),
    ('apollo-imu', 'Thorp Collections Gallery', 'Apollo Inertial Measurement Unit (test unit)',
     'MIT Instrumentation Laboratory', '1961–1966', None,
     COLL + 'The gyroscope ball that told Apollo which way it was pointing, built for vibration tests.',
     'Inertial Measurement Unit, Apollo Guidance and Navigation System, fabricated for vibration testing, 1961-1966, '
     'view 1 - MIT Museum - Cambridge, MA - DSC09135.jpg', SITE, DAD, None),
    ('minivac', 'Thorp Collections Gallery', 'Minivac 601 computer kit', 'Scientific Development Corporation', '1962',
     None, COLL + 'A teaching kit of relays, switches and lights designed by Claude Shannon to show how computers work.',
     'Minivac 6010 Computer, Scientific Development Corporation, 1962 - MIT Museum - Cambridge, MA - DSC09163.jpg',
     SITE, DAD, None),
    ('solar-cell', 'Thorp Collections Gallery', 'Solar cell prototype', 'MIT', '1969', None,
     COLL + 'An early solar cell from MIT’s research on power from sunlight.',
     'Solar cell prototype, 1969 - MIT Museum - Cambridge, MA - DSC09144.jpg', SITE, DAD, None),
    ('nerd-kit', 'Thorp Collections Gallery', 'Nerd Kit', 'Apsco', '1998', None,
     COLL + 'A joke gift set from the 1990s: a tongue-in-cheek look at the “nerd” image of MIT students.',
     'Nerd Kit, Apsco, 1998 - MIT Museum - Cambridge, MA - DSC09157.jpg', SITE, DAD, None),
    ('freezing-time', 'Kurtz Gallery', 'Freezing Time: Edgerton and the Beauty of the Machine Age',
     'Harold “Doc” Edgerton', 'Feb 5 – Nov 29, 2026', 'Photographs',
     'Doc Edgerton’s strobe and high-speed flash photographs from the 1930s, which froze a milk drop, a bullet and a '
     'hummingbird’s wings, with the stroboscopes he invented at MIT.', None, SITE, None, ('2026-02-05', '2026-11-29')),
    ('water-lines', 'Kurtz Gallery', 'Water Lines', 'MIT architecture students', 'Dec 17, 2026 – June 27, 2027',
     'Thesis drawings',
     'Where people meet water, by design: drawings from the museum’s collection of more than 8,000 MIT architecture '
     'thesis drawings, over 150 years, with work by recent graduates. Part of the OCEANS season.', ('booklet', 8),
     OCEANS, 'Arthur V. Edwards, A Quarantine Hospital, MIT architecture thesis, 1889; MIT Museum',
     ('2026-12-17', '2027-06-27')),
]
WHERE = {
    'Exchange Gallery': 'The museum calls it the Exchange Gallery; it is taken to be the gallery beside The Exchange on '
                        'the Second Floor (approximate).',
    'Gruber Gallery': 'Which gallery the show is in is a guess: the Gruber Gallery holds changing exhibitions.',
    'Grand Stair 2': 'In the Made to Measure case at the top of the grand stair (the instruments in it are approximate).',
}


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for key, room, title, maker, when, medium, text, pic, url, credit, span in ON_VIEW:
        if span and date.fromisoformat(span[1]) < TODAY: continue          # closed
        fl, gname = rooms[room]
        img = picture(f'mit-{key}', pic) if pic else None
        if img:
            if isinstance(pic, tuple): cred = credit
            else: cred = f'{credit}, via {COMMONS}' if credit else COMMONS
        a = {'id': f'mit-{key}', 'title': title, 'artist': maker, 'date': when, 'medium': medium,
             'description': text if not span or date.fromisoformat(span[0]) <= TODAY
             else f'Opens {when.split(" – ")[0]}. ' + text,
             'gallery': room, 'galleryName': gname, 'floor': fl,
             'placeNote': WHERE.get(room, 'Where the museum’s floor map and its descriptions put it.'),
             'url': url, 'image': img, 'imageCredit': cred if img else None}
        if span: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return {'source': 'MIT Museum: floor maps and OCEANS booklet (its file server); objects photographed in the museum, '
                      'from Wikimedia Commons',
            'checked': TODAY.isoformat(), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': TODAY.isoformat(),
            'source': 'MIT Museum floor maps and OCEANS booklet; Wikimedia Commons',
            'onViewKnown': True,
            'note': 'The MIT Museum has about 1.5 million objects but no open online catalogue this guide can read (its '
                    'website blocks automated readers). This list is its current shows and highlight objects that '
                    'were photographed in the new building, placed in the gallery the museum’s own map shows.',
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
    print(f'{works["count"]} on view ({sum("image" in a for a in works["artworks"])} with pictures)')


if __name__ == '__main__':
    sys.exit(main())
