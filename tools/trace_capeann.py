#!/usr/bin/env python3
"""Print the Cape Ann Museum floor guide's outlines and walls as flat-plan coordinates (helper for build_capeann.py).

    python3 -m venv .venv && .venv/bin/pip install pymupdf shapely
    .venv/bin/python tools/trace_capeann.py CAM-Downtown-Map-and-Floor-Guide.pdf

The PDF (capeannmuseum.org/wp-content/uploads/2026/06/CAM-Downtown-Map-and-Floor-Guide.pdf) draws the four levels as
an isometric stack. A page point (x, y) on a level is the plan point (u, v) with x = cos30 (u + v) and
y = sin30 (v - u) + 462 - DY[level], DY measured on the elevator shaft (the grey column through every level): the
shaft's left corner is at page y 462.0 on Level 1, 328.4 on Level 2, 270.2 on Level 3 and 112.8 on Level 4.
Floor outlines are the light blue fills (drawings 19-22), walls the blue strokes. The room polygons in
build_capeann.py were copied from this output; room names and icons were read off the drawing by eye.
"""
import math
import sys

import pymupdf
from shapely.geometry import Point, Polygon

C = math.cos(math.radians(30))
LEVELS = {'1': (19, 0.0), '2': (20, 133.6), '3': (21, 191.8), '4': (22, 349.2)}   # outline drawing, DY
WALL = (0.515, 0.643, 0.729)


def plan(x, y, dy):
    y += dy
    return round((x / C - (y - 462) / 0.5) / 2, 1), round((x / C + (y - 462) / 0.5) / 2, 1)


def main(path):
    drawings = pymupdf.open(path)[0].get_drawings()
    for level, (i, dy) in LEVELS.items():
        pts = [(it[1].x, it[1].y) for it in drawings[i]['items'] if it[0] in 'lc']
        outline = Polygon(pts).buffer(1.5)
        print(f'Level {level} outline:', [plan(x, y, dy) for x, y in pts])
        for d in drawings:
            if d['type'] != 's' or tuple(round(c, 3) for c in d['color']) != WALL: continue
            for it in d['items']:
                if it[0] != 'l': continue
                a, b = (it[1].x, it[1].y), (it[2].x, it[2].y)
                if outline.contains(Point(a)) and outline.contains(Point(b)) and math.dist(a, b) > 1:
                    print('   wall', plan(*a, dy), plan(*b, dy))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'CAM-Downtown-Map-and-Floor-Guide.pdf')
