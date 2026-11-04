#!/usr/bin/env python3
"""Read the Yale Peabody Museum's exhibition pages (run: python3 tools/harvest_ypm.py).

    .cache/ypm/pages/       the pages, read once and kept
    .cache/ypm/map.pdf      the museum's own floor plan (peabody.yale.edu/resource/download/215, Oct 2025)
    .cache/ypm/cards.json   one row per gallery page and per object card on it

peabody.yale.edu answers scripts and its robots.txt allows everything outside admin, search and user pages. The
collection database (peabody.collections.yale.edu) is a JavaScript app behind CloudFront that blocks scripts, so
it is not used: each gallery page has cards (heading, text, picture, credit, catalogue number) for the things in it.
One page every 2 seconds.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'ypm'
SITE = 'https://peabody.yale.edu'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def get(path, name):
    f = CACHE / 'pages' / f'{name}.html'
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, SITE + path], capture_output=True).stdout
        time.sleep(2)
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def text(s):
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = re.sub(r'</p>\s*<p[^>]*>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    s = '\n'.join(re.sub(r'\s+', ' ', l).strip() for l in s.split('\n'))
    return re.sub(r'\n+', '\n', s).strip()


def best_src(tag):
    ss = re.search(r'srcset="([^"]+)"', tag)
    if ss:
        cands = [c.strip().rsplit(' ', 1) for c in html.unescape(ss[1]).split(',') if c.strip()]
        cands = [(int(w.rstrip('w')), u) for u, w in cands if w.rstrip('w').isdigit()]
        fit = [c for c in cands if c[0] <= 1120] or cands
        return SITE + max(fit)[1]
    src = re.search(r'src="([^"]+)"', tag)
    return SITE + html.unescape(src[1]) if src else None


def page_rows(slug, page):
    rows = []
    body = page.split('class="site-footer"')[0]
    title = text(re.search(r'<title>(.*?)</title>', page, re.S)[1]).split(' | ')[0]
    intro = ' '.join(text(t) for t in re.findall(r'<div\s+class="text">(.*?)</div>', body, re.S))
    hero = re.search(r'<img loading="eager"[^>]*16_5_[^>]*>', body)
    rows.append({'page': slug, 'kind': 'gallery', 'title': title, 'text': intro,
                 'image': best_src(hero[0]) if hero else None, 'url': f'{SITE}/explore/exhibitions/{slug}'})
    for cls in ('text-with-image', 'content-spotlight-portrait'):
        for m in re.finditer(rf'class="{cls}">(.*?)(?=<div class="ys-block-wrapper|class="site-footer")', page, re.S):
            b = m[1]
            h = re.search(rf'class="{cls}__heading"\s*>(.*?)</h2>', b, re.S)
            if not h: continue
            t = re.search(rf'class="{cls}__text">(.*?)</div>\s*</div>', b, re.S)
            img = re.search(r'<img[^>]+>', b)
            cap = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', b, re.S)
            links = [(html.unescape(u), text(l)) for u, l in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)]
            more = [l.replace('More info:', '').strip() for u, l in links if l.startswith('More info')]
            rows.append({'page': slug, 'kind': 'card', 'title': text(h[1]), 'text': text(t[1]) if t else '',
                         'image': best_src(img[0]) if img else None, 'credit': text(cap[1]) if cap else '',
                         'catalog': more, 'links': [u for u, l in links], 'pos': m.start()})
    rows[1:] = sorted(rows[1:], key=lambda r: r['pos'])
    return rows


def main():
    idx = get('/explore/exhibitions', 'exhibitions')
    slugs = sorted(set(re.findall(r'href="/explore/exhibitions/([a-z0-9-]+)"', idx)))
    rows = []
    for s in slugs:
        page = get(f'/explore/exhibitions/{s}', s)
        if page: rows += page_rows(s, page)
    for s in ('about-time', 'unfolding-history'):
        get(f'/news/{s}', f'news_{s}')
    pdf = CACHE / 'map.pdf'
    if not pdf.exists():
        pdf.write_bytes(subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, SITE + '/resource/download/215'],
                                       capture_output=True).stdout)
    (CACHE / 'cards.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'{len(slugs)} pages, {len(rows)} rows')
    for r in rows: print(f"  {r['page'][:24]:24} {r['kind']:7} {'P' if r['image'] else ' '} {r['title'][:50]}")


if __name__ == '__main__':
    main()
