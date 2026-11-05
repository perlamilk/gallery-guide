#!/usr/bin/env python3
"""Read the Berkshire Museum’s works on Google Arts & Culture (run: python3 tools/harvest_berkshire.py).

    .cache/berkshire/gac/            the pages, read once and kept
    .cache/berkshire/gac-works.json  one row per museum work: title, artist, date, medium, type, credit, text, picture

Why Google Arts & Culture: berkshiremuseum.org's robots.txt disallows ClaudeBot, Claude-Web and anthropic-ai, so its
pages are not read, and the museum has no open online collection. It publishes works on Google Arts & Culture
(artsandculture.google.com/partner/berkshire-museum), whose robots.txt allows reading every page except /api. The works
the museum sold in 2018 (Rockwell, Calder, Bierstadt's Giant Redwoods, the Bouguereaus...) are no longer listed there.
This reads the partner page and the museum's stories there, then
each work they show, one page every 2 seconds. The collection's own listing
(/explore/collections/berkshire-museum) shows only its first 20 works without the /api, so only those are read. Works lent by others are dropped.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'berkshire' / 'gac'
GAC = 'https://artsandculture.google.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PARTNER = '/partner/berkshire-museum'


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
    pages = [('', start), ('', get('/explore/collections/berkshire-museum?c=assets'))]
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
        # a story can show works lent by other museums: drop loans
        f = fields(page)
        credit = ' '.join([f.get('Rights', ''), f.get('Provenance', ''), f.get('Credit Line', '')])
        if re.search(r'\bLoan', credit):   # loans belong to others
            continue
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
    print(f'{len(assets)} work pages seen, {len(rows)} Berkshire Museum works')


if __name__ == '__main__':
    main()
