#!/usr/bin/env python3
"""Read the Davis Museum's works on Google Arts & Culture (run: python3 tools/harvest_davis.py).

    .cache/davis/gac/            the pages, read once and kept
    .cache/davis/gac-works.json  one row per Davis work: title, artist, date, medium, type, credit, text, picture

Why Google Arts & Culture: the Davis's own collection site (davis.emuseum.com) answers 403 to cloud machines and
its Bloomberg Connects guide can't be read either. The Davis publishes 277 works on Google Arts & Culture
(artsandculture.google.com/partner/the-davis-museum), whose robots.txt allows reading every page except /api.
This reads the partner page and the Davis's stories (online exhibitions) there, then each work they show,
one page every 2 seconds. Works from other museums that appear in a story are dropped.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'davis' / 'gac'
GAC = 'https://artsandculture.google.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PARTNER = '/partner/the-davis-museum'


def get(path):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (re.sub(r'[^\w-]+', '_', path.strip('/')) + '.html')
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, GAC + path], capture_output=True).stdout
        time.sleep(2)
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def unjs(s):
    return html.unescape(json.loads('"' + s + '"'))


def fields(page):
    """The 'Details' block of a work page: [["Title",[["Laughing Fool",…]],0],["Date",[["ca. 1500"]],0],…]."""
    out = {}
    for m in re.finditer(r'\["([A-Z][A-Za-z ]{1,40})",\[\["((?:[^"\\]|\\.)*)"(?:,"((?:[^"\\]|\\.)*)")?', page):
        k = m[1]
        if k not in out: out[k] = unjs(m[2]) if k != 'External Link' else (unjs(m[3]) if m[3] else '')
    return out


def main():
    assets = {}                     # work page -> title of the story that shows it ('' for the partner page)
    start = get(PARTNER)
    pages = [('', start)]
    for sid in sorted(set(re.findall(r'/story/(?:[\w-]+/)?([\w-]{14})\b', start))):
        p = get(f'/story/{sid}')
        t = re.search(r'<title>([^<]*?)(?: — Google Arts &amp; Culture)?</title>', p)
        pages.append((html.unescape(t[1]) if t else '', p))
    for story, p in pages:
        for a in re.findall(r'/asset/[\w%-]+/[\w-]{14}', p):
            assets.setdefault(a, story)
    rows = []
    for a in assets:
        page = get(a)
        # a story can show works lent by other museums (British Museum, National Library of Medicine…): keep only
        # works whose rights or provenance name the Davis or Wellesley
        f = fields(page)
        credit = ' '.join([f.get('Rights', ''), f.get('Provenance', ''), f.get('Credit Line', '')])
        if not re.search(r'Davis|Wellesley', credit) or re.search(r'\bLoan', credit):   # loans belong to others
            continue
        img = re.search(r'<meta property="og:image" content="([^"]+)"', page)
        desc = re.search(r'<meta property="og:description" content="([^"]*)"', page)
        rows.append({'gac': GAC + a, 'story': assets[a], 'title': f.get('Title', ''), 'artist': f.get('Artist') or f.get('Creator', ''),
                     'date': f.get('Date', '') or f.get('Date Created', ''), 'medium': f.get('Medium', ''),
                     'type': f.get('Type', ''), 'credit': f.get('Provenance', '') or f.get('Credit Line', ''),
                     'place': f.get('Location', '') or f.get('Place Part Of', '') or f.get('Creator Nationality', ''),
                     'dimensions': f.get('Physical Dimensions', ''), 'accession': f.get('Object Number', '') or
                     f.get('Accession Number', ''), 'record': f.get('External Link', ''),
                     'text': html.unescape(desc[1]) if desc and 'over 2000 leading museums' not in desc[1] else '',
                     'image': img[1] if img else None})
    (CACHE.parent / 'gac-works.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'{len(assets)} work pages seen, {len(rows)} Davis works')


if __name__ == '__main__':
    main()
