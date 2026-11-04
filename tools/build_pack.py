#!/usr/bin/env python3
"""Write data/pack-<museum>.json for each museum with a map guide: every file its offline pack needs,
with its size, so the app can show an accurate download size and a progress bar by megabytes.
Run by tools/publish.sh before each publish."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

PACKS = [
    # (museum, pack list, data files, artworks file, What to Notice file)
    ('Q49133', 'data/pack-mfa.json',
     ['data/artworks.json', 'data/floors.json', 'data/tours.json', 'data/curiosities.json', 'data/notice.json'],
     'data/artworks.json', 'data/notice.json'),
    ('Q403080', 'data/pack-wadsworth.json',
     ['data/wadsworth/artworks.json', 'data/wadsworth/floors.json'],
     'data/wadsworth/artworks.json', None),
    ('Q3783572', 'data/pack-harvard.json',
     ['data/harvard/artworks.json', 'data/harvard/floors.json'],
     'data/harvard/artworks.json', None),
    ('Q847508', 'data/pack-worcester.json',
     ['data/worcester/artworks.json', 'data/worcester/floors.json'],
     'data/worcester/artworks.json', None),
    ('Q49135', 'data/pack-gardner.json',
     ['data/gardner/artworks.json', 'data/gardner/floors.json'],
     'data/gardner/artworks.json', None),
    ('Q1465805', 'data/pack-clark.json',
     ['data/clark/artworks.json', 'data/clark/floors.json'],
     'data/clark/artworks.json', None),
    ('Q2148186', 'data/pack-risd.json',
     ['data/risd/artworks.json', 'data/risd/floors.json'],
     'data/risd/artworks.json', None),
    ('Q3373790', 'data/pack-pem.json',
     ['data/pem/artworks.json', 'data/pem/floors.json'],
     'data/pem/artworks.json', None),
    ('Q6352575', 'data/pack-ycba.json',
     ['data/ycba/artworks.json', 'data/ycba/floors.json'],
     'data/ycba/artworks.json', None),
    ('Q1568434', 'data/pack-yale.json',
     ['data/yale/artworks.json', 'data/yale/floors.json'],
     'data/yale/artworks.json', None),
]

for museum, out_path, files, art_path, notice_path in PACKS:
    if not os.path.exists(art_path):
        continue
    files = list(files)
    art = json.load(open(art_path))['artworks']
    notice = json.load(open(notice_path))['works'] if notice_path else {}
    for a in art:
        for u in (a.get('image'), (a.get('img') or {}).get('p')):
            if u and u not in files and not u.startswith('http'): files.append(u)   # remote pictures (Harvard) stay online
    for w in notice.values():
        if w.get('image') and w['image'] not in files: files.append(w['image'])
    out = [{'u': u, 's': os.path.getsize(u)} for u in files if os.path.exists(u)]
    missing = [u for u in files if not os.path.exists(u)]
    json.dump({'museum': museum, 'works': len(art), 'notice': len(notice), 'bytes': sum(f['s'] for f in out), 'files': out},
              open(out_path, 'w'), separators=(',', ':'))
    print(f"{out_path}: {len(out)} files, {sum(f['s'] for f in out) / 1e6:.0f} MB" + (f", {len(missing)} missing: {missing[:5]}" if missing else ''))
