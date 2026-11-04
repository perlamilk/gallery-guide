#!/usr/bin/env python3
"""Read the Addison Gallery's works on view from its own collection site (run: python3 tools/harvest_addison.py OUT.json [CACHE_DIR]).

The Addison's collection search (an EmbARK Web Kiosk at accessaddison.andover.edu) is shown through the museum's
website: https://addison.andover.edu/search-the-collection/?embark_query=<kiosk path>. Each exhibition is a
"portfolio" there, so the works now on view are exactly the works in the current shows' portfolios:

    2600  Fall 2026: America in the Making   (Levels 1 and 2, September 8, 2026 to spring 2027)
     212  Ongoing: Ship Models               (Lower Level, permanently installed)

For every work the script opens its record page (artist, title, date, size, medium, credit line, accession
number, the museum's commentary and picture), one page every 1.5 seconds, so a run takes about 15 minutes.
When the museum hangs a new season, add its portfolio number (from the "Recent Exhibitions" list on the
search page) to PORTFOLIOS and run this again, then tools/build_addison.py.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://addison.andover.edu/search-the-collection/?embark_query='
PORTFOLIOS = {'2600': 'America in the Making', '212': 'Ship Models'}
# Works installed for good in the building, outside any exhibition (accession numbers, from the museum's gallery map):
# Manship's Venus fountain, Kendrick's Behind the Cross, LeWitt's ceiling wall drawing, Chihuly's floats on the green roof
INSTALLED = ['1930.291', '1983.36', '1993.49', '2010.96a-j']
UA = 'gallery-guide/1.0 (personal museum guide; https://github.com/perlamilk/gallery-guide)'
PAUSE = 1.5


CACHE = None  # a folder to keep the pages read so far (a second run picks up where the first stopped)


def get(kiosk_path, tries=4):
    url = BASE + urllib.parse.quote(kiosk_path, safe='/?=&:%"')
    cached = CACHE and CACHE / (re.sub(r'\W+', '_', kiosk_path)[-120:] + '.html')
    if cached and cached.exists():
        return cached.read_text()
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                page = r.read().decode('utf-8', 'replace')
            if cached: cached.write_text(page)
            time.sleep(PAUSE)
            return page
        except Exception as e:  # the kiosk is slow at times: wait and try again
            print(f'  retry {n + 1} after {e}', file=sys.stderr)
            time.sleep(10 * (n + 1))
    raise RuntimeError(f'could not read {url}')


def text(s):
    s = re.sub(r'<sup>.*?</sup>', '', s or '', flags=re.S)
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    return '\n'.join(re.sub(r'[ \t\r\f\v]+', ' ', line).strip() for line in s.split('\n')).strip()


def field(page, label):
    m = re.search(r'<strong>' + re.escape(label) + r':</strong>(.*?)</div>', page, re.S)
    return text(m[1]) if m else ''


def parse(page):
    i = page.find('class="row singlePortfolio"')
    if i < 0:
        return None
    body = page[i:]
    w = {}
    img = re.search(r'<img src="(https://accessaddison\.andover\.edu/Media/Previews/[^"]+)"', body)
    big = re.search(r"window\.open\('(https://accessaddison\.andover\.edu/Media/images/[^']+)'", body)
    if img: w['preview'] = img[1]
    if big: w['large'] = big[1]
    col = body[body.find('<div class="col">'):]
    head = col[:col.find('<div>')]
    artists = re.findall(r'artist-maker/info/(\d+)\?artistName=[^"]*">(.*?)</a>\s*(\([^)]*\))?', head, re.S)
    w['artist'] = '; '.join(text(a[1]) for a in artists) or ''
    if artists and artists[0][2]: w['artistDates'] = text(artists[0][2]).strip('()')
    t = re.search(r'<h4>(.*?)</h4>(.*?)$', head, re.S)
    if t:
        w['title'] = text(t[1])
        rest = [x for x in text(t[2]).split('\n') if x]
        if rest: w['date'] = rest[0]
        if len(rest) > 1: w['dimensions'] = rest[1]
    w['medium'] = field(col, 'Medium and Support')
    w['credit'] = field(col, 'Credit Line')
    w['number'] = field(col, 'Accession Number')
    c = re.search(r'<h2>Commentary</h2>\s*<div class="embarkInfoNotes">(.*?)</div>', body, re.S)
    if c:
        notes = text(c[1])
        w['commentary'] = re.sub(r'\n{2,}', '\n\n', notes)
    return {k: v for k, v in w.items() if v}


def main():
    global CACHE
    if len(sys.argv) > 2:
        CACHE = Path(sys.argv[2])
        CACHE.mkdir(exist_ok=True)
    out = {'harvested': time.strftime('%Y-%m-%d'), 'source': BASE, 'portfolios': PORTFOLIOS, 'works': []}
    for pid, name in PORTFOLIOS.items():
        q = f'Portfolios = "{pid}"'
        first = get(f'/objects-1/info?query={urllib.parse.quote(q)}&sort=0')
        last = max([int(n) for n in re.findall(r'page=(\d+)', first)] + [1])
        print(f'{name}: {last} works', file=sys.stderr)
        ids, got = {}, []
        for p in range(1, last + 1):
            page = first if p == 1 else get(f'/objects-1/info?query={urllib.parse.quote(q)}&sort=0&page={p}')
            for oid, rest in re.findall(r'/objects-1/info/(\d+)\?query=([^"]*)"', page):
                n = re.search(r'page=(\d+)', rest)
                ids[int(n[1]) if n else 1] = oid
            w = parse(page)
            if w:
                w.update(portfolio=pid, show=name, page=p)
                got.append(w)
            print(f'  {p}/{last} {w.get("number") if w else "?"}', file=sys.stderr, flush=True)
        for w in got:  # each record page links to the records before and after it, which gives their ids
            if w['page'] in ids: w['oid'] = ids[w['page']]
        out['works'] += got
    have = {w.get('number') for w in out['works']}
    for num in INSTALLED:
        if num in have: continue
        page = get(f'/objects-1/info?query={urllib.parse.quote(f"mfs all {chr(34)}{num}{chr(34)}")}&sort=0')
        w = parse(page)
        if w and w.get('number') == num:
            w.update(portfolio='installed', show='Permanently installed', page=1)
            out['works'].append(w)
            print(f'  installed {num}', file=sys.stderr)
        else:
            print(f'  installed {num}: not found', file=sys.stderr)
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
    print(f'{len(out["works"])} works', file=sys.stderr)


if __name__ == '__main__':
    main()
