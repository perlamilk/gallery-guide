#!/usr/bin/env python3
"""Read the ICA Boston collection from icaboston.org, politely (run: python3 tools/harvest_ica.py).

The museum's collection search (icaboston.org/collection) loads its results from
wp-admin/admin-ajax.php?action=fetch_artworks (16 works a page). Each work then has its own page with
artist, year, materials, dimensions, credit line, accession number and a short text. Everything is
cached in .cache/ica (one request every 2 seconds); the result goes to .cache/ica/collection.json,
which tools/build_ica.py reads.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'ica'
API = 'https://www.icaboston.org/wp-admin/admin-ajax.php?action=fetch_artworks'
UA = 'Mozilla/5.0 (gallery-guide personal museum guide)'


def get(url, name, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if f.exists() and f.stat().st_size > 500 and not refresh:
        return f.read_text(errors='replace')
    for attempt in range(3):
        out = subprocess.run(['curl', '-sL', '-m', '40', '-A', UA, url], capture_output=True, check=False).stdout
        time.sleep(2)                    # polite: one request every 2 seconds
        if len(out) > 500: break
        time.sleep(10 * (attempt + 1))
    f.write_bytes(out)
    return out.decode('utf-8', 'replace')


def text(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).split())


def field(page, name):
    return [text(m) for m in re.findall(
        rf'<div class="field field-name-field-{name}[^"]*"[^>]*>(.*?)</div>\s*(?=<div class="field|</div>\s*</div>|\n\s*\n)', page, re.S)]


def parse_work(page):
    w = {}
    m = re.search(r'<div class="group-info field-group-div">(.*?)<div class="field field-name-field-notes', page, re.S)
    info = m[1] if m else ''
    w['artist'] = ', '.join(text(a) for a in re.findall(r'<div class="artist[^"]*">(.*?)</div>', info, re.S))
    y = re.search(r'field-name-field-year.*?<div class="field-item[^"]*">(.*?)</div>', info, re.S)
    w['date'] = text(y[1]) if y else ''
    mat = re.search(r'field-name-field-materials[^>]*>(.*?)</div>', info, re.S)
    w['medium'] = text(mat[1]) if mat else ''
    dims = [text(d) for d in re.findall(r'field-name-field-dimensions[^>]*>(.*?)</div>', info, re.S)]
    w['edition'] = next((d for d in dims if re.match(r'(Edition|Unique|AP\b|Artist)', d)), '')
    w['dimensions'] = next((d for d in dims if d != w['edition']), '')
    n = re.search(r'field-name-field-notes.*?</div>\s*</div>\s*</div>', page, re.S)
    items = [text(i) for i in re.findall(r'<div class="field-item[^"]*">(.*?)</div>', n[0], re.S)] if n else []
    acc = [i for i in items if re.fullmatch(r'[\w.\-]+(?: ?[a-z.\-]+)?', i) and re.search(r'\d', i)]
    w['accession'] = acc[-1] if acc else ''
    w['credit'] = next((i for i in items if i and i not in acc), '')
    body = re.search(r'field-name-body.*?<div class="field-item[^"]*">(.*?)</div>', page, re.S)
    w['about'] = text(body[1]) if body else ''
    og = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    w['ogImage'] = og[1] if og else ''
    return w


def best_src(thumb):
    srcs = re.findall(r'(https://[^\s"]+?) (\d+)w', thumb or '')
    pick = [u for u, wd in srcs if 400 <= int(wd) <= 800] or [u for u, wd in srcs]
    m = re.search(r'src="([^"]+)"', thumb or '')
    return (sorted(srcs, key=lambda s: abs(int(s[1]) - 683))[0][0] if srcs else (m[1] if m else '')), \
           (re.search(r'alt="([^"]*)"', thumb or '') or [None, ''])[1]


def main():
    refresh = '--refresh' in sys.argv
    first = json.loads(get(API, 'api-1.json', refresh))
    pages = first['meta']['total_page']
    rows = list(first['data'])
    for p in range(2, pages + 1):
        rows += json.loads(get(f'{API}&page={p}', f'api-{p}.json', refresh))['data']
    print(f'{len(rows)} works listed (site says {first["meta"]["total"]})', flush=True)
    out = []
    for i, r in enumerate(rows):
        slug = r['permalink'].rstrip('/').split('/art/')[-1].replace('/', '__')
        page = get(r['permalink'], f'art-{slug}.html', refresh)
        w = parse_work(page)
        img, alt = best_src(r.get('thumbnail'))
        out.append({'wpId': r['id'], 'title': html.unescape(r['title']), 'artists': html.unescape(r['artists'] or ''),
                    'url': r['permalink'], 'image': img or w['ogImage'], 'alt': html.unescape(alt), **w})
        if i % 25 == 0: print(f'  {i + 1}/{len(rows)} {out[-1]["title"]}', flush=True)
    (CACHE / 'collection.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'wrote {len(out)} works to .cache/ica/collection.json')


if __name__ == '__main__':
    main()
