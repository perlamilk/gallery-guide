#!/usr/bin/env python3
"""Harvest what the Cape Ann Museum (Gloucester, MA) publishes about its collection on capeannmuseum.org.

The museum has no public collection database yet ("we are in the process of digitizing our collections"), its
Digital Collections Catalog (Quartex) shows a "Page Not Available" screen, and Fitz Henry Lane Online disallows Claude
agents in robots.txt, so it is not read. capeannmuseum.org is WordPress and its robots.txt allows everyone; its REST
API gives:

    .cache/capeann/media.json        every item of the media library (title, caption, alt text, picture URL). Pictures of
                                     works carry the museum's own captions ("Artist, Title, date, medium. Gift of ...
                                     [Acc. #2002.004.002]")
    .cache/capeann/exhibitions.json  every exhibition page (current, upcoming and past) with its text and campus
    .cache/capeann/pages.json        the visit pages (hours, admission, amenities)
    .cache/capeann/posts-*.json      news posts that describe the renovated galleries (reopened June 2026)
    .cache/capeann/commons.json      Wikimedia Commons files in Category:Cape Ann Museum, Gloucester and its subcategories
                                     (depth 3). Most are Daderot's photos of the galleries; their file names carry the
                                     label ("Title, by Artist, date, medium - Cape Ann Museum - Gloucester, MA - DSC....")

One request at a time, 2 seconds apart; everything is cached, so a re-run asks nothing again (delete files to refresh).
Then run tools/build_capeann.py.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'capeann'
API = 'https://www.capeannmuseum.org/wp-json/wp/v2/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'


def get(path, **params):
    url = API + path + ('?' + urllib.parse.urlencode(params) if params else '')
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                total = int(r.headers.get('X-WP-TotalPages') or 1)
                out = json.loads(r.read())
            time.sleep(2)
            return out, total
        except Exception as e:
            print(f'  retry {url} ({e})', file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f'{url} kept failing')


def all_pages(path, **params):
    out, page, total = [], 1, 1
    while page <= total:
        rows, total = get(path, per_page=100, page=page, **params)
        out += rows
        print(f'  {path} page {page}/{total}')
        page += 1
    return out


def cached(name, fn):
    f = CACHE / name
    if not f.exists():
        f.write_text(json.dumps(fn(), ensure_ascii=False))
    return json.loads(f.read_text())


WDQS = 'https://query.wikidata.org/sparql'
CUA = 'gallery-guide/1.0 (https://github.com/perlamilk/gallery-guide; personal museum guide)'


def _json(url, accept='application/json'):
    req = urllib.request.Request(url, headers={'User-Agent': CUA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def members(cat):
    """Files and subcategories of a Commons category: from the Commons API when it answers, else through the Wikidata
    Query Service's MediaWiki API bridge (commons.wikimedia.org answers 429 to cloud machines much of the time, and
    the query service then allows one request a minute). Each category's answer is cached."""
    done = CACHE / 'commons-cats.json'
    known = json.loads(done.read_text()) if done.exists() else {}
    if cat in known: return [tuple(x) for x in known[cat]]
    rows = None
    try:
        out, cont = [], {}
        while True:
            q = _json('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(
                {'action': 'query', 'list': 'categorymembers', 'cmtitle': cat, 'cmlimit': 'max', 'format': 'json',
                 'formatversion': 2, **cont}))
            out += [(m['ns'], m['title']) for m in q['query']['categorymembers']]
            if 'continue' not in q: break
            cont = {'cmcontinue': q['continue']['cmcontinue']}
            time.sleep(2)
        rows = out
    except Exception as e:
        print(f'  Commons API: {e}; asking the query service', file=sys.stderr)
    if rows is None:
        q = ('SELECT ?t ?ns WHERE { SERVICE wikibase:mwapi { bd:serviceParam wikibase:endpoint "commons.wikimedia.org"; '
             'wikibase:api "Generator"; mwapi:generator "categorymembers"; mwapi:gcmtitle "%s"; mwapi:gcmlimit "max". '
             '?t wikibase:apiOutput mwapi:title. ?ns wikibase:apiOutput "@ns". } }' % cat.replace('"', '\\"'))
        for wait in (65, 120, 300, 600):
            time.sleep(wait)
            try:
                b = _json(WDQS + '?' + urllib.parse.urlencode({'query': q}), 'application/sparql-results+json')
                rows = [(int(x['ns']['value']), x['t']['value']) for x in b['results']['bindings']]
                break
            except Exception as e:
                print(f'  retry {cat} ({e})', file=sys.stderr)
        if rows is None: raise SystemExit(f'{cat} kept failing')
    known[cat] = rows
    done.write_text(json.dumps(known, ensure_ascii=False))
    time.sleep(2)
    return rows


def commons_tree(root='Category:Cape Ann Museum, Gloucester', depth=3):
    """{file title: category it was found in}. Pictures are then read from upload.wikimedia.org thumbnails."""
    files, seen, todo = {}, set(), [(root, 0)]
    while todo:
        cat, d = todo.pop(0)
        if cat in seen: continue
        seen.add(cat)
        for ns, t in members(cat):
            if ns == 14 and d < depth: todo.append((t, d + 1))
            elif ns == 6: files.setdefault(t, cat)
        print(f'  {cat}: {len(files)} files so far, {len(todo)} categories to go', flush=True)
    return files


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    cached('media.json', lambda: all_pages('media', _fields='id,date,slug,title,caption,alt_text,source_url,'
                                                            'media_details.width,media_details.height,post'))
    cached('exhibitions.json', lambda: all_pages('exhibition', _fields='id,slug,link,title,content,excerpt,'
                                                                     'exhibition_status,campus,featured_media,modified'))
    cached('pages.json', lambda: all_pages('pages', _fields='id,slug,link,title,content,modified'))
    for term in ('reopens', 'renovation', 'galleries'):
        cached(f'posts-{term}.json', lambda: get('posts', search=term, per_page=50,
                                                 _fields='id,slug,link,date,title,content')[0])
    cached('commons.json', commons_tree)
    print('done')


if __name__ == '__main__':
    sys.exit(main())
