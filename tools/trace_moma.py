#!/usr/bin/env python3
"""Trace MoMA's own 2025 floor plans into flat-map rooms (helper for build_moma.py).

    .venv/bin/pip install opencv-python-headless numpy pillow
    .venv/bin/python tools/trace_moma.py .cache/moma/am      # writes tools/data/moma-plan.json

The pictures are MoMA's 2025 visitor floor plans (the same drawings as the museum's printed "Floor Plan and Guide"),
as copied on all-maps.com (MOMA-Museum-Map-2025-1..7-scaled.webp; moma.org itself is behind a Cloudflare challenge).
Every floor is drawn in the same frame, so a pixel is the same place on every floor once the frame is shifted
(floors 3 and 6 and the lower levels sit lower in their pictures: SHIFT).

Galleries are lilac, public halls white, back-of-house grey, walls thin darker lines. Each room gets a seed (a point
inside it, read off the drawing by eye, in the coordinates of a crop that starts at pixel 200, 260); a watershed
from the seeds fills each room up to its walls; white pockets with no seed (light wells, voids over the atrium) are
dropped. Doors are where two rooms touch with no wall between them.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OFF = (200, 260)
SHIFT = {1: 0, 2: 0, 3: 63, 4: 0, 5: 0, 6: 82, 7: 101}
FILLS = {'lilac': (213, 204, 228), 'white': (243, 239, 247), 'grey': (231, 233, 235)}

# picture -> {room id: (kind, crop x, crop y)}; kind 'void' = a pocket to drop
SEEDS = {
    5: {'510': ('gallery', 130, 100), '509': ('gallery', 190, 140), '508': ('gallery', 260, 120),
        '507': ('gallery', 352, 100), '505': ('gallery', 408, 100), '503': ('gallery', 500, 100),
        '502': ('gallery', 623, 100), '504': ('gallery', 490, 185), '501': ('gallery', 566, 175),
        '500': ('gallery', 790, 150), '511': ('gallery', 133, 220), '506': ('gallery', 408, 255),
        '512': ('gallery', 160, 282), '516': ('gallery', 266, 290), '518': ('gallery', 520, 320),
        '517': ('gallery', 420, 330), '513': ('gallery', 132, 345), '522': ('gallery', 540, 390),
        '523': ('gallery', 700, 395), '515': ('gallery', 67, 440), '519': ('gallery', 430, 482),
        '520': ('gallery', 530, 482), '521': ('gallery', 650, 480), '514': ('gallery', 134, 470),
        'W5': ('corridor', 340, 400), 'S5': ('corridor', 830, 340),
        'v1': ('void', 620, 280), 'v2': ('void', 270, 460)},
    4: {'409': ('gallery', 130, 100), '408': ('gallery', 200, 100), '407': ('gallery', 350, 100),
        '405': ('gallery', 407, 100), '403': ('gallery', 500, 100), '402': ('gallery', 610, 100),
        '404': ('gallery', 490, 185), '401': ('gallery', 600, 175), '400': ('gallery', 790, 150),
        '411': ('gallery', 130, 220), '410': ('gallery', 188, 220), '406': ('gallery', 408, 255),
        '412': ('gallery', 130, 300), '414': ('gallery', 264, 322), '416': ('gallery', 519, 322),
        '415': ('gallery', 406, 345), '418': ('gallery', 519, 390), '420': ('gallery', 620, 390),
        '421': ('gallery', 700, 395), '413': ('gallery', 65, 440), 'Studio': ('space', 270, 480),
        '417': ('gallery', 430, 482), '419': ('gallery', 540, 482),
        'W4': ('corridor', 340, 400), 'S4': ('corridor', 830, 340), 'v1': ('void', 620, 280)},
    3: {'3 North': ('gallery', 605, 220), '3 South': ('gallery', 640, 530), '3 East': ('gallery', 1100, 500),
        'W3': ('corridor', 352, 500), 'S3': ('corridor', 790, 400), 'v1': ('void', 590, 360)},
    2: {'207': ('gallery', 130, 100), '206': ('gallery', 248, 100), '205': ('gallery', 347, 100),
        '203': ('gallery', 420, 100), '204': ('gallery', 518, 100), 'Creativity Lab': ('space', 620, 110),
        '202': ('gallery', 404, 175), '201': ('gallery', 517, 175), '208': ('gallery', 130, 235),
        '216': ('gallery', 403, 255), 'Atrium': ('gallery', 640, 300), '215': ('gallery', 402, 345),
        '209': ('gallery', 130, 355), '210': ('gallery', 62, 440), '211': ('gallery', 174, 440),
        '212': ('gallery', 260, 440), '214': ('gallery', 493, 460), '213': ('gallery', 402, 480),
        '2 South': ('gallery', 800, 480), 'W2': ('corridor', 335, 400), 'N2': ('corridor', 752, 165),
        'S2': ('corridor', 950, 300), 'Store': ('space', 1060, 420), 'Cafe 2': ('space', 1250, 440),
        'E2': ('corridor', 1430, 240), 'v1': ('void', 620, 440)},
    1: {'1 North': ('gallery', 258, 320), '1 South': ('gallery', 258, 450),
        'Sculpture Garden': ('gallery', 1000, 160), 'Lobby': ('corridor', 650, 120),
        'The Modern': ('space', 1150, 330), 'E1': ('corridor', 1450, 200),
        'East Lobby': ('corridor', 950, 420)},
    6: {'6': ('gallery', 520, 300), 'N6': ('corridor', 700, 200), 'Terrace Cafe': ('space', 130, 500)},
    7: {'Museum Store': ('space', 250, 470), 'Theater 2': ('space', 620, 500), 'Film Center': ('corridor', 740, 350),
        'Theater 1': ('space', 1020, 380), 'Theater 3': ('space', 1530, 280), 'Tisch Atrium': ('corridor', 1350, 320)},
}


# lines that close the street doors on floor 1, so the street does not flood into the lobby (crop coordinates)
SEAL = {1: [((550, 49), (685, 49)), ((1470, 49), (1560, 49)), ((550, 505), (685, 505)), ((1095, 505), (1175, 505))]}


def classify(img):
    a = img.astype(int)
    d = np.stack([np.abs(a - np.array(c)).sum(2) for c in FILLS.values()])
    cls = d.argmin(0)
    ink = d.min(0) > 22
    return cls, ink


def trace(path, n):
    bgr = cv2.imread(str(path))
    rgb = bgr[:, :, ::-1]
    cls, ink = classify(rgb)
    h, w = cls.shape
    for (x0, y0), (x1, y1) in SEAL.get(n, []):
        sealm = np.zeros((h, w), np.uint8)
        cv2.line(sealm, (x0 + OFF[0], y0 + OFF[1]), (x1 + OFF[0], y1 + OFF[1]), 1, 3)
        ink = ink | (sealm > 0)
    # outside the building: the background reached from the corner without crossing a line
    free = (cv2.dilate(ink.astype(np.uint8), np.ones((5, 5), np.uint8)) == 0).astype(np.uint8)
    outside = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(free.copy(), outside, (5, 5), 2, flags=4 | (2 << 8) | cv2.FLOODFILL_MASK_ONLY)
    outside = outside[1:-1, 1:-1] > 0
    markers = np.zeros((h, w), np.int32)
    names = {}
    seeds = SEEDS[n]
    for i, (rid, (kind, cx, cy)) in enumerate(seeds.items(), start=2):
        names[i] = (rid, kind)
        cv2.circle(markers, (cx + OFF[0], cy + OFF[1]), 3, i, -1)
    markers[outside & (markers == 0)] = 1
    grey = (cls == 2) & ~ink
    grey = cv2.erode(grey.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    markers[grey & (markers == 0)] = 1
    # everything far from the drawn area is outside too
    markers[:OFF[1], :] = 1; markers[OFF[1] + 640:, :] = 1
    # flood over a plain picture: walls and text black, galleries, halls and back rooms in three greys
    flat = np.choose(cls, [190, 255, 225]).astype(np.uint8)
    flat[ink] = 0
    cv2.watershed(cv2.merge([flat, flat, flat]), markers)
    rooms, doors = [], []
    masks = {}
    for i, (rid, kind) in names.items():
        m = (markers == i).astype(np.uint8)
        if kind == 'void': continue
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs: print('  no region for', rid); continue
        c = max(cs, key=cv2.contourArea)
        ap = cv2.approxPolyDP(c, 2.0, True)[:, 0, :]
        sh = SHIFT[n]
        rooms.append({'id': rid, 'kind': kind, 'area': int(m.sum()),
                      'poly': [[int(x), int(y) - sh] for x, y in ap]})
        masks[rid] = m
    # doors: watershed lines (-1) with rooms on both sides and no ink nearby
    line = markers == -1
    inkd = cv2.dilate(ink.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    ids = {v[0]: k for k, v in names.items() if v[1] != 'void'}
    k = np.ones((5, 5), np.uint8)
    dil = {rid: cv2.dilate(m, k) > 0 for rid, m in masks.items()}
    rl = list(masks)
    for a in range(len(rl)):
        for b in range(a + 1, len(rl)):
            contact = line & dil[rl[a]] & dil[rl[b]] & ~inkd
            if contact.sum() < 6: continue
            nlab, lab, stats, cent = cv2.connectedComponentsWithStats(contact.astype(np.uint8), connectivity=8)
            for j in range(1, nlab):
                if stats[j, cv2.CC_STAT_AREA] >= 6:
                    doors.append({'a': rl[a], 'b': rl[b], 'at': [round(cent[j][0]), round(cent[j][1]) - SHIFT[n]],
                                  'size': int(stats[j, cv2.CC_STAT_AREA])})
    # the building's outline (drawn under the rooms as back-of-house)
    inside = (~outside).astype(np.uint8)
    inside[:OFF[1], :] = 0; inside[OFF[1] + 640:, :] = 0; inside[:, :OFF[0] + 20] = 0; inside[:, OFF[0] + 1620:] = 0
    inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outline = [[[int(x), int(y) - SHIFT[n]] for x, y in cv2.approxPolyDP(c, 2.0, True)[:, 0, :]]
               for c in cs if cv2.contourArea(c) > 5000 and cv2.boundingRect(c)[3] > 100]
    return rooms, doors, markers, outline


def main(folder):
    folder = Path(folder)
    out = {}
    for n in SEEDS:
        p = folder / f'MOMA-Museum-Map-2025-{n}-scaled.png'
        if not p.exists():
            from PIL import Image
            Image.open(folder / f'MOMA-Museum-Map-2025-{n}-scaled.webp').convert('RGB').save(p)
        rooms, doors, markers, outline = trace(p, n)
        out[str(n)] = {'rooms': rooms, 'doors': doors, 'outline': outline}
        # a picture to check the result by eye
        img = cv2.imread(str(p))
        rng = np.random.default_rng(1)
        col = rng.integers(60, 255, (markers.max() + 2, 3))
        over = img.copy()
        for i in range(2, markers.max() + 1):
            over[markers == i] = (0.45 * img[markers == i] + 0.55 * col[i]).astype(np.uint8)
        for r in rooms:
            pts = np.array([[x, y + SHIFT[n]] for x, y in r['poly']], np.int32)
            cv2.polylines(over, [pts], True, (0, 0, 0), 1)
            M = pts.mean(0).astype(int)
            cv2.putText(over, r['id'], tuple(int(v) for v in M), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160), 1)
        for d in doors:
            cv2.circle(over, (d['at'][0], d['at'][1] + SHIFT[n]), 4, (0, 0, 255), -1)
        cv2.imwrite(str(folder / f'trace-{n}.png'), over[OFF[1]:OFF[1] + 640, OFF[0]:OFF[0] + 1650])
        for o in outline:
            cv2.polylines(over, [np.array([[x, y + SHIFT[n]] for x, y in o], np.int32)], True, (0, 120, 0), 2)
        cv2.imwrite(str(folder / f'trace-{n}.png'), over[OFF[1]:OFF[1] + 640, OFF[0]:OFF[0] + 1650])
        print(n, len(rooms), 'rooms', len(doors), 'doors', len(outline), 'outlines', [len(o) for o in outline])
    (ROOT / 'tools' / 'data' / 'moma-plan.json').write_text(json.dumps(out, separators=(',', ':')))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / '.cache' / 'moma' / 'am')
