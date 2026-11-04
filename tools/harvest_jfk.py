#!/usr/bin/env python3
"""Read the JFK Presidential Library and Museum's objects on Google Arts & Culture (run: python3 tools/harvest_jfk.py).

    .cache/jfk/gac/            the pages, read once and kept
    .cache/jfk/gac-works.json  one row per object: title, date, type, text, picture, the story that shows it

Why Google Arts & Culture: jfklibrary.org answers 403 to cloud machines and its robots.txt shuts out AI agents
(ClaudeBot, Claude-Web, anthropic-ai), so this guide does not read it at all. The museum publishes objects and an
online exhibit on Google Arts & Culture (artsandculture.google.com/partner/john-f-kennedy-presidential-library-and-museum),
whose robots.txt allows every page except /api. This reads the partner page, the collection's first page and the
museum's stories there, then each object they show, one page every 2 seconds.
"""
import html
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'jfk' / 'gac'
GAC = 'https://artsandculture.google.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PARTNER = '/partner/john-f-kennedy-presidential-library-and-museum'
COLLECTION = '/explore/collections/john-f-kennedy-presidential-library-and-museum?c=assets'


def get(path):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (re.sub(r'[^\w-]+', '_', path.strip('/'))[:150] + '.html')
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, GAC + path], capture_output=True).stdout
        time.sleep(2)
        if not out: return ''
        f.write_bytes(out)
    return f.read_text(errors='replace')


def unjs(s):
    return html.unescape(json.loads('"' + s + '"'))


def fields(page):
    """The 'Details' block of an object page: [["Title",[["…"]],0],["Date Created",[["1962"]],0],…]."""
    out = {}
    for m in re.finditer(r'\["([A-Z][A-Za-z ]{1,40})",\[\["((?:[^"\\]|\\.)*)"', page):
        if m[1] not in out: out[m[1]] = unjs(m[2])
    return out


def text_of(page):
    """The whole text under the picture: kept in the page data right after the picture's address."""
    m = re.search(r',null,"//lh3[^"]+",\[null,"((?:[^"\\]|\\.)*)"', page)
    if m:
        t = unjs(m[1])
        t = re.sub(r'<br\s*/?>|</p>', '\n', t)
        t = re.sub(r'<[^>]+>', '', t)
        return re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n\n', t)).strip()
    m = re.search(r'"description":"((?:[^"\\]|\\.)*)"', page)
    return unjs(m[1]).strip() if m else ''


def main():
    assets = {}                     # object page -> title of the story that shows it ('' for the partner pages)
    start = get(PARTNER)
    pages = [('', start), ('', get(COLLECTION))]
    stories = sorted(set(re.findall(r'/story/(?:[\w%-]+/)?([\w-]{14})\b', start)))
    for sid in stories:
        p = get(f'/story/{sid}')
        t = re.search(r'<title>([^<]*?)(?: — Google Arts &amp; Culture)?</title>', p)
        pages.append((html.unescape(t[1]) if t else '', p))
    for story, p in pages:
        for a in re.findall(r'/asset/[^"\\/]+/[\w-]{14}', p):
            assets.setdefault(a, story)
    rows = []
    for a in assets:
        page = get(a)
        f = fields(page)
        creator = f.get('Creator', '')
        img = re.search(r'<meta property="og:image" content="([^"]+)"', page)
        rows.append({'gac': GAC + a, 'story': assets[a], 'title': f.get('Title', ''), 'creator': creator,
                     'date': f.get('Date Created', '') or f.get('Date', ''), 'type': f.get('Type', ''),
                     'medium': f.get('Medium', ''), 'place': f.get('Location Created', '') or f.get('Location', ''),
                     'rights': f.get('Rights', ''), 'accession': f.get('Object Number', '') or f.get('Accession Number', ''),
                     'text': text_of(page), 'image': img[1] if img else None})
    (CACHE.parent / 'gac-works.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'{len(stories)} stories, {len(rows)} objects')


if __name__ == '__main__':
    main()
