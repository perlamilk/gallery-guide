#!/usr/bin/env python3
"""Download the full-size picture for every What to Notice guide that doesn't have one yet.
Reads data/notice.json; for each work whose `image` file is missing, asks Wikimedia Commons
for its `file` at up to 1280 px wide and 1600 px tall and saves it as data/notice/<id>.jpg.
  python3 tools/fetch_notice_images.py
"""
import json, os, time, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
UA = {'User-Agent': 'GalleryGuide/1.0 (https://github.com/perlamilk/gallery-guide)'}

def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == 3: raise
            time.sleep(2 ** (i + 1))

works = json.load(open('data/notice.json'))['works']
todo = {k: w for k, w in works.items() if not os.path.exists(w['image'])}
print(f'{len(todo)} pictures to download')
for k, w in todo.items():
    q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url|size',
                                'titles': 'File:' + w['file']})
    page = next(iter(json.loads(get('https://commons.wikimedia.org/w/api.php?' + q))['query']['pages'].values()))
    info = page['imageinfo'][0]
    width = min(1280, info['width'], int(1600 * info['width'] / info['height']))
    q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url',
                                'iiurlwidth': width, 'titles': 'File:' + w['file']})
    page = next(iter(json.loads(get('https://commons.wikimedia.org/w/api.php?' + q))['query']['pages'].values()))
    url = page['imageinfo'][0].get('thumburl') or page['imageinfo'][0]['url']
    os.makedirs(os.path.dirname(w['image']), exist_ok=True)
    open(w['image'], 'wb').write(get(url))
    print(f"{k}: {width}px  {w['file']}")
    time.sleep(1)
