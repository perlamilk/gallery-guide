#!/usr/bin/env python3
"""Read the Eric Carle Museum's own pages for the works it shows (run: python3 tools/harvest_carle.py).

The Carle has no public collection database ("a long-term goal", 2022). What it publishes is
  - a page for each current and upcoming exhibition, with the gallery it is in and pictured works with captions,
  - Collection Highlights (6 themes) and Featured Artists (14 artists) pages: 300+ works of the permanent
    collection, put online for the 20th anniversary in 2022.
carlemuseum.org's robots.txt allows these pages. They are fetched one at a time, 3 seconds apart, and kept in
.cache/carle (not in git), so a second run reads nothing from the web. Output: .cache/carle/harvest.json, read by
tools/build_carle.py.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'carle'
SITE = 'https://carlemuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'

EXHIBITIONS = [
    'current-exhibition/eric-carles-modernist-inspirations',
    'current-exhibition/soul-sound-voice-art-jerry-pinkney',
    'current-exhibition/under-cork-tree-story-ferdinand',
    'current-exhibition/entwined-memory-indigenous-stories-creation-place-and',
    'upcoming-exhibition/weaving-words-fiber-arts-and-picture-books',
    'upcoming-exhibition/precious-things-we-share-past-present-and-future',
]
HIGHLIGHTS = ['animals', 'beloved-picture-book-characters', 'children-adventure', 'folk-tales-fairy-tales-fantasy',
              'home-away', 'music-dance']
ARTISTS = ['alice-bolam-preston', 'antonio-frasconi', 'arnold-lobel', 'ashley-bryan', 'brinton-turkle', 'eric-carle',
           'j-p-miller', 'juhong-chen', 'leo-lionni', 'leonard-weisgard', 'petra-mathers', 'simms-taback',
           'susanne-suba', 'william-steig']

_last = [0.0]


def get(path, binary=False):
    """One page or picture from carlemuseum.org, cached on disk."""
    name = re.sub(r'[^\w.-]+', '_', path.split('?')[0].strip('/'))
    f = CACHE / ('img' if binary else 'pages') / (name if binary else name + '.html')
    if f.exists() and f.stat().st_size > 0:
        return f if binary else f.read_text(errors='replace')
    f.parent.mkdir(parents=True, exist_ok=True)
    wait = 3 - (time.time() - _last[0])
    if wait > 0: time.sleep(wait)
    url = path if path.startswith('http') else SITE + path
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
    _last[0] = time.time()
    if not out:
        print('  no answer:', url, file=sys.stderr)
        return None
    f.write_bytes(out)
    return f if binary else out.decode(errors='replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).replace(' ,', ',').replace(' .', '.').strip()


SKIP_IMG = re.compile(r'/styles/(teaser|social|thumbnail|card)|logo|_install_|install\d|gallery[-_]view|banner', re.I)
STOP = re.compile(r'\b(Previous|Gallery Views|Featured Artists|Exhibition Highlights|Explore Further|Event|'
                  r'What to Expect|Learn more)\b')


def pictures(page):
    """(picture url, caption) for every captioned artwork picture on a page."""
    s = re.sub(r'(?s)<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', page)
    imgs = list(re.finditer(r'<img[^>]*?(?:data-src|src)="(/sites/default/files/[^"]+)"[^>]*>', s))
    out, seen = [], set()
    for i, m in enumerate(imgs):
        src = html.unescape(m.group(1))
        if SKIP_IMG.search(src): continue
        end = imgs[i + 1].start() if i + 1 < len(imgs) else len(s)
        text = clean(s[m.end():min(end, m.end() + 4000)]).replace('See full image', '').strip()
        text = text.replace('Featured Image Caption', '').strip()
        cut = STOP.search(text)
        if cut: text = text[:cut.start()].strip()
        if len(text) < 12 or not re.search(r'©|Collection|Courtesy|Gift|Public domain|Illustration|Museum', text):
            continue
        key = re.sub(r'\?.*', '', src.split('/')[-1])
        if key in seen: continue
        seen.add(key)
        out.append({'src': src, 'caption': text})
    return out


def main():
    data = {'checked': time.strftime('%Y-%m-%d'), 'exhibitions': [], 'collection': []}
    for path in EXHIBITIONS:
        page = get('/art-books/exhibitions/' + path)
        if not page: continue
        body = clean(re.sub(r'(?s)<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', page))
        title = clean(re.search(r'<title>(.*?)\|', page, re.S).group(1))
        when = re.search(re.escape(title) + r' ((?:[A-Z][a-z]+ \d{1,2}, \d{4}|[A-Z][a-z]+ \d{1,2}) - [A-Z][a-z]+ \d{1,2}, \d{4}) '
                         r'(West Gallery|East Gallery|Central Gallery|Reading Library)', body)
        data['exhibitions'].append({'path': path, 'title': title, 'dates': when and when.group(1),
                                    'room': when and when.group(2), 'url': SITE + '/art-books/exhibitions/' + path,
                                    'works': pictures(page)})
        print(f'{title}: {when and when.group(2)}, {len(data["exhibitions"][-1]["works"])} pictures')
    for group, names in (('collection-highlights', HIGHLIGHTS), ('featured-artists', ARTISTS)):
        for n in names:
            path = f'/art-books/collections/{group}/{n}'
            page = get(path)
            if not page: continue
            works = pictures(page)
            data['collection'].append({'path': path, 'url': SITE + path, 'works': works})
            print(f'{path}: {len(works)} pictures')
    (CACHE / 'harvest.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
