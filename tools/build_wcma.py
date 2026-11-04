#!/usr/bin/env python3
"""Build the Williams College Museum of Art (WCMA, Williamstown) guide (run: python3 tools/build_wcma.py <clone>).

    data/guides/Q12072937.json   the WCMA works listed on the museum page

<clone> is a copy of github.com/wcmaart/collection, the museum's own open data (CC0, about 17,000 records
exported from its collection database, last updated Oct 2024). Pictures come from tools/harvest_wcma.py.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSEUM = 'Q12072937'
CACHE = ROOT / '.cache' / 'wcma'

# whole departments that are listed; prints, photographs and drawings only when the record has a description
KEEP = {'WCMA-PAINTING', 'WCMA-SCULPTURE', 'WCMA-AFRICAN', 'WCMA-ANCIENT', 'WCMA-EASTERN', 'WCMA-DEC ARTS',
        'WCMA-AMERINDIAN', 'WCMA-PACIFIC', 'WCMA-WALLS'}
PRENDERGAST_SKIP = {'photograph', 'book', 'frame', 'tool', 'document', 'letter', 'magazine', 'card', 'postcard',
                    'envelope', 'notebook', 'sketchbook page', 'ephemera', 'negative', 'newspaper', 'brochure'}
TYPES = {'WCMA-PAINTING': 'Painting', 'WCMA-SCULPTURE': 'Sculpture', 'WCMA-AFRICAN': 'African art',
         'WCMA-ANCIENT': 'Ancient art', 'WCMA-EASTERN': 'Asian art', 'WCMA-DEC ARTS': 'Decorative arts',
         'WCMA-AMERINDIAN': 'Native American art', 'WCMA-PACIFIC': 'Pacific art', 'WCMA-WALLS': 'WALLS loan art',
         'WCMA-Prendergast': 'Prendergast collection', 'WCMA-PRINTS': 'Print', 'WCMA-PHOTO': 'Photograph',
         'WCMA-DRAWING': 'Drawing'}


def load_objects(clone):
    return json.loads((clone / 'Objects-utf8.json').read_text(encoding='utf-8-sig'))


def choose(objs):
    out = []
    for o in objs:
        c = o['classification']
        if c not in TYPES: continue
        if '(LEAD SCREEN)' in (o['title'] or '') and not o['filename']: continue
        name = (o['object_name'] or '').lower().strip()
        if c in KEEP or len(describe(o) or '') > 80 or (c == 'WCMA-Prendergast' and name not in PRENDERGAST_SKIP):
            out.append(o)
    return out


def describe(o):
    d = (o['Description'] or '').replace('\\\\s', "'s").replace('\\\\', "'")
    return clean(d) if len(d) > 40 and not d.upper().startswith('SEE ') else None


def clean(s):
    s = re.sub(r'\s+', ' ', (s or '').replace('(LEAD SCREEN)', '')).strip(' ,;')
    return s or None


def year_of(o):
    a, b = o['creation_date_earliest'], o['creation_date_latest']
    if isinstance(a, int) and isinstance(b, int) and (a or b): return round((a + b) / 2)
    m = re.search(r'-?\d{3,4}', o['creation_date'] or '')
    return int(m.group()) if m else None


def work(o, iiif):
    w = {'id': f'wcma-{o["id"]}', 'title': clean(o['title']) or 'Untitled'}
    if clean(o['maker']) and o['maker'].strip().lower() not in ('unknown', 'unidentified artist'):
        w['artist'] = clean(o['maker'])
    elif clean(o['culture']):
        w['artist'] = clean(o['culture'])
    for k, src in (('date', 'creation_date'), ('medium', 'medium'), ('culture', 'culture'),
                   ('accession', 'accession_number'), ('dimensions', 'dimensions'), ('credit', 'credit_line')):
        v = clean((o[src] or '').replace('\r\n', ' '))
        if v and v.lower() != 'no date': w[k] = v
    if describe(o): w['caption'] = describe(o)
    y = year_of(o)
    if y is not None: w['year'] = y
    w['type'] = TYPES[o['classification']]
    w['url'] = f'https://egallery.williams.edu/objects/{o["id"]}'
    pic = iiif.get(str(o['id']))
    if pic:
        w['imageUrl'] = f'https://rs.williams.edu/iiif/image/{pic}/full/400,/0/default.jpg'
    w['source'] = 'WCMA open collection data (CC0)'
    if pic: w['imageCredit'] = 'Williams College Museum of Art'
    return w


def main():
    objs = load_objects(Path(sys.argv[1]))
    f = CACHE / 'iiif.json'
    iiif = json.loads(f.read_text()) if f.exists() else {}
    works = [work(o, iiif) for o in choose(objs)]
    # pictured works first, then by how central the department is
    order = ['Painting', 'Sculpture', 'Prendergast collection', 'Asian art', 'African art', 'Ancient art',
             'Native American art', 'Pacific art', 'Decorative arts', 'Photograph', 'Print', 'Drawing', 'WALLS loan art']
    works.sort(key=lambda w: (not w.get('imageUrl'), order.index(w['type']), -(w.get('year') or -9999)))
    guide = {'museum': MUSEUM, 'name': 'Williams College Museum of Art', 'checked': '2026-11-04',
             'source': 'WCMA open collection data (github.com/wcmaart/collection, CC0)', 'onViewKnown': False,
             'note': f'WCMA owns about {len(objs):,} works. Listed here: its paintings, sculpture, ancient, '
                     'African, Asian, Native American and decorative art, the Prendergast collection, and the '
                     'prints, photographs and drawings the museum wrote a caption for. Until Dec 23, 2026 only '
                     'the Object Lab in Lawrence Hall is open, so most of these are in storage until the new '
                     'museum opens.',
             'works': works}
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(works), 'pictures': sum(1 for w in works if w.get('imageUrl')),
                              'onView': None, 'galleries': False, 'checked': '2026-11-04', 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(len(works), 'works,', idx['museums'][MUSEUM]['pictures'], 'with pictures')


if __name__ == '__main__':
    main()
