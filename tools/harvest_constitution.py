#!/usr/bin/env python3
"""Read the USS Constitution Museum's online collection, once and slowly (run: python3 tools/harvest_constitution.py).

The museum's "Explore the Collection" pages (ussconstitutionmuseum.org/collection-items/...) are listed in its
sitemap (collection_items-sitemap.xml, about 205 objects). Each page gives the title, the museum's text, creator,
date, medium, dimensions, catalogue number, credit line and terms of use (CC BY-NC-ND 3.0), and a picture.

robots.txt asks for 10 seconds between requests, so this takes about an hour; every page and picture is kept in
.cache/constitution, so running it again only reads what is new. Output: .cache/constitution/collection.json, which
tools/build_constitution.py reads.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'constitution'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITEMAP = 'https://ussconstitutionmuseum.org/collection_items-sitemap.xml'
DELAY = 10
_last = [0.0]


def get(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    wait = _last[0] + DELAY - time.time()
    if wait > 0: time.sleep(wait)
    subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, '-o', str(dest), url])
    _last[0] = time.time()
    return dest if dest.exists() and dest.stat().st_size > 0 else None


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def parse(page):
    t = page.read_text(errors='replace')
    item = {}
    m = re.search(r'<div class="heading-divider container">\s*<h2>(.*?)</h2>', t, re.S)
    item['title'] = text(m.group(1)) if m else None
    m = re.search(r'<!--ONE COLUMN CONTENT-->.*?<div class="col-lg-12">(.*?)</div>', t, re.S)
    if m:
        paras = [text(p) for p in re.findall(r'<p>(.*?)</p>', m.group(1), re.S)]
        item['text'] = '\n\n'.join(p for p in paras if p)
    for label, body in re.findall(r'<p><strong>([^<]+)</strong><br>(.*?)</p>\s*(?=<p><strong>|</div>)', t, re.S):
        item[label.strip()] = text(body)
    m = re.search(r'id="download_media_image" href="([^"]+)"', t)
    item['image'] = m.group(1) if m else None
    if not item['image']:
        m = re.search(r'<meta property="og:image" content="([^"]+)"', t)
        item['image'] = m.group(1) if m else None
    return item


def main():
    sm = get(SITEMAP, CACHE / 'ci-sitemap.xml')
    urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', sm.read_text()) if u.rstrip('/').count('/') > 3
            and '/collection-items/' in u and not u.endswith('/collection-items/')]
    print(len(urls), 'objects')
    items = []
    for i, u in enumerate(urls):
        slug = u.rstrip('/').rsplit('/', 1)[1]
        page = get(u, CACHE / 'items' / f'{slug}.html')
        if not page: print('  missing', u); continue
        it = parse(page)
        it['url'] = u
        it['slug'] = slug
        if it.get('image'):
            ext = it['image'].rsplit('.', 1)[-1].lower()[:4]
            pic = get(it['image'], CACHE / 'pics' / f'{slug}.{ext}')
            it['picture'] = str(pic.relative_to(ROOT)) if pic else None
        items.append(it)
        if i % 20 == 0: print(f'  {i + 1}/{len(urls)} {it.get("title")}', flush=True)
    (CACHE / 'collection.json').write_text(json.dumps(items, ensure_ascii=False, indent=1))
    print(len(items), 'saved,', sum(bool(i.get('picture')) for i in items), 'with pictures')


if __name__ == '__main__':
    sys.exit(main())
