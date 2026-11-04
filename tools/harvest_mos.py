#!/usr/bin/env python3
"""Read the Museum of Science (Boston) exhibit pages on mos.org (run: python3 tools/harvest_mos.py).

    .cache/mos/pages/        the pages, read once and kept
    .cache/mos/exhibits.json one row per page: title, subtitle, permanent or not, location, text, picture

mos.org's robots.txt allows every page outside /admin, /search and the user pages, and lists them all in its
sitemap. This reads the sitemap, then each exhibit, live presentation and drop-in activity page, one page every
2 seconds. Each page states its "Location" (wing and level), which places it on the map.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'mos'
SITE = 'https://www.mos.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
KINDS = ('visit/exhibits/', 'visit/live-presentations/', 'visit/drop-in-activities/')


def get(url, name):
    f = CACHE / 'pages' / (re.sub(r'[^\w-]+', '_', name.strip('/'))[:150] + '.html')
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def lines(page):
    t = re.sub(r'<script.*?</script>|<style.*?</style>|<header.*?</header>|<footer.*?</footer>|<nav.*?</nav>', '',
               page, flags=re.S)
    t = re.sub(r'</?(em|i|strong|b|a)\b[^>]*>', '', t)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', t))
    return [re.sub(r'\s+', ' ', l).strip() for l in t.split('\n') if l.strip()]


def after(ls, key):
    return ls[ls.index(key) + 1] if key in ls and ls.index(key) + 1 < len(ls) else ''


def meta(page, prop):
    m = re.search(rf'<meta (?:property|name)="{prop}" content="([^"]*)"', page)
    return html.unescape(m[1]) if m else ''


BAD_ALT = re.compile(r'logo|pride|overnight|weekend|celebration|gala|members', re.I)


def first_picture(page):
    """The first picture in the page body, when the page has no og:image (skips logos and event photos)."""
    for tag in re.findall(r'<img[^>]+>', page):
        src = re.search(r'src="([^"]+)"', tag)
        alt = re.search(r'alt="([^"]*)"', tag)
        if not src or '/files/' not in src[1] and 'widen.net' not in src[1]: continue
        if re.search(r'logo|optnav|favicon|MathWorks', src[1]) or (alt and BAD_ALT.search(alt[1])): continue
        url = html.unescape(src[1])
        return (SITE + url) if url.startswith('/') else url
    return None


def main():
    sm = CACHE / 'sitemap.xml'
    if not sm.exists():
        sm.parent.mkdir(parents=True, exist_ok=True)
        sm.write_bytes(subprocess.run(['curl', '-s', '-f', '-m', '60', '-A', UA, SITE + '/sitemap.xml'],
                                      capture_output=True).stdout)
    urls = sorted({u for u in re.findall(r'<loc>([^<]+)</loc>', sm.read_text())
                   if any(u.startswith(f'{SITE}/{k}') for k in KINDS) and '/touring' not in u})
    rows = []
    for u in urls:
        page = get(u, u[len(SITE):])
        if not page: continue
        ls = lines(page)
        title = meta(page, 'og:title') or ls[0].split(' | ')[0]
        try:
            i = ls.index(title, 1)
        except ValueError:
            i = 1
        sub = ls[i + 1] if i + 1 < len(ls) else ''
        body = []
        for l in ls[i + 2:]:
            if l in ('Get Tickets', 'Audience', 'Top'): break
            if l in ('Image', 'Permanent', 'Temporary', 'Close Modal'): continue
            body.append(l)
        text = re.sub(r' ([,.;:!?)])', r'\1', ' '.join(body))
        rows.append({'url': u, 'kind': u[len(SITE) + 1:].split('/')[1], 'title': title, 'subtitle': sub,
                     'permanent': 'Permanent' in ls[:i + 6], 'location': after(ls, 'Location'),
                     'audience': after(ls, 'Audience'), 'price': after(ls, 'Price'),
                     'summary': meta(page, 'og:description'), 'text': text,
                     'image': meta(page, 'og:image') or first_picture(page)})
    (CACHE / 'exhibits.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'{len(rows)} pages')
    for r in rows: print(f"  {r['kind'][:5]} {'P' if r['permanent'] else ' '} {r['location'][:28]:28} {r['title']}")


if __name__ == '__main__':
    main()
