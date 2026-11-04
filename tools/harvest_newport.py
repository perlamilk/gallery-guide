#!/usr/bin/env python3
"""Collect the Newport Art Museum's works from its own website (run before tools/build_newport.py).

newportartmuseum.org is WordPress. Its robots.txt asks for 10 seconds between requests, so every page is fetched once,
10 seconds apart, and kept in .cache/newport. What is read:

  - the exhibitions now on view: /wp-json/wp/v2/exhibitions?exhibitions-categories=22 ("Now On View"), each
    exhibition's page (its text, the captioned pictures in its gallery, and the gallery the page names) and its
    featured picture (/wp-json/wp/v2/media/<id>)
  - the collection highlights on /collection/american-art, /works-on-paper, /contemporary-art and /photography
    (15 captioned pictures each, with credit line and accession number)
  - the 2025 Cushing show page, whose captions name four Cushing paintings in the museum's own collection

Writes .cache/newport/works.json.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'newport'
SITE = 'https://newportartmuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
NOW_ON_VIEW = 22
COLLECTION = ['american-art', 'works-on-paper', 'contemporary-art', 'photography']
CUSHING_2025 = 'howard-gardiner-cushing-a-harmony-of-line-and-color'


def get(url, name):
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(10)                                  # robots.txt: Crawl-delay 10
        if not out: raise SystemExit(f'no answer from {url}')
        f.write_bytes(out)
    return f.read_text()


def text(s):
    s = re.sub(r'<br\s*/?>', ' ', s or '')
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s))).strip()


def slides(page):
    """The captioned pictures in a page's slide gallery: [(picture url, caption)]."""
    out = []
    for m in re.finditer(r"fc-gallery-slide-image\" style=\"background-image: url\('([^']+)'\);\">(.*?)"
                         r"(?=fc-gallery-slide-image\"|</section>)", page, flags=re.S):
        cap = re.search(r'fc-image-caption">(.*?)</p>', m[2], flags=re.S)
        cap = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', m[2], flags=re.S) if not cap else cap
        out.append((m[1], text(cap[1]) if cap else ''))
    if not out:                                         # older pages: <img> + <figcaption>
        for m in re.finditer(r'<img[^>]+src="(https://pub[^"]+)"[^>]*>\s*(?:</a>)?\s*<figcaption[^>]*>(.*?)</figcaption>',
                             page, flags=re.S):
            out.append((m[1], text(m[2])))
    return [(u, c) for u, c in out if c]


def body(page):
    """An exhibition page's own text (between "Back To Exhibitions" and the address in the footer)."""
    i = page.find('Back To Exhibitions')
    j = page.find('76 Bellevue Avenue', i)
    seg = page[i:j] if i > 0 else ''
    seg = re.split(r'fc-gallery-slick', seg)[0]
    paras = [text(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', seg, flags=re.S)]
    return [p for p in paras if p and len(p) > 40]


def where(page):
    """The gallery an exhibition page names under its dates (e.g. "Cushing Gallery", "Griswold House")."""
    i = page.find('Back To Exhibitions')
    head = text(page[i:i + 3000])
    m = re.search(r'\d{4}\s+(Cushing Gallery|Griswold House|Ilgenfritz Gallery|Cushing Building|[A-Z][a-z]+ Gallery)',
                  head)
    return m[1] if m else None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    exh = json.loads(get(f'{SITE}/wp-json/wp/v2/exhibitions?per_page=50&exhibitions-categories={NOW_ON_VIEW}',
                         'now-on-view.json'))
    shows = []
    for e in exh:
        page = get(e['link'], f'ex-{e["slug"]}.html')
        i = page.find('Back To Exhibitions')
        dates = re.search(r'([A-Z][a-z]+ \d+, \d{4})\s*-\s*([A-Z][a-z]+ \d+, \d{4})', text(page[i:i + 3000]))
        pic = None
        if e.get('featured_media'):
            m = json.loads(get(f'{SITE}/wp-json/wp/v2/media/{e["featured_media"]}', f'media-{e["featured_media"]}.json'))
            pic = m.get('source_url')
        shows.append({'slug': e['slug'], 'title': text(e['title']['rendered']), 'url': e['link'],
                      'dates': f'{dates[1]}–{dates[2]}' if dates else None,
                      'where': where(page), 'text': body(page), 'image': pic,
                      'works': [{'image': u, 'caption': c} for u, c in slides(page)]})
    coll = []
    for c in COLLECTION:
        page = get(f'{SITE}/collection/{c}/', f'pg-collection-{c}.html')
        coll += [{'area': c, 'image': u, 'caption': cap} for u, cap in slides(page)]
    page = get(f'{SITE}/exhibitions/{CUSHING_2025}/', 'ex-cushing-harmony.html')
    cushing = [{'image': u, 'caption': c} for u, c in slides(page) if 'Collection of Newport Art Museum' in c]
    out = {'checked': time.strftime('%Y-%m-%d'), 'shows': shows, 'collection': coll, 'cushing': cushing}
    (CACHE / 'works.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'{len(shows)} shows on view, {sum(len(s["works"]) for s in shows)} captioned works in them, '
          f'{len(coll)} collection highlights, {len(cushing)} Cushing paintings')
    for s in shows: print(f'  {s["title"]} ({s["dates"]}) at {s["where"]}: {len(s["works"])}')


if __name__ == '__main__':
    main()
