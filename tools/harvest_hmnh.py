#!/usr/bin/env python3
"""Collect pictures of the Harvard Museum of Natural History's displays (run: python3 tools/harvest_hmnh.py).

    .cache/hmnh/commons/      Wikimedia Commons category, search and file pages, read once and kept
    .cache/hmnh/files.json    one row per picture: file name, description, author, licence, date, categories

hmnh.harvard.edu (and the museum pages of mcz.harvard.edu, oeb.harvard.edu, mgmh.fas.harvard.edu) answer scripts
with 403 (Akamai), and Wikidata knows almost nothing about what is on view. So the pictures are photos visitors took in
the galleries and shared on Wikimedia Commons under free licences: the Commons categories for the museum, the Glass
Flowers, its minerals and meteorites, plus a file search for the museum's name. The Commons API rate-limits the cloud
(429), so the ordinary HTML pages are read instead, one every 2 seconds.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'hmnh'
C = CACHE / 'commons'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
W = 'https://commons.wikimedia.org'
CATS = ['Harvard_Museum_of_Natural_History', 'Harvard_University_Glass_Flowers',
        'Meteorites_in_the_Harvard_Museum_of_Natural_History', 'Minerals_in_the_Harvard_Museum_of_Natural_History',
        'Blaschka_glass_invertebrates_at_Harvard', 'Ware_Collection_of_Blaschka_Glass_Models_of_Plants']
# Photos from the galleries whose names don't say Harvard
EXTRA_FILES = ['Kronosaurus_(2509835673).jpg', 'Kronosaurus_queenslandicus.jpg', 'Kronosaurus_skull.jpg',
               'Latimeria_chalumnae_Harvard.jpg']
SEARCHES = ['Harvard Museum of Natural History', 'HMNH', 'Kronosaurus Harvard']
WAYFINDING = 'https://bpb-us-e1.wpmucdn.com/websites.harvard.edu/dist/f/80/files/2023/10/HMSC-Wayfinding-Brochure-2023.pdf'


def get(url, name):
    f = C / name
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def text(s):
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    return re.sub(r'\s+', ' ', s).strip()


def files_in(page):
    out = []
    for x in re.findall(r'<a href="/wiki/(File:[^"#?]+)"', page):
        x = unquote(html.unescape(x))[5:]
        if x not in out: out.append(x)
    return out


def safe(s):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', s)[:150]


def file_row(name):
    p = get(f'{W}/wiki/File:{quote(name.replace(" ", "_"))}', f'files/{safe(name)}.html')
    if not p: return None
    p = p.replace('&#95;', '_')
    row = {'file': name}
    d = re.search(r'<td class="description">(.*?)</td>', p, re.S)
    if d:
        en = re.search(r'<div class="description[^"]* en"[^>]*>(.*?)</div>', d[1], re.S)
        row['description'] = text(re.sub(r'<span class="language en"[^>]*>.*?</span>', '', (en or d)[1], flags=re.S))
    for key, tid in (('date', 'fileinfotpl_date'), ('author', 'fileinfotpl_aut'), ('source', 'fileinfotpl_src')):
        m = re.search(rf'id="{tid}"[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>', p, re.S)
        if m: row[key] = text(m[1])[:200]
    lic = re.findall(r'<span class="licensetpl_short"[^>]*>(.*?)</span>', p, re.S)
    if lic: row['license'] = text(lic[0])
    row['categories'] = [unquote(html.unescape(c)) for c in
                         re.findall(r'<li><a href="/wiki/Category:([^"]+)"', p.split('id="catlinks"')[-1])]
    return row


def main():
    names = []
    for c in CATS:
        page = get(f'{W}/wiki/Category:{c}', f'cat_{c}.html')
        n = 0
        while page:
            names += [f for f in files_in(page) if f not in names]
            nxt = re.search(r'<a href="([^"]+filefrom=[^"]+)"[^>]*>next page', page)
            if not nxt: break
            n += 1
            page = get(W + html.unescape(nxt[1]), f'cat_{c}_{n}.html')
    for s in SEARCHES:
        page = get(f'{W}/w/index.php?title=Special:Search&ns6=1&limit=500&fulltext=1&search={quote(s)}',
                   f'search_{safe(s)}.html')
        for f in files_in(page):
            if re.search(r'(?i)harvard|hmnh|hmcz|mcz', f) and f not in names: names.append(f)
    names += [f for f in EXTRA_FILES if f not in names]
    names = [n for n in names if not re.search(r'(?i)\.(pdf|djvu|svg|tif)$|Bulletin|Memoirs|annual_report|IA_', n)]
    rows = []
    for i, n in enumerate(names):
        r = file_row(n)
        if r: rows.append(r)
        if i % 25 == 0: print(f'{i}/{len(names)}', flush=True)
    (CACHE / 'files.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    pdf = CACHE / 'wayfinding2023.pdf'
    if not pdf.exists():
        pdf.write_bytes(subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, WAYFINDING],
                                       capture_output=True).stdout)
    print(f'{len(rows)} pictures')


if __name__ == '__main__':
    main()
