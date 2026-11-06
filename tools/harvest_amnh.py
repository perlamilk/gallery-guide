#!/usr/bin/env python3
"""Collect pictures of the American Museum of Natural History's halls (run: python3 tools/harvest_amnh.py).

    .cache/amnh/commons/      Wikimedia Commons category and file pages, read once and kept
    .cache/amnh/where.json    every file in the categories read, with the categories it was found in
    .cache/amnh/files.json    one row per picture used: file, categories, description, author, licence, date
                              (only the files tools/build_amnh.py chose, listed in .cache/amnh/chosen.json)
    .cache/amnh/map.pdf       the museum's visitor map (for tools/trace_amnh.py)

amnh.org's pages answer scripts with 403 (Cloudflare), though its PDF downloads work. So the pictures are photos
visitors took in the halls and shared on Wikimedia Commons under free licences. Commons sorts them into one category
per hall ("Milstein Hall of Ocean Life at American Museum of Natural History"...), so most pictures have an exact hall;
the museum-wide categories of fossils, dioramas, meteorites and minerals are read too and placed by subject in
tools/build_amnh.py. The Commons API answers the cloud with 429, so the ordinary category and file pages are read instead,
one every 1.5 seconds, everything cached. Pictures are not downloaded: the guide shows them from Commons
(Special:FilePath), like other guides do.
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'amnh'
C = CACHE / 'commons'
W = 'https://commons.wikimedia.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
MAP = 'https://www.amnh.org/content/download/385996/5752508/file/english-map.pdf'
VISITOR = 'https://www.amnh.org/content/download/434604/6322482/file/visitor-information-english.pdf'
SUFFIX = '_at_American_Museum_of_Natural_History'
HALLS = ['Akeley_Hall_of_African_Mammals', 'Allison_and_Roberto_Mignone_Halls_of_Gems_and_Minerals',
         'Anne_and_Bernard_Spitzer_Hall_of_Human_Origins', 'Arthur_Ross_Hall_of_Meteorites',
         'Bernard_Family_Hall_of_North_American_Mammals', 'David_S._and_Ruth_L._Gottesman_Hall_of_Planet_Earth',
         'Dorothy_and_Lewis_B._Cullman_Hall_of_the_Universe', 'Hall_of_African_Peoples', 'Hall_of_Asian_Mammals',
         'Hall_of_Birds_of_the_World', 'Hall_of_Fossil_Reptiles', 'Hall_of_Mexico_and_Central_America',
         'Hall_of_New_York_City_Birds', 'Hall_of_North_American_Forests', 'Hall_of_Ornithischian_Dinosaurs',
         'Hall_of_Primates', 'Hall_of_Primitive_Mammals', 'Hall_of_Reptiles_and_Amphibians',
         'Hall_of_Saurischian_Dinosaurs', 'Hall_of_South_American_Peoples', 'Hall_of_Vertebrate_Origins',
         'Margaret_Mead_Hall_of_Pacific_Peoples', 'Milstein_Hall_of_Ocean_Life',
         'Sanford_Hall_of_North_American_Birds', 'Theodore_Roosevelt_Hall_of_Biodiversity',
         'Warburg_Hall_of_New_York_State_Environments']
CATS = [h + SUFFIX for h in HALLS] + [
    'Northwest_Coast_Hall_in_the_American_Museum_of_Natural_History', 'Paul_and_Irma_Milstein_Hall_of_Advanced_Mammals',
    'Susan_and_Peter_J._Solomon_Family_Insectarium', 'Theodore_Roosevelt_Memorial_Hall',
    'Richard_Gilder_Center_for_Science,_Education,_and_Innovation', 'Star_of_India_(gem)',
    'Dioramas_in_the_American_Museum_of_Natural_History', 'Fossils_in_the_American_Museum_of_Natural_History',
    'Meteorites_of_the_American_Museum_of_Natural_History', 'Minerals_in_the_American_Museum_of_Natural_History',
    'Hominids_in_the_American_Museum_of_Natural_History', 'Astronomy_in_the_American_Museum_of_Natural_History',
    'Anthropological_collection_of_the_American_Museum_of_Natural_History',
    'Animals_in_the_American_Museum_of_Natural_History']
DEPTH = 2          # subcategories followed this deep (Fossils has one per animal group)




def get(url, name):
    f = C / name
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        out = b''
        for wait in (1.5, 20, 90):
            out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
            time.sleep(wait)
            if out: break
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def safe(s):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', s)[:150]


def text(s):
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    return re.sub(r'\s+', ' ', s).strip()


def listing(cat):
    """Files and subcategories of a Commons category, from its ordinary pages (the API answers the cloud with 429)."""
    files, subs, n = [], [], 0
    page = get(f'{W}/wiki/Category:{quote(cat)}', f'cat/{safe(cat)}.html')
    while page:
        if 'id="mw-subcategories"' in page:
            part = page.split('id="mw-subcategories"')[1].split('id="mw-category-media"')[0]
            subs += [unquote(html.unescape(x)) for x in re.findall(r'<a [^>]*href="/wiki/Category:([^"#?]+)"', part)
                     if unquote(html.unescape(x)) not in subs]
        if 'id="mw-category-media"' in page:
            part = page.split('id="mw-category-media"')[1]
            files += [unquote(html.unescape(x))[5:] for x in re.findall(r'<a href="/wiki/(File:[^"#?]+)"', part)
                      if unquote(html.unescape(x))[5:] not in files]
        nxt = re.search(r'<a href="([^"]+filefrom=[^"]+)"[^>]*>next page', page)
        if not nxt: break
        n += 1
        page = get(W + html.unescape(nxt[1]), f'cat/{safe(cat)}_{n}.html')
    return files, subs


def file_row(name):
    p = get(f'{W}/wiki/File:{quote(name.replace(" ", "_"))}', f'files/{safe(name)}.html')
    if not p: return None
    p = p.replace('&#95;', '_')
    row = {'file': name}
    d = re.search(r'<td class="description">(.*?)</td>', p, re.S)
    if d:
        en = re.search(r'<div class="description[^"]* en"[^>]*>(.*?)</div>', d[1], re.S)
        row['description'] = text(re.sub(r'<span class="language en"[^>]*>.*?</span>', '', (en or d)[1], flags=re.S))
    for key, tid in (('date', 'fileinfotpl_date'), ('author', 'fileinfotpl_aut')):
        m = re.search(rf'id="{tid}"[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>', p, re.S)
        if m: row[key] = text(m[1])[:200]
    lic = re.findall(r'<span class="licensetpl_short"[^>]*>(.*?)</span>', p, re.S)
    if lic: row['license'] = text(lic[0])
    row['categories'] = [unquote(html.unescape(c)) for c in
                         re.findall(r'<li><a href="/wiki/Category:([^"]+)"', p.split('id="catlinks"')[-1])]
    return row


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    for url, name in ((MAP, 'map.pdf'), (VISITOR, 'visitor.pdf')):
        if not (CACHE / name).exists():
            subprocess.run(['curl', '-s', '-f', '-L', '-A', UA, '-o', str(CACHE / name), url], check=True)
    where = {}                      # file -> categories it was found in ("top > sub" for subcategories)
    for top in CATS:
        todo, seen = [(top, 0)], set()
        while todo:
            cat, d = todo.pop(0)
            if cat in seen: continue
            seen.add(cat)
            files, subs = listing(cat)
            for f in files:
                where.setdefault(f, [])
                k = top if cat == top else f'{top} > {cat}'
                if k not in where[f]: where[f].append(k)
            if d < DEPTH:
                # only subcategories about this museum (others lead to other museums' collections)
                todo += [(s_, d + 1) for s_ in subs if re.search(r'(?i)american_museum_of_natural_history|amnh', s_)]
    (CACHE / 'where.json').write_text(json.dumps(where, ensure_ascii=False, indent=0))
    names = [f for f in where if not re.search(r'(?i)\.(pdf|djvu|svg|tiff?|webm|ogv|mp4|mp3|ogg)$', f)]
    print(len(names), 'files', flush=True)
    if '--list' in sys.argv: return
    chosen = CACHE / 'chosen.json'
    if chosen.exists():
        keep = set(json.loads(chosen.read_text()))
        names = [n for n in names if n in keep]
    rows = []
    for i, n in enumerate(names):
        r = file_row(n)
        if r:
            r['cats'] = where[n]
            rows.append(r)
        if i % 50 == 0: print(f'{i}/{len(names)}', flush=True)
    (CACHE / 'files.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(len(rows), 'pictures described')


if __name__ == '__main__':
    main()
