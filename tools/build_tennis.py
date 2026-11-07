#!/usr/bin/env python3
"""Build the International Tennis Hall of Fame (Newport, RI) map guide (run: python3 tools/build_tennis.py).

    data/tennis/floors.json     the grounds of the Newport Casino and the museum floor, seen from above (flat 2D)
    data/tennis/artworks.json   the museum's galleries and what is in them, the historic grounds, and every Hall of
                                Famer honoured in the Hall of Famers Gallery
    data/tennis/images/         their pictures, made smaller for phones
    data/guides/Q52454.json     the same list, for the museum page

First run tools/harvest_tennis.py (it fills .cache/tennis). The Hall of Famers' portraits come from Wikimedia
Commons, which answers 429 when a cloud machine asks too often: `python3 tools/build_tennis.py --portraits` downloads
the missing ones 6 s apart (waiting and retrying when told to slow down); without it only cached ones are used.
tools/tennis_portraits.py adds them without the harvest cache (Nov 2026: 206 portraits), with the same file names.

The map
-------
GROUNDS (floor G) are traced from the Hall of Fame's own 2026 site map (the Hall of Fame Open "what you need to
know" page, info.tennisfame.com/hubfs/2026 HFO Site Map.jpg; 1316 x 1400 px as traced). That map has north to the
RIGHT (Bellevue Avenue along the top, Memorial Boulevard on the right, Freebody Street at the bottom); it is turned a
quarter turn here so north is up, which also lines Bellevue Avenue up north-south as it really runs (checked against
the OpenStreetMap outlines of the Casino, way 719468746, and the courts). It is a drawn map, so distances are
approximate. Tournament-only things on it (sponsor booths, bars, the box office) are left out; the Fan Zone is the
parking lot by Memorial Boulevard the rest of the year.

THE MUSEUM (floor 2) is on the second floor of the Casino building (tennisfame.com: "The museum is on the second
floor of the Historic Newport Casino Building", elevator access). The Hall of Fame publishes no gallery plan, so the
galleries are APPROXIMATE: their names come from the 2025 reopening and June 2026 press releases and the museum's own
gallery photos (Newport Tennis Traditions, The Birth of Tennis, The Popular Game, The Open Era, Grand Slam, ATP and
Global Galleries, The Majors, the Celebration Gallery and, at the end of the visit, the Hall of Famers Gallery);
their order and places in the building are a guess, and the map says so. The Court Tennis Viewing Gallery and the
Legends Lounge are in the court tennis building on the grounds, as the site map shows.

Coordinates: the site map's pixels (x right, y down) turned with T(); about 0.17 m per unit.
"""
import html
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
OUT = ROOT / 'data' / 'tennis'
CACHE = ROOT / '.cache' / 'tennis'
MUSEUM = 'Q52454'
SITE = 'https://www.tennisfame.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
WM_UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'
TODAY = date.today()
FETCH = '--portraits' in sys.argv
SOURCE = ('Grounds: the International Tennis Hall of Fame’s 2026 site map, turned north-up; museum floor approximate, '
          'from the Hall of Fame’s descriptions of its galleries')


def T(x, y):
    """A point on the Hall of Fame's site map (north to the right) -> map units, north up."""
    return [round(y - 110, 1), round(1160 - x, 1)]


def poly(*pts):
    return [T(x, y) for x, y in pts]


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


# ---- floor G: the grounds ------------------------------------------------------------------------------------
HORSESHOE = poly((605, 520), (645, 520), (655, 555), (700, 580), (745, 555), (758, 520), (805, 520), (800, 560),
                 (775, 600), (735, 620), (700, 627), (665, 620), (625, 600), (605, 560))
GROUNDS = [  # id, kind, name, polygon, short label
    ('Welcome Center', 'gallery', 'Welcome Center: museum tickets, bag check (backpacks, large bags, racquets and '
     'drinks stay here), the Museum Store and the stairs and elevator up to the museum',
     poly((722, 262), (838, 228), (838, 330), (722, 330)), 'Welcome Center'),
    ('Entrance Arch', 'corridor', 'The entrance arch from Bellevue Avenue, through the Casino building to the Lawn',
     rect(690, 266, 722, 330), None),
    ('South Wing', 'space', 'The Casino’s south wing and the shops on Bellevue Avenue (museum on the floor above)',
     poly((570, 275), (690, 268), (690, 330), (608, 330), (608, 545), (570, 545)), 'Casino'),
    ('North Wing', 'space', 'The Casino’s north wing (the museum’s Celebration and Hall of Famers galleries are '
     'above, approximately)', rect(805, 330, 838, 520), None),
    ('1881 Club', 'gallery', 'The Horseshoe Piazza with its clock tower, the 1881 Club (members’ and event space) '
     'wrapped round the Lawn', HORSESHOE, '1881 Club'),
    ('The Lawn', 'gallery', 'The Lawn (the Horseshoe Court): the grass court inside the Casino, under the clock tower',
     poly((640, 362), (700, 342), (760, 362), (762, 500), (745, 530), (700, 542), (655, 530), (638, 500)), 'The Lawn'),
    ('Center Court', 'gallery', 'Bill Talbert Center Court, the stadium court of the Hall of Fame Open',
     poly((300, 700), (490, 690), (500, 885), (300, 895)), 'Center Court'),
    ('West Boxes', 'space', 'West Boxes (stadium seats)', poly((205, 655), (520, 598), (548, 625), (240, 725)), None),
    ('North Boxes', 'space', 'North Boxes (stadium seats)', poly((493, 705), (548, 705), (548, 855), (500, 855)),
     None),
    ('East Boxes', 'space', 'East Boxes (stadium seats)', poly((282, 905), (505, 870), (512, 900), (287, 935)), None),
    ('South Stands', 'space', 'South Stands (stadium seats)', poly((172, 742), (290, 722), (298, 900), (195, 935)),
     None),
    ('Front Lawn Courts', 'gallery', 'Front Lawn Courts 1–3: grass courts open to the public in season (book through '
     'the Pro Shop)', rect(610, 648, 790, 1025), 'Front Lawn Courts'),
    ('Practice Courts', 'space', 'Practice Courts (grass)', rect(200, 945, 355, 1240), 'Practice Courts'),
    ('Court 6', 'space', 'Court 6 (grass)', rect(365, 930, 525, 1230), 'Court 6'),
    ('Hard Courts', 'space', 'Three outdoor hard courts (under a bubble in winter)', rect(828, 770, 1005, 1005),
     'Hard Courts'),
    ('Chris Evert Learning Center', 'space', 'Chris Evert Learning Center', rect(845, 425, 1005, 540),
     'Chris Evert Center'),
    ('Parking Lot', 'corridor', 'The lot by Memorial Boulevard (the Fan Zone and box office during the July '
     'tournament; it is not a public visitors’ lot)', rect(830, 540, 1105, 745), None),
    ('Offices', 'space', 'Hall of Fame offices', rect(1035, 745, 1100, 1045), None),
    ('Indoor Tennis', 'space', 'Von Auersperg Building: three indoor hard courts with a viewing gallery, and the '
     'Hall of Fame Tennis Club’s Pro Shop on Memorial Boulevard', rect(900, 1045, 1100, 1300), 'Indoor Tennis'),
    ('Legends Lounge', 'gallery', 'Legends Lounge: a lounge for donors and Hall of Famers (private)',
     rect(540, 1045, 830, 1078), None),
    ('Court Tennis', 'gallery', 'The court tennis (real tennis) court, one of 49 in the world, and the museum’s Court '
     'Tennis Viewing Gallery above it', rect(540, 1078, 615, 1275), 'Court Tennis'),
    ('Clay Court', 'space', 'Clay court', rect(615, 1082, 718, 1255), 'Clay'),
    ('Casino Theatre', 'gallery', 'The Casino Theatre (Stanford White, 1881)',
     poly((720, 1078), (830, 1078), (830, 1160), (810, 1160), (810, 1275), (720, 1275)), 'Casino Theatre'),
    ('Freebody Drive', 'corridor', 'Driveway from Freebody Street (cars and deliveries)', rect(810, 1160, 900, 1300),
     None),
]
GROUND_DOORS = [('Entrance Arch', 'Welcome Center', (722, 300)), ('Entrance Arch', 'The Lawn', (706, 345)),
                ('South Wing', 'The Lawn', (620, 430)), ('1881 Club', 'The Lawn', (700, 545)),
                ('1881 Club', 'Front Lawn Courts', (700, 640)), ('Parking Lot', 'Chris Evert Learning Center', (925, 540)),
                ('Parking Lot', 'Hard Courts', (900, 760)), ('Freebody Drive', 'Casino Theatre', (812, 1200))]
GROUND_AMENITIES = [('entrance', 705, 238), ('entrance', 1105, 690), ('entrance', 855, 1300),
                    ('info', 780, 300), ('shop', 812, 262), ('coat', 750, 312), ('elevator', 765, 348),
                    ('stairs', 735, 318), ('restroom-all', 1080, 585), ('restroom-all', 200, 915),
                    ('water', 860, 552), ('water', 200, 955)]
GROUND_LABELS = [
    ('Bellevue Avenue', 'area', 705, 150),
    ('Memorial Boulevard', 'area', 1150, 760),
    ('Freebody Street', 'area', 665, 1345),
    ('Main entrance on Bellevue Avenue (Welcome Center and the arch)', 'note', 640, 195),
    ('Gate from Memorial Boulevard (the main gate during the July tournament)', 'note', 1135, 620),
    ('Bus stops (RIPTA 67 and the trolley): “Bellevue & Memorial Blvd (at Tennis Hall of Fame)” by the entrance',
     'note', 840, 160),
    ('Parking: street parking, the paid Bellevue Gardens lot across Bellevue Ave, or the Newport Transportation '
     'Center and the trolley', 'note', 560, 160),
    ('Grounds free to walk, 10–5 daily · museum upstairs in the Casino (ticket)', 'note', 420, 560),
    ('Restrooms by the Memorial Blvd gate and by the South Stands (as on the Hall of Fame’s map)', 'note', 260, 1290),
    ('Audrain Automobile Museum (next door, south)', 'place', 470, 230),
]

# ---- floor 2: the museum (approximate) -------------------------------------------------------------------------
GALLERIES = [
    ('Newport Tennis Traditions', 'Newport Tennis Traditions: tennis at the Casino since 1881 and the US Open trophies',
     poly((760, 245), (838, 228), (838, 330), (760, 330)), 'Newport'),
    ('Birth of Tennis', 'The Birth of Tennis (1874–1918)', poly((700, 266), (760, 255), (760, 330), (700, 330)),
     'Birth of Tennis'),
    ('Popular Game', 'The Popular Game (1918–1968)', rect(640, 270, 700, 330), 'Popular Game'),
    ('Open Era', 'The Open Era (1968–today)', poly((570, 275), (640, 270), (640, 330), (570, 330)), 'Open Era'),
    ('Grand Slam Gallery', 'Grand Slam Gallery', rect(570, 330, 608, 400), 'Grand Slam'),
    ('ATP Gallery', 'ATP Gallery', rect(570, 400, 608, 450), 'ATP'),
    ('Global Gallery', 'Global Gallery: Davis Cup, Billie Jean King Cup, wheelchair tennis', rect(570, 450, 608, 500),
     'Global'),
    ('The Majors', 'The Majors, presented by Rolex (immersive film narrated by Roger Federer)',
     rect(570, 500, 608, 545), 'The Majors'),
    ('Celebration Gallery', 'Celebration Gallery and the Inspirational Legacies AR sculpture',
     rect(805, 330, 838, 425), 'Celebration'),
    ('Hall of Famers Gallery', 'Hall of Famers Gallery: a cast racquet for every Hall of Famer (the end of the visit)',
     rect(805, 425, 838, 520), 'Hall of Famers'),
]
MUSEUM_DOORS = [('Newport Tennis Traditions', 'Birth of Tennis', (760, 300)), ('Birth of Tennis', 'Popular Game', (700, 300)),
                ('Popular Game', 'Open Era', (640, 300)), ('Open Era', 'Grand Slam Gallery', (590, 330)),
                ('Grand Slam Gallery', 'ATP Gallery', (590, 400)), ('ATP Gallery', 'Global Gallery', (590, 450)),
                ('Global Gallery', 'The Majors', (590, 500)), ('Newport Tennis Traditions', 'Celebration Gallery', (820, 330)),
                ('Celebration Gallery', 'Hall of Famers Gallery', (820, 425))]
MUSEUM_AMENITIES = [('elevator', 800, 320), ('stairs', 775, 318)]
MUSEUM_LABELS = [
    ('Museum (2nd floor of the Casino): the order and places of the galleries are approximate', 'note', 420, 300),
    ('The Lawn (below)', 'area', 700, 440),
    ('Bellevue Avenue', 'area', 705, 150),
    ('Up from the Welcome Center by stairs or elevator', 'note', 900, 300),
    ('No strollers, backpacks, large bags, racquets, food or drink in the galleries · no flash', 'note', 420, 600),
    ('Court Tennis Viewing Gallery: in the court tennis building across the grounds (see the Grounds)', 'note', 640,
     1000),
]


def floor(fid, label, order, rooms, doors, amenities, labels, area, home):
    rs = [{'id': rid, 'kind': kind, 'name': name, 'poly': pl, **({'label': short} if short else {})}
          for rid, kind, name, pl, short in rooms]
    ids = {r['id'] for r in rs}
    ds = []
    for a, b, (x, y) in doors:
        assert a in ids and b in ids, (a, b)
        ds.append({'a': a, 'b': b, 'at': T(x, y), 'width': 10, 'axis': 'o'})
    return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area, 'rooms': rs,
            'closed': [], 'amenities': [{'type': t, 'at': T(x, y)} for t, x, y in amenities],
            'labels': [{'text': t, 'kind': k, 'at': T(x, y)} for t, k, x, y in labels], 'doors': ds, 'homeView': home}


def build_floors():
    g = floor('G', 'Grounds (ground level)', 1, GROUNDS, GROUND_DOORS, GROUND_AMENITIES, GROUND_LABELS,
              'Welcome Center · Museum Store · the Lawn · Center Court · grass courts · Court Tennis · Casino Theatre · '
              'restrooms', ['Welcome Center', 'The Lawn', 'Center Court', 'Front Lawn Courts'])
    m = floor('2', 'Museum (2nd floor)', 2,
              [(rid, 'gallery', name, pl, short) for rid, name, pl, short in GALLERIES], MUSEUM_DOORS,
              MUSEUM_AMENITIES, MUSEUM_LABELS,
              'Newport Tennis Traditions · Birth of Tennis · Popular Game · Open Era · Grand Slam · ATP · Global · '
              'The Majors · Celebration · Hall of Famers (places approximate)',
              [r[0] for r in GALLERIES])
    return {'about': 'Built by tools/build_tennis.py. The grounds are traced from the International Tennis Hall of '
                     'Fame’s own 2026 site map (north is to the right on it; turned here so north is up). The museum '
                     'on the Casino’s second floor has no published plan: its galleries are placed approximately.',
            'source': SOURCE, 'units': 'site-map pixels, about 0.17 m, north up', 'approximate': True,
            'defaultFloor': '2', 'galleryWord': 'Gallery', 'floors': [g, m]}


# ---- pictures ------------------------------------------------------------------------------------------------
_last = [0.0]


def picture(key, src, url=None, gap=6):
    """A phone-sized JPEG in data/tennis/images from a cached file or (politely) a URL; returns the app path."""
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/tennis/images/{key}.jpg'
    raw = src
    if raw is None or not raw.exists():
        if not url: return None
        raw = CACHE / 'portraits' / f'{key}.bin'
        if not raw.exists():
            if not FETCH: return None        # portraits are fetched only with --portraits (slow, Wikimedia limits)
            raw.parent.mkdir(parents=True, exist_ok=True)
            wait = _last[0] + gap - time.time()
            if wait > 0: time.sleep(wait)
            for pause in (60, 180, None):        # Wikimedia answers 429 when asked too fast: wait and try again
                out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', WM_UA, url], capture_output=True).stdout
                _last[0] = time.time()
                if out or pause is None: break
                print(f'  busy, waiting {pause} s', flush=True); time.sleep(pause)
            if not out: print('  no picture from', url, flush=True); return None
            raw.write_bytes(out)
    try: im = Image.open(io.BytesIO(raw.read_bytes()))
    except Exception:
        print('  not a picture:', raw); return None
    im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/tennis/images/{key}.jpg'


def ithf(name):
    return picture('ithf-' + re.sub(r'[^a-z0-9]+', '-', name.lower().rsplit('.', 1)[0])[:60], CACHE / 'img' / name)


def habs(n):
    return picture(f'habs-{n}', CACHE / 'loc' / 'img' / f'{n}.jpg')


ITHF_CREDIT = 'International Tennis Hall of Fame'
HABS_CREDIT = 'Historic American Buildings Survey (Library of Congress, HABS RI-331), public domain'
MUSEUM_PAGE = f'{SITE}/museum-and-grounds/the-museum'
REOPEN = f'{SITE}/ithf-unveils-newly-renovated-museum'
FEDERER = (f'{SITE}/international-tennis-hall-of-fame-unveils-new-roger-federer-exhibit-ahead-of-2026-induction-'
           '45d74f5577a354e1')
GROUNDS_PAGE = f'{SITE}/museum-and-grounds/historic-grounds'

# The museum's galleries and what the Hall of Fame says is in them, with its own photographs.
# key, title, room, floor, picture, credit, url, date, text, kind
EXHIBITS = [
    ('welcome', 'Welcome Center and Museum Store', 'Welcome Center', 'G', ('i', '194BellevueAve-BP-PH-ITHF-MH-00025copy-Edit-Edit-Edit-Edit.jpeg'),
     REOPEN, '2025', 'Renovated for the museum’s 2025 reopening: buy tickets here (or show your online ticket, '
     'good any day), leave backpacks, large bags, racquets and drinks, and take the stairs or elevator up to the '
     'museum on the second floor. Audio tours in English, Spanish, French, German and Italian.', 'Space'),
    ('store', 'The Museum Store', 'Welcome Center', 'G', ('i', '194BellevueAve-BP-PH-ITHF-01349copy-Edit.jpeg'),
     REOPEN, '2025', 'The new Museum Store at the entrance on Bellevue Avenue: books, apparel and gifts inspired by '
     'the collection, open during museum hours.', 'Space'),
    ('traditions', 'Newport Tennis Traditions Gallery', 'Newport Tennis Traditions', '2',
     ('i', '194BellevueAve-BP-PH-ITHF-MH-00174-Edit-Edit--1-.jpeg'), REOPEN, '2025',
     'Celebrates the origins of tennis in Newport and its link with the US Open, which began on the Casino’s lawns '
     'in 1881 as the U.S. National Championships, with the perpetual US Open trophies on display.', 'Gallery'),
    ('birth', 'The Birth of Tennis (1874–1918)', 'Birth of Tennis', '2', ('i', 'r-1-gb-7-u-10-u-7-aibzislrdn.jpg'),
     MUSEUM_PAGE, '1874–1918', 'The first of the museum’s three history galleries: lawn tennis from Major Walter '
     'Clopton Wingfield’s patent of 1874 to the end of the First World War, when Newport hosted the national '
     'championships.', 'Gallery'),
    ('popular', 'The Popular Game (1918–1968)', 'Popular Game', '2', ('i', 'pip-91-e-7-nbshybykvdmtc.jpg'),
     MUSEUM_PAGE, '1918–1968', 'Tennis between the wars and after: the stars of the amateur era, the pros who toured '
     'for money, and the fashion, racquets and trophies of fifty years.', 'Gallery'),
    ('openera', 'The Open Era (1968–today)', 'Open Era', '2', ('i', 'vtcbblwyyq-3-dswllaopl.jpg'), MUSEUM_PAGE,
     '1968–today', 'From 1968, when amateurs and professionals could at last play the same tournaments, to today’s '
     'champions: match-worn clothes, racquets and trophies.', 'Gallery'),
    ('lacoste', 'René Lacoste’s “Crocodile” blazer', 'Popular Game', '2', ('i', 'g-2-khlmboa-9-pbuvllh-4-fz.jpg'),
     MUSEUM_PAGE, '1920s', 'From the museum’s fashion archive: the blazer of the French champion René Lacoste, '
     'nicknamed “the Crocodile”, with the crocodile emblem that later became his shirt brand. Every object tied to a '
     'Hall of Famer is labelled with their life and career. (Where it hangs now is not published.)', 'Clothing'),
    ('art', 'The Art of Tennis', 'Open Era', '2', ('i', 'jtcnxtd-2-kkecn-5-ctidej.jpg'), MUSEUM_PAGE, None,
     'Tennis has inspired many artists, and tennis-inspired art hangs throughout the museum, like this portrait of '
     'Chris Evert among her things. (Its gallery is not published.)', 'Art'),
    ('ashe', 'Ashe ’68 VR experience', 'Open Era', '2', ('i', 'Ashe-images-for-web.jpg'), MUSEUM_PAGE, '1968',
     'A virtual-reality film that takes you back to 1968, when Arthur Ashe became the first Black man to win the US '
     'Open, and used his new fame to speak out against injustice. Ashe won three Grand Slam singles titles and was '
     'the first Black player chosen for the U.S. Davis Cup team.', 'Interactive'),
    ('touch', 'Tennis trivia touch table', 'Grand Slam Gallery', '2', ('i', 'Museum-Interactive-Experience.jpg'),
     MUSEUM_PAGE, None, 'A five-foot touch table where two players “serve” tennis trivia questions back and forth. '
     'Nearby, “Call the Match” lets you record yourself as a TV commentator. (Places in the museum approximate.)',
     'Interactive'),
    ('majors', 'The Majors, presented by Rolex', 'The Majors', '2', ('i', '194BellevueAve-BP-PH-ITHF-00645.jpeg'),
     MUSEUM_PAGE, '2025', 'An immersive video room: relive the great moments of the four Grand Slam tournaments '
     '(Australian Open, Roland-Garros, Wimbledon, US Open), narrated by Roger Federer, who reflects on his own most '
     'momentous matches in the 2026 version.', 'Interactive'),
    ('federer-rg', 'Roger Federer’s 2009 Roland-Garros kit and trophy', 'Grand Slam Gallery', '2',
     ('i', 'Museum_Update_-23.jpeg'), FEDERER, '2009', 'Part of “Tennis, Transcended: Roger Federer’s Path to '
     'Greatness” (from June 2026), a museum-wide exhibit for his induction: match-worn and signed clothes and '
     'racquets from his title runs at Wimbledon 2007 and 2009 and Roland-Garros 2009. Highlights of his greatest '
     'matches also play in the ATP and Grand Slam Galleries.', 'Exhibit'),
    ('federer-racquets', 'Racquets and trophies from great careers', 'ATP Gallery', '2', ('i', 'Museum_Update_-22.jpeg'),
     FEDERER, None, 'A case of racquets old and new with trophies, among the memorabilia added across the museum in '
     'June 2026.', 'Exhibit'),
    ('global', 'Global Gallery: Davis Cup, Billie Jean King Cup and wheelchair tennis', 'Global Gallery', '2', None,
     FEDERER, '2026', 'Updated in June 2026 with exhibits on the Davis Cup and the Billie Jean King Cup and on 50 '
     'years of wheelchair tennis, including “Ask a Pro”, an interactive in which the wheelchair-tennis pioneer Rick '
     'Draney answers questions about life and competition in the sport.', 'Gallery'),
    ('ar', 'Inspirational Legacies AR Sculpture', 'Celebration Gallery', '2',
     ('i', '194BellevueAve-BP-PH-ITHF-MH-00114-Edit-Edit.jpeg'), REOPEN, '2025', 'The centrepiece of the Celebration '
     'Gallery, which tells how each generation of champions inspired the next: a sculpture of hanging tennis balls. '
     'Point your phone at it to see which players inspired today’s champions.', 'Interactive'),
    ('celebration', 'Celebration Gallery', 'Celebration Gallery', '2', ('i', '194BellevueAve-BP-PH-ITHF-MH-00062copy-Edit-Edit.jpeg'),
     REOPEN, '2025', 'Unique artifacts tell the stories of tennis legends across generations, around the AR '
     'sculpture.', 'Gallery'),
    ('hofgallery', 'Hall of Famers Gallery: the cast racquets', 'Hall of Famers Gallery', '2',
     ('i', '194BellevueAve-BP-PH-ITHF-MH-00358-Edit.jpeg'), REOPEN, '2025', 'Since 2025 every Hall of Famer, past and '
     'future, is honoured with a cast golden racquet, the new symbol of induction; all of them stand together here, '
     'at the end of the visit, with tribute cases for the newest class.', 'Gallery'),
    ('federer-cases', 'Tennis, Transcended: Roger Federer’s tribute cases', 'Hall of Famers Gallery', '2',
     ('i', 'Museum_Update_-7.jpeg'), FEDERER, '2026', 'Tribute cases for Roger Federer, inducted on August 29, 2026: '
     'match-worn clothes from all four majors, signed kits and racquets.', 'Exhibit'),
    ('federer-wimbledon', 'Roger Federer’s Wimbledon whites', 'Hall of Famers Gallery', '2', ('i', 'Museum_Update_-13.jpeg'),
     FEDERER, None, 'Federer’s all-white Wimbledon clothes and shoes, in the 2026 tribute.', 'Clothing'),
    ('carillo', 'Mary Carillo tribute case', 'Hall of Famers Gallery', '2', ('i', 'Museum_Update_-18.jpeg'), FEDERER,
     '2026', 'For the 2026 Contributor inductee Mary Carillo, player and one of tennis’s great broadcasters: the '
     'Olympic torch she carried at the 2010 Vancouver Winter Games, her 2023 Emmy Award, and credentials and mic '
     'flags.', 'Exhibit'),
    ('hofcases', 'Tribute cases of recent Hall of Famers', 'Hall of Famers Gallery', '2',
     ('i', '194BellevueAve-BP-PH-ITHF-00732copy-Edit.jpeg'), REOPEN, '2025', 'The 2025 class tribute showed Maria '
     'Sharapova’s dresses from her 2004 Wimbledon, 2006 US Open and 2012 Roland-Garros titles and the Bryan '
     'brothers’ doubles trophies and 2012 Olympic gold medal. The cases change as new classes are inducted.',
     'Exhibit'),
    ('courttennis', 'Court Tennis Viewing Gallery', 'Court Tennis', 'G', ('i', '194BellevueAve-BP-PH-ITHF-01302-Edit.jpeg'),
     REOPEN, '2025', 'Renovated in 2025: the history of court tennis (real tennis, the indoor game of kings that lawn '
     'tennis came from) and other racquet sports, looking down on the Casino’s court, one of just 49 court tennis '
     'courts in the world.', 'Gallery'),
    ('legends', 'Legends Lounge', 'Legends Lounge', 'G', ('i', '194BellevueAve-BP-PH-ITHF-MH-09960-Edit-Edit-Edit.jpeg'),
     REOPEN, '2025', 'Opened in 2025 as a place for donors and Hall of Famers to gather in Newport (not open to '
     'museum visitors).', 'Space'),
]

# The historic grounds (Newport Casino, McKim, Mead & White, 1880; National Historic Landmark 1987)
GROUND_ITEMS = [
    ('facade', 'The Newport Casino on Bellevue Avenue', 'Entrance Arch', ('h', 144556), HABS_CREDIT, GROUNDS_PAGE, '1880',
     'McKim, Mead & White’s first major commission, built in 1880 for James Gordon Bennett Jr., publisher of the '
     'New York Herald: shops and a restaurant on the street, club rooms above, in shingle, stone and brick. One of '
     'the finest Shingle Style buildings in America, a National Historic Landmark since 1987. Photo 1970.',
     'McKim, Mead & White'),
    ('elevation', 'The Casino’s Bellevue Avenue elevation', 'Entrance Arch', ('i', 'Newport-Casino-Elevation-Bellevue-Avenue-1.jpg'),
     ITHF_CREDIT, GROUNDS_PAGE, '1880', 'The architects’ drawing of the street front. Despite its name, the Casino '
     'never had gambling: “casino” comes from the Italian casina, a small social building on a country estate.',
     'McKim, Mead & White'),
    ('lawn', 'The Lawn and the clock tower', 'The Lawn', ('i', 'Clocktower-07_2022-08-08.jpg'), ITHF_CREDIT,
     GROUNDS_PAGE, '1880', 'The grass court inside the Casino, framed by the Horseshoe Piazza and its clock tower. '
     'On August 31, 1881 the first U.S. National Men’s Singles Championship, today’s US Open, was played at the '
     'Casino, with a string quartet; it stayed here until 1914.', 'McKim, Mead & White'),
    ('court1970', 'The interior court, looking south (1970)', 'The Lawn', ('h', 144560), HABS_CREDIT, GROUNDS_PAGE, '1970',
     'The Historic American Buildings Survey’s photograph of the court and the clock tower from the entrance.',
     'HABS'),
    ('painting', 'Tennis at the Casino, 1880s', '1881 Club', ('i', 'vc-2-s-6-akjwyjbjofo-36-sb.jpg'), ITHF_CREDIT,
     GROUNDS_PAGE, '1880s', 'Watching tennis through the Casino’s lattice. Archery, billiards, concerts, dancing, '
     'horse shows, lawn bowling and theatricals filled its summers; on opening day in 1880 more than 3,000 people '
     'came to look.', 'International Tennis Hall of Fame'),
    ('centercourt', 'Bill Talbert Center Court', 'Center Court', None, None, f'{SITE}/club/outdoor', None,
     'The stadium court of the Hall of Fame Open (ATP Challenger and WTA 125, every July), named for the Hall of '
     'Famer Bill Talbert. The grass courts were completely renovated in 2020; the public can book them in season '
     '(May to October) at the Pro Shop, 401-849-4777.', 'International Tennis Hall of Fame'),
    ('theatre', 'The Casino Theatre', 'Casino Theatre', ('h', 144543), HABS_CREDIT, GROUNDS_PAGE, '1881',
     'Stanford White’s theatre and ballroom for 300, with removable seats; its gold-trimmed ivory interior had a sky-'
     'blue ceiling with golden stars. Photo 1970.', 'McKim, Mead & White'),
    ('theatre-old', 'The Casino Theatre in its heyday', 'Casino Theatre', ('i', 'zbzykrz-5-rkfcsl-0-lx-068.jpg'),
     ITHF_CREDIT, GROUNDS_PAGE, None, 'An old photograph of the theatre’s entrance from the museum’s archive.',
     'International Tennis Hall of Fame'),
    ('bennett', 'James Gordon Bennett Jr.', 'Welcome Center', ('i', 'mastt-1-utgtzlor-8-v-2-vy-5.jpg'), ITHF_CREDIT,
     GROUNDS_PAGE, None, 'The Casino’s founder. Legend says he built it after his polo partner, Captain Henry Candy, '
     'rode a horse onto the porch of the gentlemen’s Newport Reading Room on a bet and lost his guest membership; in '
     'fact Bennett had planned a social club since 1878.', 'International Tennis Hall of Fame'),
    ('vanalen', 'Jimmy Van Alen, founder of the Hall of Fame', 'Welcome Center', ('i', 'baysdjmq-6-fijca-6-cjjjg.jpg'),
     ITHF_CREDIT, GROUNDS_PAGE, '1954', 'When the Casino was in danger of demolition in the 1950s, its president Jimmy '
     'Van Alen and his wife Candy founded a National Tennis Hall of Fame here, after visiting baseball’s Hall of Fame. '
     'Van Alen also invented the tiebreak. The International Tennis Federation recognized the Hall in 1986.',
     'International Tennis Hall of Fame'),
]


# ---- Hall of Famers ---------------------------------------------------------------------------------------
def unwiki(s):
    s = re.sub(r'<ref[^>]*/>|<ref.*?</ref>', '', s, flags=re.S)
    s = re.sub(r'\{\{sortname\|([^|}]*)\|([^|}]*)(?:\|[^}]*)?\}\}', r'\1 \2', s)
    s = re.sub(r'\{\{(?:flagu|flag|flagicon)\|([^|}]*)[^}]*\}\}', r'\1', s)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', s)
    s = re.sub(r"'''?|<[^>]+>", '', s)
    return html.unescape(re.sub(r'\s+', ' ', s)).strip()


def hall_of_famers():
    text = (CACHE / 'list.wiki').read_text()
    contrib_at = text.find('==Contributor category==')
    former_at = text.find('===Former members===')
    rows = []
    for m in re.finditer(r'\n\|-\s*\n(.*?)(?=\n\|-|\n\|\})', text, re.S):
        if former_at <= m.start() < contrib_at:          # Bob Hewitt was expelled in 2016
            continue
        r = m[1]
        y = re.search(r'\|\s*align="?center"?\s*\|\s*(\d{4})', r)
        n = re.search(r'!\s*scope="row"[^|\n]*\|(.*)', r)
        if not (y and n): continue
        cells = [c.strip() for c in re.findall(r'\n\|(?!align)([^\n]*)', '\n' + r.split('\n', 2)[-1])]
        slug = re.search(r'tennisfame\.com/(?:hall-of-famers/inductees/)?([a-z0-9-]+)(?=[\s|/]?)', r)
        if slug and slug[1] in ('hall-of-famers', 'hall-of-fame', 'inductees'): slug = None
        player = m.start() < contrib_at
        nat = unwiki(cells[0]) if cells else ''
        what = unwiki(cells[1]) if len(cells) > 1 else ''
        rows.append({'year': int(y[1]), 'name': unwiki(n[1]), 'nationality': nat,
                     'category': (what or 'Player') if player else 'Contributor',
                     'contribution': '' if player else what, 'slug': slug[1] if slug else None,
                     'women': 'afeeee' in n[0]})
    return rows


def wikidata():
    out = {}
    for b in json.loads((CACHE / 'wd.json').read_text())['results']['bindings']:
        v = {k: x['value'] for k, x in b.items()}
        cur = out.setdefault(v['ithf'], v)
        for k in v: cur.setdefault(k, v[k])
        out.setdefault(re.sub(r'[^a-z]', '', v.get('pLabel', '').lower()), cur)
        words = re.findall(r'[a-z]+', v.get('pLabel', '').lower())
        if len(words) >= 2: out.setdefault(('first-last', words[0], words[-1]), cur)
    return out


def find(wd, r):
    words = re.findall(r'[a-z]+', r['name'].lower())
    return (wd.get(r['slug']) or wd.get(re.sub(r'[^a-z]', '', r['name'].lower()))
            or (len(words) >= 2 and wd.get(('first-last', words[0], words[-1]))) or {})


def years(v):
    b = v.get('birth', '')[:4]; d = v.get('death', '')[:4]
    return f'{b}–{d}' if b and d else (f'born {b}' if b else None)


def hof_works():
    wd = wikidata()
    out = []
    for r in hall_of_famers():
        v = find(wd, r)
        img = None; src = None
        if v.get('img'):
            fname = urllib.parse.unquote(v['img'].rsplit('/', 1)[1])
            src = 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(fname.replace(' ', '_'))
            img = picture('hof-' + re.sub(r'[^a-z0-9]+', '-', r['name'].lower()).strip('-')[:50], None,
                          'https://commons.wikimedia.org/wiki/Special:FilePath/'
                          + urllib.parse.quote(fname.replace(' ', '_')) + '?width=500')
        cat = r['category']
        about = (f'{r["name"]} ({r["nationality"]}) was inducted into the International Tennis Hall of Fame in '
                 f'{r["year"]}' + (f' in the {cat} category' if cat != 'Contributor' else ' as a Contributor')
                 + (f': {r["contribution"]}' if r['contribution'] else '') + '.')
        if v.get('desc'): about += f' Wikidata: {v["desc"]}.'
        about += (' Like every Hall of Famer, they are honoured with a cast racquet in the Hall of Famers Gallery. '
                  'The picture is a photograph of them, not of an object in the museum.') if img else \
                 ' Like every Hall of Famer, they are honoured with a cast racquet in the Hall of Famers Gallery.'
        a = {'id': 'hof-' + (r['slug'] or re.sub(r'[^a-z0-9]+', '-', r['name'].lower())), 'title': r['name'],
             'artist': r['name'], 'date': str(r['year']), 'year': r['year'],
             'medium': f'Hall of Famer, class of {r["year"]} · {cat} · {r["nationality"]}' + (f' · {years(v)}' if years(v) else ''),
             'type': 'Hall of Famer',
             'caption': r['contribution'] or None, 'gallery': 'Hall of Famers Gallery', 'galleryName': 'Hall of Famers Gallery',
             'floor': '2', 'placeNote': 'Every Hall of Famer has a cast racquet in the Hall of Famers Gallery.',
             'description': about, 'descriptionKind': 'From the Hall of Fame’s list of inductees (via Wikipedia) and Wikidata',
             'url': f'{SITE}/hall-of-famers/inductees/{r["slug"]}' if r['slug'] else f'{SITE}/hall-of-famers/inductees',
             'image': img, 'imageCredit': img and 'Wikimedia Commons', 'imageSource': img and src}
        out.append({k: x for k, x in a.items() if x not in (None, '')})
    return out


def build_works():
    floor_of = {r[0]: 'G' for r in GROUNDS} | {r[0]: '2' for r in GALLERIES}
    names = {r[0]: r[2] for r in GROUNDS} | {r[0]: r[1] for r in GALLERIES}
    out = []
    for key, title, room, fl, pic, url, when, text, kind in EXHIBITS:
        img = ithf(pic[1]) if pic else None
        a = {'id': f'tennis-{key}', 'title': title, 'artist': 'International Tennis Hall of Fame', 'date': when,
             'medium': kind, 'type': kind, 'gallery': room, 'galleryName': names[room].split(':')[0], 'floor': fl,
             'placeNote': 'The museum publishes no gallery plan: the place is approximate.' if fl == '2' else None,
             'description': text, 'descriptionKind': 'From the International Tennis Hall of Fame’s own pages',
             'url': url, 'image': img, 'imageCredit': img and ITHF_CREDIT}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    for key, title, room, pic, credit, url, when, text, who in GROUND_ITEMS:
        img = (habs(pic[1]) if pic[0] == 'h' else ithf(pic[1])) if pic else None
        a = {'id': f'tennis-{key}', 'title': title, 'artist': who, 'date': when, 'medium': 'Historic grounds',
             'type': 'Building', 'gallery': room, 'galleryName': names[room].split(':')[0], 'floor': floor_of[room],
             'description': text, 'descriptionKind': 'From the Hall of Fame’s Historic Grounds page and the HABS record',
             'url': url, 'image': img, 'imageCredit': img and credit}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    hof = hof_works()
    out += sorted(hof, key=lambda a: (a['year'], a['title']))
    return {'source': 'International Tennis Hall of Fame (tennisfame.com), Historic American Buildings Survey, '
                      'Wikipedia’s list of inductees and Wikidata/Wikimedia Commons portraits',
            'checked': TODAY.isoformat(), 'count': len(out), 'complete': True, 'artworks': out}, len(hof)


def build_guide(works, n_hof):
    rows = [{k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                               'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                               'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                               'floor': a['floor']}.items() if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'International Tennis Hall of Fame', 'checked': TODAY.isoformat(),
            'source': 'International Tennis Hall of Fame; HABS; Wikipedia and Wikidata', 'onViewKnown': True,
            'note': 'The Hall of Fame shows nearly 2,000 objects from a collection of more than 30,000 artifacts, '
                    'telling tennis history from its birth to today in the second floor of the 1880 Newport Casino. '
                    'It publishes no online catalogue, so this guide lists its galleries and highlights named by the '
                    f'museum, the historic grounds, and all {n_hof} Hall of Famers honoured with a cast racquet in the '
                    'Hall of Famers Gallery. Now showing: “Tennis, Transcended: Roger Federer’s Path to Greatness” '
                    '(since June 2026).',
            'works': rows}


def main():
    if not (CACHE / 'wd.json').exists():
        raise SystemExit('run tools/harvest_tennis.py first')
    OUT.mkdir(exist_ok=True)
    (OUT / 'floors.json').write_text(json.dumps(build_floors(), ensure_ascii=False, separators=(',', ':')))
    works, n_hof = build_works()
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, n_hof)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} entries ({n_hof} Hall of Famers), {sum("image" in a for a in works["artworks"])} with pictures')


if __name__ == '__main__':
    sys.exit(main())
