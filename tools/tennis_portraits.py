#!/usr/bin/env python3
"""Add the missing Hall of Famer portraits to the Tennis Hall of Fame guide without a full rebuild
(run: python3 tools/tennis_portraits.py).

build_tennis.py needs the harvest cache (.cache/tennis) and Wikimedia used to answer 429 to cloud machines, so
most portraits were left out in Nov 2026. This asks Wikidata once for every person with an International Tennis
Hall of Fame id (P3363) and a picture (P18), downloads each missing picture from Wikimedia Commons, politely
spaced, as data/tennis/images/hof-<name>.jpg (the same file name build_tennis.py uses, so a later rebuild keeps
them), and writes them into data/tennis/artworks.json and data/guides/Q52454.json. Run build_pack.py afterwards.
"""
import hashlib, io, json, re, subprocess, time, urllib.parse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UA = 'GalleryGuide/1.0 (personal museum guide; one request every few seconds)'
GAP = 3
QUERY = ('SELECT ?ithf ?pLabel ?img WHERE { ?p wdt:P3363 ?ithf . ?p wdt:P18 ?img . '
         'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')


def sparql():
    for _ in range(4):                 # the Wikidata query service allows about one query a minute from clouds
        r = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, '-H', 'Accept: application/sparql-results+json',
                            '--data-urlencode', 'query=' + QUERY, 'https://query.wikidata.org/sparql'], capture_output=True)
        if r.returncode == 0: break
        print('  query service busy, waiting 70 s', flush=True); time.sleep(70)
    r.check_returncode()
    out = r.stdout
    return [{k: v['value'] for k, v in b.items()} for b in json.loads(out)['results']['bindings']]


def norm(s): return re.sub(r'[^a-z]', '', s.lower())


def thumb(fname):
    # straight to the picture server: commons.wikimedia.org's Special:FilePath redirect answers 429 to clouds
    h = hashlib.md5(fname.encode()).hexdigest()
    q = urllib.parse.quote(fname)
    ext = '.jpg' if fname.lower().endswith(('.tif', '.tiff')) else ('.png' if fname.lower().endswith('.svg') else '')
    return f'https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/500px-{q}{ext}'


def fetch(url):
    for pause in (30, 120, None):
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', '-', url],
                           capture_output=True)
        code, body = r.stdout[-3:], r.stdout[:-3]
        if code == b'200': return body
        if code != b'429' or pause is None: return None      # missing (e.g. no 500 px version): don't wait
        print(f'  busy, waiting {pause} s', flush=True); time.sleep(pause)


def save(raw, dest):
    im = Image.open(io.BytesIO(raw))
    im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert('RGB'); im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)


def main():
    rows = sparql()
    by_slug = {r['ithf']: r for r in rows}
    by_name = {norm(r.get('pLabel', '')): r for r in rows}
    art_path = ROOT / 'data/tennis/artworks.json'
    art = json.loads(art_path.read_text())
    added = 0
    for a in art['artworks']:
        if a.get('type') != 'Hall of Famer' or a.get('image'): continue
        r = by_slug.get(a['id'][4:]) or by_name.get(norm(a['title']))
        if not r: continue
        fname = urllib.parse.unquote(r['img'].rsplit('/', 1)[1]).replace(' ', '_')
        key = 'hof-' + re.sub(r'[^a-z0-9]+', '-', a['title'].lower()).strip('-')[:50]
        dest = ROOT / 'data/tennis/images' / f'{key}.jpg'
        if not dest.exists():
            time.sleep(GAP)
            raw = fetch(thumb(fname)) or fetch(thumb(fname).replace('/thumb/', '/').rsplit('/', 1)[0])
            try: save(raw, dest)
            except Exception:
                print('  no picture for', a['title'], flush=True); continue
        a['image'] = f'data/tennis/images/{key}.jpg'
        a['imageCredit'] = 'Wikimedia Commons'
        a['imageSource'] = 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(fname)
        if 'not of an object' not in a.get('description', ''):
            a['description'] += ' The picture is a photograph of them, not of an object in the museum.'
        added += 1
        print(f'{added:3} {a["title"]}', flush=True)
    art_path.write_text(json.dumps(art, ensure_ascii=False, separators=(',', ':')))
    guide_path = ROOT / 'data/guides/Q52454.json'
    guide = json.loads(guide_path.read_text())
    img = {a['id']: a['image'] for a in art['artworks'] if a.get('image')}
    for w in guide['works']:
        if not w.get('imageUrl') and w['id'] in img: w['imageUrl'] = img[w['id']]
    guide_path.write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data/guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums']['Q52454']['pictures'] = sum(bool(w.get('imageUrl')) for w in guide['works'])
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print('added', added, 'portraits')


if __name__ == '__main__':
    main()
