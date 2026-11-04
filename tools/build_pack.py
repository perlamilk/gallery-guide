#!/usr/bin/env python3
"""Write data/pack-mfa.json: every file the MFA offline pack needs, with its size,
so the app can show an accurate download size and a progress bar by megabytes.
Run by tools/publish.sh before each publish."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
files = ['data/artworks.json', 'data/floors.json', 'data/tours.json', 'data/curiosities.json', 'data/notice.json']
art = json.load(open('data/artworks.json'))['artworks']
notice = json.load(open('data/notice.json'))['works']
for a in art:
    for u in (a.get('image'), (a.get('img') or {}).get('p')):
        if u and u not in files: files.append(u)
for w in notice.values():
    if w.get('image') and w['image'] not in files: files.append(w['image'])
out = [{'u': u, 's': os.path.getsize(u)} for u in files if os.path.exists(u)]
missing = [u for u in files if not os.path.exists(u)]
json.dump({'museum': 'Q49133', 'works': len(art), 'notice': len(notice), 'bytes': sum(f['s'] for f in out), 'files': out},
          open('data/pack-mfa.json', 'w'), separators=(',', ':'))
print(f"pack: {len(out)} files, {sum(f['s'] for f in out) / 1e6:.0f} MB" + (f", {len(missing)} missing: {missing[:5]}" if missing else ''))
