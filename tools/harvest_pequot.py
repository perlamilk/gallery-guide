#!/usr/bin/env python3
"""Read the Mashantucket Pequot Museum's items on Google Arts & Culture (run: python3 tools/harvest_pequot.py).

    .cache/pequot/gac/            the pages, read once and kept
    .cache/pequot/gac-works.json  one row per museum item: title, creator, date, medium, type, credit, text, picture

Why Google Arts & Culture: pequotmuseum.org answers 403 to cloud machines (Cloudflare), though its robots.txt allows
everything; only its PDFs and pictures under /wp-content/uploads can be read. The museum publishes items and stories
on Google Arts & Culture (artsandculture.google.com/partner/the-mashantucket-pequot-museum-research-center), whose
robots.txt allows reading every page except /api. This reads the partner page, the collection listing and the museum's
stories there, then each item they show, one page every 2 seconds. Items lent by others are dropped.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'pequot' / 'gac'
GAC = 'https://artsandculture.google.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PARTNER = '/partner/the-mashantucket-pequot-museum-research-center'


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
    pages = [('', start), ('', get('/explore/collections/the-mashantucket-pequot-museum-research-center?c=assets'))]
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
        # every item here is on the Pequot Museum's own partner pages (its stories show only its own collection,
        # with a few loans to it, which it shows as well)
        f = fields(page)
        if not f.get('Title'): continue
        img = re.search(r'<meta property="og:image" content="([^"]+)"', page)
        desc = re.search(r'<meta property="og:description" content="([^"]*)"', page)
        full = re.search(r'<section class="[^"]*"><div class="R5VDUc">(.*?)</div></section>', page, re.S)
        if full:     # the whole text under the picture (og:description is cut at 200 characters)
            full = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<br\s*/?>|</p>', '\n', full[1])))
            full = re.sub(r'<[^>]+>', '', full).strip()
        rows.append({'gac': GAC + a, 'story': assets[a], 'title': f.get('Title', ''), 'artist': f.get('Artist') or f.get('Creator', ''),
                     'date': f.get('Date', '') or f.get('Date Created', ''), 'medium': f.get('Medium', ''),
                     'type': f.get('Type', ''), 'credit': f.get('Provenance', '') or f.get('Credit Line', ''),
                     'place': f.get('Location', '') or f.get('Place Part Of', '') or f.get('Creator Nationality', ''),
                     'dimensions': f.get('Physical Dimensions', ''), 'accession': f.get('Object Number', '') or
                     f.get('Accession Number', ''), 'record': f.get('External Link', ''),
                     'text': full or html.unescape(desc[1]) if desc and 'over 2000 leading museums' not in desc[1] else '',
                     'image': img[1] if img else None})
    (CACHE.parent / 'gac-works.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'{len(assets)} item pages seen, {len(rows)} items')


if __name__ == '__main__':
    main()
