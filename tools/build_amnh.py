#!/usr/bin/env python3
"""Build the American Museum of Natural History map guide.

Run: python3 tools/trace_amnh.py (once, needs opencv), python3 tools/harvest_amnh.py --list, python3 tools/build_amnh.py
--choose, python3 tools/harvest_amnh.py, python3 tools/build_amnh.py.

    data/amnh/floors.json       the Lower Level and Floors 1-4, seen from above (flat 2D)
    data/amnh/artworks.json     the halls and the specimens, dioramas and objects in them (photos from Wikimedia Commons)
    data/guides/Q217717.json    the same, for the museum page

Where the information comes from
--------------------------------
The map is the museum's own visitor map (English, "© 2026", made August 2026; amnh.org/content/download/385996/
5752508/file/english-map.pdf). Its rooms, grey areas, doorways and icons are traced by tools/trace_amnh.py
(tools/data/amnh-trace.json). Map units are PDF points x 2; Central Park West is at the bottom, Columbus Avenue at the
top. The names, the entrances (from the museum's visitor information sheet, March 2026) and the stairs are added here
by hand. Where two halls share an open space, the line between them is where the tracing put it.

The things in the halls: photos visitors shared on Wikimedia Commons (tools/harvest_amnh.py). Commons keeps one
category per hall, so a photo from a hall's category is in that hall (placeNote says so). Photos from the museum-wide
categories (fossils, dioramas, meteorites, minerals, cultures) are placed by what they show (RULES); those that fit no
hall are left out, and the guessed ones are marked placeGuessed. Old photos (before 2000) are left out, since halls
have changed. Pictures are shown from Commons (Special:FilePath), not copied.
"""
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'amnh'
CACHE = ROOT / '.cache' / 'amnh'
MUSEUM = 'Q217717'
NAME = 'American Museum of Natural History'
MAP_URL = 'https://www.amnh.org/content/download/385996/5752508/file/english-map.pdf'
S = 0.45                        # map units -> frame

# room id -> (name shown, short label or None, kind or None to keep the traced one)
ROOMS = {
    # Lower Level
    'Food Court': ('Food Court (10:45 am–4:45 pm)', None, 'space'),
    'The Universe': ('Dorothy and Lewis B. Cullman Hall of the Universe: the Willamette meteorite, planets and '
                     'galaxies, under the Hayden Sphere', 'Hall of the Universe', 'gallery'),
    'School Lunchrooms': ('School lunchrooms (groups)', None, 'space'),
    'Parking Garage LL': ('Parking garage (entrance on 81st Street)', None, 'space'),
    'Subway Exit Hall': ('Subway entrance (81st Street station, B and C trains): tickets, ATM, restrooms', None,
                         'corridor'),
    # Floor 1
    'Meteorites': ('Arthur Ross Hall of Meteorites: Ahnighito, the 34-ton Cape York meteorite', 'Meteorites', 'gallery'),
    'Gems and Minerals': ('Allison and Roberto Mignone Halls of Gems and Minerals: the Patricia amethyst geode, '
                          'the Star of India', 'Gems & Minerals', 'gallery'),
    'Gems and Minerals Gallery': ('Melissa and Keith Meister Gallery: changing shows of gems and minerals', 'Gallery',
                                  'gallery'),
    'Human Origins Learning Lab': ('Human Origins Learning Lab (classroom)', None, 'space'),
    'Human Origins': ('Anne and Bernard Spitzer Hall of Human Origins: Lucy, Turkana Boy and our human family',
                      'Human Origins', 'gallery'),
    'Program Theaters': ('Program theaters', None, 'space'),
    'Exploration Atrium': ('Kenneth C. Griffin Exploration Atrium: the canyon-like heart of the Gilder Center',
                           'Exploration Atrium', 'space'),
    'Insectarium': ('Susan and Peter J. Solomon Family Insectarium: live insects and a leafcutter ant colony',
                    'Insectarium', 'gallery'),
    'Collections Core 1': ('Louis V. Gerstner, Jr. Collections Core: three floors of collection cases', 'Collections Core',
                           'gallery'),
    'Gilder Gift Shop': ('Gilder Gift Shop', None, 'space'),
    'Cafe on 1': ('Cafe on 1 (11 am–4:30 pm)', None, 'space'),
    'Futter Gallery': ('Arthur and Joan Futter Gallery (77th Street entrance hall): the Hall of Northwest Coast '
                       'canoe and changing shows', 'Futter Gallery', 'gallery'),
    'Northwest Coast': ('Northwest Coast Hall: the great canoe and monumental carvings of the First Nations of the '
                        'Pacific Northwest (the museum’s oldest hall, renewed in 2022)', 'Northwest Coast', 'gallery'),
    'Sensory Room': ('Sensory room (a quiet room)', None, 'space'),
    'Discovery Room': ('Discovery Room (hands-on, for families)', None, 'space'),
    'Giant-Screen Theater': ('LeFrak Family Giant-Screen Theater (ticketed films)', 'Giant-Screen Theater', 'space'),
    'Small Mammals': ('Hall of Small Mammals', 'Small Mammals', 'gallery'),
    'The Museum Shop 1': ('The Museum Shop (Floor 1)', None, 'space'),
    'Ocean Life': ('Milstein Hall of Ocean Life: the 94-foot blue whale and the ocean dioramas', 'Ocean Life',
                   'gallery'),
    'New York State Environment': ('Felix M. Warburg Hall of New York State Environment', 'NY State Environment',
                                   'gallery'),
    'North American Forests': ('Hall of North American Forests: the giant sequoia slice', 'N. American Forests',
                               'gallery'),
    'Biodiversity': ('Hall of Biodiversity: the Spectrum of Life wall and the Dzanga-Sangha rainforest',
                     'Biodiversity', 'gallery'),
    'North American Mammals': ('Bernard Family Hall of North American Mammals: the Alaska brown bears, bison and '
                               'wolves dioramas', 'N. American Mammals', 'gallery'),
    'Planetarium': ('Hayden Planetarium Space Theater (ticketed space show), Rose Center', 'Planetarium', 'space'),
    'Grand Foyer': ('Rose Center Grand Foyer (81st Street entrance)', None, 'corridor'),
    'Planet Earth': ('David S. and Ruth L. Gottesman Hall of Planet Earth: rocks, earthquakes and the dynamic Earth',
                     'Planet Earth', 'gallery'),
    'Roosevelt Memorial Hall': ('Theodore Roosevelt Memorial Hall: tours start here; security desk, lost and found',
                                'Roosevelt Memorial Hall', 'space'),
    'Parking Garage 1': ('Parking garage (81st Street)', None, 'space'),
    'School Group Check-In': ('School group check-in', None, 'corridor'),
    'Restrooms (Gilder, Floor 1)': ('Restrooms, family/all-gender restroom and companion care room', None, 'space'),
    'West Hall': ('Hallway', None, 'corridor'),
    'Restrooms (west, Floor 1)': ('Restrooms', None, 'space'),
    'Rose Center Hall': ('Hallway to the Rose Center', None, 'corridor'),
    'Gilder Hall': ('Gilder Center hallway', None, 'corridor'),
    'Hall to Roosevelt Memorial Hall': ('Hallway with stairs to Floor 2', None, 'corridor'),
    # Floor 2
    'South American Peoples': ('Hall of South American Peoples', 'South American Peoples', 'gallery'),
    'Mexico and Central America': ('Hall of Mexico and Central America: Olmec, Maya and Aztec art', 'Mexico & C. America',
                                   'gallery'),
    'Birds of the World': ('Hall of Birds of the World', 'Birds of the World', 'gallery'),
    'African Peoples': ('Hall of African Peoples', 'African Peoples', 'gallery'),
    'Asian Peoples': ('Gardner D. Stout Hall of Asian Peoples', 'Asian Peoples', 'gallery'),
    'Asian Mammals': ('Hall of Asian Mammals: the Asian elephants and tigers', 'Asian Mammals', 'gallery'),
    'African Mammals': ('Akeley Hall of African Mammals: the herd of African elephants and the dioramas',
                        'African Mammals', 'gallery'),
    'Akeley Gallery': ('Akeley Gallery (changing shows)', 'Akeley Gallery', 'gallery'),
    'The Museum Shop 2': ('The Museum Shop (Floor 2)', None, 'space'),
    'Rotunda': ('Theodore Roosevelt Rotunda (Central Park West entrance): the Barosaurus defending her young',
                'Rotunda', 'space'),
    'Collections Core 2': ('Louis V. Gerstner, Jr. Collections Core', 'Collections Core', 'gallery'),
    'Butterfly Vivarium': ('Davis Family Butterfly Vivarium (ticketed): hundreds of live butterflies',
                           'Butterfly Vivarium', 'gallery'),
    'The Restaurant at Gilder': ('The Restaurant at Gilder (11:30 am–3:30 pm, table service)', None, 'space'),
    'North Galleria': ('North Galleria', None, 'corridor'),
    'East Galleria': ('East Galleria', None, 'corridor'),
    'Terrace': ('Arthur Ross Terrace (outdoors)', None, 'space'),
    'Big Bang Theater': ('Big Bang Theater and the Heilbrunn Cosmic Pathway (Rose Center)', 'Big Bang', 'gallery'),
    'Scales of the Universe': ('Scales of the Universe (Rose Center): from galaxies to atoms around the Hayden Sphere',
                               'Scales of the Universe', 'gallery'),
    'Cosmic Shop': ('Cosmic Shop', None, 'space'),
    'Restrooms (Gilder, Floor 2)': ('Restrooms and family/all-gender restroom', None, 'space'),
    'Restrooms (North Galleria)': ('Restrooms and family/all-gender restroom', None, 'space'),
    # Floor 3
    'Pacific Peoples': ('Margaret Mead Hall of Pacific Peoples: the Easter Island moai cast', 'Pacific Peoples',
                        'gallery'),
    'Climate Learning Lab': ('Climate Learning Lab', None, 'space'),
    'Invisible Worlds': ('Invisible Worlds (ticketed): the immersive theater of the Gilder Center', 'Invisible Worlds',
                         'gallery'),
    'Collections Core 3': ('Louis V. Gerstner, Jr. Collections Core', 'Collections Core', 'gallery'),
    'Primates': ('Hall of Primates', 'Primates', 'gallery'),
    'North American Birds': ('Leonard C. Sanford Hall of North American Birds', 'N. American Birds', 'gallery'),
    'New York State Mammals': ('Hall of New York State Mammals', 'NY State Mammals', 'gallery'),
    'New York City Birds': ('Hall of New York City Birds', 'NYC Birds', 'gallery'),
    'African Mammals Mezzanine': ('Akeley Hall of African Mammals, upper level: the dioramas of the mezzanine',
                                  'African Mammals (upper)', 'gallery'),
    'Gallery 3': ('Gallery 3 (ticketed shows)', 'Gallery 3', 'gallery'),
    'Reptiles and Amphibians': ('Hall of Reptiles and Amphibians: the Komodo dragons', 'Reptiles & Amphibians',
                                'gallery'),
    'West Hall 3': ('Hallway', None, 'corridor'),
    'Restrooms (Gilder, Floor 3)': ('Restrooms, family/all-gender restroom and lactation room', None, 'space'),
    'Mezzanine Hall': ('Hallway', None, 'corridor'),
    'Classroom 3': ('Classroom', None, 'space'),
    # Floor 4
    'Research Library': ('Research Library', None, 'space'),
    'Alcove Gallery': ('Alcove Gallery (Research Library)', 'Alcove Gallery', 'gallery'),
    'Vertebrate Origins': ('Hall of Vertebrate Origins: fishes, pterosaurs, turtles and sea reptiles',
                           'Vertebrate Origins', 'gallery'),
    'Orientation Center': ('Miriam and Ira D. Wallach Orientation Center: start of the fossil halls; the Titanosaur',
                           'Orientation Center', 'gallery'),
    'Cafe on 4': ('Cafe on 4 (11 am–4:30 pm)', None, 'space'),
    'Gallery 4': ('Gallery 4 (ticketed shows)', 'Gallery 4', 'gallery'),
    'Saurischian Dinosaurs': ('Hall of Saurischian Dinosaurs: Tyrannosaurus rex, Apatosaurus', 'Saurischian Dinosaurs',
                              'gallery'),
    'Advanced Mammals': ('Paul and Irma Milstein Hall of Advanced Mammals: mammoths, mastodons, horses',
                         'Advanced Mammals', 'gallery'),
    'Ornithischian Dinosaurs': ('Hall of Ornithischian Dinosaurs: Triceratops, Stegosaurus, duck-billed dinosaurs',
                                'Ornithischian Dinosaurs', 'gallery'),
    'Primitive Mammals': ('Lila Acheson Wallace Wing: Hall of Primitive Mammals', 'Primitive Mammals', 'gallery'),
    'Turret': ('Turret', None, 'space'),
    'Dino Store': ('Dino Store', None, 'space'),
    'Gilder Hall 4': ('Gilder Center hallway', None, 'corridor'),
    'Classroom 4': ('Classroom', None, 'space'),
    'Fossil Halls Landing': ('Landing (stairs and elevators)', None, 'corridor'),
}

# Amenities added by hand (PDF points): stairs (the map draws steps, not an icon) and the entrances
STAIRS = {
    'LL': [(373, 274), (279, 515), (342, 515), (466, 492)],
    '1': [(131, 308), (142, 411), (389, 271), (266, 519), (356, 519), (506, 494), (446, 530), (310, 254)],
    '2': [(128, 314), (128, 406), (268, 519), (344, 519), (281, 235), (308, 260), (385, 503)],
    '3': [(128, 321), (128, 411), (265, 519), (358, 519), (292, 238)],
    '4': [(126, 402), (265, 519), (357, 519), (296, 236)],
}
ENTRANCES = {'LL': [(310, 575)], '1': [(318, 193), (508, 466)], '2': [(311, 570)]}
NOTES = {
    'LL': [('Subway: B, C (81st St)', 310, 600)],
    '1': [('77th Street door (special events)', 75, 372), ('Member entrance, under the front steps', 311, 585),
          ('Gilder Center entrance (Columbus Ave)', 330, 182), ('Rose Center entrance (81st St)', 495, 445)],
    '2': [('Main entrance: Central Park West steps', 311, 590)],
}
STREETS = [('COLUMBUS AVENUE', 288, 100), ('CENTRAL PARK WEST', 300, 625), ('77th St', 32, 330), ('81st St', 545, 330)]
FLOORS = [('LL', 'Lower Level', 'Food Court · Hall of the Universe · Subway entrance · Parking'),
          ('1', 'Floor 1', 'Entrances · Ocean Life · Meteorites · Gems & Minerals · Human Origins · North American '
                'Mammals · Planet Earth · Gilder Center'),
          ('2', 'Floor 2', 'Main entrance & Rotunda · African & Asian Mammals · Peoples halls · Birds of the World · '
                'Butterfly Vivarium · Big Bang'),
          ('3', 'Floor 3', 'Pacific Peoples · Primates · Reptiles & Amphibians · North American Birds · Invisible '
                'Worlds'),
          ('4', 'Floor 4', 'Fossil halls: dinosaurs and mammals · Vertebrate Origins · Research Library')]
DROP_ICONS = {'4': [('shop', 79, 405)]}          # false matches (the Cafe on 4 dining icon)


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def P(x, y):                    # PDF points -> map units
    return [round(x * 2, 1), round(y * 2, 1)]


def build_floors():
    tr = json.loads((ROOT / 'tools' / 'data' / 'amnh-trace.json').read_text())
    floors = []
    for order, (fid, label, area) in enumerate(FLOORS):
        t = tr[fid]
        rooms = []
        for rid, poly in t['polys'].items():
            name, short, kind = ROOMS[rid]
            r = {'id': rid, 'kind': kind or t['kinds'][rid], 'name': name, 'poly': poly}
            if r['kind'] == 'gallery': r['label'] = short or rid
            if r['kind'] != 'corridor': r['labelAt'] = t['seeds'][rid]
            rooms.append(r)
        am, notes = [], []
        for kind, x, y in t['icons']:
            if any(k == kind and abs(x - 2 * a) < 20 and abs(y - 2 * b) < 20 for k, a, b in DROP_ICONS.get(fid, [])):
                continue
            if kind == 'ticket':
                notes.append({'text': 'Tickets', 'kind': 'note', 'at': [x, y + 14]})
                continue
            am.append({'type': kind, 'at': [x, y]})
        am += [{'type': 'stairs', 'at': P(x, y)} for x, y in STAIRS.get(fid, [])]
        am += [{'type': 'entrance', 'at': P(x, y)} for x, y in ENTRANCES.get(fid, [])]
        notes += [{'text': s, 'kind': 'note', 'at': P(x, y)} for s, x, y in NOTES.get(fid, [])]
        floors.append({
            'id': fid, 'label': label, 'order': order, 'transform': [S, 0, 0], 'area': area, 'rooms': rooms,
            'closed': [{'poly': c} for c in t['closed']], 'amenities': am,
            'labels': [{'text': s, 'kind': 'area', 'at': P(x, y)} for s, x, y in STREETS], 'notes': notes,
            'doors': [{'a': a, 'b': b, 'at': [x, y], 'width': 16, 'axis': 'o'} for a, b, x, y, n in t['doors']]})
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
    return {'about': 'Built by tools/build_amnh.py. Traced from the American Museum of Natural History’s own visitor '
                     'map (English, 2026): the five levels, every hall, the grey areas closed to visitors, restrooms, '
                     'family/all-gender restrooms, lactation and companion care rooms, elevators, escalators, dining, '
                     'shops, information and ticket desks. Walls are simplified; stairs and the entrances (from the '
                     'museum’s visitor information sheet) are placed by hand.',
            'source': 'American Museum of Natural History, visitor map (2026)', 'sourceUrl': MAP_URL,
            'units': 'PDF points of the map x 2; Central Park West is at the bottom, Columbus Avenue at the top',
            'approximate': False, 'defaultFloor': '1', 'galleryWord': 'Hall', 'floors': floors}


# ---- halls and things in them -------------------------------------------------------------------------------------

SUFFIX = ' at American Museum of Natural History'
# Commons hall category -> room
HALL_CAT = {
    'Akeley Hall of African Mammals': 'African Mammals',
    'Allison and Roberto Mignone Halls of Gems and Minerals': 'Gems and Minerals',
    'Anne and Bernard Spitzer Hall of Human Origins': 'Human Origins',
    'Arthur Ross Hall of Meteorites': 'Meteorites',
    'Bernard Family Hall of North American Mammals': 'North American Mammals',
    'David S. and Ruth L. Gottesman Hall of Planet Earth': 'Planet Earth',
    'Dorothy and Lewis B. Cullman Hall of the Universe': 'The Universe',
    'Hall of African Peoples': 'African Peoples', 'Hall of Asian Mammals': 'Asian Mammals',
    'Hall of Birds of the World': 'Birds of the World', 'Hall of Mexico and Central America': 'Mexico and Central America',
    'Hall of New York City Birds': 'New York City Birds', 'Hall of North American Forests': 'North American Forests',
    'Hall of Ornithischian Dinosaurs': 'Ornithischian Dinosaurs', 'Hall of Primates': 'Primates',
    'Hall of Primitive Mammals': 'Primitive Mammals', 'Hall of Reptiles and Amphibians': 'Reptiles and Amphibians',
    'Hall of Saurischian Dinosaurs': 'Saurischian Dinosaurs', 'Hall of South American Peoples': 'South American Peoples',
    'Hall of Vertebrate Origins': 'Vertebrate Origins', 'Margaret Mead Hall of Pacific Peoples': 'Pacific Peoples',
    'Milstein Hall of Ocean Life': 'Ocean Life', 'Sanford Hall of North American Birds': 'North American Birds',
    'Theodore Roosevelt Hall of Biodiversity': 'Biodiversity',
    'Warburg Hall of New York State Environments': 'New York State Environment',
    'Northwest Coast Hall in the American Museum of Natural History': 'Northwest Coast',
    'Paul and Irma Milstein Hall of Advanced Mammals': 'Advanced Mammals',
    'Susan and Peter J. Solomon Family Insectarium': 'Insectarium',
    'Theodore Roosevelt Memorial Hall': 'Roosevelt Memorial Hall',
    'Star of India (gem)': 'Gems and Minerals',
}
# (regex on file name + description + categories, room, kind). First match wins; used for photos whose category
# doesn't name the hall, and to move Hall of Fossil Reptiles / Gilder Center photos to the right room.
RULES = [
    (r'barosaurus', 'Rotunda', 'Fossil'),
    (r'titanosaur|patagotitan', 'Orientation Center', 'Fossil'),
    (r'willamette', 'The Universe', 'Meteorite'),
    (r'ahnighito|cape york|meteorit', 'Meteorites', 'Meteorite'),
    (r'butterfl|vivarium', 'Butterfly Vivarium', 'Live animals'),
    (r'insectarium|leafcutter|leaf-cutter', 'Insectarium', 'Live animals'),
    (r'collections core', 'Collections Core 1', 'Specimen'),
    (r'invisible worlds', 'Invisible Worlds', 'Exhibit'),
    (r'griffin|exploration atrium|gilder center|gilder_center', 'Exploration Atrium', 'Architecture'),
    (r'tyrannosaur|t\. ?rex|allosaur|apatosaur|brontosaur|deinonych|velociraptor|albertosaur|coelophys|'
     r'saurischian|theropod|sauropod|oviraptor|ornithomimid|struthiomimus|gorgosaur|carnotaur|mamenchisaur|'
     r'buitreraptor|herrerasaur|plateosaur', 'Saurischian Dinosaurs', 'Fossil'),
    (r'tricerat|stegosaur|ankylosaur|euoplocephal|edmontosaur|anatotitan|hadrosaur|corythosaur|lambeosaur|saurolophus|'
     r'protocerat|psittacosaur|pachycephalosaur|styracosaur|iguanodon|ornithischian|maiasaur|parasaurolophus|'
     r'chasmosaur|centrosaur|duck-bill', 'Ornithischian Dinosaurs', 'Fossil'),
    (r'mammoth|mammuthus|mastodon|mammut\b|equus|horse|smilodon|saber|sabre|rhino|indricother|paracerather|'
     r'brontother|megaloceros|irish elk|bison antiquus|camel|giraffokeryx|deinother|gomphother|platybelodon|'
     r'whale fossil|andrewsarchus|daeodon|entelodon', 'Advanced Mammals', 'Fossil'),
    (r'glyptodon|doedicurus|ground sloth|megatheri|uintather|coryphodon|diprotodon|thylacoleo|monotreme|'
     r'marsupial|xenarthr|pantodont|eremotherium', 'Primitive Mammals', 'Fossil'),
    (r'dunkleosteus|placoderm|megalodon|carcharocles|shark jaw|eryops|dimetrodon|pterosaur|pteranodon|plesiosaur|'
     r'elasmosaur|ichthyosaur|mosasaur|tylosaur|archelon|stupendemys|deinosuch|kronosaur|eusthenopteron|'
     r'coelacanth|fish fossil|vertebrate origins', 'Vertebrate Origins', 'Fossil'),
    (r'lucy|australopith|turkana|homo erectus|neanderthal|hominid|hominin|human origins', 'Human Origins', 'Fossil'),
    (r'star of india|amethyst|geode|gem\b|gems|mineral|crystal|tourmaline|beryl|quartz|azurite|malachite|topaz|'
     r'sapphire|emerald|opal', 'Gems and Minerals', 'Mineral'),
    (r'blue whale|ocean life|coral reef|andros|walrus|sperm whale|giant squid|dolphin|manta|sea lion', 'Ocean Life',
     'Diorama'),
    (r'okapi|gorilla|african elephant|lion\b|lions|zebra|giraffe|kudu|bongo|gerenuk|hyena|cheetah|impala|wildebeest|'
     r'akeley|african wild dog|nyala|eland|oryx|buffalo', 'African Mammals', 'Diorama'),
    (r'tiger|asian elephant|panda|gaur|sloth bear|indian rhinoceros|leopard|ibex|yak|asian mammals|clouded', 'Asian Mammals',
     'Diorama'),
    (r'grizzly|brown bear|kodiak|moose|caribou|pronghorn|mountain goat|bighorn|wolves|wolf|jaguar|cougar|puma|'
     r'american bison|bison|musk ox|elk\b|wapiti|alaska', 'North American Mammals', 'Diorama'),
    (r'easter island|moai|rapa nui|maori|polynesia|melanesia|micronesia|pacific peoples|new guinea|'
     r'margaret mead', 'Pacific Peoples', 'Object'),
    (r'tlingit|haida|kwakwaka|kwakiutl|nuxalk|tsimshian|totem|great canoe|northwest coast', 'Northwest Coast', 'Object'),
    (r'olmec|maya\b|mayan|aztec|zapotec|mixtec|teotihuac|mexic|costa rica|panama|guatemala', 'Mexico and Central America',
     'Object'),
    (r'inca|moche|nazca|chimu|peru|andes|andean|amazon|shuar|ecuador|bolivia|south american', 'South American Peoples',
     'Object'),
    (r'african peoples|benin|yoruba|kuba|dogon|asante|ashanti|masai|maasai|zulu|congo|pygmy|mbuti', 'African Peoples',
     'Object'),
    (r'asian peoples|siberia|tibet|china|chinese|japan|korea|mongol|india\b|vietnam|samurai', 'Asian Peoples', 'Object'),
    (r'komodo|crocodil|alligator|snake|python|lizard|turtle|tortoise|frog|salamander|reptile|amphibian', 'Reptiles and Amphibians',
     'Specimen'),
    (r'primate|chimpanz|orangutan|lemur|gibbon|baboon|monkey', 'Primates', 'Specimen'),
    (r'sequoia|forest', 'North American Forests', 'Diorama'),
    (r'earthquake|volcan|planet earth|banded iron|black smoker|sulfide', 'Planet Earth', 'Specimen'),
    (r'big bang|cosmic pathway|scales of the universe|hayden sphere|rose center', 'Scales of the Universe', 'Exhibit'),
]
# hall entries: room -> short text about the hall
HALL_TEXT = {
    'Ocean Life': 'The museum’s best-known room: a 94-foot (29 m) model of a female blue whale hangs over two levels '
                  'of ocean dioramas, from the Andros coral reef to the sperm whale fighting a giant squid.',
    'Meteorites': 'Ahnighito, a 34-ton piece of the Cape York meteorite brought from Greenland by Robert Peary in '
                  '1897, stands on pillars that go down to the bedrock, with meteorites from Mars and the Moon.',
    'Gems and Minerals': 'Reopened in 2021 after a full renewal: thousands of minerals and gems, a giant amethyst '
                         'geode taller than a person and the 563-carat Star of India sapphire.',
    'Human Origins': 'The story of human evolution, with casts of Lucy, Turkana Boy and Neanderthals, and the '
                     'footprints of Laetoli.',
    'North American Mammals': 'Classic dioramas of animals of North America, among them the Alaska brown bears, '
                              'bison and the wolves in the snow, restored in 2012.',
    'Planet Earth': 'How the Earth works: rocks you can touch, black smokers from the sea floor, banded iron and the '
                    'earthquake and volcano galleries.',
    'Biodiversity': 'The 100-foot Spectrum of Life wall with more than 1,500 specimens and a walk-in African rainforest '
                    'from the Dzanga-Sangha reserve.',
    'New York State Environment': 'The seasons in a Dutchess County landscape: forests, farms, soil and water of '
                                  'New York State.',
    'North American Forests': 'Dioramas of the forests of North America and a 1,400-year-old slice of a giant sequoia.',
    'Northwest Coast': 'The museum’s first hall (1899), reopened in 2022 with the First Nations: monumental carvings, '
                       'masks and the 63-foot great canoe.',
    'Small Mammals': 'Small North American mammals in their habitats.',
    'Insectarium': 'Live insects, a working beehive and a leafcutter ant colony you can follow through the walls.',
    'Collections Core 1': 'Cases of the museum’s collections, rising three floors along the Gilder Center: '
                          'specimens from its 34 million objects.',
    'Exploration Atrium': 'The canyon-like atrium of the Gilder Center (2023), designed by Studio Gang, joining ten '
                          'buildings of the museum.',
    'African Mammals': 'Carl Akeley’s hall (1936): a herd of eight African elephants in the middle and 28 dioramas of '
                       'Africa’s animals and landscapes around it.',
    'Asian Mammals': 'Dioramas of Asian animals, with the two Asian elephants in the middle of the hall.',
    'Birds of the World': 'Dioramas of birds in their habitats on every continent.',
    'African Peoples': 'Cultures of Africa: masks, textiles, tools and ceremonies.',
    'Asian Peoples': 'Cultures of Asia, from Siberia and the Silk Road to Japan and India.',
    'Mexico and Central America': 'Ancient Mexico and Central America: the Olmec, Maya and Aztec, with the colossal '
                                  'Olmec head cast.',
    'South American Peoples': 'Peoples of the Andes and the Amazon: Inca, Moche and Amazonian cultures.',
    'Rotunda': 'The Theodore Roosevelt Rotunda, the Central Park West entrance: a Barosaurus rears up to defend '
               'her young from an Allosaurus, under murals of Roosevelt’s life.',
    'Butterfly Vivarium': 'Ticketed: hundreds of live butterflies fly free among tropical plants.',
    'Big Bang Theater': 'A short show on the birth of the universe, then the Cosmic Pathway ramp: 13 billion years in '
                        '360 feet.',
    'Scales of the Universe': 'Walkway around the Hayden Sphere comparing sizes, from galaxies to atoms.',
    'Pacific Peoples': 'Margaret Mead’s hall of the Pacific islands, with a cast of an Easter Island moai.',
    'Primates': 'Our closest relatives: apes, monkeys and lemurs.',
    'North American Birds': 'Dioramas of the birds of North America.',
    'New York State Mammals': 'Mammals of New York State.',
    'New York City Birds': 'The birds you can see in New York City.',
    'Reptiles and Amphibians': 'Komodo dragons, crocodiles, snakes and frogs, and how reptiles and amphibians live.',
    'Invisible Worlds': 'Ticketed: an immersive show of the networks of life, from cells to the biosphere.',
    'Orientation Center': 'Start of the fossil halls. The 122-foot Titanosaur, one of the largest dinosaurs ever found, '
                          'fills the room and pokes its head out the door.',
    'Saurischian Dinosaurs': 'Tyrannosaurus rex, Apatosaurus and the other “lizard-hipped” dinosaurs and their bird '
                             'descendants.',
    'Ornithischian Dinosaurs': '“Bird-hipped” dinosaurs: Triceratops, Stegosaurus, armored and duck-billed dinosaurs.',
    'Advanced Mammals': 'Mammoths, mastodons, horses, saber-toothed cats and the other recent mammals.',
    'Primitive Mammals': 'Early mammals and their relatives: glyptodonts, giant sloths and more.',
    'Vertebrate Origins': 'Fishes, the first animals on land, pterosaurs, turtles and the sea reptiles.',
    'The Universe': 'The Hall of the Universe under the Hayden Sphere: the 15-ton Willamette meteorite, the largest '
                    'found in the United States, and the stars and galaxies.',
    'Planetarium': 'Ticketed space show in the Hayden Planetarium, inside the Hayden Sphere.',
    'Roosevelt Memorial Hall': 'The hall under the Rotunda, honoring Theodore Roosevelt; guided tours start here.',
    'Gallery 3': 'Ticketed temporary exhibitions (check your ticket).',
    'Gallery 4': 'Ticketed temporary exhibitions (check your ticket).',
}
SKIP = r'(?i)logo|map\b|floor ?plan|diagram|chart|sign\b|signage|ticket|exterior|facade|façade|building|night|' \
       r'gala|portrait of|journal|1[89]\d\d|expedition|staff|people at|crowd|selfie'
PER_ROOM = 40                   # at most this many photos per hall


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def title_of(f, desc):
    t = re.sub(r'\.(jpe?g|png|gif|webp)$', '', f, flags=re.I).replace('_', ' ')
    t = re.sub(r'(?i)\s*[-–,]?\s*(at the |in the |at |in )?(the )?american museum of natural history', '', t)
    t = re.sub(r'(?i)\s*[-–,]?\s*\(?\bamnh\b\)?', ' ', t)
    t = re.sub(r'\(\d{6,}\)|\bDSC[F_N]?\d+|\bIMG[_ ]\d+|\bP\d{6,}|\b\d{8}[_ ]\d+|\(\d+\)$', ' ', t)
    t = re.sub(r'(\s+\d+)+$', '', t)            # trailing photo numbers ("2024 031")
    t = re.sub(r'\s+', ' ', t).strip(' -–,.')
    t = re.sub(r'(?i)(\s+(at|in|the|of|-))+$', '', t)
    if len(re.sub(r'[^A-Za-z]', '', t)) < 4:
        d = re.split(r'(?<=[.!?])\s', desc or '')[0]
        t = d[:90] if d else ''
    return t[:120]


def photo_date(d):
    d = re.sub(r'(?i)taken on|date[: ]|\s*\d{1,2}:\d\d(:\d\d)?|\(.*?\)|,\s*$', '', d or '').strip(' ,')
    return f'photographed {d}' if d and len(d) < 30 and re.search(r'\d{4}', d) else None


def year_of(r):
    m = re.search(r'\b(1[89]\d\d|20\d\d)\b', r.get('date') or '')
    return int(m[1]) if m else None


def place(f, cats, desc):
    """(room, kind, exact?) for a photo, or None to leave it out."""
    hay = ' '.join([f, desc or '', ' '.join(cats)]).lower().replace('_', ' ')
    for c in cats:
        top = c.split(' > ')[0].replace('_', ' ')
        hall = HALL_CAT.get(top.replace(SUFFIX, ''))
        if hall:
            if hall == 'African Mammals' and re.search(r'mezzanine|upper level|balcony', hay): hall = 'African Mammals Mezzanine'
            kind = next((k for rx, room, k in RULES if room == hall and re.search(rx, hay)), None)
            return hall, kind or ('Diorama' if 'diorama' in hay else 'In the hall'), True
    for rx, room, kind in RULES:
        if re.search(rx, hay):
            return room, ('Diorama' if 'diorama' in f.lower() and kind != 'Fossil' else
                          'Specimen' if kind == 'Diorama' else kind), False
    return None


def choose():
    """The files worth reading (written to .cache/amnh/chosen.json for tools/harvest_amnh.py)."""
    where = json.loads((CACHE / 'where.json').read_text())
    cand = []
    for f, cats in where.items():
        if re.search(SKIP, f) or re.search(r'(?i)\.(pdf|djvu|svg|tiff?|webm|ogv|mp4|ogg)$', f): continue
        p = place(f, cats, '')
        if p: cand.append((p[0], not p[2], f))
    out, per = [], {}
    for room, guessed, f in sorted(cand):          # photos with an exact hall first
        if per.get(room, 0) >= PER_ROOM + 10: continue
        per[room] = per.get(room, 0) + 1
        out.append(f)
    (CACHE / 'chosen.json').write_text(json.dumps(out, ensure_ascii=False))
    print(len(out), 'files chosen')


def credit(r):
    who = text(r.get('author'))
    who = re.sub(r'(?i)^(own work,? )|\s*\(talk\)|\s*from .*$', '', who).strip()[:60] or 'unknown'
    lic = r.get('license') or 'see Commons'
    return f'Photo: {who}, {lic} (Wikimedia Commons)'


def commons_url(f, width=800):
    return f'https://commons.wikimedia.org/wiki/Special:FilePath/{quote(f)}?width={width}'


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    rows = json.loads((CACHE / 'files.json').read_text())
    works, per, hero, seen_titles = [], {}, {}, set()

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})

    cand = []
    for r in rows:
        f = r['file']
        if re.search(SKIP, f): continue
        y = year_of(r)
        if y and y < 2000: continue
        desc = text(r.get('description'))
        if re.search(r'(?i)\b(1[89]\d\d)\b', desc[:80]) and not y: continue
        p = place(f, r.get('cats', []) + r.get('categories', []), desc)
        if not p: continue
        room, kind, exact = p
        if room not in rooms: continue
        title = title_of(f, desc)
        if not title: continue
        # photos with a real subject name first, then the rest; newest first
        score = (0 if re.search(r'[a-z]{4,}', title) and not re.search(r'(?i)^(american museum|museum|hall|natural history)', title) else 1,
                 -(y or 0))
        cand.append((room, score, f, title, kind, exact, desc, r))
    cand.sort(key=lambda c: (c[0], c[1]))
    for room, score, f, title, kind, exact, desc, r in cand:
        key = (room, re.sub(r'[^a-z]', '', title.lower())[:40])
        if key in seen_titles and per.get(room, 0) > 8: continue
        if per.get(room, 0) >= PER_ROOM: continue
        seen_titles.add(key)
        per[room] = per.get(room, 0) + 1
        hero.setdefault(room, f)
        a = {'id': 'amnh-' + re.sub(r'[^a-z0-9]+', '-', f.lower())[:70].strip('-'), 'title': title, 'artist': kind,
             'description': desc[:600] if desc and desc.lower() != title.lower() else None,
             'url': 'https://commons.wikimedia.org/wiki/File:' + quote(f.replace(' ', '_')),
             'image': commons_url(f), 'imageCredit': credit(r),
             'date': photo_date(r.get('date'))}
        if exact:
            note = 'In the hall where the photo was taken (its Wikimedia Commons category names the hall).'
        else:
            note = 'Placed by what the photo shows: the photo doesn’t say which hall it was taken in, so the hall is ' \
                   'our guess.'
        add(a, room, not exact, note)
    # one entry for each hall, first
    for room, txt in HALL_TEXT.items():
        if room not in rooms: continue
        f = hero.get(room)
        a = {'id': f'amnh-hall-{re.sub(r"[^a-z0-9]+", "-", room.lower())}', 'title': rooms[room][1].split(':')[0],
             'artist': 'Hall', 'description': txt, 'url': 'https://www.amnh.org/exhibitions/permanent',
             'image': commons_url(f) if f else None}
        if f: a['imageCredit'] = next(credit(r) for r in rows if r['file'] == f)
        add(a, room, False, 'On the museum’s visitor map (2026).')
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['artist'] != 'Hall'))
    seen, out = set(), []
    for a in works:
        if a['id'] in seen: continue
        seen.add(a['id'])
        out.append(a)
    return {'source': 'Photos from Wikimedia Commons, placed on the museum’s visitor map (2026)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': works['source'], 'onViewKnown': True,
            'note': 'The museum holds about 34 million specimens and artifacts; its website can’t be read by this '
                    'guide. Listed here are its halls and photos visitors took in them (Wikimedia Commons), in the '
                    'halls where the museum’s 2026 map puts them. Photos that don’t name their hall are placed by '
                    'subject (marked as a guess).',
            'works': rows}


def main():
    if '--choose' in sys.argv:
        return choose()
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True, 'checked': guide['checked'],
                              'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} halls and things ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
