#!/usr/bin/env python3
"""Download the full-size picture for every What to Notice guide that doesn't have one yet.
Reads data/notice.json; for each work whose `image` file is missing, asks Wikimedia Commons
for its `file` at up to 1280 px wide and 1600 px tall and saves it as data/notice/<id>.jpg.
  python3 tools/fetch_notice_images.py
Commons rate-limits shared IPs, so it batches the API lookups and waits out any 429.
"""
import json, os, time, urllib.parse, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
UA = {'User-Agent': 'GalleryGuide/1.0 (https://github.com/perlamilk/gallery-guide)'}
API = 'https://commons.wikimedia.org/w/api.php?'

def get(url, tries=8):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if i == tries - 1 or e.code not in (429, 500, 502, 503, 504): raise
            wait = int(e.headers.get('Retry-After') or 0) or 2 ** (i + 1)
        except Exception:
            if i == tries - 1: raise
            wait = 2 ** (i + 1)
        print(f'  waiting {wait + 1}s…'); time.sleep(wait + 1)

def imageinfo(titles, **extra):
    """{filename: imageinfo} for up to 50 Commons files in one request."""
    q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url|size',
                                'titles': '|'.join('File:' + t for t in titles), **extra})
    d = json.loads(get(API + q))['query']
    names = {n['to']: n['from'] for n in d.get('normalized', [])}
    out = {}
    for p in d['pages'].values():
        t = names.get(p['title'], p['title']).removeprefix('File:')
        if 'imageinfo' in p: out[t] = p['imageinfo'][0]
    return out

works = json.load(open('data/notice.json'))['works']
todo = {k: w for k, w in works.items() if not os.path.exists(w['image'])}
print(f'{len(todo)} pictures to download')
files = sorted({w['file'] for w in todo.values()})
info = {}
for i in range(0, len(files), 50):
    info.update(imageinfo(files[i:i + 50]))
# group by target width so each width needs one batched thumbnail lookup
widths = {}
for f in files:
    if f not in info: print(f'NOT ON COMMONS: {f}'); continue
    ii = info[f]
    widths.setdefault(min(1280, ii['width'], int(1600 * ii['width'] / ii['height'])), []).append(f)
thumbs = {}
for width, fs in widths.items():
    for i in range(0, len(fs), 50):
        for f, ii in imageinfo(fs[i:i + 50], iiurlwidth=width).items():
            thumbs[f] = (width, ii.get('thumburl') or ii['url'])
for k, w in todo.items():
    if w['file'] not in thumbs: continue
    width, url = thumbs[w['file']]
    os.makedirs(os.path.dirname(w['image']), exist_ok=True)
    data = get(url)
    open(w['image'], 'wb').write(data)
    print(f"{k}: {width}px {len(data)//1024} KB  {w['file']}")
    time.sleep(1)
missing = [k for k, w in works.items() if not os.path.exists(w['image'])]
print(f'{len(missing)} still missing' + (': ' + ', '.join(missing) if missing else ''))
