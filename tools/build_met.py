#!/usr/bin/env python3
"""Build The Met's works: data/met/artworks.json (every object The Met lists as on view at Fifth Avenue,
in its gallery on the map) and data/guides/Q160236.json (the highlights, for the museum page).

Reads .cache/met/obj/*.json from tools/harvest_met.py (The Met Collection API, Open Access) and
data/met/floors.json from tools/build_met_map.py. Pictures are The Met's own Open Access images,
linked from images.metmuseum.org (public domain works only: the API leaves the rest without a picture)."""
import glob, json, os, re, datetime, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
Q = 'Q160236'
IMG = 'https://images.metmuseum.org/CRDImages/'
TODAY = datetime.date.today().isoformat()


def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('’', '’')).strip()


def main():
    floors = json.load(open('data/met/floors.json'))
    rooms = {}
    for f in floors['floors']:
        for r in f['rooms']:
            if r['kind'] == 'gallery':
                for i in [r['id'], *r.get('aliases', [])]:
                    rooms[i] = (r['id'], r['name'], f['id'])
    works, skipped = [], collections.Counter()
    for p in glob.glob('.cache/met/obj/*.json'):
        o = json.load(open(p))
        if not o:
            continue
        g = clean(o.get('GalleryNumber'))
        if o.get('department') == 'The Cloisters' or o.get('repository', '').endswith('Cloisters'):
            skipped['Cloisters'] += 1
            continue
        if g not in rooms:
            skipped[g or 'no gallery'] += 1
            continue
        gid, gname, floor = rooms[g]
        title = clean(o.get('title')) or clean(o.get('objectName')) or 'Untitled'
        artist = clean(o.get('artistDisplayName'))
        culture = clean(o.get('culture'))
        w = {'id': f"met{o['objectID']}", 'title': title}
        if artist:
            w['artist'] = artist
        elif culture:
            w['artist'] = culture
        if clean(o.get('objectDate')):
            w['date'] = clean(o['objectDate'])
        if isinstance(o.get('objectBeginDate'), int) and (o.get('objectBeginDate') or o.get('objectEndDate')):
            w['year'] = o['objectBeginDate']
        if clean(o.get('medium')):
            w['medium'] = clean(o['medium'])[:160]
        typ = clean(o.get('classification')) or clean(o.get('objectName'))
        if typ:
            w['type'] = typ
        country = clean(o.get('country')) or culture or clean(o.get('artistNationality'))
        if country:
            w['country'] = country
        if clean(o.get('period')) or clean(o.get('dynasty')):
            w['period'] = ', '.join(x for x in (clean(o.get('period')), clean(o.get('dynasty'))) if x)
        if o.get('accessionNumber'):
            w['accession'] = o['accessionNumber']
        w['gallery'] = gid
        if gid != g:
            w['galleryNumber'] = g
        w['floor'] = floor
        img = o.get('primaryImageSmall') or ''
        if img.startswith(IMG) and '/web-large/' in img:
            w['image'] = img[len(IMG):].replace('/web-large/', '/mobile-large/')
        elif img:
            w['image'] = img
        if o.get('isHighlight'):
            w['highlight'] = True
        works.append(w)
    # highlights first, then by gallery
    works.sort(key=lambda w: (not w.get('highlight'), w['floor'], w['gallery'], w['title']))
    pics = sum('image' in w for w in works)
    print(len(works), 'works,', pics, 'with pictures; skipped', skipped.most_common(12))
    json.dump({'source': 'The Metropolitan Museum of Art Collection API (Open Access): objects on view, with their gallery numbers',
               'checked': TODAY, 'count': len(works), 'complete': True,
               # js/data.js fills these in for every work
               'defaults': {'onView': True, 'imageCredit': 'The Metropolitan Museum of Art (Open Access, public domain)'},
               'urlTemplate': 'https://www.metmuseum.org/art/collection/search/{n}',
               'imageBase': IMG,
               'artworks': works},
              open('data/met/artworks.json', 'w'), ensure_ascii=False, separators=(',', ':'))

    hi = [w for w in works if w.get('highlight')]
    gw = [{'id': w['id'], 'title': w['title'], **({'artist': w['artist']} if 'artist' in w else {}),
           **({'date': w['date']} if 'date' in w else {}), **({'type': w['type']} if 'type' in w else {}),
           'url': f"https://www.metmuseum.org/art/collection/search/{w['id'][3:]}",
           **({'imageUrl': (w['image'] if w['image'].startswith('http') else IMG + w['image'])} if 'image' in w else {}), 'onView': True,
           'gallery': w['gallery'], 'floor': w['floor']} for w in hi]
    json.dump({'museum': Q, 'name': 'The Metropolitan Museum of Art', 'checked': TODAY,
               'source': 'The Met Collection API (Open Access)', 'onViewKnown': True,
               'note': f'The Met has more than 1.5 million works; {len(works):,} are on view at Fifth Avenue and all of them are '
                       f'in the map guide, in their galleries. Listed here are the {len(hi):,} that The Met marks as highlights.',
               'works': gw},
              open(f'data/guides/{Q}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    gj = json.load(open('data/guides.json'))
    gj['museums'][Q] = {'works': len(works), 'pictures': pics, 'onView': len(works), 'galleries': True,
                        'checked': TODAY, 'source': 'The Met Collection API (Open Access): every object on view, with its gallery'}
    json.dump(gj, open('data/guides.json', 'w'), ensure_ascii=False, indent=1)
    print(len(hi), 'highlights')


if __name__ == '__main__':
    main()
