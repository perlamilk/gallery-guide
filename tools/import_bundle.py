#!/usr/bin/env python3
"""Put a harvest into the app.

    python3 tools/import_bundle.py ~/Downloads/mfa-harvest.bundle

Reads the single file made by tools/export-bundle.js, then writes
  data/artworks.json            all works on view, sorted by gallery
  data/images/images-NNN.bin    the pictures, about 15 MB per pack
Works that tours.json uses but the harvest lacks keep their old entry (and .jpg).
Checks everything before replacing anything; prints a short report.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
IMAGES = os.path.join(DATA, 'images')
PACK_SIZE = 15_000_000
MAGIC = b'MFAHARV1'


def fail(msg):
    sys.exit(f'import stopped: {msg}')


def main(path):
    with open(path, 'rb') as f:
        blob = f.read()
    if blob[:8] != MAGIC:
        fail('not a harvest bundle')
    n = int.from_bytes(blob[8:12], 'little')
    doc = json.loads(blob[12:12 + n].decode('utf-8'))
    pics = memoryview(blob)[12 + n:]
    works = doc.get('artworks') or []
    if len(works) < 500:
        fail(f'only {len(works)} works in the bundle; the harvest looks unfinished')

    # repack pictures in gallery order (the bundle is already sorted that way)
    packs, current = [], bytearray()
    for w in works:
        img = w.pop('img', None)
        if not img:
            continue
        o, l = img['o'], img['l']
        if o + l > len(pics) or l <= 0:
            fail(f'picture for {w.get("id")} lies outside the bundle')
        if current and len(current) + l > PACK_SIZE:
            packs.append(current)
            current = bytearray()
        w['img'] = {'p': f'data/images/images-{len(packs) + 1:03d}.bin', 'o': len(current), 'l': l}
        current += pics[o:o + l]
    if current:
        packs.append(current)

    # keep tour works the harvest didn't include
    old = json.load(open(os.path.join(DATA, 'artworks.json')))['artworks']
    tours = json.load(open(os.path.join(DATA, 'tours.json')))['tours']
    tour_ids = {str(i) for t in tours for s in t['stops'] for i in s.get('works', [])}
    have = {str(w['id']) for w in works}
    kept = [w for w in old if str(w['id']) in tour_ids and str(w['id']) not in have]
    works.extend(kept)
    # a harvested work with no picture yet keeps the sample's picture, if it had one
    old_pics = {str(w['id']): w for w in old if w.get('image')}
    for w in works:
        o = old_pics.get(str(w['id']))
        if o and 'img' not in w and not w.get('image'):
            for k in ('image', 'imageSource', 'imageCredit'):
                if o.get(k):
                    w[k] = o[k]
    keep_jpgs = {os.path.basename(w['image']) for w in works if w.get('image')}

    # spot-check pictures are JPEG/PNG/WebP
    for w in works[:: max(1, len(works) // 200)]:
        if 'img' in w:
            pack = packs[int(w['img']['p'][-7:-4]) - 1]
            head = bytes(pack[w['img']['o']:w['img']['o'] + 4])
            if not (head[:3] == b'\xff\xd8\xff' or head == b'\x89PNG' or head == b'RIFF'):
                fail(f'picture for {w["id"]} is not an image')

    # write: packs first, then the JSON that points at them
    for name in os.listdir(IMAGES):
        if name.endswith('.bin') or (name.endswith('.jpg') and name not in keep_jpgs):
            os.remove(os.path.join(IMAGES, name))
    for i, p in enumerate(packs, 1):
        with open(os.path.join(IMAGES, f'images-{i:03d}.bin'), 'wb') as f:
            f.write(p)
    doc['artworks'] = works
    doc['count'] = len(works)
    with open(os.path.join(DATA, 'artworks.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))

    with_pic = sum(1 for w in works if 'img' in w or w.get('image'))
    galleries = len({w.get('gallery') for w in works if w.get('gallery')})
    missing_tour = sorted(tour_ids - {str(w['id']) for w in works})
    print(f'{len(works)} works · {with_pic} with pictures · {galleries} galleries · '
          f'{len(packs)} packs ({sum(map(len, packs)) / 1e6:.0f} MB)')
    print(f'kept from the sample: {len(kept)} · tour works missing: {missing_tour or "none"}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
