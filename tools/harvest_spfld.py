#!/usr/bin/env python3
"""Read the Springfield Museums' gallery pages and collection highlights (run: python3 tools/harvest_spfld.py).

    .cache/spfld/pages/        the pages, read once and kept
    .cache/spfld/maps/         the museums' own maps (springfieldmuseums.org/map: campus + every floor of the 5 museums)
    .cache/spfld/items.json    one row per collection highlight (title, maker, date, medium, accession, On View?, picture)
    .cache/spfld/galleries.json one row per gallery page under /about/ (title, text, picture)

springfieldmuseums.org is WordPress; its robots.txt allows everything. The collection highlights are the ~920
"portfolio" pages listed in portfolio-sitemap.xml: each has the object's data and an "On View?" field. One page every
2 seconds.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'spfld'
SITE = 'https://springfieldmuseums.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
MAPS = ['2015/10/springfield-museums-campus-map-2017', '2015/09/dr-seuss-sculpture-garden-map'] + [
    f'2020/11/{m}' for m in (
        'amazing-world-dr-seuss-museum-map-first-floor', 'amazing-world-dr-seuss-museum-map-second-floor',
        'damour-museum-of-fine-arts-museum-map-first-floor', 'damour-museum-of-fine-arts-museum-map-second-floor',
        'g-w-v-smith-art-museum-map-first-floor', 'g-w-v-smith-art-museum-map-second-floor',
        'museum-of-springfield-history-map-first-floor', 'museum-of-springfield-history-map-second-floor',
        'springfield-science-museum-map-first-floor', 'springfield-science-museum-map-lower-level',
        'springfield-science-museum-map-second-floor')]


def fetch(url, f):
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
        if not out: return None
        f.write_bytes(out)
    return f.read_bytes()


def page(url):
    name = re.sub(r'[^a-z0-9]+', '-', url.replace(SITE, '').lower()).strip('-') or 'home'
    b = fetch(url, CACHE / 'pages' / f'{name[:150]}.html')
    return b.decode('utf-8', 'replace') if b else ''


def text(s):
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', s, flags=re.S)
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = re.sub(r'</(p|h[1-6]|li)>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    s = '\n'.join(re.sub(r'\s+', ' ', l).strip() for l in s.split('\n'))
    return re.sub(r'\n+', '\n', s).strip()


def big_image(s):
    m = re.search(r'id="popup-wrapper">\s*<img[^>]+src="([^"]+)"', s) or \
        re.search(r'<img[^>]+class="[^"]*wp-post-image[^"]*"[^>]*>', s)
    if not m: return None
    if m.re.pattern.startswith('id='): return m[1]
    src = re.search(r'src="([^"]+)"', m[0])
    return src[1] if src else None


def item(url):
    s = page(url)
    if not s: return None
    t = re.search(r'<h1 class="entry-title[^"]*"[^>]*>(.*?)</h1>', s, re.S) or re.search(r'<title>(.*?)\|', s, re.S)
    art = re.search(r'<article class="entry-content[^"]*">(.*?)</article>', s, re.S)
    body = art[1] if art else ''
    desc = text(body.split('<dl', 1)[0])
    meta = {text(k): text(v) for k, v in re.findall(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>', body, re.S)}
    head = s.split('related-portfolio-posts', 1)[0].split('<footer', 1)[0]
    cats = sorted(set(re.findall(r'portfolio_category/([a-z0-9-]+)/', head.split('</header>', 1)[-1])))
    return {'url': url, 'title': text(t[1]) if t else '', 'text': desc, 'meta': meta, 'image': big_image(s),
            'cats': cats}


SKIP_IMG = re.compile(r'logo|affiliate|springfield-museums-\d|medallion|Access-for-All|-map|map-|icon|narm|ASTC|AAM-|'
                      r'MassMutual|sccd|MCC_|WesternMass', re.I)


def best(tag):
    ss = re.search(r'srcset="([^"]+)"', tag)
    src = re.search(r'\bsrc="([^"]+)"', tag)
    if ss:
        c = [x.strip().rsplit(' ', 1) for x in html.unescape(ss[1]).split(',') if x.strip()]
        c = [(int(w.rstrip('w')), u) for u, w in c if len(c) and w.rstrip('w').isdigit()]
        fit = [x for x in c if x[0] <= 1300] or c
        if fit: return max(fit)[1]
    return src[1] if src else None


def gallery(url):
    s = page(url)
    if not s: return None
    t = re.search(r'<title>(.*?)\|', s, re.S)
    body = s.split('<footer', 1)[0]
    k = body.find('Home &raquo;') if 'Home &raquo;' in body else body.find('Home »')
    if k > 0: body = body[k:]
    lines = text(body).split('\n')
    home = next((i for i, l in enumerate(lines) if l.startswith('Home »')), -1)
    lines = [l for l in lines[home + 1:] if not re.match(r'^Springfield Museums\d{4}-', l)]
    imgs = []
    for tag in re.findall(r'<img[^>]+>', body):
        u = best(tag)
        if u and 'wp-content/uploads' in u and not SKIP_IMG.search(u) and u not in imgs: imgs.append(u)
    return {'url': url, 'title': text(t[1]) if t else '', 'text': '\n'.join(lines)[:4000],
            'image': imgs[0] if imgs else None, 'images': imgs[:12]}


def main():
    for m in MAPS:
        fetch(f'{SITE}/wp-content/uploads/{m}.png', CACHE / 'maps' / f'{m.rsplit("/", 1)[1]}.png')
    psm = (fetch(f'{SITE}/page-sitemap.xml', CACHE / 'page-sm.xml') or b'').decode()
    gal_urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', psm) if '/about/' in u and 'wp-content' not in u]
    gals = [g for g in (gallery(u) for u in gal_urls) if g]
    (CACHE / 'galleries.json').write_text(json.dumps(gals, ensure_ascii=False, indent=1))
    print(len(gals), 'gallery pages', flush=True)
    sm = (fetch(f'{SITE}/portfolio-sitemap.xml', CACHE / 'port-sm.xml') or b'').decode()
    urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', sm) if '/portfolio-item/' in u]
    rows = []
    for i, u in enumerate(urls):
        r = item(u)
        if r: rows.append(r)
        if i % 50 == 0:
            print(i, len(urls), flush=True)
            (CACHE / 'items.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (CACHE / 'items.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(len(rows), 'items;', sum(r['meta'].get('On View?', '').lower().startswith('yes') for r in rows), 'on view')


if __name__ == '__main__':
    sys.exit(main())
