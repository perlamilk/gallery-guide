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
                ['First-floor galleries: $11 (ages 14+)', 'Ages 13 and under: $5', 'Students, educators, military: $8',
                 'Day membership, all floors: $40'], '617-227-0270', None),
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
                 ['Sun, Mon, Wed–Fri: 12–5 pm', 'Sat: 10 am–5 pm', 'Tue: closed', 'Last entry 4:40 pm'],
                 ['Adults: $20', 'Seniors 60+: $15', 'Students: $9', 'Third weekend of the month: free'], '203-438-4519', None),
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
                 ['Wed–Fri: 12–4 pm', 'Sat–Sun: 11 am–5 pm', 'First Thursday: 12–7 pm', 'Mon–Tue: closed'],
                 FREE, '978-345-4207', None),
    'Q14714982': ('625 Williams Street, New London, CT 06320',
                  ['Tue–Sat: 10 am–5 pm', 'Sun: 1–5 pm', 'Mon: closed', 'Last entry 4 pm'],
                  ['Adults: $12', 'Seniors 60+: $9', 'Active military: $7', 'Youth 12 and under: free',
                   'First Saturday of the month: free'], '860-443-2545', None),
    'Q7367636': ('415 South Street, Waltham, MA 02453',
                 ['Wed–Sun: 11 am–5 pm', 'Mon–Tue: closed'], ['Free (register for a free ticket)'], '781-736-3434', None),
    'Q5508243': ('455 Oak Street, Brockton, MA 02301',
                 ['Tue–Sun: 10 am–5 pm', 'Mon: closed'], ['By donation'], '508-588-6000', None),
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
    'Q41512158': ('21 Edwards Street, Springfield, MA 01103',
                  ['Tue–Sat: 10 am–5 pm', 'Sun: 11 am–5 pm', 'Mon: closed'],
                  ['Adults: $27.50 (one ticket, five museums)', 'Seniors 60+ and college students: $18', 'Youth 5–17: $15',
                   'Under 5: free', 'Springfield residents: free'], '413-263-6800', ['Part of the Springfield Museums']),
    'Q105553919': ('21 Edwards Street, Springfield, MA 01103',
                   ['Closed for restoration'],
                   ['Springfield Museums ticket: adults $27.50', 'Seniors 60+ and college students: $18', 'Youth 5–17: $15'],
                   '413-263-6800', ['Part of the Springfield Museums']),
    'Q4892280': ('39 South Street, Pittsfield, MA 01201',
                 ['Fri–Wed: 10 am–5 pm', 'Thu: closed'],
                 ['Adults: $18', 'Seniors and college students: $15', 'Youth 4–17: $8', '3 and under: free'], '413-443-7171', None),
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
                 ['Wed–Fri: 10 am–4 pm', 'Sat: 10 am–5 pm', 'Sun: 12–5 pm', 'Mon–Tue: closed'],
                 ['Adults: $15', 'Members: free'], '413-559-6300', None),
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
    'Q2166814': {'id': 'Q2166814', 'name': 'Rosecliff', 'at': [41.465, -71.30454], 'links': 10,
                 'image': 'Rosecliff (1308020662).jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/rosecliff/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'Rosecliff'},
    'Q7731834': {'id': 'Q7731834', 'name': 'The Elms', 'at': [41.4778, -71.309], 'links': 5,
                 'image': 'The Elms, Newport, Rhode Island - View from Great Lawn edit1.jpg',
                 'website': 'https://www.newportmansions.org/mansions-and-gardens/the-elms/', 'city': 'Newport',
                 'state': 'Rhode Island', 'wikipedia': 'The_Elms_(Newport,_Rhode_Island)'},
    'Q122945': {'id': 'Q122945', 'name': 'Yale Peabody Museum', 'at': [41.315753, -72.921175], 'links': 30,
                'image': 'Yale Peabody Museum 2.JPG', 'website': 'https://peabody.yale.edu/', 'city': 'New Haven',
                'state': 'Connecticut', 'wikipedia': 'Peabody_Museum_of_Natural_History'},
    'Q7005471': {'id': 'Q7005471', 'name': 'New Bedford Whaling Museum', 'at': [41.6353, -70.9232], 'links': 20,
                 'image': 'Nbwmentrance.jpg', 'website': 'https://www.whalingmuseum.org/', 'city': 'New Bedford',
                 'state': 'Massachusetts', 'wikipedia': 'New_Bedford_Whaling_Museum'},
    'Q1139748': {'id': 'Q1139748', 'name': 'Museum of Science', 'at': [42.3675, -71.0711], 'links': 40,
                 'image': 'Museumofsciencebostonaugust2005.jpg', 'website': 'https://www.mos.org/', 'city': 'Boston',
                 'state': 'Massachusetts', 'wikipedia': 'Museum_of_Science_(Boston)'},
    'Q4681251': {'id': 'Q4681251', 'name': 'Addison Gallery of American Art', 'at': [42.6486, -71.1333], 'links': 6,
                 'image': 'Phillips Academy, Andover, MA - Addison Gallery of American Art.JPG',
                 'website': 'https://addison.andover.edu/', 'city': 'Andover', 'state': 'Massachusetts',
                 'wikipedia': 'Addison_Gallery_of_American_Art'},
}

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
