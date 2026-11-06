#!/usr/bin/env python3
"""Read the Rose Art Museum's own pages once, slowly, into .cache/rose (run: python3 tools/harvest_rose.py).

brandeis.edu answers 403 to cloud machines, so this runs on a home computer. It honours brandeis.edu/robots.txt,
reads only pages under /rose/ (visit, accessibility, FAQ, what is on view, the collection and about pages, and this
year's and last year's exhibitions and press PDFs), waits 3 seconds between pages and 1.5 seconds between pictures,
and stops after MAX_PAGES pages and MAX_IMAGES pictures. Everything is cached: a second run reads nothing it already
has. The Rose's online catalogue (rosecollection.brandeis.edu) closes itself to robots in its robots.txt, so it is not
read at all.

    .cache/rose/pages/<path>.html   the pages (and press PDFs as .pdf)
    .cache/rose/img/<path>          the pictures shown on them
    .cache/rose/index.json          url -> cached file, and for each page the pictures on it with their alt text

brandeis.edu refuses this script even from a home connection, so run it as `python3 tools/harvest_rose.py --wayback`:
then every page and picture is read from the Internet Archive's newest copy (web.archive.org/web/<time>id_/<url>),
found with the archive's availability API, one at a time with the same pauses.
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'rose'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
HOST = 'https://www.brandeis.edu'
DELAY, IMG_DELAY = 3, 1.5
MAX_PAGES, MAX_IMAGES = 160, 450
SEEDS = ['/rose/', '/rose/exhibitions', '/rose/onview/whitten.html', '/rose/index.html', '/rose/visit/index.html', '/rose/visit/accessibility.html',
         '/rose/frequently-asked-questions.html', '/rose/exhibitions/index.html', '/rose/onview/index.html',
         '/rose/onview/collection/index.html', '/rose/collection/index.html', '/rose/about/index.html',
         '/rose/about/history.html', '/rose/about/pressroom.html', '/rose/visit/directions.html',
         '/rose/visit/groups.html', '/rose/programs/index.html']
OLD_YEAR = re.compile(r'(?<!\d)(19\d\d|20[01]\d|202[0-4])(?!\d)')
SKIP = re.compile(r'/(give|support|join|membership|donate|calendar|events?|news-archive)/|\.(zip|docx?|xlsx?|mp4|mov)$',
                  re.I)


WAYBACK = '--wayback' in sys.argv     # brandeis.edu refuses robots even from home: read the Internet Archive's copies


def archived(url):
    """The Internet Archive's newest copy of url (raw, as the museum served it), or None."""
    q = 'https://archive.org/wayback/available?timestamp=20261105&url=' + urllib.request.quote(url, safe='')
    try:
        out = subprocess.run(['curl', '-s', '-f', '-m', '60', '-A', UA, q], capture_output=True).stdout
        snap = json.loads(out or b'{}').get('archived_snapshots', {}).get('closest')
    except ValueError:
        return None
    time.sleep(1)
    if not snap or snap.get('status') != '200': return None
    return f"https://web.archive.org/web/{snap['timestamp']}id_/{url}"


def get(url, dest, delay=DELAY):
    """Fetch url into dest once (cached)."""
    if dest.exists() and dest.stat().st_size > 200: return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = archived(url) if WAYBACK else url
    if not src:
        print('no archived copy of', url, flush=True)
        return None
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, src], capture_output=True).stdout
    time.sleep(delay)
    if not out:
        print('could not read', url, flush=True)
        return None
    dest.write_bytes(out)
    print('read', url, flush=True)
    return out


def local(path, folder):
    p = unquote(path).lstrip('/')
    if p.endswith('/') or not p: p += 'index.html'
    return CACHE / folder / re.sub(r'[^A-Za-z0-9._/-]', '_', p)


def main():
    robots = urllib.robotparser.RobotFileParser()
    raw = get(f'{HOST}/robots.txt', CACHE / 'robots.txt', delay=1)
    robots.parse((raw or b'').decode('utf-8', 'replace').splitlines())
    if raw is None:
        print('brandeis.edu did not answer: nothing read')
        return 1
    index = {'pages': {}, 'images': {}}
    todo, seen, n_img = list(SEEDS), set(), 0
    while todo and len(index['pages']) < MAX_PAGES:
        path = todo.pop(0)
        if path in seen: continue
        seen.add(path)
        url = HOST + path
        if not robots.can_fetch(UA, url):
            print('robots.txt closes', url)
            continue
        is_pdf = path.lower().endswith('.pdf')
        body = get(url, local(path, 'pages'))
        if not body: continue
        entry = {'file': str(local(path, 'pages').relative_to(CACHE)), 'images': []}
        index['pages'][url] = entry
        if is_pdf: continue
        t = body.decode('utf-8', 'replace')
        for m in re.finditer(r'<img\b[^>]*>', t, re.I):
            tag = m.group(0)
            src = re.search(r'\bsrc="([^"]+)"', tag)
            if not src: continue
            u = urljoin(url, html.unescape(src.group(1)))
            pu = urlparse(u)
            if pu.netloc != 'www.brandeis.edu' or not re.search(r'\.(jpe?g|png|webp|gif)$', pu.path, re.I): continue
            if re.search(r'logo|icon|sprite|social|banner-bg', pu.path, re.I): continue
            alt = re.search(r'\balt="([^"]*)"', tag)
            entry['images'].append({'url': u, 'alt': html.unescape(alt.group(1)) if alt else ''})
            if u in index['images'] or n_img >= MAX_IMAGES: continue
            if not robots.can_fetch(UA, u): continue
            if get(u, local(pu.path, 'img'), delay=IMG_DELAY):
                index['images'][u] = str(local(pu.path, 'img').relative_to(CACHE))
                n_img += 1
        for href in re.findall(r'\bhref="([^"#]+)', t, re.I):
            u = urljoin(url, html.unescape(href).strip())
            pu = urlparse(u)
            if pu.netloc not in ('www.brandeis.edu', 'brandeis.edu') or not pu.path.startswith('/rose/'): continue
            p = re.sub(r'/+', '/', pu.path)
            if p in seen or p in todo or SKIP.search(p): continue
            if OLD_YEAR.search(p): continue
            if p.lower().endswith('.pdf') and not re.search(r'map|floor|2025|2026|visit|access', p, re.I): continue
            todo.append(p)
        (CACHE / 'index.json').write_text(json.dumps(index, indent=1))
    (CACHE / 'index.json').write_text(json.dumps(index, indent=1))
    print(f"{len(index['pages'])} pages, {len(index['images'])} pictures in {CACHE}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
