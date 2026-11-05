"""Visit information (full address, hours, ticket prices) for the museums near the MFA.

Typed by hand from each museum's own website (or, where the site blocks robots, from
listings that quote it), checked 2026-11-04. Hours and prices change: re-check a museum's
site and update its entry and `infoChecked` here, then run:

    python3 tools/visit_info.py      # writes the fields into data/museums.json

If tools/build_open_data.py --museums rebuilds museums.json, run this again afterwards.
The Wadsworth (Q403080) is kept by its own guide work, so it is not listed here.
"""
import json, os, re

CHECKED = '2026-11-04'
FREE = ['Free for everyone']

# id: (address, hours, admission, phone or None, notes or None)
VISIT = {
    'Q49133': ('465 Huntington Avenue, Boston, MA 02115',
               ['Sun, Mon, Wed, Sat: 10 am–5 pm', 'Thu–Fri: 10 am–10 pm', 'Tue: closed', 'Last entry 30 minutes before closing'],
               ['Adults: $30', 'Youth 7–17: $14', 'Children 6 and under: free', 'Members: free'], '617-267-9300', None),
    'Q49135': ('25 Evans Way, Boston, MA 02115',
               ['Mon, Wed, Fri: 11 am–5 pm', 'Thu: 11 am–9 pm', 'Sat–Sun: 10 am–5 pm', 'Tue: closed'],
               ['Adults: $25', 'Seniors 65+: $22', 'Students: $15', '17 and under: free', 'Members: free'], '617-566-1401', None),
    'Q11643': ('Dorchester Brewing Company, 1250 Massachusetts Avenue, Boston, MA 02125',
               ['Open during the brewery’s hours', 'Closes Sun–Mon 9 pm, Tue–Thu 10 pm, Fri–Sat 11 pm', 'Fri–Sat after 6 pm: 21 and over only'],
               FREE, None, None),
    'Q1568434': ('1111 Chapel Street, New Haven, CT 06510',
                 ['Tue–Fri: 10 am–5 pm', 'Thu (Sept–June): 10 am–8 pm', 'Sat–Sun: 11 am–5 pm', 'Mon: closed'],
                 FREE, '203-432-0600', None),
    'Q131342274': ('1111 Chapel Street, New Haven, CT 06510',
                   ['Tue–Fri: 10 am–5 pm', 'Thu (Sept–June): 10 am–8 pm', 'Sat–Sun: 11 am–5 pm', 'Mon: closed'],
                   FREE, '203-432-0600', ['Part of the Yale University Art Gallery']),
    'Q3783572': ('32 Quincy Street, Cambridge, MA 02138',
                 ['Tue–Sun: 10 am–5 pm', 'Mon and major holidays: closed'], FREE, '617-495-9400', None),
    'Q809600': ('Harvard Art Museums, 32 Quincy Street, Cambridge, MA 02138',
                ['Tue–Sun: 10 am–5 pm', 'Mon and major holidays: closed'], FREE, '617-495-9400',
                ['Inside the Harvard Art Museums building']),
    'Q1017269': ('Harvard Art Museums, 32 Quincy Street, Cambridge, MA 02138',
                 ['Tue–Sun: 10 am–5 pm', 'Mon and major holidays: closed'], FREE, '617-495-9400',
                 ['Inside the Harvard Art Museums building']),
    'Q1465805': ('225 South Street, Williamstown, MA 01267',
                 ['Sept–June: Tue–Sun 10 am–5 pm', 'July–Aug: daily 10 am–5 pm', 'Open most federal-holiday Mondays'],
                 ['Adults: $22', 'Seniors 65+: $20', 'Ages 18–25 and college students: $10', 'Under 18: free',
                  'First Sunday of the month (Oct–May): free'], '413-458-2303', None),
    'Q713204': ('9 Glendale Road (Route 183), Stockbridge, MA 01262',
                ['Mon, Tue, Thu, Fri: 10 am–4 pm', 'Sat–Sun: 10 am–5 pm', 'Wed: closed'],
                ['Adults: $25', 'Seniors and retired military: $23', 'College students: $15', 'Children 6–18: $5',
                 'Children 5 and under: free', 'Rockwell’s Studio tour: +$10'], '413-931-2221',
                'Free parking by the museum. The front door faces the lawn; Rockwell’s Studio is a short walk across the '
                'grounds and is open May to early November (it closes for the season after Nov 8, 2026). The Terrace '
                'Café is open in summer only. Exploring Calvin and Hobbes and Norman Rockwell: The Human Touch open Nov '
                '14, 2026. No backpacks or large bags in the galleries.'),
    'Q2007919': ('Columbia Point, Boston, MA 02125',
                 ['Daily: 10 am–5 pm', 'Closes at 2 pm the day before Thanksgiving (Nov 25, 2026), on Christmas Eve '
                  'and New Year’s Eve', 'Closed Thanksgiving, Christmas and New Year’s Day',
                  'Timed tickets: book an entry time online'],
                 ['Adults 18–61: $24', 'Seniors 62+: $12', '17 and under: free',
                  'Presidential library foundation members: free',
                  'Massachusetts public library card holders: 50% off'], '617-514-1600',
                 ['Free parking in the museum’s lot. By train: Red Line to JFK/UMass, then the free UMass Boston '
                  'shuttle to the "JFK Library" stop',
                  'Tickets, restrooms and a self-service coat room in the entrance lobby',
                  'Start with the introductory film in Theater I; the exhibits are one floor down and end in the '
                  'glass Pavilion',
                  'Kennedy Café, off the Pavilion: 10 am–4 pm',
                  'The Edward M. Kennedy Institute for the U.S. Senate is next door']),
    'Q1139748': ('1 Science Park, Boston, MA 02114',
                 ['Exhibit Halls: daily, 9 am–5 pm',
                  'Planetarium and Omni Theater: Sun–Thu 9 am–5 pm, Fri–Sat until 10 pm (last show)',
                  'Closes at 2 pm the day before Thanksgiving (Nov 25, 2026) and on Christmas Eve',
                  'Closed Thanksgiving and Christmas'],
                 ['Adults: $33', 'Seniors 60+: $29', 'Children 3–11: $28', 'Under 3: free', 'Members: free',
                  'Planetarium, Omni or 4-D show: +$6 each with admission',
                  'Show only (Planetarium or Omni): adults $10, seniors $9, children $8'], '617-723-2500',
                 ['No timed tickets: just pick the day you visit',
                  'Museum garage (5 am–midnight): from $15 for the first hour. By train: Green Line to Science Park',
                  'Start at the Box Office or the information desk in the Main Lobby (Level 1)',
                  'Riverview Café (Level 1): food 11 am–3:30 pm (Fri to 4:30 pm), Starbucks 7:30 am–4:30 pm',
                  'Don’t miss Lightning! in the Theater of Electricity, the dinosaurs and the Apollo capsule '
                  '(Lower Level)']),
    'Q7005471': ('18 Johnny Cake Hill, New Bedford, MA 02740',
                 ['Daily: 9 am–5 pm',
                  'Closed Thanksgiving, Christmas Day and New Year’s Day'],
                 ['Adults: $24', 'Seniors 65+: $22', 'Youth: $14', 'Children under 3: free', 'Members: free',
                  'Active military, Massachusetts teachers, NEMA/AAM cardholders: free',
                  'New Bedford residents: 50% off', '3D movie: $6 ($4 for members or with admission)'], '508-997-0046',
                 ['While the plaza is rebuilt, the way in is through the Museum Store',
                  'Johnny Cake Hill has no parking during street work: use the Elm Street Garage (51 Elm Street, '
                  'two blocks away) or metered street parking',
                  'No café: you may eat your own food in the Lobby and in Harbor View (Upper Level)',
                  'Free lockers in the coat room; big bags and umbrellas go there',
                  'Highlights Tours at 11 am and 2 pm, included with admission',
                  'Don’t miss the whale skeletons over the Lobby, the Lagoda (Main Level) and Harbor View']),
    'Q2001855': ('26 Oxford Street, Cambridge, MA 02138',
                 ['Daily: 9 am–5 pm', 'Closed on a few holidays (usually Thanksgiving, Dec 24–25 and Jan 1); check '
                  'the museum’s website before going on a holiday'],
                 ['Adults: $20', 'Seniors 65+: $18', 'Students with ID and youth 3–18: $15', 'Under 3: free',
                  'Harvard ID: free with one guest',
                  'Massachusetts residents: free Sun 9 am–noon and Wed 3–5 pm (Sept–May), with proof of residency',
                  'EBT/WIC cardholders: free with up to five guests',
                  'Same ticket gets you into the Peabody Museum of Archaeology & Ethnology next door'],
                 '617-495-3045',
                 ['No café and no food or drink in the galleries; cafés in Harvard Square, 10 minutes’ walk',
                  'Main entrance at 26 Oxford Street, then stairs up to the galleries on the 3rd floor; the '
                  'ground-level accessible entrance is around the side, with an elevator to the galleries',
                  'Restrooms on the 3rd floor near Earth & Planetary Sciences; accessible restroom by the elevator',
                  'Parking: Harvard’s 52 Oxford Street Garage, next to the museum; Red Line to Harvard, 10 minutes’ '
                  'walk',
                  'Don’t miss the Glass Flowers, the Kronosaurus, the whale skeletons in the Great Mammal Hall and '
                  'the giant amethyst geode in Earth & Planetary Sciences']),
    'Q122945': ('170 Whitney Avenue, New Haven, CT 06511',
                ['Tue–Fri: 10 am–5 pm', 'Sat–Sun: noon–5 pm (the museum’s footer says Sat 10 am–5 pm; check before '
                 'going early on a Saturday)', 'Mon: closed (open on MLK Day and Yale Commencement)',
                 'Closed New Year’s Day, Juneteenth, July 4, Thanksgiving, Christmas Eve and Christmas Day'],
                ['Free for everyone, no ticket needed (groups must book)'], None,
                ['No café inside: snacks are allowed only in the Central Gallery (Floor 1); food trucks at Sachem '
                 'and Prospect Streets and cafés on Whitney Avenue, 5–8 minutes’ walk',
                 'Main entrance on Whitney Avenue; group entrance on Sachem Street',
                 'Parking: Yale Lot 22V (corner of Whitney Avenue and Humphrey Street, also accessible parking); on '
                 'weekends all of Lot 22 and nearby Yale garages',
                 'Coatroom and lockers in the Lobby; wheelchairs, stools and sensory bags at the front desk',
                 'Wellness/lactation room on the lower level; all-gender restrooms on Floors 1 and 3',
                 'Free Amuse app: the museum’s digital guide and gallery map',
                 'Don’t miss the Brontosaurus and The Age of Reptiles mural (Burke Hall), Archelon in the Central '
                 'Gallery and the Living Lab (Floor 3)']),
    'Q847508': ('55 Salisbury Street, Worcester, MA 01609',
                ['Wed–Sun: 10 am–4 pm', 'Mon–Tue: closed'],
                ['Adults: $22', 'Seniors and students: $17', '17 and under: free', 'Members: free'], '508-799-4406', None),
    'Q6352575': ('1080 Chapel Street, New Haven, CT 06510',
                 ['Tue: 10 am–5 pm', 'Wed: 10 am–7 pm', 'Thu–Sat: 10 am–5 pm', 'Sun: 11 am–5 pm', 'Mon: closed'],
                 FREE, '203-432-2800', None),
    'Q478013': ('10½ Beacon Street, Boston, MA 02108',
                ['Mon–Thu: 9 am–8 pm', 'Fri–Sat: 9 am–5 pm', 'Sun: closed'],
                ['First floor: $11 (ages 14+)', 'Ages 13 and under, with an adult: $5',
                 'Students, educators, military (with ID): $8',
                 'Card to Culture (EBT, WIC, ConnectorCare): $2 per adult, children 12 and under free',
                 'NARM/ROAM members: free', 'Day membership, all 12 floors: $40'], '617-227-0270',
                ['Your ticket covers the first floor: the Long Room, the Calderwood Gallery’s exhibitions, the Gordon '
                 'Reading Room and the Leventhal Living Room. The upper reading rooms and the fifth-floor terrace need a '
                 'day membership',
                 'Step-free path on the right of the front steps and a lift inside the vestibule; two accessible '
                 'elevators; restrooms on floors B, 1, 2, 3 and 4',
                 'Free digital guide with audio for the first floor on the Bloomberg Connects app',
                 'Folio, the bistro, has its own door next door at 14A Beacon Street',
                 'Coat Room with lockers on the first floor; check the planned closings before you go']),
    'Q3152226': ('25 Harbor Shore Drive, Boston, MA 02210',
                 ['Tue, Wed, Sat, Sun: 10 am–5 pm', 'Thu–Fri: 10 am–9 pm (first Friday: 5 pm)', 'Mon: closed'],
                 ['Adults: $20', 'Seniors 65+: $17', 'Students: $15', '18 and under: free',
                  'Thursday 5–9 pm: free (book ahead)'], '617-478-3100', None),
    'Q4681251': ('3 Chapel Avenue, Andover, MA 01810',
                 ['Tue–Sat: 10 am–5 pm', 'Sun: 1 pm–5 pm', 'Mon: closed',
                  'Closed national holidays, December 24, and August 1 through Labor Day'],
                 FREE, '978-749-4015',
                 'On the Phillips Academy campus, at Main Street (Route 28) and Chapel Avenue; free parking. Restrooms are on '
                 'the Lower Level (an accessible restroom is on Level 1). No café. An accessible lift is down the ramp to the '
                 'left of the main entrance stairs, and an elevator serves every floor.'),
    'Q5460633': ('96 Lyme Street, Old Lyme, CT 06371',
                 ['Tue–Sun: 10 am–5 pm (January–March: 10 am–4 pm)', 'Mon: closed',
                  'Closed New Year’s Day, Easter, Memorial Day, Juneteenth, July 4, Labor Day, Thanksgiving and the day '
                  'after, December 24 and 25'],
                 ['Adults: $18', 'Seniors 62+: $17', 'Students 13+: $16', 'Children 5–12: $7.50', '4 and under: free',
                  'SNAP/EBT cardholders (up to 4 people), military and veterans: free',
                  'Wee Faerie Village (Oct 3–Nov 8, 2026): adults $23, seniors $22, students $21, 12 and under free'],
                 '860-434-5542',
                 'One ticket covers the whole 12-acre campus: the Krieble Gallery, the Griswold House, the Chadwick Studio and '
                 'the gardens. Tickets are sold only at the admissions desk. Free parking. Restrooms are in the Krieble '
                 'Gallery, the Hartman Education Center and the House. Café Flo (May–October) is on the veranda over the '
                 'river; reservations suggested (860-434-5542 x126). The House’s second floor and the Chadwick Studio are '
                 'not wheelchair accessible. Holiday Magic lights up the campus Nov 27, 2026–Jan 3, 2027.'),
    'Q1890082': ('75 Greenmanville Avenue, Mystic, CT 06355',
                 ['Nov 2–30, 2026: Thu–Sun 10 am–4 pm (grounds close 5 pm); closed Nov 26',
                  'Dec 3–23: Lantern Lights, Thu–Sun (daily Dec 21–23) 2–8:30 pm; closed Dec 1–2 and 24–25',
                  'Dec 26–31: daily 10 am–4 pm',
                  'Jan 2–Mar 19, 2027: north campus only, Fri–Sun 10 am–4 pm',
                  'Spring to fall: daily 10 am–5 pm (grounds close 6 pm)'],
                 ['Adults: $35', 'Seniors 65+: $33', 'Youth 4–17: $25', '3 and under: free', 'Members: free'],
                 '860-572-0711',
                 'A 19-acre outdoor museum: wear comfortable shoes, the historic ground is uneven. Two entrances on '
                 'Greenmanville Avenue (Route 27), North and South, each with free parking. Restrooms at both entrances, '
                 'in the Thompson Exhibition Building, by Greenmans’ Landing, by the Discovery Barn and on Lighthouse '
                 'Point. Food at Anchor Mystic Café (South Entrance), Propeller Coffee Bar (Thompson Building), '
                 'Greenmans’ Landing and Schaefer’s Spouter Tavern. Leashed pets are welcome outdoors but not in '
                 'buildings or on vessels. Sabino cruises and boat rentals are seasonal.'),
    'Q1839461': ('137 Warren Avenue, Plymouth, MA 02360',
                 ['2026 season: daily 9 am–5 pm, through Sunday, Nov 29 (the Sunday after Thanksgiving)',
                  'Closed for the winter after Nov 29; reopens in spring 2027',
                  'Plentiful Café: 9 am–4 pm (hot food 11 am–3 pm)'],
                 ['Heritage Pass (all sites, two days): adults $46, seniors $41.40, children $29',
                  'Combination Pass (Plimoth Patuxet and Mayflower II, two days): adults $44, seniors $39.60, children $27',
                  'Plimoth Patuxet only: adults $35, seniors $31.50, children $20',
                  'Mayflower II only: adults $19, seniors $17.10, children $13',
                  'Plimoth Grist Mill only: adults $11, seniors $9.90, children $8', 'Members: free'],
                 '508-746-1622',
                 'One museum in three places. The main campus (137 Warren Avenue; for GPS from Route 3 use 26 River '
                 'Street) has the Visitor Center, the Historic Patuxet Homesite, the 17th-Century English Village and the '
                 'Craft Center, on 40 acres of mostly unpaved, sometimes steep paths: wear comfortable shoes and allow at '
                 'least 2.5 hours. Free parking; accessible parking in the lower lot. Free golf-cart rides between the '
                 'sites (9:30 am–4:30 pm, ask any staff member). Restrooms on both sides of the Visitor Center and in the '
                 'Craft Center; food at the Plentiful Café (Visitor Center). Mayflower II is at State Pier, 75 Water '
                 'Street, and the Plimoth Grist Mill at 6 Spring Lane, both downtown about 3 miles away: drive, don’t walk '
                 '(metered parking on the waterfront). Mayflower II is not wheelchair accessible. Service animals only. '
                 'November, Thanksgiving week especially, is the busiest time of year.'),
    'Q7005718': ('56 Lexington Street, New Britain, CT 06052',
                 ['Tue–Sun: 10 am–5 pm', 'Fri: 10 am–8 pm', 'Mon: closed'],
                 ['Adults: $22', 'Seniors 67+: $18', 'College students and ages 6–17: $10', '5 and under: free'],
                 '860-229-0257', 'Museum Café: Tue–Sun 10 am–2:30 pm. New Britain residents get in free on the first Saturday '
                 'of the month; one free Community Day a month for everyone.'),
    'Q588474': ('1040 MASS MoCA Way, North Adams, MA 01247',
                ['Wed–Mon: 10 am–5 pm', 'Tue: closed', 'Closed Thanksgiving and Christmas'],
                ['Adults: $25', 'Seniors 65+ and veterans: $22', 'Students: $15', 'Kids 6–16: $10', '5 and under: free',
                 'EBT, WIC and ConnectorCare cards: $2', 'Kidspace: always free'],
                '413-662-2111', 'James Turrell’s Perfectly Clear and Hind Sight need a timed reservation, made at the '
                                'Box Office or at reserve@massmoca.org. Some outdoor and seasonal galleries '
                                '(Anselm Kiefer, the Boiler House, Mary Lum) are open May to October only.'),
    'Q14715853': ('20 Elm Street at Bedford Terrace, Northampton, MA 01063',
                  ['Tue–Sun: 11 am–4 pm', 'Second Friday of the month: open until 8 pm', 'Mon and major holidays: closed'],
                  FREE, '413-585-2760', 'No café in the museum. Lockers, coatroom, strollers and wheelchairs by the '
                                         'Lobby; elevators to every floor.'),
    'Q6803132': ('41 Quadrangle Drive, Amherst, MA 01002',
                 ['Tue–Sun: 9 am–5 pm', 'Mon: closed'], FREE, '413-542-2335',
                 ['All galleries are on one floor, wheelchair-accessible', 'Accessible parking at the front entrance']),
    'Q4713992': ('258 Main Street, Ridgefield, CT 06877',
                 ['Sun, Mon, Wed–Fri: 12–5 pm', 'Sat: 10 am–5 pm', 'Tue: closed', 'Last entry 4:40 pm',
                  'Closed Thanksgiving, Christmas Day and New Year’s Day',
                  'Sculpture Garden: dawn to dusk every day (free)'],
                 ['Adults: $20', 'Seniors 60+: $15', 'Students: $9',
                  'Members, educators, children under 13, military families: free',
                  'SNAP EBT card (Museums for All): free for up to 4', 'Third weekend of the month: free',
                  'Book online in advance (encouraged)'], '203-438-4519',
                 ['No café: restaurants and coffee shops are a 5-minute walk along Main Street',
                  'Free parking on site; by train, Metro-North to Katonah, then a 20-minute taxi',
                  'Elevator; restrooms on the first floor with changing stations; strollers welcome',
                  'Photos without flash are fine (not where a sign says no); pencils only for sketching']),
    'Q2148186': ('20 North Main Street, Providence, RI 02903',
                 ['Tue, Wed, Fri, Sat, Sun: 10 am–5 pm', 'Thu: 12–8 pm', 'Mon: closed'],
                 ['Adults: $22', 'Seniors 62+: $17', 'College students: $12', '18 and under: free',
                  'Sundays and Thursday 5–8 pm: free'], '401-454-6500', None),
    'Q3373790': ('161 Essex Street, Salem, MA 01970',
                 ['Thu–Mon: 10 am–5 pm', 'Tue–Wed: closed'],
                 ['Adults: $25', 'Seniors 65+: $23', 'Students: $15', 'Under 16: free', 'Salem residents: free'],
                 '978-745-9500', None),
    'Q1786400': ('44 Ochre Point Avenue, Newport, RI 02840',
                 ['Daily: 9 am–5 pm (last admission 4 pm)', 'Hours change with the season: see the operating schedule',
                  'Timed tickets: choose a date and time when you buy'],
                 ['Adults: $32', 'Youth 6–12: $14', 'Children under 6: free', 'Preservation Society members: free'],
                 '401-847-1000',
                 ['Tickets, The Breakers Café (9 am–4 pm) and restrooms in the Welcome Center; free parking across Ochre Point Avenue',
                  'Restrooms and the Museum Store also in the basement of the house, at the end of the tour',
                  'Free audio tour in the Newport Mansions app: bring a phone and earbuds',
                  'Partly accessible: ramps to floor 1, an elevator to floor 2 run by staff; 40 stairs otherwise']),
    'Q2650982': ('596 Bellevue Avenue, Newport, RI 02840',
                 ['Daily: 9 am–5 pm (last admission 4 pm)', 'Hours change with the season: see the operating schedule',
                  'No timed ticket needed'],
                 ['Adults: $25 (One Property ticket)', 'Youth 6–12: $10', 'Children under 6: free',
                  'Preservation Society members: free'],
                 '401-847-1000',
                 ['Tickets at the house; free parking across Bellevue Avenue (about 150 m / 503 ft to the front door)',
                  'Restrooms and the Museum Store in the basement, at the end of the tour; one accessible restroom on floor 2',
                  'Afternoon Tea & Dining at the Chinese Tea House on the back lawn, by the Cliff Walk (book ahead)',
                  'Free audio tour (and a kids’ tour) in the Newport Mansions app: bring a phone and earbuds',
                  'Partly accessible: a ramp to floor 1 and a staff-run elevator to floor 2 and the basement; no air-conditioning']),
    'Q7752461': ('2 Plunkett Street, Lenox, MA 01240 (at the corner of Route 7)',
                 ['Grounds and gardens: free, every day of the year, dawn to dusk',
                  'Mansion and Bookstore now (November to January 2): Saturday and Sunday, 10 am–3 pm',
                  'Mansion closed January 3 to April; May–October open daily, usually 10 am–5 pm (some early closings '
                  'on Saturdays for events)',
                  'Terrace Café closed for the season (open May–October); the NightWood café opens November 21',
                  'NightWood light-and-sound walk in the woods: Nov 21, 25, 27–28; Dec 4, 5, 11–12, 17–23, 26–31; '
                  'Jan 2 (separate ticket)',
                  'Check edithwharton.org/hours-admission before you go'],
                 ['Mansion (guided or self-guided tour, with all exhibits): adults $22, seniors 65+ $20, students $13, '
                  'children and teens 18 and under free',
                  'Teachers and military with ID $10 (also for one family member); caregivers free',
                  'Grounds, gardens, Terrace Café and Bookstore: free, no ticket needed',
                  'Bank of America Museums on Us: free on the first full weekend of each month; Card to Culture (EBT, '
                  'WIC, ConnectorCare): free for up to 4 adults',
                  'A NightWood ticket gives 50% off a house tour; Berkshire Site Partnership: $2 off after Herman '
                  'Melville’s Arrowhead (May 9–Oct 31)',
                  'Private tour of Wharton’s library: $150 for two, by reservation'],
                 '413-551-5111',
                 ['Edith Wharton’s own house (1902), which she designed with its gardens. Allow 1.5–2 hours',
                  'Park in the free Parking Field by the Admission Booth and the Stable, then walk about a quarter mile '
                  '(400 m) down the drive to the Mansion; staff can take you by golf cart',
                  'Accessible parking right in front of the Mansion for placard holders; the accessible entrance is to '
                  'the right of the Forecourt',
                  'Restrooms in the Stable and in the Mansion on floors 1 and 2, across from the elevator; changing '
                  'tables in the accessible restrooms',
                  'An elevator reaches all three floors; free manual wheelchairs. The Italian Garden has a ramp; other '
                  'paths are gravel, grass or steep woods',
                  'Free audio tour (English and Spanish) on your phone: bring earbuds; guest Wi-Fi, little cell signal',
                  'Guided tours often sell out: buy tickets ahead. Dogs on leash on the grounds (not on NightWood)']),
    'Q5093884': ('4 Williamsville Road, Stockbridge, MA 01262',
                 ['Open May 15 – October 31 (2026 season): every day except Tuesday, 10 am–5 pm',
                  'Closed for the winter now; it reopens in mid-May 2027 (dates not announced yet)',
                  'Guided tours of the Residence and Studio start between 11 am and 2 pm; self-guided visits '
                  '10–11 am and 3–5 pm',
                  'Check chesterwood.org/hours-admissions before you go'],
                 ['Full estate, with the Residence and Studio tour: adults $25, seniors 65+ $23, students $18, '
                  'military $18, National Trust members $22, children 12 and under free',
                  'Grounds only (no Residence or Studio): adults $18; seniors, students 13+, military and National '
                  'Trust members $16; children 12 and under free',
                  'Members free. Buy online ahead: guided tours often sell out',
                  'Other discounts may apply (EBT, library pass, Stockbridge residents). Not part of NARM'],
                 '413-298-3579',
                 ['Daniel Chester French’s summer home and studio, where he made the seated Lincoln for the Lincoln '
                  'Memorial. Allow at least 1.5 hours',
                  'Start at the Visitor Center in the Barn Gallery (admissions desk, Museum Shop). Restrooms are in '
                  'their own small building between the parking lot and the Residence',
                  'No café: there is a picnic area, and restaurants in Stockbridge and Lenox',
                  'Paved walkways between buildings and ramps into every building; drop-off at the Visitor Center, '
                  'accessible parking, a wheelchair on request. The Woodland Walk is a mostly flat dirt path; the '
                  'Ledges Trail is a steep climb',
                  'Admissions desk (in season): 413-298-2023']),
    'Q5647064': ('1843 West Housatonic Street, Pittsfield, MA 01201 (for GPS: 34 Lebanon Mountain Road, Hancock, MA 01237)',
                 ['Through Nov 29, 2026: Friday, Saturday and Sunday, 11 am–4 pm (Mon–Thu closed)',
                  'Closed for the winter after Nov 29; the Village reopens in April (in 2026 it opened April 18)',
                  'Seasonal hours change: check hancockshakervillage.org/visit/hours-admission before you go'],
                 ['Adults $20; seniors, AAA, MTA cardholders and US military (active and retired) $18',
                  'Youth 13–17 $8; children 12 and under free on family visits',
                  'Massachusetts EBT, WIC and ConnectorCare cards: $2 for up to two adults, kids 17 and under included',
                  'Members free; NARM reciprocal museum. Your ticket is good all day, so you can leave and come back',
                  'No ticket needed for the Shaker Mercantile store or the Believer’s Room exhibition'],
                 '413-443-0188',
                 ['The Shakers’ 1791 “City of Peace”: twenty historic buildings on a working farm with heritage animals. '
                  'Plan 2–3 hours and wear comfortable shoes',
                  'Start at the Visitor Center (tickets, restrooms, store). The Village Café is closed for now: picnic '
                  'tables by the Visitor Center, or ask the store for food nearby',
                  'The Meetinghouse, Ministry’s Shop, Horse Barn and Schoolhouse are across Route 20: cross only at the '
                  'marked crosswalk',
                  'Restrooms: Visitor Center and the Office Privy by the Trustees’ Office',
                  'Visitor Center, galleries, store and restrooms are wheelchair accessible; dirt paths and boardwalks run '
                  'through the Village, and the Round Stone Barn and Trustees’ Office have ramps, but most historic '
                  'buildings are not accessible',
                  'No pets (service dogs welcome). No tripods inside historic buildings',
                  'Farm & Forest Trail: an easy, accessible 1-mile loop from the Round Stone Barn']),
    'Q7085141': ('1 Old Sturbridge Village Road, Sturbridge, MA 01566 (for GPS: 29 Stallion Hill Road, Sturbridge, MA 01518)',
                 ['Through Nov 14, 2026: Wednesday–Sunday, 9:30 am–4 pm (Mon–Tue closed)',
                  'Nov 15–26, 2026: closed, getting ready for Christmas by Candlelight',
                  'Nov 27–Dec 27, 2026: Christmas by Candlelight only, select evenings 2–8 pm (Thursdays 4–8 pm), separate ticket',
                  'Hours change with the season: check osv.org/visit before you go'],
                 ['Bought online: adults $27, seniors 60+ $25, youth 4–17 $12, children 3 and under free',
                  'At the door: adults $30, seniors 60+ $28, youth 4–17 $15, children 3 and under free',
                  'Daytime tickets are good for one day; Christmas by Candlelight and other evening events need their own ticket',
                  'Members: free'],
                 '508-347-0290',
                 ['A 200-acre outdoor village of the 1830s: more than 40 historic buildings, farms and three water-powered '
                  'mills, with costumed historians. Plan 3–4 hours and wear good walking shoes',
                  'Start at the Country Bank Visitor Center: tickets, the free map guide, the Clock Gallery and restrooms',
                  'Food: Bullard Tavern cafeteria (Wed–Sun 11 am–3 pm), Ox & Yoke Café by the entrance, Miner Grant Bake '
                  'Shop; Village Scoop Shop in summer',
                  'Roads are unpaved but firm; steeper bits by the Bullard Tavern, the Glass exhibit and the Herb Garden. '
                  'Wheelchairs free to borrow and strollers to rent at the Visitor Center',
                  'Accessible restrooms: Visitor Center, Ox & Yoke, Bullard Tavern, next to the Countryside Gallery, Museum '
                  'Education Center',
                  'First aid behind the Friends Meetinghouse; a horse-drawn wagon (with ramp) runs from the Bullard Tavern to '
                  'the Blacksmith Shop in season']),
    'Q4165331': ('351 Farmington Avenue, Hartford, CT 06105',
                 ['Daily: 9:30 am–5:30 pm; last tours start at 4:15 pm',
                  'Closed Tuesdays from January through March',
                  'Closed Easter Sunday, July 4, Thanksgiving, Dec 24, Dec 25 and Jan 1',
                  'The house is shown only by guided tour (about 1 hour): buy timed tickets ahead, tours sell out'],
                 ['House tour: adults 17–64 $28, seniors 65+ $26, children 6–16 $15, under 6 free',
                  'Living History tour (about 70 min): adults $31, seniors $29, children $23 (not for under 8)',
                  'Museum Center only (galleries and film, no house): adults and seniors $8, children 6–16 $6',
                  'Members: free · EBT card (Museums for All): $3 house tour, up to 4 people'],
                 '860-247-0998',
                 ['Free parking: set GPS to 385 Farmington Avenue (main lot, a few hundred feet west of the house); for '
                  'limited mobility, the rear lot at 65 Forest Street',
                  'Start at the Museum Center: tickets, the Ken Burns film, two galleries, the store and the restrooms '
                  '(no restrooms in the house)',
                  'Nook Farm Café on the Museum Center’s second floor: May–October, about 11 am–3 pm',
                  'The tour climbs 41 steps to the Billiard Room and 40 back down; no elevator. Floor 1 and the Museum '
                  'Center are wheelchair accessible',
                  'No photos inside the house (photos of the outside are welcome)',
                  'CT Transit buses 60, 62, 64 and 66 stop at Farmington Ave and Woodland St; the Stowe Center is next door']),
    'Q5664050': ('77 Forest Street, Hartford, CT 06105',
                 ['Wed: 10:45 am–5 pm', 'Thu–Sat: 9:45 am–5 pm', 'Sun–Tue: closed',
                  'Closed June 19, Thanksgiving and Dec 25',
                  'Fall 2026: open for booked group tours and some public tours: book a 30- or 60-minute tour ahead '
                  '(only 12 people per tour)'],
                 ['Adults 17–64: $20', 'Seniors 65+: $15', 'Children 6–16 and college students (ID): $10',
                  'Under 6 and members: free', 'Hartford residents (photo ID): free',
                  'EBT card (Museums for All): $3, up to 5 people · Blue Star military families: free (call ahead)',
                  'Nook Farm self-guided audio tour: $15'],
                 '860-522-9258',
                 ['Free parking in the Stowe Center lot on Forest Street (one way from Farmington Avenue), on the left '
                  'side of Forest Street, or in the Mark Twain House lot at 385 Farmington Avenue',
                  'Tours start at the Visitor Center: tickets, the store and the only restroom (accessible)',
                  'These are history tours (talks), not house tours; floor 2 of the house is up one flight of stairs, '
                  'with an alternative tour for people who can’t climb',
                  'No large backpacks, food, drinks or gum in the house; no flash or video. Picnics on the grounds are '
                  'welcome',
                  'No café: the Nook Café at the Mark Twain House next door (May–October)',
                  'CT Transit buses 60, 62, 64 and 66 stop at Farmington Ave and Woodland St']),
    'Q2166814': ('548 Bellevue Avenue, Newport, RI 02840',
                 ['Closed for the season; reopens Jan 29, 2027',
                  'When open: daily, hours change with the season: see the operating schedule',
                  'No timed ticket needed'],
                 ['Adults: $25 (One Property ticket)', 'Youth 6–12: $10', 'Children under 6: free',
                  'Preservation Society members: free', 'The exhibition on floor 2 is included'],
                 '401-847-1000',
                 ['Tickets at the house; free parking next to the house (2 accessible spaces), about 105 m (345 ft) to the front door',
                  'Restrooms and the Museum Store in the basement (27 steps down); one accessible restroom on floor 1',
                  'No café at Rosecliff: the nearest is the Chinese Tea House at Marble House',
                  'Floor 2 holds the exhibition “Revolution Reimagined: Evolving Stories from Newport’s Past”',
                  'Free audio tour in the Newport Mansions app: bring a phone and earbuds',
                  'Partly accessible: a lift to floor 1 and a staff-run elevator to floor 2 (not to the basement); air-conditioned']),
    'Q5087517': ('474 Bellevue Avenue, Newport, RI 02840',
                 ['Closed now; reopens Saturday, Nov 21, 2026 for Holidays at the Newport Mansions',
                  'Nov 21, 2026 – Jan 3, 2027: open Saturdays and Sundays only (times on the operating schedule)',
                  'In the main season: daily, hours change with the season: see the operating schedule',
                  'No timed ticket needed'],
                 ['Adults: $25 (One Property ticket)', 'Youth 6–12: $10', 'Children under 6: free',
                  'Preservation Society members: free',
                  'City of Newport residents: free (show proof of residency)',
                  'EBT or WIC card (any state): $4 per person, up to 4 people (buy in person at The Breakers Welcome '
                  'Center, Marble House, The Elms, Rosecliff or Green Animals)'],
                 '401-847-1000',
                 ['Free parking next to the house (1 accessible space, 245 ft / 75 m from the front door)',
                  'Self-guided audio tour in the free Newport Mansions app: bring a phone and earbuds',
                  'Also in the app: a GPS landscape tour of the park and its rare old trees',
                  'Not accessible: 9 steps up to the front door, 33 steps to floor 2, no elevator or lift',
                  'One restroom in the house (not accessible); no café at Chateau-sur-Mer',
                  'The tour route is about 517 ft (158 m): 266 ft on floor 1, 251 ft on floor 2; air-conditioned']),
    'Q52454': ('194 Bellevue Avenue, Newport, RI 02840',
               ['Museum open daily, 10 am – 5 pm (last admission 4:30)',
                'Grounds open daily 10 am – 5 pm, free (no ticket needed)',
                'Guided tours Friday, Saturday and Sunday at 11 am and 2 pm',
                'Closed Thanksgiving, Christmas Eve and Christmas Day 2026',
                'July 4–11, 2027 (Hall of Fame Open) and Aug 22–30, 2027 (Induction): closed, or tournament/event '
                'ticket needed'],
               ['Adults: $25', 'Seniors, military, students and USTA members: $21.50', 'Kids 12 and under: free',
                'Museum professionals (AAM, NEMA, ISHA): free',
                'SNAP/EBT card: free for up to 4 people (Museums for All)',
                'Active military and families free Memorial Day – Labor Day (Blue Star Museums)',
                'Online tickets are not dated: use them any day; non-refundable'],
               '401-849-3990',
               ['The museum is on the second floor of the 1880 Newport Casino; elevator and wheelchairs available',
                'Nearly 2,000 objects on view from 30,000; allow 1–1½ hours. Audio tours in 5 languages',
                'Leave backpacks, large bags, racquets and drinks at the Welcome Center; no strollers in the museum',
                'No museum parking lot: street parking, the paid Bellevue Gardens lot across the street, or park at '
                'the Newport Transportation Center and ride RIPTA trolley 67 to the door',
                'You can book the historic grass courts in season (May–Oct): Pro Shop 401-849-4777',
                'No café; Museum Store at the entrance on Bellevue Avenue']),
    'Q4820080': ('222 Bellevue Avenue, Newport, RI 02840',
                 ['Open daily, 10 am – 4 pm',
                  'Exhibition now: “Best Shown: Winners from the Audrain Collections”, Sept 19, 2026 – Jan 10, 2027',
                  'Between exhibitions the museum changes its cars over: check audrainautomuseum.org before you go '
                  '(next show opens Jan 16, 2027)'],
                 ['Adults: $18', 'Seniors (65+): $10', 'Military and students (with ID): $10', 'Children 6–17: $8',
                  'Members: free',
                  'Online tickets are valid for one year: bring the order confirmation to the front desk',
                  'American Express not accepted for tickets'],
                 '401-856-4420',
                 ['“More of an art museum than a car museum”: 15–20 rare cars at a time, from more than 300 it can '
                  'draw on, in shows that change every few months. Allow about an hour',
                  'Everything is on one floor: the ground floor of the 1902 Audrain Building on Bellevue Avenue',
                  'Free digital guide on Bloomberg Connects: scan the QR code on any car’s placard',
                  'Racing simulators (best for ages 9–12 and up; free simulator time for members)',
                  'No museum parking lot: street parking on Bellevue Avenue and nearby; RIPTA bus 67 stops at '
                  'Bellevue & Memorial Blvd (Tennis Hall of Fame), a minute’s walk',
                  'Small museum shop by the entrance']),
    'Q7370843': ('680 Bellevue Avenue, Newport, RI 02840',
                 ['2026 season: through Sunday, Nov 8 — Tuesday–Friday 10 am–4 pm, Saturday and Sunday 10 am–5 pm '
                  '(closed Mondays)',
                  'A Rough Point Holiday: Nov 27 – Dec 27, 2026, Friday–Sunday 10 am–4 pm (separate holiday ticket)',
                  'Holiday After Dark: Fridays and Saturdays 4–5:30 pm, Nov 27 – Dec 26 (drinks and jazz on the terrace)',
                  'Closed for the winter after Dec 27; the 2027 season usually opens in late March',
                  'Check newportrestoration.org/plan-a-visit before you go (schedule subject to change)'],
                 ['General admission: $25 (house, exhibitions and grounds)', 'Students with ID: $12.50',
                  'Children 12 and under: free', 'Newport County residents: free (show proof of address)',
                  'EBT or WIC card (any state): $5 per person (Museums for All)', 'Blue Star Museum: free for active '
                  'military families in summer',
                  'No need to buy ahead: tickets online or at the museum entrance'],
                 '401-847-8344',
                 ['Doris Duke’s ocean-front home (1887–91, enlarged by the Dukes in 1922–24), with her art, furniture '
                  'and fashion collections. Self-guided: allow 60–90 minutes',
                  'Get the free “Newport Restoration Foundation” app before you go (room map, stories, videos); bring '
                  'earbuds',
                  'Limited parking on site, with accessible spaces; NRF suggests parking at the Newport Gateway Center '
                  '(23 America’s Cup Ave) and taking the free hop-on, hop-off Route 67 trolley (May–October), which '
                  'stops at Rough Point',
                  'Accessible parking, entrance and restrooms, and an elevator to the second floor; bike racks on site',
                  '2026 exhibitions: Women Designers of the 20th Century and Fashioning Resiliency (Doris Duke Fashion '
                  'Gallery), 1776 | 2026 (Newport Galleries) and Keeping Rough Point Above Water',
                  'Not part of the Preservation Society (Newport Mansions) ticket: Rough Point is run by the Newport '
                  'Restoration Foundation']),
    'Q7731834': ('367 Bellevue Avenue, Newport, RI 02840',
                 ['Closed for its transformation; reopens Nov 16, 2026 as “The Elms Experience”',
                  'Timed tickets: choose a date and time when you buy; arrive 10 minutes early',
                  'Hours change with the season: see the operating schedule',
                  'Carriage House Café on the grounds: daily 11 am–5 pm (last seating 4 pm)'],
                 ['The Elms Experience: Adults $35', 'Youth 6–12: $20', 'Members (adult or youth): $20',
                  'Children under 6: free', 'Servant Life Tour (guided): separate ticket'],
                 '401-847-1000',
                 ['Free parking next to the house (4 accessible spaces), about 116 m (382 ft) to the front door; buses on Bellevue Court',
                  'Restrooms in the basement of the house (14 steps down from the entryway); one accessible restroom',
                  'Carriage House Café (accessible), overlooking the gardens: snacks, lunch, beer and wine; book on Resy or walk in',
                  'Not accessible: no ramps, elevators or lifts; 7 steps into the house, 39 to floor 2, 53 down to the basement',
                  'Free audio tour in the Newport Mansions app: bring a phone and earbuds']),
    'Q1618645': ('35 Mountain Road, Farmington, CT 06032',
                 ['Wed–Sun: 10 am–4 pm (house by guided tour)', 'Mon–Tue: closed', 'Grounds: daily 7:30 am–5:30 pm'],
                 ['Adults: $20', 'Seniors 62+: $18', 'Students: $15', 'Grounds and trails: free'], '860-677-4787',
                 ['Tickets, lockers and restrooms in the visitor center (Carriage Barn); free parking',
                  'Wheelchair access: house floor 1, Museum Shop, exhibition gallery and Sunken Garden; floor 2 by stairs only',
                  'No food is sold; picnic only in marked areas']),
    'Q5455423': ('185 Elm Street, Fitchburg, MA 01420',
                 ['Wed–Fri: 12–4 pm', 'Sat–Sun: 11 am–5 pm', 'First Thursday: 12–7 pm (FAM at Night)',
                  'Mon–Tue: closed',
                  'Also closed New Year’s Day, Easter Sunday, Independence Day, Thanksgiving and Christmas'],
                 ['Free for everyone (sponsored by Rollstone Bank & Trust)'], '978-345-4207',
                 ['Free parking in front of the entrance on Elm Street (accessible spaces near the door) and in the '
                  'Merriam Parkway courtyard lot; not in the Fitchburg Arts Community lot across the street',
                  'Wheelchair accessible: automatic doors, an elevator, and a step-free bridge to the Merriam Parkway '
                  'Building; two wheelchairs to borrow',
                  'Restrooms in the first-floor hallway; coat check by the lobby',
                  'Large bags, umbrellas, food and drink aren’t allowed in the galleries',
                  'No café; FAM Store items are sold at the front desk']),
    'Q14714982': ('625 Williams Street, New London, CT 06320',
                  ['Tue–Sat: 10 am–5 pm', 'Sun: 1–5 pm', 'Mon: closed', 'Last entry 4 pm',
                   'First Thursday (Sep–May): open to 8 pm, last entry 7 pm'],
                  ['Adults: $12', 'Seniors 60+: $9', 'Active military: $7', 'SNAP EBT card (Museums for All): $3',
                   'Youth 12 and under, members, New London residents: free',
                   'New London Public Schools, Connecticut College, USCGA and Mitchell College students and staff: free',
                   'First Saturday of the month: free'], '860-443-2545',
                  ['The grounds are being rebuilt as Lyman Allyn Park: the museum stays open, expect some '
                   'construction noise', 'Free parking behind the museum; accessible parking and a ramp at the side '
                   'entrance (ring the bell)']),
    'Q7367636': ('415 South Street, Waltham, MA 02453',
                 ['Wed–Sun: 11 am–5 pm', 'Mon–Tue: closed'], ['Free (register for a free ticket)'], '781-736-3434', None),
    'Q5508243': ('455 Oak Street, Brockton, MA 02301',
                 ['Tue–Sun: 10 am–5 pm', 'Mon: closed',
                  'Also closed Thanksgiving, Christmas Eve, Christmas Day, New Year’s Day and July 4; '
                  'New Year’s Eve 10 am–2 pm'],
                 ['Admission by donation (pay what you wish)', 'Guided group tours: a fee (book ahead)'],
                 '508-588-6000',
                 ['Free parking; accessible parking and entrance at the lower lot (Education Entrance)',
                  'No café: snacks at the shop, and you can bring lunch to the Lounge or the patio',
                  'Bus: BAT #4A from Brockton station (request stop)']),
    'Q12072937': ('15 Lawrence Hall Drive, Williamstown, MA 01267',
                  ['Mon–Fri: 9 am–5 pm (smaller space while the new museum is built)', 'Sat–Sun: closed'],
                  FREE, '413-597-2429', ['Until Dec 23, 2026 only the Object Lab gallery in Lawrence Hall is open',
                                          'Closed from Dec 23, 2026 until the new museum opens (expected 2027–28)']),
    'Q4664294': ('300 Walnut Avenue, Boston, MA 02119',
                 ['Fri–Sun: 1–5 pm', 'Often open only for events: call before you go'],
                 ['Adults: $5', 'Seniors and children: $4'], '617-442-8614',
                 ['Home of the Museum of the National Center of Afro-American Artists']),
    'Q4769571': ('21 Brown Street, Providence, RI 02906',
                 ['Closed to the public for renovation'], FREE, '401-863-2165', ['Part of the Brown University Library']),
    'Q6974447': ('Vernon Court, 492 Bellevue Avenue, Newport, RI 02840',
                 ['Closed for renovation'], ['Adults: $20', 'Seniors and military: $18', 'Students: $14', 'Children 5–12: $10'],
                 '401-851-8949', ['Children under 5 are not admitted']),
    'Q7758868': ('21 Edwards Street, Springfield, MA 01103',
                 ['Tue–Sat: 10 am–5 pm', 'Sun: 11 am–5 pm', 'Mon: closed',
                  'Open on MLK Day, Presidents’ Day, Patriots’ Day, Columbus Day and Veterans Day',
                  'Closed New Year’s Day, Easter, Memorial Day, Juneteenth, July 4, Labor Day, Thanksgiving, Dec 24 and 25',
                  'Dr. Seuss Sculpture Garden (free): daily 9 am–8 pm from Patriots’ Day to Columbus Day, 9 am–5 pm the '
                  'rest of the year'],
                 ['One ticket, all five museums: adults $27.50', 'Seniors 60+ and college students: $18',
                  'Youth 5–17: $15', 'Under 5: free', 'Springfield residents (with ID): free',
                  'Special exhibitions may cost extra · Sculpture Garden: free'],
                 '413-263-6800',
                 ['Buy tickets at the Welcome Center, in the Science Museum (or online)',
                  'Free parking in the two Edwards Street lots and on State Street across from the City Library; '
                  'accessible spaces in the Edwards Street lots and by the Smith Art Museum; EV charging on Edwards Street',
                  'Blake House Café: Tue–Sun 11 am–3 pm (no museum ticket needed)',
                  'All five buildings are wheelchair accessible, with accessible restrooms',
                  'Non-flash photos for personal use are allowed in many galleries; sketching in pencil only',
                  'The Museum of Springfield History is across Edwards Street from the Quadrangle']),
    'Q41512158': ('21 Edwards Street, Springfield, MA 01103',
                  ['Tue–Sat: 10 am–5 pm', 'Sun: 11 am–5 pm', 'Mon: closed'],
                  ['Adults: $27.50 (one ticket, five museums)', 'Seniors 60+ and college students: $18', 'Youth 5–17: $15',
                   'Under 5: free', 'Springfield residents: free'], '413-263-6800', ['Part of the Springfield Museums']),
    'Q105553919': ('21 Edwards Street, Springfield, MA 01103',
                   ['Tue–Sat: 10 am–5 pm', 'Sun: 11 am–5 pm', 'Mon: closed'],
                   ['Springfield Museums ticket: adults $27.50', 'Seniors 60+ and college students: $18', 'Youth 5–17: $15'],
                   '413-263-6800', ['Part of the Springfield Museums']),
    'Q4892280': ('39 South Street, Pittsfield, MA 01201',
                 ['Friday–Wednesday 10 am–5 pm', 'Closed Thursdays'],
                 ['Adults: $18', 'Seniors and college students: $15', 'Youth 4–17: $8', '3 and under: free',
                  'Members: free', 'Museums for All: free regular admission with an EBT card',
                  'Library museum passes: discounted entry'],
                 '413-443-7171',
                 ['Reopened July 29, 2026 after a $12.1 million renovation: the aquarium is now on the first floor, '
                  'twice its old size',
                  'Now on view: Soulful Creatures: Animal Mummies in Ancient Egypt (Brooklyn Museum), Galleries '
                  '206–208, through January 17, 2027',
                  'Enter from South Street (Route 7), past Wally the Stegosaurus on the front lawn; lockers and coat '
                  'racks in the lobby',
                  'Art, natural history and history under one roof: good for families; a small café and the Museum '
                  'Shop are by the entrance',
                  'Accessible: elevator to the second floor, accessible ticket counter, wheelchairs to borrow']),
    'Q5506454': ('102 Prospect Hill Road, Harvard, MA 01451',
                 ['Museum buildings, Store and Café: Thu–Sun 10 am–4 pm, late April to early November',
                  '2026 season was Apr 30 – Nov 1: the buildings are closed for the winter and reopen in spring 2027',
                  'Buildings close 12–12:30 pm for lunch',
                  'Open holiday Mondays (Memorial Day, Labor Day, Indigenous Peoples’ Day)',
                  'Grounds and trails: every day, sunrise to sunset (until 4 pm Fri–Sun)',
                  'Holiday Artisan Market: Dec 5–6, 2026, 11 am–4 pm'],
                 ['Adults: $18', 'Students and seniors: $15', 'Children: $9', 'Trustees members: free',
                  'Grounds and trails: free'], '978-456-3924',
                 ['The buildings stand on a steep hill: accessible parking at the upper lot (Museum Store) and the '
                  'lower lot (Wayside and galleries)',
                  'Accessible restrooms at Prospect House (Admissions, Café, Store) and at the Wayside Visitor Center',
                  'The galleries, Café and Store are wheelchair-accessible; the Shaker Gallery and the Farmhouse are not',
                  'Fruitlands Café (Fireside Catering, 978-456-3703) is open Thu–Sun in season',
                  'About 3 miles of trails: a trail map is on the board in the parking area. Dogs on leash',
                  'From Route 2, exit 109A: Route 110 south, first right onto Old Shirley Road, about 2 miles']),
    'Q5738956': ('67 Grove Street, Sandwich, MA 02563',
                 ['Main season: every day 10 am–5 pm (last entry 4:30 pm), late April to mid-October',
                  '2026 season was April 25 – October 18: the galleries are closed until the 2027 season',
                  'Gardens Aglow (holiday lights): 4:30–8:30 pm on 25 evenings, Nov 27 – Dec 27, 2026 '
                  '(closed Mondays except Dec 21, and Dec 1, 24 and 25); timed tickets, entry until 8 pm'],
                 ['Adults: $26', 'Youth 3–17: $16', 'Children 2 and under: free', 'Members: free',
                  'Gardens Aglow (advance, timed): adults $30, youth $20; day-of tickets double',
                  'The Adventure Park is separate (10% off within 7 days with a Heritage receipt)'],
                 '508-888-3300',
                 ['Free shuttle for visitors with mobility challenges: seven stops (benches with the access symbol), '
                  'about every 20 minutes',
                  'Family restrooms in the Welcome Center, the Automobile Gallery, the American Art & Carousel Gallery '
                  'and Lilly’s Café; portable restrooms by Hidden Hollow',
                  'Unlimited rides on the 1908 Looff Carousel are included with admission',
                  'Lilly’s Café serves food, beer and wine; picnics are welcome on the grounds',
                  'Walking from the Welcome Center: Automobile Gallery 4 min, Special Exhibitions Gallery 10 min, '
                  'American Art & Carousel Gallery 15 min',
                  'No pets (service animals welcome); open rain or shine; buy tickets online for quick entry']),
    'Q6783079': ('110 Pequot Trail, Mashantucket, CT 06338',
                 ['Wednesday–Saturday 9 am–5 pm (last admission 4 pm), March–October',
                  'November: Tuesday–Saturday 9 am–5 pm (last admission 4 pm)',
                  'December–February: not on the museum’s hours page; call before you go'],
                 ['Adults (18–64): $25', 'Seniors (65+): $20', 'College students and educators (with ID): $20',
                  'Youth (6–17): $16', 'Children under 5: free', 'Members: free',
                  'Groups of 10 or more: adults $18; add a guided tour for $10 a person',
                  'Foxwoods Rewards points are accepted for admission'],
                 '800-411-9671',
                 ['Start in the Gathering Space (entry level, Level 3) and take the ramp or elevator down: the '
                  'exhibits run as a timeline, from the Ice Age on Level 1 back up to the present on Level 2',
                  'The Witness, a half-hour film on the 1637 Pequot War (ages 12 and older), shows at 11 am, 1 pm and '
                  '3 pm',
                  'Pick up the audio guide at the Three Sisters diorama, before the Pequot Village (Level 1)',
                  'The café is temporarily closed; the Gift Shop sells work by certified Native American artists',
                  'Accessible throughout: infrared wayfinding with audio description, closed captions and replica '
                  'artifacts to touch; elevators to every level and up the observation tower',
                  'Free parking in the large lot on the south side of Pequot Trail; accessible parking in front of the '
                  'museum']),
    'Q4978055': ('1 Museum Drive, Greenwich, CT 06830',
                 ['Tuesday–Sunday 10 am–5 pm (last admission 4:30 pm)',
                  'Closed Mondays and major holidays'],
                 ['Tuesdays: free for everyone', 'Adults: $20 (Wednesday–Sunday)', 'Seniors (65+): $15',
                  'Students: $15', 'Children under 5: free', 'Members: free',
                  'Museums for All: up to four people free with one EBT card',
                  'Bank of America cardholders: free on the first full weekend of each month',
                  'The ground floor (lobby, café, store) is free to enter during museum hours'],
                 '203-869-0376',
                 ['The entrance faces Bruce Park: the lobby, café, Museum Store and lecture hall are on the ground '
                  'floor, and all the galleries are one level up, by the main stairs or the elevator',
                  'Art in the Richter Art Wing (east and south), science in the old house (west): the Sculpture '
                  'Gallery joins them',
                  'Free digital guide: The Bruce on the Bloomberg Connects app',
                  'No advance tickets needed; groups of 10 or more book ahead',
                  'Accessible: elevator to the galleries, accessible restrooms, wheelchairs at the front desk']),
    'Q6716306': ('314 Main Street, Gambrill Center (MIT Building E28), Cambridge, MA 02142',
                 ['Daily 10 am–5 pm (last entry 4:30 pm)',
                  'After Dark (ages 18+): second Thursday of each month, 6–9 pm',
                  'Closed Thanksgiving, Christmas Eve, Christmas Day, New Year’s Day and July 4; closes 3 pm on '
                  'New Year’s Eve',
                  'Museum Store: daily 10 am–6 pm'],
                 ['Adults: $20', 'Seniors (65+): $15', 'College students with ID: $10', 'Youth (6–18): $10',
                  'Children 5 and under: free', 'Family (2 adults + 2 youth): $55',
                  'MIT students, faculty, staff and alumni: free with ID, plus one guest',
                  'Cambridge residents: free with the free Cambridge Resident Membership',
                  'The lobby and Museum Store are free to enter'],
                 '617-253-5927',
                 ['Next to the Kendall/MIT Red Line station: the museum entrance is on the plaza by the station',
                  'Galleries on the Second and Third Floors, by the grand stair or the elevator; restrooms and water '
                  'fountains on every floor',
                  'Maker Hub drop-in activities every day, free with admission',
                  'No café inside: food and coffee all around Kendall Square',
                  'Accessible: elevator to every floor; sensory maps (noise, light, crowds) on the museum’s website',
                  'Also free nearby: the Hart Nautical Gallery (ship models) at 55 Massachusetts Avenue, Mon–Fri '
                  '10 am–4:30 pm']),
    'Q7868542': ('Building 22, Charlestown Navy Yard, Boston, MA 02129 (no street address: for GPS use the Nautica '
                 'Parking Garage, 88 Constitution Road, Boston, MA 02129)',
                 ['Museum: open daily 10 am–5 pm',
                  'Museum: closed Thanksgiving, Christmas Day and New Year’s Day; closes 2 pm on December 24',
                  'Ship (USS Constitution): Wednesday–Sunday 10 am–4 pm',
                  'Ship: closed Martin Luther King Jr. Day, Thanksgiving, Christmas Day and New Year’s Day'],
                 ['Museum (suggested admission): Pay it Forward $25 · Standard $15 · Reduced free–$10',
                  'Ship: free, first come, first served',
                  'Ship: Navy security screening; photo ID (driver’s license or passport) for everyone 18 and over'],
                 '617-426-1812',
                 ['The museum (a non-profit) and the ship (an active-duty U.S. Navy ship) are run separately, next to '
                  'each other: the museum is at the head of Dry Dock 1, the ship at Pier 1',
                  'Check in at the museum’s admission desk; no food or drink in the exhibits',
                  'Museum: two floors, all accessible by elevator; restrooms on the first floor',
                  'Ship: sailors lead tours of the top (spar), gun and berth decks; steep ladder-like steps below; '
                  'wheelchairs only on the top deck and only at a favorable tide; no strollers on board',
                  'Parking: Nautica Parking Garage (the museum validates); or the F4 ferry from Long Wharf to Pier 4',
                  'Next door: the National Park Service Visitor Center (restrooms) and USS Cassin Young']),
    'Q5158830': ('53 Cambridge Turnpike, Concord, MA 01742',
                 ['Tuesday–Sunday 10 am–4 pm (fall hours); closed most Mondays',
                  'Open on Monday holidays: MLK Day, Presidents’ Day, Patriots’ Day, Memorial Day, Juneteenth, '
                  'July 4, Labor Day, Indigenous Peoples’ Day, New Year’s Eve and New Year’s Day; also Mondays in '
                  'December',
                  'Closed Easter Sunday, Thanksgiving, Christmas Eve and Christmas Day'],
                 ['Adults: $16', 'Seniors and students: $13', 'Youth (6–17): $10', 'Children 5 and under: free',
                  'Members: free',
                  'During Family Trees (Nov 21, 2026 – Jan 3, 2027): adults $20, seniors and students $15, youth '
                  '$10, children 3–5 $5, 2 and under free',
                  'Active military and family: free; EBT/WIC/ConnectorCare: $2 (up to 4 people)',
                  'Library passes: $5 off each ticket; Patriot Pass with the Concord Visitor Center: $2 off',
                  'Tickets at the front desk any time, no reservation needed; same-day re-entry'],
                 '978-369-9763',
                 ['Free parking in the museum’s lot (enter from Cambridge Turnpike) and on the street',
                  'Train: Fitchburg Line commuter rail to Concord station, then a 1-mile walk',
                  'Restrooms (with changing table), elevator, coat rack, lockers and water fountain on the first '
                  'floor; ramps and the elevator reach every gallery',
                  'No café: picnics are welcome on the grounds, and Concord center is a short walk away',
                  'Free audio guide on the Bloomberg Connects app (bring earbuds)',
                  'Plan 1–2 hours for the sixteen galleries and the special exhibition',
                  'Across the road from the Ralph Waldo Emerson House']),
    'Q2019741': ('51 Sandy Pond Road, Lincoln, MA 01773',
                 ['Sculpture park and store: Tue–Fri 10 am–4 pm, Sat–Sun 10 am–5 pm',
                  'Twisted Tree Café: Tue–Fri 10 am–3 pm, Sat–Sun 10 am–4 pm',
                  'Mon: closed (open holiday Mondays, 10 am–4 pm)', 'Indoor galleries closed for renovation'],
                 ['Adults: $14', 'Seniors and students: $12', '12 and under: free',
                  'Trustees members and Lincoln residents: free', 'EBT, WIC and MassHealth cardholders: free'],
                 '781-259-8355', 'The museum’s indoor galleries are closed for renovation; the 30-acre sculpture park, '
                                 'the Twisted Tree Café and the store are open. Restrooms by the café (accessible) and '
                                 'in the museum (3rd floor, elevator). Dogs on leash are welcome in the park.'),
    'Q4796749': ('189 Alden Street, Duxbury, MA 02332',
                 ['Wed–Sun: 12–5 pm', 'Thu: 12–8 pm', 'Mon–Tue: closed'], FREE, '781-934-6634', None),
    'Q5386237': ('125 West Bay Road, Amherst, MA 01002',
                 ['Wed–Fri: 10 am–4 pm', 'Sat: 10 am–5 pm', 'Sun: 12–5 pm', 'Mon–Tue: closed',
                  'First Thursdays Oct–Jun: also 4–7 pm (Carle After Dark)'],
                 ['Adults: $15', 'Youth 1–18, students, teachers, seniors 65+: $10', 'Members: free',
                  'First Thursdays Oct–Jun, 4–7 pm: pay as you wish'], '413-559-6300',
                 ['Everything is on one level, wheelchair-accessible; power-assist doors at the entrance',
                  'Free parking, 4 accessible spaces; PVTA bus stop "Eric Carle Museum" on West Bay Road',
                  'No restaurant: the Carle Café has a vending machine and you may bring food; picnic in Bobbie’s Meadow',
                  'Art Studio, Reading Library and Bookshop open the same hours as the museum',
                  'Closed Memorial Day, Juneteenth, July 4, Labor Day, Thanksgiving, Dec 24–25, Jan 1']),
    'Q74035008': ('611 Massachusetts Avenue, Arlington, MA 02474',
                  ['Sat–Sun: 12–4 pm', 'Other days by appointment'], FREE, '781-641-0747', None),
    'Q15694044': ('106 Central Street, Wellesley, MA 02481',
                  ['Tue–Sun: 11 am–5 pm', 'Mon and holidays: closed'], FREE, '781-283-2051', None),
    'Q7018775': ('76 Bellevue Avenue, Newport, RI 02840',
                 ['Wed–Mon: 11 am–4 pm', 'Tue: closed',
                  'Closed New Year’s Eve and Day, Easter Sunday, Thanksgiving, Christmas Eve and Christmas Day'],
                 ['Adults: $20', 'Seniors 65+: $15', 'College students: $10', '17 and under: free',
                  'Active military and spouse: free', 'Members: free'], '401-848-8200',
                 'Two gallery buildings on a lawn at Bellevue Avenue and Old Beach Road: the Griswold House (1864, '
                 'Richard Morris Hunt) and the Cushing Memorial Gallery. Free parking off Downing Street and off Old '
                 'Beach Road; the south lot off Downing Street is the step-free way into all three buildings. The '
                 'Museum School (Coleman Center) is at 26 Liberty Street. No café.'),
    'Q7152453': ('Choate Rosemary Hall, 333 Christian Street, Wallingford, CT 06492',
                 ['Gallery open during the school year: call for hours'], FREE, '203-697-2423', None),
    'Q5017445': ('4676 Falmouth Road (Route 28), Cotuit, MA 02635',
                 ['Mar 18–Dec 20: Wed–Sun 10 am–4 pm', 'Mon–Tue and winter: closed'],
                 ['Adults: $12', 'Seniors and students: $10', 'Under 12: free'], '508-428-7581', None),
    'Q6802407': ('2101 Commonwealth Avenue, Boston, MA 02135',
                 ['Mon–Fri: 10 am–5 pm', 'Sat–Sun: 12–5 pm'], FREE, '617-552-8587', ['Boston College, Brighton Campus']),
    'Q6941007': ('203 Union Street, Clinton, MA 01510',
                 ['Thu–Sun: 10 am–4 pm', 'Mon–Wed: closed'],
                 ['Adults: $15', 'Seniors 65+: $12', 'Students and under 18: free', 'First Sunday of the month: free'],
                 '978-598-5000', None),
    'Q7894833': ('Fine Arts Center, 151 Presidents Drive, Amherst, MA 01003',
                 ['Tue–Fri: 11 am–4:30 pm', 'Sat–Sun: 12–4 pm', 'First Thursday: until 8 pm',
                  'Mon, holidays and university breaks: closed'], FREE, '413-545-3670', None),
    'Q5913507': ('900 Lafayette Boulevard, Bridgeport, CT 06604',
                 ['Mon–Fri: 8:30 am–5:30 pm', 'Thu: until 7 pm', 'Weekends and state holidays: closed'],
                 FREE, '203-332-5052', ['At CT State Housatonic; usually closed most of August']),
    'Q16954084': ('14 Vernon Street, Framingham, MA 01701',
                  ['Wed–Sun: 12–5 pm', 'Thu: until 8:30 pm', 'Mon–Tue: closed'],
                  ['Adults: $11', 'Seniors: $9', 'Students: $8', 'Under 17: free'], '508-215-5110', None),
    'Q24534715': ('1 Royce Circle, Storrs, CT 06268',
                  ['Wed, Fri, Sun: 11 am–5 pm', 'Thu, Sat: 11 am–7 pm', 'Mon–Tue: closed'],
                  ['Suggested donation: $5'], '860-486-8580', None),
    'Q14715429': ('60 Hope Lane, Dennis, MA 02638',
                  ['Tue–Sat: 10 am–4 pm', 'Sun: 12–4 pm', 'Mon: closed', 'From Dec 1: Thu–Sat 10 am–4 pm, Sun 12–4 pm'],
                  ['Adults: $10', 'Seniors 62+: $8', 'Ages 13–18 and students: $7', '12 and under: free'], '508-385-4477', None),
    'Q18965051': ('963 Washington Street, Canton, MA 02021',
                  ['Tue–Sun: 1–5 pm', 'Mon: closed'], ['See Mass Audubon for current fees'], '781-821-8853', None),
    'Q4948083': ('486 Harrison Avenue, Boston, MA 02118',
                 ['Wed–Sun: 11 am–5 pm', 'First Friday: 5–8:30 pm', 'Mon–Tue: closed'], FREE, '617-482-7781', None),
    'Q4801555': ('50 Orange Street, New Haven, CT 06510',
                 ['Wed–Sat: 12–6 pm', 'Sun–Tue: closed'], FREE, '203-772-2709', None),
    'Q140842682': ('New Salem, MA 01355',
                   ['Wed–Sun: 10 am–5 pm', 'Mon–Tue: closed'], ['Adults: $16', 'Reduced: $12'], None, None),
    'Q18325686': ('1678 Asylum Avenue, West Hartford, CT 06117',
                  ['Open during the university’s academic year: call for hours'], FREE, '860-231-5399', None),
    'Q123689395': ('1801 Massachusetts Avenue, Cambridge, MA 02140',
                   ['Tue–Fri: 9 am–6 pm', 'Thu: until 8 pm', 'Mon: closed'], FREE, None, ['Lesley University, Porter Square']),
    'Q138002039': ('44 Troy Street, Fall River, MA 02720', None, None, None, None),
    'Q15694003': ('27 Pleasant Street, Gloucester, MA 01930',
                  ['Tue–Sun: 10 am–5 pm (last entry 4:30 pm)', 'Mon: closed',
                   'Also closed MLK Day, Presidents’ Day, Memorial Day, July 4, Labor Day, Indigenous Peoples’ Day, '
                   'Thanksgiving, Christmas Eve and Day, New Year’s Eve and Day'],
                  ['Adults: $20', 'Seniors 65+: $15', 'Cape Ann residents: $15 (free on the second Saturday of the month)',
                   'Students with ID and youth 18 and under: free', 'Members: free'],
                  '978-283-0455',
                  ['No café: food and drink aren’t allowed in the galleries; coffee shops and restaurants nearby',
                   'No museum parking: metered city lot across the street (2-hour limit), longer parking on Rogers '
                   'Street and St. Peter’s Square',
                   'Train: MBTA Newburyport/Rockport line to Gloucester, then a 10–15 minute walk',
                   'CAM Green campus (13 Poplar Street, free) is closed for the season until spring 2027']),
}

# Museums the Wikidata rebuild leaves out (their Wikidata type isn't one tools/build_open_data.py asks for);
# added to museums.json if missing, so their pages exist
EXTRA = {
    'Q14715853': {'id': 'Q14715853', 'name': 'Smith College Museum of Art', 'at': [42.318502, -72.636378], 'links': 7,
                  'image': '020 Elm St Smith College Museum.jpg', 'website': 'https://scma.smith.edu/',
                  'city': 'Northampton', 'state': 'Massachusetts', 'wikipedia': 'Smith_College_Museum_of_Art'},
    'Q5460633': {'id': 'Q5460633', 'name': 'Florence Griswold Museum', 'at': [41.325556, -72.3275], 'links': 7,
                 'image': 'Florence Griswold House, Old Lyme, CT.jpg', 'website': 'https://flogris.org/',
                 'city': 'Old Lyme', 'state': 'Connecticut', 'wikipedia': 'Florence_Griswold_Museum'},
    'Q1890082': {'id': 'Q1890082', 'name': 'Mystic Seaport Museum', 'at': [41.3625, -71.965278], 'links': 7,
                 'image': 'Big boat.jpg', 'website': 'https://mysticseaport.org/', 'city': 'Mystic',
                 'state': 'Connecticut', 'wikipedia': 'Mystic_Seaport'},
    'Q1786400': {'id': 'Q1786400', 'name': 'The Breakers', 'at': [41.469722, -71.298611], 'links': 30,
                 'image': 'The Breakers Newport.jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/the-breakers/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'The_Breakers'},
    'Q2650982': {'id': 'Q2650982', 'name': 'Marble House', 'at': [41.461956, -71.305617], 'links': 20,
                 'image': 'Marble House, Newport RI.jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/marble-house/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'Marble_House'},
    'Q2007919': {'id': 'Q2007919', 'name': 'John F. Kennedy Presidential Library and Museum',
                 'at': [42.316111, -71.033889], 'links': 24, 'image': 'JFK library Stitch Crop.jpg',
                 'website': 'https://www.jfklibrary.org/', 'city': 'Boston', 'state': 'Massachusetts',
                 'wikipedia': 'John_F._Kennedy_Presidential_Library_and_Museum'},
    'Q7752461': {'id': 'Q7752461', 'name': 'The Mount, Edith Wharton’s Home', 'at': [42.33098, -73.28204],
                 'links': 15, 'image': 'The Mount from the Walled Garden by David Dashiell.jpg',
                 'website': 'https://edithwharton.org/', 'city': 'Lenox', 'state': 'Massachusetts',
                 'wikipedia': 'The_Mount_(Lenox,_Massachusetts)'},
    'Q5093884': {'id': 'Q5093884', 'name': 'Chesterwood', 'at': [42.28489, -73.35222], 'links': 10,
                 'image': 'Chesterwood (Stockbridge, MA) - house.JPG', 'website': 'https://www.chesterwood.org/',
                 'city': 'Stockbridge', 'state': 'Massachusetts', 'wikipedia': 'Chesterwood_(Massachusetts)'},
    'Q5647064': {'id': 'Q5647064', 'name': 'Hancock Shaker Village', 'at': [42.43045, -73.33905], 'links': 20,
                 'image': 'Gardens with Round Stone Barn and Dairy Ell, Hancock Shaker Village.jpg',
                 'website': 'https://hancockshakervillage.org/', 'city': 'Pittsfield', 'state': 'Massachusetts',
                 'wikipedia': 'Hancock_Shaker_Village'},
    'Q7085141': {'id': 'Q7085141', 'name': 'Old Sturbridge Village', 'at': [42.1089, -72.0987], 'links': 30,
                 'image': 'View of the Center Village Old Sturbridge Village.jpg', 'website': 'https://www.osv.org/',
                 'city': 'Sturbridge', 'state': 'Massachusetts', 'wikipedia': 'Old_Sturbridge_Village'},
    'Q4165331': {'id': 'Q4165331', 'name': 'Mark Twain House & Museum', 'at': [41.767083, -72.701389], 'links': 30,
                 'image': 'House of Mark Twain.jpg', 'website': 'https://marktwainhouse.org/', 'city': 'Hartford',
                 'state': 'Connecticut', 'wikipedia': 'Mark_Twain_House'},
    'Q52454': {'id': 'Q52454', 'name': 'International Tennis Hall of Fame', 'at': [41.4828, -71.3082], 'links': 36,
               'image': 'International Tennis Hall of Fame, Newport RI.jpg', 'website': 'https://www.tennisfame.com/',
               'city': 'Newport', 'state': 'Rhode Island', 'wikipedia': 'International_Tennis_Hall_of_Fame'},
    'Q4820080': {'id': 'Q4820080', 'name': 'Audrain Automobile Museum', 'at': [41.48203, -71.30825], 'links': 8,
                 'image': 'Audrain Automobile Museum (51488123683).jpg', 'website': 'https://www.audrainautomuseum.org/',
                 'city': 'Newport', 'state': 'Rhode Island', 'wikipedia': 'Audrain_Building'},
    'Q7370843': {'id': 'Q7370843', 'name': 'Rough Point', 'at': [41.455222, -71.305444], 'links': 8,
                 'image': 'Rough Point, Newport RI.jpg', 'website': 'https://www.newportrestoration.org/plan-a-visit/',
                 'city': 'Newport', 'state': 'Rhode Island', 'wikipedia': 'Rough_Point'},
    'Q5087517': {'id': 'Q5087517', 'name': 'Chateau-sur-Mer', 'at': [41.47125, -71.30528], 'links': 8,
                 'image': 'Chateau-sur-Mer.jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/chateau-sur-mer/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'Chateau-sur-Mer'},
    'Q5664050': {'id': 'Q5664050', 'name': 'Harriet Beecher Stowe Center', 'at': [41.766983, -72.700781], 'links': 20,
                 'image': 'Stowe Center for Literary Activism (55618577734).jpg', 'website': 'https://stowecenter.org/',
                 'city': 'Hartford', 'state': 'Connecticut',
                 'wikipedia': 'Harriet_Beecher_Stowe_House_(Hartford,_Connecticut)'},
    'Q2166814': {'id': 'Q2166814', 'name': 'Rosecliff', 'at': [41.465, -71.30454], 'links': 10,
                 'image': 'Rosecliff (1308020662).jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/rosecliff/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'Rosecliff'},
    'Q7731834': {'id': 'Q7731834', 'name': 'The Elms', 'at': [41.4778, -71.309], 'links': 5,
                 'image': 'The Elms, Newport, Rhode Island - View from Great Lawn edit1.jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/the-elms/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'The_Elms_(Newport,_Rhode_Island)'},
    'Q7758868': {'id': 'Q7758868', 'name': 'Springfield Museums', 'at': [42.10361, -72.58528], 'links': 30,
                 'image': 'Exterior - Museum of Fine Arts, Springfield, MA - DSC03877.JPG',
                 'website': 'https://springfieldmuseums.org/', 'city': 'Springfield', 'state': 'Massachusetts',
                 'wikipedia': 'Springfield_Museums'},
    'Q122945': {'id': 'Q122945', 'name': 'Yale Peabody Museum', 'at': [41.315753, -72.921175], 'links': 30,
                'image': 'Yale Peabody Museum 2.JPG', 'website': 'https://peabody.yale.edu/', 'city': 'New Haven',
                'state': 'Connecticut', 'wikipedia': 'Peabody_Museum_of_Natural_History'},
    'Q1839461': {'id': 'Q1839461', 'name': 'Plimoth Patuxet Museums', 'at': [41.93906, -70.62602], 'links': 9,
                 'image': 'Indiaans huis Plimoth Plantation.JPG', 'website': 'https://plimoth.org/', 'city': 'Plymouth',
                 'state': 'Massachusetts', 'wikipedia': 'Plimoth_Patuxet'},
    'Q2001855': {'id': 'Q2001855', 'name': 'Harvard Museum of Natural History', 'at': [42.37845, -71.11555],
                 'links': 30, 'image': 'Harvard Museum of Natural History 2.JPG',
                 'website': 'https://hmnh.harvard.edu/', 'city': 'Cambridge', 'state': 'Massachusetts',
                 'wikipedia': 'Harvard_Museum_of_Natural_History'},
    'Q7005471': {'id': 'Q7005471', 'name': 'New Bedford Whaling Museum', 'at': [41.6353, -70.9232], 'links': 20,
                 'image': 'Nbwmentrance.jpg', 'website': 'https://www.whalingmuseum.org/', 'city': 'New Bedford',
                 'state': 'Massachusetts', 'wikipedia': 'New_Bedford_Whaling_Museum'},
    'Q1139748': {'id': 'Q1139748', 'name': 'Museum of Science', 'at': [42.3675, -71.0711], 'links': 40,
                 'image': 'Museumofsciencebostonaugust2005.jpg', 'website': 'https://www.mos.org/', 'city': 'Boston',
                 'state': 'Massachusetts', 'wikipedia': 'Museum_of_Science_(Boston)'},
    'Q5506454': {'id': 'Q5506454', 'name': 'Fruitlands Museum', 'at': [42.50844, -71.60989], 'links': 2,
                 'image': 'Fruitlands Museum - exterior Bronson Alcott farmhouse.jpg',
                 'website': 'https://thetrustees.org/place/fruitlands-museum/', 'city': 'Harvard',
                 'state': 'Massachusetts', 'wikipedia': 'Fruitlands_Museum'},
    'Q5738956': {'id': 'Q5738956', 'name': 'Heritage Museums & Gardens', 'at': [41.74771, -70.50555], 'links': 8,
                 'image': 'Heritage Museum and Gardens (3789207677).jpg',
                 'website': 'https://heritagemuseumsandgardens.org/', 'city': 'Sandwich',
                 'state': 'Massachusetts', 'wikipedia': 'Heritage_Museums_and_Gardens'},
    'Q6783079': {'id': 'Q6783079', 'name': 'Mashantucket Pequot Museum & Research Center',
                 'at': [41.4661, -71.9628], 'links': 3, 'image': 'Mashantucket Pequot Museum Exterior.jpg',
                 'website': 'https://www.pequotmuseum.org/', 'city': 'Mashantucket', 'state': 'Connecticut',
                 'wikipedia': 'Mashantucket_Pequot_Museum_and_Research_Center'},
    'Q6716306': {'id': 'Q6716306', 'name': 'MIT Museum', 'at': [42.3621, -71.0867], 'links': 20,
                 'image': '(USA-Massachusetts) MIT Museum Entrance 2024-06-11.jpg', 'website': 'https://mitmuseum.mit.edu/',
                 'city': 'Cambridge', 'state': 'Massachusetts', 'wikipedia': 'MIT_Museum'},
    'Q7868542': {'id': 'Q7868542', 'name': 'USS Constitution Museum', 'at': [42.3739, -71.0556], 'links': 4,
                 'image': 'USS Constitution Museum.jpg', 'website': 'https://ussconstitutionmuseum.org/',
                 'city': 'Boston', 'state': 'Massachusetts', 'wikipedia': 'USS_Constitution_Museum'},
    'Q5158830': {'id': 'Q5158830', 'name': 'Concord Museum', 'at': [42.4577, -71.3421], 'links': 3,
                 'image': 'Concord Museum Exterior.jpg', 'website': 'https://concordmuseum.org/',
                 'city': 'Concord', 'state': 'Massachusetts', 'wikipedia': 'Concord_Museum'},
    'Q4978055': {'id': 'Q4978055', 'name': 'Bruce Museum', 'at': [41.019, -73.6235], 'links': 3,
                 'image': 'Bruce Museum Exterior Tim Hursley.jpg', 'website': 'https://brucemuseum.org/',
                 'city': 'Greenwich', 'state': 'Connecticut', 'wikipedia': 'Bruce_Museum'},
    'Q4681251': {'id': 'Q4681251', 'name': 'Addison Gallery of American Art', 'at': [42.6486, -71.1333], 'links': 6,
                 'image': 'Phillips Academy, Andover, MA - Addison Gallery of American Art.JPG',
                 'website': 'https://addison.andover.edu/', 'city': 'Andover', 'state': 'Massachusetts',
                 'wikipedia': 'Addison_Gallery_of_American_Art'},
    'Q15694003': {'id': 'Q15694003', 'name': 'Cape Ann Museum', 'at': [42.6143, -70.6624], 'links': 4,
                  'image': '2011 CapeAnnMuseum GloucesterMA.jpg', 'website': 'https://www.capeannmuseum.org/',
                  'city': 'Gloucester', 'state': 'Massachusetts', 'wikipedia': 'Cape_Ann_Museum'},
}

# Museums whose Wikidata point is off (the Lyman Allyn's is 350 m west of the building; this is OpenStreetMap's)
AT = {'Q14714982': [41.37374, -72.1029]}

# Museums whose Wikidata name is out of date (deCordova reversed its name in 2009)
NAMES = {'Q2019741': 'deCordova Sculpture Park and Museum'}

# Commons photos for museums that Wikidata has no picture for (others show a map of where they are)
PHOTOS = {
    'Q123689395': 'Lunder Arts Center, Lesley University 1803 Mass Ave Cambridge.jpg',
    'Q5913507': 'HousatonicCommunityCollegeLafayetteHallAtriumLowerLevel.jpg',
}


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'museums.json')
    doc = json.load(open(path, encoding='utf-8'))
    have = {m['id'] for m in doc['museums']}
    for e in EXTRA.values():
        if e['id'] not in have:
            i = next((i for i, m in enumerate(doc['museums']) if m.get('links', 0) < e['links']), len(doc['museums']))
            doc['museums'].insert(i, dict(e))
    seen = set()
    for m in doc['museums']:
        v = VISIT.get(m['id'])
        if not v:
            continue
        seen.add(m['id'])
        if m['id'] in NAMES: m['name'] = NAMES[m['id']]
        if m['id'] in AT: m['at'] = AT[m['id']]
        address, hours, admission, phone, notes = v
        m.update(address=address, infoChecked=CHECKED)
        # Wikidata sometimes gives the state as the city ("Massachusetts, Massachusetts")
        town = re.search(r',\s*([^,]+),\s*[A-Z]{2}\s+\d{5}$', address)
        if town and m.get('city') in (None, m.get('state')):
            m['city'] = town.group(1)
        if not m.get('image') and m['id'] in PHOTOS:
            m['image'] = PHOTOS[m['id']]
        if hours: m['hours'] = hours
        if admission: m['admission'] = admission
        if phone: m['phone'] = phone
        if notes: m['visitNotes'] = notes
    missing = set(VISIT) - seen
    if missing:
        raise SystemExit(f'not in museums.json: {sorted(missing)}')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f'visit info for {len(seen)} museums')


if __name__ == '__main__':
    main()
