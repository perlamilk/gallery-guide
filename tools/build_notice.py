#!/usr/bin/env python3
"""What to Notice guides for museums other than the MFA.
Texts and zoom regions live in tools/notice/<museum>.json ({artwork id: {steps: [...]}}); the pictures in
data/<museum>/notice/<artwork id>.jpg (about 1280 px, from the museum's open-access images or Commons).
Writes data/<museum>/notice.json, which js/site.js names in that museum's `notice` field.
Run: python3 tools/build_notice.py met moma ..."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

CREDIT = {
    'met': 'The Metropolitan Museum of Art (Open Access, public domain)',
    'moma': 'The Museum of Modern Art',
    'gardner': 'Wikimedia Commons',
    'wadsworth': 'Wikimedia Commons',
    'harvard': 'Wikimedia Commons',
}
ABOUT = ('What to Notice: guided looks at a work, one detail at a time. Written for this app from general '
         'art-history knowledge, not by the museum. Regions are fractions of the picture: x, y, width, height.')

for m in sys.argv[1:]:
    src = json.load(open(f'tools/notice/{m}.json'))
    works = {}
    for id_, w in src.items():
        img = f'data/{m}/notice/{id_}.jpg'
        if not os.path.exists(img): sys.exit(f'{m}: missing picture {img}')
        works[id_] = {'image': img, 'credit': w.get('credit') or CREDIT.get(m, 'Wikimedia Commons'), 'steps': w['steps']}
    json.dump({'about': ABOUT, 'works': works}, open(f'data/{m}/notice.json', 'w'), ensure_ascii=False, indent=1)
    print(f'data/{m}/notice.json: {len(works)} guides')
