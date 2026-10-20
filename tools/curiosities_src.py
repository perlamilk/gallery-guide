"""Source for data/curiosities.json (run: python3 tools/curiosities_src.py).

Three layers, most specific first (see js/data.js, class Curiosities):
  WORKS   facts about one work, keyed by MFA object id
  ARTISTS facts about an artist, keyed by the artist name exactly as harvested
  KINDS   facts about a kind of object; `match` is a set of case-insensitive regexes
          on artwork fields (title, culture, collection, type, medium...), all must match.
          The first matching kind wins, so specific kinds come before general ones.
Written from general art-history knowledge; keep each fact short and only write what is well established.
"""
import json
import os

SARGENT_MURALS = [
    "Part of Sargent's murals for the MFA's Rotunda and Colonnade, painted between 1916 and 1925: the last great project of his life.",
    "The panels were painted on canvas in his studio and then glued to the walls and ceiling, a technique called marouflage.",
    "Many of the male figures were modelled by Thomas McKeller, a Black elevator operator at a Boston hotel, a fact long overlooked until the MFA's 2020 exhibition about him.",
]

WORKS = {
    # Monet
    "33556": [
        "Camille Monet, the painter's wife and a brunette, wears a blond wig, playing up that she is a Parisienne dressing up as Japanese.",
        "The robe is a theatrical kimono (uchikake); its embroidered samurai seems ready to leap out of the fabric.",
        "Monet later dismissed the picture as a potboiler, but it sold for a high price at the 1876 Impressionist exhibition.",
    ],
    "34078": [
        "One of about 25 grainstack canvases Monet painted near his house at Giverny in 1890–91, following the stacks through seasons and times of day.",
        "When fifteen of them were shown together in Paris in 1891, the exhibition was a commercial triumph.",
    ],
    "32700": [
        "Monet painted more than 30 views of the cathedral front in 1892–93 from rooms he rented across the square, switching canvases as the light changed.",
        "He reworked the series for a long time back in his studio at Giverny, building the stone out of thick, crusty paint.",
    ],
    "32103": [
        "Monet painted more than 30 views of the cathedral front in 1892–93 from rooms he rented across the square, switching canvases as the light changed.",
        "This one catches the early morning, when the façade is still in shadow and the light comes from behind.",
    ],
    "31789": [
        "Monet had the pond at Giverny dug in 1893, over the objections of neighbours who feared his exotic water plants would poison their water.",
        "He painted the water lilies for nearly 30 years, about 250 canvases in all.",
    ],
    # Van Gogh
    "32542": [
        "Joseph Roulin worked for the post office at the Arles railway station, sorting mail. He and Van Gogh became close friends.",
        "Van Gogh painted every member of the Roulin family, five people in all, several times over.",
        "When Van Gogh was taken to hospital after cutting off part of his ear in December 1888, Roulin looked after him.",
    ],
    "33277": [
        "Augustine Roulin holds a rope that rocks a cradle we can't see; her baby Marcelle was born in 1888.",
        "Van Gogh imagined the picture hanging in a fishermen's cabin, comforting sailors far out at sea. He painted five versions.",
    ],
    "33278": [
        "Painted in Auvers-sur-Oise, where Van Gogh spent the last ten weeks of his life and made around 70 paintings.",
    ],
    "33491": [
        "Painted while Van Gogh lived in the asylum at Saint-Rémy-de-Provence, in a rocky gorge near the hospital.",
        "He painted it on a windy day; according to his letters, he had to weigh down his easel with stones.",
    ],
    "35481": [
        "This is the walled wheat field Van Gogh saw from his window at the asylum in Saint-Rémy. He painted it again and again through the seasons.",
    ],
    "33610": [
        "Painted in Nuenen in the Netherlands, before Van Gogh moved to Paris and his palette brightened.",
        "He made at least 28 paintings, drawings and watercolors of weavers at their looms in 1883–84.",
    ],
    # Gauguin
    "32558": [
        "Gauguin painted it in Tahiti and called it his testament; soon after finishing it he tried to take his own life, and survived.",
        "It reads from right to left: a baby at the start of life, adults in the middle, an old woman near death at the far left.",
        "He wrote the title himself in the upper left corner, as if on a worn fresco.",
    ],
    # Copley
    "30998": [
        "A true story: in 1749 the 14-year-old Brook Watson was attacked by a shark while swimming in Havana harbour and lost his right leg below the knee.",
        "Watson later became Lord Mayor of London and commissioned this painting of his own rescue.",
        "Copley painted three versions: in Washington's National Gallery, here in Boston, and a smaller one in Detroit.",
    ],
    "30881": [
        "Samuel Adams points to the Massachusetts charter, recalling how he faced down the governor after the Boston Massacre of 1770.",
        "The portrait was commissioned by John Hancock.",
    ],
    "30882": [
        "Hancock, Boston's richest merchant, is shown at his account book, ten years before he signed the Declaration of Independence in large letters.",
    ],
    # Gilbert Stuart
    "30879": [
        "Painted for Faneuil Hall. It recalls March 1776, when Washington fortified Dorchester Heights overnight and forced the British to leave Boston.",
    ],
    # Sully
    "31231": [
        "Commissioned for the North Carolina State House, the canvas turned out too big for its space, so it was sold and ended up in Boston.",
        "It shows Washington the night before his surprise attack on Trenton, December 1776.",
    ],
    # Sargent
    "31782": [
        "Sargent painted the four daughters of his friends Edward and Mary Boit in their Paris apartment in 1882.",
        "The square canvas and the girls scattered through the room, two of them half lost in shadow, puzzled critics at the time.",
        "The two huge Japanese vases in the picture came to the MFA too, and stand near the painting.",
    ],
    # Turner
    "31102": [
        "Turner was inspired by the Zong massacre of 1781, when a ship's crew threw more than 130 enslaved Africans overboard to claim insurance money.",
        "He showed it at the Royal Academy in 1840, the year of the first World Anti-Slavery Convention in London.",
        "The critic John Ruskin, its great champion, owned the painting for many years.",
    ],
    # Millet
    "31601": [
        "Shown at the Paris Salon of 1850–51, the striding peasant was read by some critics as a political statement about the rural poor.",
        "Van Gogh revered this picture and made many copies and variations of it.",
        "Its sower became the logo of the publisher Simon & Schuster.",
    ],
    # Manet
    "32372": [
        "Maximilian, the Austrian archduke installed as emperor of Mexico by Napoleon III, was shot by a firing squad in June 1867.",
        "Manet painted several versions; this loose, unfinished-looking canvas is the first. French censors kept the final version out of public view.",
    ],
    # Courbet
    "31731": [
        "The hunter leaning against the tree is Courbet himself.",
    ],
    # Rembrandt
    "32665": [
        "Rembrandt was about 22. The small painter stands far back from a huge easel, as if thinking before he paints.",
        "Many see the painter as Rembrandt himself, though his face is barely sketched in.",
    ],
    # Velázquez, El Greco
    "31124": [
        "Baltasar Carlos, heir to King Philip IV of Spain, was about two years old here. He died at 16 and never became king.",
    ],
    "31236": [
        "Paravicino was a celebrated preacher and poet; he wrote sonnets in praise of El Greco.",
    ],
    # Rogier van der Weyden
    "31035": [
        "Saint Luke was believed to have painted the Virgin's portrait, so he became the patron saint of painters.",
        "The painting was probably made for the painters' guild in Brussels, and Rogier may have given Saint Luke his own features.",
    ],
    # Homer
    "31042": [
        "A fisherman in his small dory sees a fog bank rolling in. He must row back to the schooner on the horizon before it vanishes.",
        "Homer painted it at Prouts Neck, Maine, where he lived by the sea from 1883.",
    ],
    # Degas
    "31229": ["Degas loved the racetrack, and later used Eadweard Muybridge's photographs of galloping horses to get their legs right."],
    "32250": ["Degas loved the racetrack, and later used Eadweard Muybridge's photographs of galloping horses to get their legs right."],
    # Ajanta
    "16133": [
        "From the Buddhist caves at Ajanta in western India, cut into a cliff and painted between the 2nd century B.C. and the 5th century A.D.",
    ],
}
for _id in ["31929", "31930", "31931", "31932", "31933", "31934", "31935", "31936", "32212", "32213", "32214",
            "32215", "32216", "32217", "32218", "32219", "32220", "32221", "32222", "32223", "32331", "32332", "32333"]:
    WORKS[_id] = SARGENT_MURALS

ARTISTS = {
        "Edouard Manet": {"name": "Manet", "facts": [
        "Manet's 'Luncheon on the Grass' and 'Olympia' caused scandals in the 1860s and paved the way for the Impressionists, though he never showed with them.",
    ]},
    "Paul Cézanne": {"name": "Cézanne", "facts": [
        "Picasso and Matisse both called Cézanne 'the father of us all'.",
        "He painted his wife Hortense Fiquet some 29 times.",
    ]},
    "John Singer Sargent": {"name": "Sargent", "facts": [
        "Born in Florence in 1856 to American parents, Sargent grew up travelling around Europe and first visited the United States at 20.",
        "The scandal over his portrait 'Madame X' at the 1884 Paris Salon pushed him to move to London.",
        "Tired of society portraits, he declared 'No more paughtraits' in 1907 and turned to watercolours and murals.",
    ]},
    "John Singleton Copley": {"name": "Copley", "facts": [
        "Largely self-taught, Copley was colonial Boston's leading portrait painter.",
        "He sailed for London in 1774, on the eve of the Revolution, and never came back.",
    ]},
    "Claude Monet": {"name": "Monet", "facts": [
        "His painting 'Impression, Sunrise' gave the Impressionist movement its name in 1874.",
        "Monet worked in series, painting the same subject again and again to catch changing light and weather.",
        "Cataracts in his later years changed how he saw colour; his late pictures turn redder and more abstract.",
    ]},
    "Vincent van Gogh": {"name": "Van Gogh", "facts": [
        "Van Gogh painted for only about ten years and made around 860 oil paintings.",
        "He sold very few works in his lifetime; his letters to his brother Theo tell us much of what we know about his art.",
    ]},
    "Jean-François Millet": {"name": "Millet", "facts": [
        "A farmer's son from Normandy, Millet settled in the village of Barbizon and painted peasants at work.",
        "Boston collectors loved Millet: the MFA has one of the largest Millet collections anywhere, much of it given by Quincy Adams Shaw.",
    ]},
    "William Morris Hunt": {"name": "William Morris Hunt", "facts": [
        "A Boston painter who studied with Millet at Barbizon and persuaded Bostonians to collect French Barbizon art.",
        "His brother was the architect Richard Morris Hunt, who designed the façade of the Metropolitan Museum.",
    ]},
    "Gilbert Stuart": {"name": "Gilbert Stuart", "facts": [
        "His unfinished 'Athenaeum' portrait of George Washington is the face on the U.S. one-dollar bill.",
        "He kept that portrait unfinished on purpose so he could keep painting copies to sell.",
        "Stuart spent his last years in Boston and is buried on Boston Common.",
    ]},
    "Rembrandt Harmensz. van Rijn": {"name": "Rembrandt", "facts": [
        "Rembrandt painted, drew and etched dozens of self-portraits across his life.",
        "Despite his fame he went bankrupt in 1656 and had to sell his house and art collection.",
    ]},
    "Camille Pissarro": {"name": "Pissarro", "facts": [
        "Born on the Caribbean island of St. Thomas, Pissarro was the only artist to show in all eight Impressionist exhibitions.",
        "Younger painters such as Cézanne and Gauguin looked to him as a teacher.",
    ]},
    "Jean-Baptiste-Camille Corot": {"name": "Corot", "facts": [
        "Corot's soft, silvery landscapes were so popular that an old joke says he painted 3,000 pictures, 10,000 of which are in America.",
    ]},
    "George Inness": {"name": "George Inness", "facts": [
        "Inness moved from detailed Hudson River School views to hazy, poetic landscapes shaped by his religious beliefs.",
    ]},
    "Washington Allston": {"name": "Allston", "facts": [
        "America's first major Romantic painter, Allston spent decades on 'Belshazzar's Feast', which he never finished.",
    ]},
    "James Abbott McNeill Whistler": {"name": "Whistler", "facts": [
        "Born in Lowell, Massachusetts, Whistler is best known for the portrait of his mother.",
        "He sued the critic John Ruskin for libel in 1878 and won damages of a single farthing.",
    ]},
    "Winslow Homer": {"name": "Winslow Homer", "facts": [
        "Homer began as an illustrator for Harper's Weekly, covering the Civil War.",
        "He spent his later years at Prouts Neck on the Maine coast, painting the sea.",
    ]},
    "Edgar Degas": {"name": "Degas", "facts": [
        "Degas showed with the Impressionists but preferred to call himself a Realist.",
        "Racehorses and ballet dancers fascinated him: bodies in motion, seen from unusual angles.",
    ]},
    "Paul Gauguin": {"name": "Gauguin", "facts": [
        "Gauguin was a Paris stockbroker before becoming a full-time painter.",
        "He left for Tahiti in 1891 and died in the Marquesas Islands in 1903.",
    ]},
    "Joseph Mallord William Turner": {"name": "Turner", "facts": [
        "Turner was obsessed with light, storms and steam; critics mocked his late pictures as 'soapsuds and whitewash'.",
        "He left hundreds of paintings and thousands of drawings to the British nation.",
    ]},
    "Edmund C. Tarbell": {"name": "Tarbell", "facts": [
        "A leader of the 'Boston School', Tarbell taught at the Museum School here and painted sunlit interiors.",
    ]},
    "William McGregor Paxton": {"name": "Paxton", "facts": [
        "A Boston School painter, Paxton admired Vermeer and painted quiet, polished interiors.",
    ]},
    "Elihu Vedder": {"name": "Vedder", "facts": [
        "Vedder is best known for his illustrations to the 'Rubáiyát of Omar Khayyám' (1884).",
    ]},
    "John La Farge": {"name": "La Farge", "facts": [
        "La Farge invented opalescent stained glass, a rival to Tiffany's.",
        "He painted the murals inside Trinity Church in Copley Square.",
    ]},
    "Thomas Gainsborough": {"name": "Gainsborough", "facts": [
        "Gainsborough made his living from portraits, but said he would rather paint landscapes.",
    ]},
    "François Boucher": {"name": "Boucher", "facts": [
        "Boucher was a favourite painter of Madame de Pompadour and the star of French Rococo.",
    ]},
    "Attributed to: Manaku": {"name": "Manaku", "facts": [
        "Manaku of Guler was a leading painter in the Pahari (hill) kingdoms of northern India, and the elder brother of the famous painter Nainsukh.",
        "These pages come from a great series illustrating the Ramayana, the epic of Prince Rama's war to rescue his wife Sita from the demon king Ravana.",
    ]},
    "Jeong Seon": {"name": "Jeong Seon", "facts": [
        "Jeong Seon painted Korea's real mountains rather than idealised Chinese scenery, a style called 'true-view' landscape.",
    ]},
    # Greek vase painters
    "the Brygos Painter": {"name": "the Brygos Painter", "facts": [
        "Named after the potter Brygos, whose signature appears on cups this painter decorated in Athens around 490–470 B.C.",
        "He is admired for lively drinking-party scenes and dramatic scenes of the fall of Troy.",
    ]},
    "Douris": {"name": "Douris", "facts": [
        "One of the most prolific Athenian cup painters, around 500–460 B.C.; his signature survives on dozens of vases.",
    ]},
    "Onesimos": {"name": "Onesimos", "facts": [
        "An Athenian red-figure cup painter of around 500–480 B.C., known for graceful athletes and young men.",
    ]},
    "the Pan Painter": {"name": "the Pan Painter", "facts": [
        "Named after his masterpiece, a mixing bowl here at the MFA showing the god Pan chasing a young goatherd.",
    ]},
    "the Achilles Painter": {"name": "the Achilles Painter", "facts": [
        "Named after an amphora in the Vatican showing Achilles; he is famous for refined white-ground oil flasks made for graves.",
    ]},
    "the Foundry Painter": {"name": "the Foundry Painter", "facts": [
        "Named after a cup in Berlin showing workers in a bronze foundry, one of the rare Greek images of craftsmen at work.",
    ]},
    "the Niobid Painter": {"name": "the Niobid Painter", "facts": [
        "Named after a mixing bowl in the Louvre showing Apollo and Artemis killing the children of Niobe.",
    ]},
    "the Andokides Painterthe Lysippides Painter": {"name": "the Andokides Painter", "facts": [
        "The Andokides Painter is often credited with inventing red-figure painting in Athens around 530 B.C.",
        "Some of his vases are 'bilingual': black-figure on one side, the new red-figure on the other.",
    ]},
}

GREEK_VASE_NOTE = "Most Greek vase painters never signed their work; scholars named them after a key vase, its museum, or a word painted on it."
RED_FIGURE = "In red-figure, invented in Athens around 530 B.C., the figures are left the colour of the clay and the background is painted black."

KINDS = [
    # ---- Egypt and Nubia ----
    {"id": "shabti-box", "title": "About shabti boxes", "match": {"title": "shawabty box|shabti box"}, "facts": [
        "Shabti figures were kept in painted wooden boxes placed in the tomb near the coffin."]},
    {"id": "nuri-shabti", "title": "About Nubian royal shabtis",
     "match": {"title": "(shawabty|shabti).*(taharqa|senkamanisken|aspelta|anlamani|atlanersa|amaninatakilebte|malonaqen|nastasen|harsiotef|talakhamani|siaspiqa|nasakhma|analmaye|karkamani)"},
     "facts": [
        "These come from royal pyramids at Nuri, in today's Sudan, where the kings of Kush were buried.",
        "The tombs were excavated between 1916 and 1918 by the Harvard–MFA Expedition, which is why so many are in Boston.",
        "King Taharqa, who also ruled Egypt and is mentioned in the Bible as Tirhakah, was buried with more than a thousand shabtis.",
    ]},
    {"id": "shabti", "title": "About shabtis", "match": {"title": "shawabty|shabti|ushabti"}, "facts": [
        "Shabtis were servant figures placed in tombs to do farm work for the dead in the afterlife whenever the gods called for labour.",
        "Many carry a spell from the Book of the Dead telling the figure to answer 'Here I am!' when summoned.",
        "Later burials could hold one for every day of the year, plus overseer figures to keep them working.",
    ]},
    {"id": "canopic", "title": "About canopic jars", "match": {"title": "canopic"}, "facts": [
        "Canopic jars held the organs removed during mummification: liver, lungs, stomach and intestines.",
        "Their lids often show the four sons of the god Horus: a man, a baboon, a jackal and a falcon, each guarding one organ.",
        "The heart stayed in the body; Egyptians believed it would be weighed against a feather in the judgment of the dead.",
    ]},
    {"id": "djehutynakht", "title": "About the tomb of Djehutynakht", "match": {"title": "djehutynakht"}, "facts": [
        "Found in 1915 at Deir el-Bersha by the Harvard–MFA Expedition, in a tomb robbed and set on fire in antiquity yet still crammed with wooden models.",
        "The robbers left behind a mummified head; in 2018 FBI scientists extracted its DNA, and it is believed to be Djehutynakht's.",
    ]},
    {"id": "foundation-deposit", "title": "About foundation deposits", "match": {"title": "foundation deposit"}, "facts": [
        "Before building a temple, Egyptians buried small sets of model tools, vessels and food at its corners, often inscribed with the ruler's name.",
        "Hatshepsut ruled as pharaoh around 1479–1458 B.C.; after her death many of her images and names were erased.",
    ]},
    {"id": "hatshepsut", "title": "About Hatshepsut", "match": {"title": "hatshepsut"}, "facts": [
        "Hatshepsut ruled as pharaoh around 1479–1458 B.C., one of the few women to take the full title of king.",
        "After her death many of her statues were smashed and her name erased, most likely on the orders of her successor Thutmose III.",
    ]},
    {"id": "egypt-model-vessel", "title": "About model vessels", "match": {"title": "^model (vessel|jar|cup|dish|bowl|offering)", "collection": "Egypt"}, "facts": [
        "Tiny stone and pottery vessels stood in for full-size offerings in tombs; magic made the model as good as the real thing.",
    ]},
    {"id": "egypt-model", "title": "About Egyptian tomb models",
     "match": {"title": "^model|offering bearer|procession", "collection": "Egypt"}, "facts": [
        "Wooden and stone models of boats, workshops, servants and offerings were placed in tombs so that, by magic, they would serve the dead forever.",
        "Model boats let the dead travel, including the pilgrimage to Abydos, the holy city of the god Osiris.",
    ]},
    {"id": "menkaura", "title": "About King Menkaura", "match": {"title": "menkaura|mycerinus"}, "facts": [
        "Menkaura built the third and smallest of the great pyramids at Giza, around 2490–2472 B.C.",
        "The Harvard–MFA Expedition led by George Reisner excavated his valley temple in 1908–10 and found its famous statues.",
    ]},
    {"id": "soul-house", "title": "About soul houses", "match": {"title": "soul house"}, "facts": [
        "Soul houses were pottery models of houses with an offering tray in front, set on graves so the spirit had a home and something to eat.",
    ]},
    {"id": "false-door", "title": "About false doors", "match": {"title": "false door"}, "facts": [
        "A false door is a carved doorway that doesn't open: the spirit (ka) of the dead was believed to pass through it to receive offerings.",
    ]},
    {"id": "coffin", "title": "About Egyptian coffins", "match": {"title": "coffin|sarcophag", "culture": "Egyptian"}, "facts": [
        "Wealthy Egyptians were buried in nested coffins, one inside another, often inside a stone sarcophagus.",
        "Coffins were painted with spells and gods to protect the body and guide the dead through the underworld.",
    ]},
    {"id": "funerary-mask", "title": "About funerary masks", "match": {"title": "mask", "culture": "Egyptian"}, "facts": [
        "Masks over the mummy's face gave the dead an idealised, eternal face, sometimes gilded because the gods' skin was believed to be gold.",
    ]},
    {"id": "scarab", "title": "About scarabs", "match": {"title": "scarab"}, "facts": [
        "The scarab beetle rolls balls of dung, so Egyptians linked it to the god Khepri, who rolled the sun across the sky each day.",
        "Scarabs were worn as amulets and used as seals, with names or designs carved on the flat underside.",
    ]},
    {"id": "magic-wand", "title": "About magic wands", "match": {"title": "magic knife|magic wand|apotropaic"}, "facts": [
        "Curved wands of hippopotamus ivory were carved with protective creatures and used to guard mothers and newborn babies.",
    ]},
    {"id": "hippo", "title": "About Egyptian hippos", "match": {"title": "hippopotamus", "collection": "Egypt"}, "facts": [
        "Hippos were dangerous to people on the Nile, so figures of them in tombs may have stood for chaos tamed; some had their legs broken on purpose.",
    ]},
    {"id": "kohl", "title": "About kohl", "match": {"title": "kohl"}, "facts": [
        "Kohl, black eye paint usually made from the mineral galena, was worn by men and women; it cut sun glare and may have helped prevent eye infections.",
    ]},
    {"id": "naqada", "title": "About Predynastic pottery", "match": {"title": "cross-lined|black-topped|white cross"}, "facts": [
        "Made in the Naqada period, before Egypt's first pharaohs, more than 5,000 years ago.",
        "Black-topped pots got their black rims from being fired upside down, with the rim buried in ash and smoke.",
    ]},
    {"id": "egypt-amulet", "title": "About amulets", "match": {"title": "amulet", "culture": "Egyptian|Nubian"}, "facts": [
        "Egyptians wore amulets in life and wrapped dozens inside mummy bandages; each shape carried its own protective magic.",
    ]},
    {"id": "egypt-stele", "title": "About stelae", "match": {"title": "stela|stele", "culture": "Egyptian"}, "facts": [
        "A stela is an inscribed stone slab; in tombs it named the dead and listed the offerings they hoped to receive forever.",
    ]},
    # ---- Near East ----
    {"id": "cylinder-seal", "title": "About cylinder seals", "match": {"title": "cylinder seal"}, "facts": [
        "Rolled across wet clay, a cylinder seal leaves a continuous picture, used like a signature on documents and jar stoppers.",
        "They were often worn on a string around the neck or wrist, and doubled as amulets.",
    ]},
    {"id": "stamp-seal", "title": "About stamp seals", "match": {"title": "stamp seal"}, "facts": [
        "Pressed into clay or wax, stamp seals marked ownership and sealed goods long before writing existed.",
    ]},
    # ---- Greek and Roman coins ----
    {"id": "syracuse", "title": "About the coins of Syracuse", "match": {"title": "syracuse", "type": "Numismatic"}, "facts": [
        "Syracuse in Sicily struck some of the most beautiful Greek coins, often with the nymph Arethusa's head ringed by dolphins.",
        "A few of its engravers, such as Kimon and Euainetos, even signed their dies.",
    ]},
    {"id": "alexander-coin", "title": "About Alexander's coins", "match": {"title": "alexander", "type": "Numismatic"}, "facts": [
        "Alexander the Great's silver coins show Herakles in a lion skin; many people think the face was gradually given Alexander's features.",
        "Cities kept striking coins in Alexander's name for centuries after his death in 323 B.C.",
    ]},
    {"id": "ptolemaic-gold", "title": "About Ptolemaic gold", "match": {"title": "mnaieion|octadrachm|oktadrachm"}, "facts": [
        "A mnaieion was a huge gold coin worth a mina, 100 silver drachmas, struck by the Greek kings who ruled Egypt after Alexander.",
        "Ptolemy II issued coins honouring his sister and wife Arsinoe II, worshipped as a goddess after her death.",
    ]},
    {"id": "tetradrachm", "title": "About tetradrachms", "match": {"title": "tetradrachm"}, "facts": [
        "A tetradrachm is a silver coin worth four drachmas; Athens' version, with the owl of Athena, was trusted all over the Mediterranean.",
        "A drachma was roughly a day's pay for a skilled worker in classical Athens.",
    ]},
    {"id": "stater", "title": "About staters", "match": {"title": "stater"}, "facts": [
        "'Stater' was the name of the standard coin in many Greek cities.",
        "Some of the earliest coins in the world were staters made of electrum, a natural mix of gold and silver, in Lydia and Ionia (today's Turkey).",
    ]},
    {"id": "drachm", "title": "About drachms", "match": {"title": "drachm", "culture": "Greek"}, "facts": [
        "'Drachma' comes from a word for a handful: originally six iron spits, the money of early Greece.",
    ]},
    {"id": "aureus", "title": "About the aureus", "match": {"title": "aureus"}, "facts": [
        "The aureus was Rome's gold coin, worth 25 silver denarii.",
        "Coins carried the emperor's portrait to every corner of the empire, and their backs advertised victories, buildings and virtues.",
    ]},
    {"id": "denarius", "title": "About the denarius", "match": {"title": "denarius|denarii"}, "facts": [
        "The silver denarius was the backbone of Roman money for about 450 years.",
        "Its name lives on in the Arabic 'dinar', and in the 'd' that stood for pennies in old British money.",
    ]},
    {"id": "sestertius", "title": "About the sestertius", "match": {"title": "sestertius|sestertii"}, "facts": [
        "A large brass coin worth a quarter of a denarius; its big surface made it the favourite for detailed imperial portraits.",
    ]},
    {"id": "dupondius", "title": "About the dupondius", "match": {"title": "dupondius"}, "facts": [
        "Worth two asses; to tell it apart from the similar as, the emperor often wears a radiate (spiky sun-ray) crown on it.",
    ]},
    {"id": "medallion", "title": "About Roman medallions", "match": {"title": "medallion", "collection": "Greece and Rome"}, "facts": [
        "Medallions were special presentation pieces given by emperors to officials and soldiers, not everyday money.",
    ]},
    {"id": "coin", "title": "About ancient coins", "match": {"type": "Numismatic"}, "facts": [
        "Coins were invented in western Turkey around 600 B.C.; each was hand-struck between two engraved dies with a hammer.",
    ]},
    # ---- Greek vases (shape first) ----
    {"id": "skyphos", "title": "About the skyphos", "match": {"title": "skyphos"}, "facts": [
        "A skyphos is a deep, two-handled drinking cup, a more everyday cousin of the elegant kylix.",
    ]},
    {"id": "kantharos", "title": "About the kantharos", "match": {"title": "kantharos"}, "facts": [
        "The kantharos, with its tall handles, is the cup of Dionysos, god of wine; he is often shown holding one.",
    ]},
    {"id": "kylix", "title": "About the kylix", "match": {"title": "kylix|drinking cup", "culture": "Greek"}, "facts": [
        "A kylix is a shallow wine cup for the symposium, the Greek drinking party. The painting inside was revealed as you drank.",
        "Drinkers played kottabos, flicking the last drops of wine from the cup at a target.",
        GREEK_VASE_NOTE,
    ]},
    {"id": "lekythos", "title": "About the lekythos", "match": {"title": "lekythos|lekythoi|oil flask", "culture": "Greek"}, "facts": [
        "A lekythos held olive oil. Tall white-ground lekythoi were made for Athenian graves, painted with mourning and farewell scenes.",
        GREEK_VASE_NOTE,
    ]},
    {"id": "panathenaic", "title": "About Panathenaic amphorae", "match": {"title": "panathenaic"}, "facts": [
        "Filled with olive oil from Athena's sacred trees, these amphorae were prizes at the Panathenaic Games in Athens; a winner could get dozens.",
        "They kept the old black-figure style for centuries, with Athena striding on one side and the athletic contest on the other.",
    ]},
    {"id": "amphora", "title": "About the amphora", "match": {"title": "amphora|amphorae|two-handled jar", "culture": "Greek"}, "facts": [
        "An amphora is a two-handled jar for storing and carrying wine, oil and other goods.",
        GREEK_VASE_NOTE,
    ]},
    {"id": "krater", "title": "About the krater", "match": {"title": "krater|mixing (wine-)?bowl", "culture": "Greek"}, "facts": [
        "Greeks mixed their wine with water in a krater; drinking wine neat was considered barbaric.",
        GREEK_VASE_NOTE,
    ]},
    {"id": "hydria", "title": "About the hydria", "match": {"title": "hydria|water jar"}, "facts": [
        "A hydria carried water: two side handles for lifting, and one at the back for pouring.",
        "Fetching water from the fountain house was a daily job for women, and a scene vase painters loved.",
    ]},
    {"id": "oinochoe", "title": "About the oinochoe", "match": {"title": "oinochoe|wine jug"}, "facts": [
        "An oinochoe is a wine jug, often with a three-lobed (trefoil) mouth to pour neatly into cups.",
    ]},
    {"id": "aryballos", "title": "About the aryballos", "match": {"title": "aryballos"}, "facts": [
        "A small round flask of oil that athletes hung from their wrist; they oiled their bodies before exercise and scraped off oil and dust afterwards.",
    ]},
    {"id": "alabastron", "title": "About the alabastron", "match": {"title": "alabastron"}, "facts": [
        "A slim perfume bottle, named after the alabaster stone the first ones were carved from.",
    ]},
    {"id": "pelike-stamnos", "title": "About this vase shape", "match": {"title": "pelike|stamnos"}, "facts": [
        "Pelikai and stamnoi were storage jars: the pelike sags low like a bag, the stamnos has a wide shoulder and a lid.",
        RED_FIGURE,
    ]},
    # ---- Greek figurines and more ----
    {"id": "comic-actor", "title": "About comic actors", "match": {"title": "comic actor|comedy|actor"}, "facts": [
        "Greek comic actors wore grotesque masks and padded costumes; little clay figures of them were popular souvenirs of the theatre.",
    ]},
    {"id": "tanagra", "title": "About Greek terracotta figurines", "match": {"title": "figurine|statuette", "collection": "Greece and Rome", "medium": "terracotta"}, "facts": [
        "Clay figurines like this were made from moulds by the thousands, then hand-finished and brightly painted; traces of paint often survive.",
        "Elegant draped women from the town of Tanagra became such a collecting craze in the 1870s that forgers produced many fakes.",
    ]},
    {"id": "grave-stele", "title": "About Greek grave markers", "match": {"title": "grave", "collection": "Greece and Rome"}, "facts": [
        "Athenian grave stones of the 400s and 300s B.C. show quiet farewells: the dead often clasp hands with the living.",
    ]},
    {"id": "greek-mirror", "title": "About ancient mirrors", "match": {"title": "mirror", "collection": "Greece and Rome"}, "facts": [
        "Ancient mirrors were disks of polished bronze; you had to keep polishing them to see your face.",
    ]},
    {"id": "roman-surgery", "title": "About Roman medicine", "match": {"title": "surgical|scalpel|probe|forceps", "collection": "Greece and Rome"}, "facts": [
        "Roman surgeons used bronze scalpels, probes and forceps strikingly like modern ones; sets have been found at Pompeii.",
    ]},
    {"id": "steelyard", "title": "About steelyards", "match": {"title": "steelyard"}, "facts": [
        "A steelyard is a balance with arms of unequal length: a weight, often shaped as a bust, slides along the long arm to balance the load.",
    ]},
    {"id": "greek-helmet", "title": "About Greek helmets", "match": {"title": "helmet", "collection": "Greece and Rome"}, "facts": [
        "The famous Corinthian helmet was hammered from a single sheet of bronze and covered almost the whole face.",
    ]},
    # ---- Americas ----
    {"id": "cocle", "title": "About Coclé gold", "match": {"culture": "Cocl"}, "facts": [
        "Coclé goldsmiths in central Panama hammered and embossed sheet gold into plaques and chest ornaments, often with crocodile-like creatures.",
        "Many Coclé gold pieces come from the rich burials at Sitio Conte, excavated in the 1930s.",
    ]},
    {"id": "quimbaya", "title": "About Quimbaya gold", "match": {"culture": "Quimbaya"}, "facts": [
        "Quimbaya goldsmiths in Colombia's Cauca valley were masters of lost-wax casting, often in tumbaga, an alloy of gold and copper.",
    ]},
    {"id": "mezcala", "title": "About Mezcala sculpture", "match": {"culture": "Mezcala"}, "facts": [
        "Mezcala carvers in Guerrero, Mexico, turned stone celts (axe-like blades) into strikingly abstract figures and temples.",
        "Centuries later the Aztecs collected Mezcala figures and buried them as offerings at their Great Temple in Tenochtitlan.",
    ]},
    {"id": "maya", "title": "About the Maya", "match": {"culture": "Maya"}, "facts": [
        "The Maya developed the most complete writing system in the ancient Americas, along with a precise calendar.",
    ]},
    # ---- Asia ----
    {"id": "buddha", "title": "About images of the Buddha", "match": {"title": "buddha"}, "facts": [
        "The bump on the Buddha's head (ushnisha) signals his wisdom; his long earlobes recall the heavy earrings he gave up when he renounced his life as a prince.",
        "Hand gestures (mudras) carry meaning: touching the earth recalls the moment he called the earth to witness his enlightenment.",
    ]},
    {"id": "bodhisattva", "title": "About bodhisattvas", "match": {"title": "bodhisattva|guanyin|avalokiteshvara|kannon"}, "facts": [
        "Bodhisattvas are enlightened beings who delay their own nirvana to help others; they wear jewels and crowns, unlike the plainly robed Buddha.",
    ]},
    {"id": "tsuba", "title": "About tsuba", "match": {"title": "tsuba"}, "facts": [
        "A tsuba is the guard between a Japanese sword's blade and handle.",
        "During the long peace of the Edo period, when swords were rarely used in battle, tsuba became showpieces of metalwork.",
    ]},
    {"id": "chinese-bronze", "title": "About Chinese ritual bronzes", "match": {"title": "ritual", "culture": "Chinese"}, "facts": [
        "Ancient Chinese bronzes held food and wine offered to ancestors.",
        "Unlike most of the ancient world, Shang and Zhou bronze workers cast in sectional clay moulds rather than by lost wax.",
    ]},
    # ---- Europe ----
    {"id": "french-silver", "title": "About French silver", "match": {"type": "Silver", "culture": "French"}, "facts": [
        "Little old French silver survives: Louis XIV had his own silver melted down to pay for wars, and much more was melted during the Revolution.",
        "Paris hallmarks include a date letter, so pieces can often be dated to the exact year.",
    ]},
    {"id": "american-silver", "title": "About early American silver", "match": {"type": "Silver", "culture": "American"}, "facts": [
        "With no banks, colonists turned spare coins into silverware: it was useful, showed status, and could be identified if stolen.",
    ]},
    # ---- Musical instruments ----
    {"id": "lute", "title": "About the lute", "match": {"title": "^lute|\\blute\\b"}, "facts": [
        "The European lute descends from the Arab oud; its name comes from the Arabic 'al-ʿūd', 'the wood'.",
    ]},
    {"id": "end-blown-flute", "title": "About end-blown flutes", "match": {"title": "end-blown"}, "facts": [
        "You play an end-blown flute by blowing across its sharp top rim, like blowing over a bottle; the Japanese shakuhachi works this way.",
    ]},
    {"id": "trumpet", "title": "About trumpets", "match": {"title": "^(keyed |slide |natural )?trumpet(?! marine)|^horn\\b|bugle", "collection": "Musical"}, "facts": [
        "Before valves were invented around 1815, a brass player could only play the notes natural to the tube, changing pitch with the lips alone.",
    ]},
    {"id": "saxophone", "title": "About the saxophone", "match": {"title": "saxophone"}, "facts": [
        "The Belgian instrument maker Adolphe Sax patented the saxophone in 1846.",
    ]},
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
doc = {
    "about": "Did-you-know notes written for this app from general art-history knowledge, not by the MFA. "
             "Edit tools/curiosities_src.py and run it to rebuild this file.",
    "works": WORKS,
    "artists": ARTISTS,
    "kinds": KINDS,
}
with open(os.path.join(ROOT, "data", "curiosities.json"), "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
print(f"{len(WORKS)} works · {len(ARTISTS)} artists · {len(KINDS)} kinds")
