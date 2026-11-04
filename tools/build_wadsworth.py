#!/usr/bin/env python3
"""Builds the Wadsworth Atheneum map guide's works from the museum's own "On View" list.

    python3 tools/build_wadsworth.py onview.jsonl images-folder/

Inputs (both made by tools/harvest-wadsworth.cjs, which reads the museum's public collection site
one record at a time, slowly):
  onview.jsonl     one line per work the museum marks "Currently on view? YES"
  images-folder/   one small JPEG per work, named after its object number

Writes:
  data/wadsworth/artworks.json          the works, in the same shape as data/artworks.json (MFA)
  data/wadsworth/images/images-NNN.bin  their pictures, packed into a few files (img: {p, o, l})
  data/guides/Q403080.json + guides.json  the "In the Collection" list on the museum page

Where a work hangs: the museum's collection site says whether a work is on view but not in which room,
and its map names only wings ("Avery 2: Modernism, Impressionism"). So each work gets the wing whose
legend matches its origin, date and kind (WING_RULES below). This is an estimate and the app says so.
"""
import json, re, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'wadsworth'
GUIDE = ROOT / 'data' / 'guides' / 'Q403080.json'
GUIDES = ROOT / 'data' / 'guides.json'
PORTAL = 'https://5058.sydneyplus.com/argus/final/Portal/Public.aspx?lang=en-US'
PACK_SIZE = 15e6
PLACE_NOTE = 'Wing estimated from the work’s date and origin: the museum lists it as on view, not the room.'

EUROPE = ('English', 'British', 'French', 'Italian', 'Dutch', 'Flemish', 'German', 'Spanish', 'Austrian', 'Swiss',
          'Belgian', 'Danish', 'Swedish', 'Norwegian', 'Russian', 'Irish', 'Scottish', 'Welsh', 'Netherlandish',
          'Bohemian', 'Portuguese', 'Polish', 'Hungarian', 'Czech', 'European', 'Venetian', 'Florentine', 'Sienese',
          'Bolognese', 'Neapolitan', 'Roman', 'Genoese', 'Milanese', 'Lombard', 'Ferrarese', 'Finnish', 'Romanian',
          'Croatian', 'Ukrainian', 'Latvian', 'Lithuanian', 'Estonian', 'Slovak', 'Slovenian', 'Serbian', 'Icelandic',
          'England', 'France', 'Italy', 'Netherlands', 'Germany', 'Spain', 'Austria', 'Switzerland', 'Belgium',
          'Denmark', 'Sweden', 'Norway', 'Russia', 'Ireland', 'Scotland', 'Portugal', 'Holland', 'Flanders', 'Bohemia',
          'Venice', 'Paris', 'London', 'Nevers', 'Meissen', 'Sèvres', 'Delft', 'Murano', 'Swabian')
ANCIENT = ('Egyptian', 'Egypt', 'Etruscan', 'Cypriot', 'Cyprus', 'Mesopotamian', 'Assyrian', 'Babylonian', 'Sumerian',
           'Greek', 'Greece', 'Hellenistic', 'Attic', 'Corinthian', 'Apulian', 'Campanian', 'Byzantine', 'Coptic',
           'Near Eastern', 'Persian', 'Iran', 'Syria', 'Anatolia')
AMERICA = ('American', 'United States', 'Connecticut', 'Massachusetts', 'New York', 'Pennsylvania', 'Hartford')
DECORATIVE = ('Ceramic', 'Glass', 'Furniture', 'Metalwork', 'Silver', 'Clock', 'Decorative', 'Woodwork', 'Enamel',
              'Jewelry', 'Arms', 'Firearm', 'Textile', 'Costume', 'Lighting', 'Musical')


def first(*vals):
    return next((v for v in vals if v), None)


def year_of(date):
    """'c. 1778' -> 1778, '1650-60' -> 1650, 'early 19th century' -> 1810, '500 B.C.' -> -500."""
    if not date: return None
    d = date.replace('–', '-')
    bc = re.search(r'\b(B\.?\s?C\.?E?\.?|BCE)\b', d, re.I)
    m = re.search(r'(\d{1,2})(st|nd|rd|th)\s+(century|c\.)', d, re.I)
    if m and not re.search(r'\b\d{3,4}\b', d):
        c = int(m[1]); off = 10 if re.search(r'early|first half', d, re.I) else 80 if re.search(r'late|second half', d, re.I) else 50
        y = (c - 1) * 100 + off
        return -y if bc else y
    m = re.search(r'\b(\d{3,4})\b', d)
    if not m: return None
    y = int(m[1])
    return -y if bc else y


def century(y):
    if y is None: return None
    c = abs(y) // 100 + 1
    suf = 'th' if 10 <= c % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(c % 10, 'th')
    return f'{c}{suf} century' + (' B.C.' if y < 0 else '')


def maker(text):
    """'John Trumbull\\n\\t\\nAmerican, 1756-1843' -> ('John Trumbull', 'American, 1756-1843')."""
    lines = [re.sub(r'\s+', ' ', l).strip() for l in (text or '').split('\n')]
    lines = [l for l in lines if l]
    if not lines: return '', ''
    if len(lines) == 1: return lines[0], ''
    details = lines[-1] if re.search(r'\d|,|^(' + '|'.join(EUROPE + AMERICA + ANCIENT) + r')\b', lines[-1]) else ''
    name = ' '.join(lines[:-1] if details else lines)
    return name, details


def has(text, words):
    return bool(text) and any(re.search(r'\b' + re.escape(w) + r'\b', text, re.I) for w in words)


def wing_of(w):
    """The wing (map 'gallery') a work most likely hangs in, from the museum map's legend."""
    origin = ' '.join(filter(None, [w.get('artistDetails'), w.get('country'), w.get('culture')]))
    y = w.get('year')
    deco = any(k.lower() in (w.get('area') or '').lower() for k in DECORATIVE)
    credit = w.get('creditLine') or ''
    if 'Amistad' in credit: return 'Wadsworth 2'                    # The Amistad Center for Art & Culture
    if y is not None and y >= 1946: return 'Wadsworth 1'           # Post WWII & Abstraction, Contemporary
    if has(origin, ANCIENT) or (y is not None and y < 400): return 'Morgan 1'   # Antiquities
    american = has(origin, AMERICA)
    european = has(origin, EUROPE)
    if american:
        if deco: return 'Wadsworth 3'                              # American Decorative Arts
        if y is not None and y < 1700: return 'Wadsworth 3'        # Early American Art
        return 'Avery 3'                                           # American Art 1700s–1950, Hudson River School
    if european:
        if deco:
            if 'Ceramic' in (w.get('area') or ''): return 'Wadsworth 2'     # European Ceramics
            if y is not None and y < 1600: return 'Morgan 1'                 # Medieval & Renaissance, Silver Vault
            if 'Metal' in (w.get('area') or '') or 'Silver' in (w.get('area') or ''): return 'Morgan 1'
            return 'Morgan 2'                                                # Cabinet of Art and Curiosity
        if y is None: return None
        if y < 1600: return 'Morgan 1'                             # Medieval & Renaissance Europe
        if y < 1860: return 'Morgan 2'                             # European Art
        return 'Avery 2'                                           # Impressionism, Modernism
    return None


def build(src, images):
    rows = [json.loads(l) for l in open(src) if l.strip()]
    seen, works = set(), []
    for r in rows:
        acc = r.get('Object ID')
        if not acc or acc in seen or (r.get('Currently on view?') or '').upper() != 'YES': continue
        seen.add(acc)
        name, details = maker(r.get('_maker'))
        culture = ''
        if re.match(r'^(Unidentified|Unknown)', name or ''):
            culture, name = details, ''
        place = r.get('Place Made') or ''
        date = r.get('Date') or ''
        y = year_of(date)
        w = dict(
            id=f'wad-{acc}', title=r.get('Title') or 'Untitled', artist=name, artistDetails=details if name else '',
            date=date, medium=r.get('Media') or '', dimensions=r.get('Dimensions') or None,
            accession=acc, onView=True, type=(r.get('Object Type') or '').strip().capitalize() or None,
            area=r.get('Collection area') or None, country=place.split(',')[-1].strip() if place else None,
            culture=culture or None, period=century(y), year=y, creditLine=r.get('Credit Line') or None,
        )
        wing = wing_of(w)
        if wing:
            w['gallery'] = wing
            w['wing'] = wing
            w['floor'] = wing[-1]
            w['placeNote'] = PLACE_NOTE
        w['url'] = PORTAL
        w['imageCredit'] = 'Wadsworth Atheneum Museum of Art'
        w['_file'] = images / (re.sub(r'[^A-Za-z0-9._-]+', '_', acc) + '.jpg')
        works.append({k: v for k, v in w.items() if v is not None and v != ''})

    # pack the pictures
    (OUT / 'images').mkdir(parents=True, exist_ok=True)
    for old in (OUT / 'images').glob('images-*.bin'): old.unlink()
    n, buf, packs = 1, bytearray(), 0
    def flush():
        nonlocal n, buf
        if buf:
            (OUT / 'images' / f'images-{n:03d}.bin').write_bytes(buf); n += 1; buf = bytearray()
    for w in works:
        f = w.pop('_file')
        if not f.exists(): continue
        data = f.read_bytes()
        if len(buf) + len(data) > PACK_SIZE: flush()
        w['img'] = {'p': f'data/wadsworth/images/images-{n:03d}.bin', 'o': len(buf), 'l': len(data)}
        buf += data
    flush()

    checked = os.environ.get('CHECKED') or __import__('datetime').date.today().isoformat()
    doc = {'source': 'Wadsworth Atheneum collection site (5058.sydneyplus.com), works marked "Currently on view"; wings estimated',
           'checked': checked, 'count': len(works), 'complete': True, 'artworks': works}
    (OUT / 'artworks.json').write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))

    # the museum page's "In the Collection": works on view, then what Wikidata adds that isn't on view
    old = json.loads(GUIDE.read_text()) if GUIDE.exists() else {'works': []}
    on_acc = {w['accession'] for w in works}
    rest = [dict(x, onView=False) for x in old.get('works', []) if x.get('id', '').startswith('Q') and x.get('accession') not in on_acc]
    keep = ('id', 'title', 'artist', 'date', 'year', 'type', 'medium', 'accession', 'onView', 'gallery', 'floor', 'img', 'url')
    gworks = [{k: w[k] for k in keep if k in w} for w in works] + rest
    GUIDE.write_text(json.dumps({'museum': 'Q403080', 'name': 'Wadsworth Atheneum Museum of Art', 'checked': checked,
                                 'source': 'Wadsworth Atheneum collection site · Wikidata (CC0)', 'onViewKnown': True,
                                 'note': 'Works marked on view by the museum. Their wing is estimated.', 'works': gworks},
                                ensure_ascii=False, separators=(',', ':')))
    idx = json.loads(GUIDES.read_text())
    idx['museums']['Q403080'] = {'works': len(gworks), 'pictures': sum(1 for w in gworks if w.get('img') or w.get('image')),
                                 'onView': len(works), 'galleries': True, 'checked': checked,
                                 'source': 'Wadsworth Atheneum collection site · Wikidata (CC0)'}
    GUIDES.write_text(json.dumps(idx, ensure_ascii=False, indent=1))

    by = {}
    for w in works: by[w.get('gallery', '(no wing)')] = by.get(w.get('gallery', '(no wing)'), 0) + 1
    print(f"{len(works)} works on view, {sum(1 for w in works if 'img' in w)} pictures in {n - 1} packs")
    for k in sorted(by): print(f'  {k}: {by[k]}')


if __name__ == '__main__':
    build(sys.argv[1], Path(sys.argv[2]))
