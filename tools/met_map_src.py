#!/usr/bin/env python3
"""Fetch and merge The Met's own indoor map (maps.metmuseum.org, made by Living Map) for the Fifth Avenue
building: vector tiles at zoom 18 → .cache/met/indoor.json, one merged feature per map object and floor
(polygons pieced back together across tile edges), in longitude/latitude.

Run once; tools/build_met.py reads the result. About 50 tile requests, half a second apart."""
import glob, json, math, os, time, urllib.request, collections
import mapbox_vector_tile as mvt
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, linemerge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(ROOT, '.cache', 'met')
T = os.path.join(C, 'mapsrc', 'tiles')
Z = 18
UA = {'User-Agent': 'gallery-guide/1.0 (museum visitor guide)'}
URL = 'https://prod.cdn.livingmap.com/tiles/the_met/{z}/{x}/{y}.pbf?lang=en-GB'
BBOX = (-73.9672, 40.7762, -73.9598, 40.7818)   # the Fifth Avenue building and the plaza


def tile(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def fetch():
    os.makedirs(T, exist_ok=True)
    x0, y0 = tile(BBOX[0], BBOX[3]); x1, y1 = tile(BBOX[2], BBOX[1])
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            p = os.path.join(T, f'{Z}_{x}_{y}.pbf')
            if os.path.exists(p):
                continue
            with urllib.request.urlopen(urllib.request.Request(URL.format(z=Z, x=x, y=y), headers=UA), timeout=60) as r:
                open(p, 'wb').write(r.read())
            time.sleep(0.5)


def lonlat(x, y, tx, ty, ext):
    n = 2 ** Z
    lon = (tx + x / ext) / n * 360 - 180
    yy = ty + 1 - y / ext                     # tile y grows down, decoded y grows up
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return lon, lat


def walk(g, f):
    if isinstance(g[0], (int, float)):
        return f(*g)
    return [walk(c, f) for c in g]


def main():
    fetch()
    parts = collections.defaultdict(list)
    props = {}
    for p in glob.glob(os.path.join(T, '*.pbf')):
        _, tx, ty = map(int, os.path.basename(p)[:-4].split('_'))
        for layer, v in mvt.decode(open(p, 'rb').read()).items():
            if layer not in ('indoor', 'outdoor'):
                continue
            ext = v.get('extent', 4096)
            for ft in v['features']:
                pr = ft['properties']
                g = ft['geometry']
                g = {'type': g['type'], 'coordinates': walk(g['coordinates'], lambda x, y: lonlat(x, y, tx, ty, ext))}
                key = (layer, pr.get('geom_id'), pr.get('floor_id'), g['type'].replace('Multi', ''), pr.get('geom_type'))
                parts[key].append(shape(g))
                props[key] = pr
    out = []
    for key, gs in parts.items():
        kind = key[3]
        if kind == 'Polygon':
            g = unary_union([x.buffer(1e-7) for x in gs]).buffer(-1e-7)
        elif kind == 'LineString':
            u = unary_union(gs)
            g = linemerge(u) if u.geom_type == 'MultiLineString' else u
        else:
            g = gs[0]
        out.append({'layer': key[0], 'props': props[key], 'geometry': mapping(g)})
    json.dump(out, open(os.path.join(C, 'indoor.json'), 'w'))
    print(len(out), 'features')


if __name__ == '__main__':
    main()
