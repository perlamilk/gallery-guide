#!/usr/bin/env python3
"""Read what the International Tennis Hall of Fame guide needs, once and slowly, into .cache/tennis.

    python3 tools/harvest_tennis.py

  .cache/tennis/html/       tennisfame.com pages (the museum, its 2025 reopening and June 2026 Federer exhibit
                            press releases, the historic grounds, hours and admission, FAQ), 5 s apart.
                            tennisfame.com has no robots.txt (the address answers with the home page), so nothing
                            is off limits; we read plain pages only, never the site's content API.
  .cache/tennis/hub/        the Hall of Fame Open "what you need to know" page on info.tennisfame.com (HubSpot;
                            robots.txt allows it) and the 2026 site map picture it shows: the grounds map.
  .cache/tennis/img/        the museum's photographs on those pages (cdn0.scrvt.com), 4 s apart.
  .cache/tennis/loc/        the Historic American Buildings Survey record of the Newport Casino (HABS RI-331,
                            www.loc.gov/item/ri0065, public domain): its photographs and caption index.
  .cache/tennis/list.wiki   Wikipedia's "List of members of the International Tennis Hall of Fame" (one request).
  .cache/tennis/wd.json     every Hall of Famer in Wikidata (ITHF id P3363) with a portrait (one SPARQL request;
                            Wikidata limits clouds to about one request a minute, so it is never repeated).
Portraits themselves are downloaded by tools/build_tennis.py, 3 s apart.
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'tennis'
SITE = 'https://www.tennisfame.com'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
WM_UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'
PAGES = ['visit/hours-and-admission', 'about/faq', 'visit', 'museum-and-grounds', 'museum-and-grounds/the-museum',
         'museum-and-grounds/historic-grounds', 'about/history', 'ithf-unveils-newly-renovated-museum',
         'Museum-Renovation-Project', 'club/outdoor', 'club/indoor', 'digitalexhibits',
         'international-tennis-hall-of-fame-unveils-new-roger-federer-exhibit-ahead-of-2026-induction-45d74f5577a354e1']
PHOTO_PAGES = ['museum-and-grounds/the-museum', 'museum-and-grounds/historic-grounds', 'museum-and-grounds',
               'ithf-unveils-newly-renovated-museum',
               'international-tennis-hall-of-fame-unveils-new-roger-federer-exhibit-ahead-of-2026-induction-45d74f5577a354e1']
HUB = 'https://info.tennisfame.com/what-you-need-to-know-for-your-cerity-partners-hall-of-fame-open-experience-1'
SITE_MAP = 'https://info.tennisfame.com/hubfs/2026%20HFO%20Site%20Map.jpg'
LOC = 'https://tile.loc.gov/storage-services/service/pnp/habshaer/ri/ri0000/ri0065/photos/{}pv.jpg'
LOC_CAPTIONS = 'https://tile.loc.gov/storage-services/master/pnp/habshaer/ri/ri0000/ri0065/data/ri0065cap.pdf'
WIKI_LIST = ('https://en.wikipedia.org/w/index.php?title=List_of_members_of_the_International_Tennis_Hall_of_Fame'
             '&action=raw')
SPARQL = '''SELECT ?p ?pLabel ?ithf ?img ?country ?countryLabel ?birth ?death ?desc WHERE {
  ?p wdt:P3363 ?ithf .
  OPTIONAL { ?p wdt:P18 ?img }
  OPTIONAL { ?p wdt:P1532 ?country }
  OPTIONAL { ?p wdt:P569 ?birth } OPTIONAL { ?p wdt:P570 ?death }
  OPTIONAL { ?p schema:description ?desc FILTER(LANG(?desc)="en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}'''


def fetch(url, dest, delay, ua=UA, extra=()):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '120', '-A', ua, *extra, url], capture_output=True).stdout
    time.sleep(delay)
    if not out:
        print('could not read', url)
        return False
    dest.write_bytes(out)
    print('read', url, flush=True)
    return True


def photo_urls(page):
    s = page.read_text(errors='replace')
    s = s[s.find('Donation Request Form'):]          # skip the menu and the header logos
    return [u for u in dict.fromkeys(re.findall(r'https://cdn0\.scrvt\.com/[^"&)\s]+\.(?:jpe?g|JPE?G)', s))]


def main():
    for p in PAGES:
        fetch(f'{SITE}/{p}', CACHE / 'html' / (p.replace('/', '_') + '.html'), 5)
    fetch(HUB, CACHE / 'hub' / 'open2026.html', 5)
    fetch(SITE_MAP, CACHE / 'hub' / 'site2026.jpg', 5)
    for p in PHOTO_PAGES:
        for u in photo_urls(CACHE / 'html' / (p.replace('/', '_') + '.html')):
            fetch(u, CACHE / 'img' / u.split('/')[-1], 4)
    for n in range(144543, 144561):
        fetch(LOC.format(n), CACHE / 'loc' / 'img' / f'{n}.jpg', 2)
    fetch(LOC_CAPTIONS, CACHE / 'loc' / 'cap.pdf', 2)
    fetch(WIKI_LIST, CACHE / 'list.wiki', 2, WM_UA)
    fetch('https://query.wikidata.org/sparql', CACHE / 'wd.json', 2, WM_UA,
          ['-H', 'Accept: application/sparql-results+json', '--data-urlencode', f'query={SPARQL}'])
    rows = json.loads((CACHE / 'wd.json').read_text())['results']['bindings']
    print(len({r['p']['value'] for r in rows}), 'Hall of Famers in Wikidata')


if __name__ == '__main__':
    main()
