#!/usr/bin/env python3
"""Find the picture of each chosen WCMA work (run: python3 tools/harvest_wcma.py <path to wcmaart/collection clone>).

WCMA publishes its whole catalogue as open data (github.com/wcmaart/collection, CC0) and a small picture
service for it (github.com/wcmaart/getThumb, get-thumb.herokuapp.com), which answers an object id with a
redirect to the picture on the museum's IIIF server (rs.williams.edu). This asks that service once per work,
one at a time, and keeps each answer in .cache/wcma/iiif.json, so a rerun only asks about new works.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_wcma import ROOT, choose, load_objects  # noqa: E402

CACHE = ROOT / '.cache' / 'wcma'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def main():
    objs = load_objects(Path(sys.argv[1]))
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / 'iiif.json'
    known = json.loads(f.read_text()) if f.exists() else {}
    todo = [o for o in choose(objs) if o['filename'] and str(o['id']) not in known]
    print(len(todo), 'to ask', flush=True)
    for i, o in enumerate(todo):
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-m', '40', '-A', UA, '-w', '%{http_code} %{redirect_url}',
                            f'https://get-thumb.herokuapp.com/getThumb.php?objectid={o["id"]}'],
                           capture_output=True, text=True).stdout.split(' ', 1)
        if r[0] == '302' and len(r) > 1 and '/iiif/image/' in r[1]:
            known[str(o['id'])] = r[1].split('/iiif/image/')[1].split('/')[0]
        elif r[0] == '200':
            known[str(o['id'])] = None   # the service answered: no picture
        else:
            print('busy', o['id'], r[0], flush=True)
            time.sleep(10)               # busy or down: leave it for the next run
        if i % 50 == 0:
            f.write_text(json.dumps(known))
            print(i, r[0], flush=True)
        time.sleep(0.5)
    f.write_text(json.dumps(known))


if __name__ == '__main__':
    main()
