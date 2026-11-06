#!/usr/bin/env python3
"""Fetch MoMA's open collection data and the pictures of every work on view (run before tools/build_moma.py).

    python3 tools/harvest_moma.py

- Artworks.json and Artists.json: MoMA's collection on GitHub (github.com/MuseumofModernArt/collection, CC0),
  downloaded from media.githubusercontent.com (the files are in Git LFS). Each record has an `OnView` field such as
  "MoMA, Floor 5, 516" for the works on view when the file was exported.
- Pictures: each record's ImageURL (www.moma.org/media/..., 1024 px), fetched once, 1.5 s apart, into
  .cache/moma/img/<ObjectID>.jpg. www.moma.org pages sit behind a Cloudflare challenge; the /media pictures do not.
"""
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'moma'
LFS = 'https://media.githubusercontent.com/media/MuseumofModernArt/collection/main/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def get(url, dest):
    r = subprocess.run(['curl', '-s', '-f', '-L', '-m', '120', '-A', UA, '-o', str(dest), url])
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    for name in ('Artworks.json', 'Artists.json'):
        if not (CACHE / name).exists():
            print('downloading', name); get(LFS + name, CACHE / name)
    works = [w for w in json.loads((CACHE / 'Artworks.json').read_text())
             if (w.get('OnView') or '').startswith('"MoMA, Floor') and w.get('ImageURL')]
    (CACHE / 'img').mkdir(exist_ok=True)
    todo = [w for w in works if not (CACHE / 'img' / f'{w["ObjectID"]}.jpg').exists()]
    print(len(works), 'on view with pictures;', len(todo), 'to fetch')
    for i, w in enumerate(todo):
        dest = CACHE / 'img' / f'{w["ObjectID"]}.jpg'
        if not get(w['ImageURL'], dest):
            print('  failed', w['ObjectID']); dest.unlink(missing_ok=True)
        if i % 100 == 0: print(i, flush=True)
        time.sleep(1.5)


if __name__ == '__main__':
    main()
