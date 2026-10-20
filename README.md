# Gallery Guide — MFA Boston (prototype)

A personal, ad-free 3D guide to the Art of Europe galleries at the Museum of Fine Arts, Boston.
It is a Progressive Web App: plain HTML, CSS and JavaScript plus three.js, with no build step.
Add it to your iPhone home screen and it runs full-screen, offline, with its own icon.

## What's in the folder

```
mfa-guide/
├── index.html              the page
├── manifest.webmanifest    name, icon, full-screen settings for the home screen
├── sw.js                   offline support (caches the app, data and images)
├── css/app.css             all styling: colour tokens (light + dark) at the top
├── js/
│   ├── app.js              search, bottom sheet, room & artwork views, floor switcher
│   ├── map3d.js            the 3D map (three.js): rooms, labels, facility icons, gestures, camera
│   ├── icons.js            facility pictograms + the words search understands (English/Portuguese)
│   ├── data.js             loads + searches the JSON (the only code that reads data)
│   ├── routes.js           walking directions: doorways, stairs and elevators as a graph
│   ├── visits.js           visit diary and favorites, stored on the device (IndexedDB)
│   └── config.js           map colours and sizes (mirror the CSS tokens)
├── data/
│   ├── artworks.json       ← the artworks. Replace this file to update the guide
│   ├── tours.json          ← ready-made tours: stops (galleries) and works to look for
│   ├── floors.json         ← the whole map: rooms, facilities, labels for Levels G/LG–3
│   └── images/             artwork images, one per work (<id>.jpg)
├── fonts/                  Instrument Serif (display type), bundled for offline use
├── icons/                  app icons
├── vendor/                 three.js r170 + OrbitControls (bundled for offline use)
└── tools/
    ├── serve.py            local preview server (no caching)
    ├── trace_pdf.py        rebuilds data/floors.json from the MFA map PDF
    └── README.md           plan for the weekly MFA scraper (not built yet)
```

## Changing the data

### artworks.json

Each work looks like this. You can edit, add or remove entries without touching any code.

```json
{
  "id": "32542",                       // MFA object number (from the collection URL)
  "title": "Postman Joseph Roulin",
  "artist": "Vincent van Gogh",
  "artistDetails": "Dutch (worked in France), 1853–1890",
  "date": "1888",
  "medium": "Oil on canvas",
  "gallery": "255",                    // must match a room id in floors.json to light up
  "galleryName": "Sidney and Esther Rabb Gallery",
  "floor": "2",
  "image": "data/images/32542.jpg",    // the copy the app shows (works offline)
  "imageUrl": "https://collections.mfa.org/internal/media/dispatcher/1447565/preview",
  "url": "https://collections.mfa.org/objects/32542",
  "accession": "35.1982",
  "onView": true,
  "type": "Painting",                  // ┐
  "country": "Netherlands",            // ├ ready for filters later
  "period": "19th century",            // ┘
  "imageCredit": "Public domain, via Wikimedia Commons",
  "imageSource": "https://commons.wikimedia.org/wiki/File:..."
}
```

- A work whose `gallery` isn't on the map still appears in search, marked "not on this map yet".
- Works with `"onView": false` are hidden.
- After changing files, bump `VERSION` in `sw.js` (e.g. `v1` → `v2`) so your phone downloads the new version.

### floors.json

The whole museum map (Levels G/LG, 1, 2 and 3), generated from the MFA visitor map PDF by
`tools/trace_pdf.py`. Nothing is traced by eye: room shapes, names, gallery numbers and facility icons
are read from the PDF's vector drawing. Coordinates are **PDF points** of each floor's own drawing, so a
correction can be read straight off the printed map. Per floor:

- `rooms[]` — `kind` is `gallery` (numbered), `space` (named: courtyards, cafés, shops, auditoriums) or `corridor`.
  A shape that carries several gallery numbers lists the extras in `aliases`.
- `closed[]` — areas that are grey on the PDF (not open to visitors).
- `amenities[]` — restrooms, elevators, stairs, dining, shop, information, nursing room, accessible entrances,
  emergency call boxes, water fountains and coat check, from the map's icons.
- `labels[]` — wing names and notes (entrances, the Conservation Center elevator).
- `transform` — `[scale, dx, dy]` that lines the floor up with Level 2 (the PDF draws floors in different places and sizes).
- `homeView` — the rooms the map frames when it opens or when you tap Recenter.

To re-trace a new edition of the PDF:

```bash
python3 -m venv .venv && .venv/bin/pip install pymupdf numpy pillow
.venv/bin/python tools/trace_pdf.py path/to/mfa-boston-map.pdf
```

Hand decisions (room splits, names, pinned labels) live in `OVERRIDES` at the top of the script.

## Tours

`data/tours.json` holds the ready-made tours. Each stop is a gallery number plus the works to look for there
(MFA object ids from `artworks.json`) and a short note. Add or edit tours there; no code changes needed.
Starting a tour also starts a visit in the diary, and each "next stop" checks the room off.

## Directions

Routes use the doorways traced from the PDF (gaps in the wall lines) and link stairs and elevators that sit in the same
place on neighbouring floors. "Avoid stairs" uses elevators only. Distances are estimates (1 PDF point ≈ 0.35 m).
Your starting point is the last room you checked off, an entrance, or the room you tap on the map.

## Loading the full list of works on view

`tools/harvest-mfa.js` collects every work marked On View (about 7,700) from collections.mfa.org.
You run it yourself in your own browser (Chrome works best):

1. Copy the script: `pbcopy < tools/harvest-mfa.js` (from the mfa-guide folder).
2. Open https://collections.mfa.org in its own Chrome window, open the console (Cmd+Option+J), type `allow pasting` if asked, paste, press Enter.
3. Click **Start** in the panel. It takes about 4 hours, one request at a time. Keep the window visible and the Mac awake (`caffeinate -dim` in Terminal).
   Progress is saved: if it stops, paste the script again and click Start.
4. Click **Download**. Put `artworks.json` in `data/` (replacing the sample) and the `images-*.bin` files in `data/images/`. Allow multiple downloads if Chrome asks.
5. Bump `VERSION` in `sw.js`.

Images are stored in a few "pack" files (about 15 MB each) instead of thousands of small files, so they can still be uploaded through GitHub's website.

## Preview on your Mac

```bash
python3 tools/serve.py
```

Then open http://localhost:8770 (run the command from inside the `mfa-guide` folder).

---

## Put it online for free with GitHub Pages (step by step)

You only do this once. Later updates are a drag and drop.

**1. Create a GitHub account**
Go to https://github.com/signup and sign up (free). Verify your email.

**2. Create a repository (a project folder on GitHub)**
- Click the **+** at the top right → **New repository**.
- Repository name: `gallery-guide` (any name works; it becomes part of the address).
- Choose **Public**. Free GitHub Pages needs a public repository, which means anyone with the link could see the files. It's only artwork data, nothing private.
- Tick **Add a README file**.
- Click **Create repository**.

**3. Upload the app's files**
- In your new repository, click **Add file → Upload files**.
- Open the `mfa-guide` folder in Finder, select **everything inside it** (`Cmd+A`): `index.html`, `sw.js`, `manifest.webmanifest`, and the folders `css`, `js`, `data`, `fonts`, `icons`, `vendor`, `tools`.
- Drag them all into the upload area of the browser window. Folders keep their structure.
- Wait until every file is listed, then click **Commit changes** at the bottom.
- Check that `index.html` sits at the top level of the repository, not inside an `mfa-guide` folder.

**4. Turn on GitHub Pages**
- In the repository, click **Settings** (top bar) → **Pages** (left menu).
- Under **Build and deployment → Source**, choose **Deploy from a branch**.
- Branch: **main**, folder: **/ (root)** → **Save**.
- After a minute or two, refresh the page. It shows: *Your site is live at `https://<your-username>.github.io/gallery-guide/`*.

**5. Open that address on your iPhone in Safari** and follow "Install on your iPhone" below.

**Updating later:** repeat step 3 with only the changed files (for example `data/artworks.json` and new images),
after bumping `VERSION` in `sw.js`. GitHub Pages republishes automatically in about a minute.

> Prefer Netlify? Create a free account at https://app.netlify.com, choose **Add new site → Deploy manually**,
> and drag the whole `mfa-guide` folder onto the page. You get an address like `https://something.netlify.app`.

## Install on your iPhone

1. Open the site address in **Safari** (home-screen apps must be added from Safari).
2. Tap the **Share** button (the square with an arrow pointing up).
3. Scroll down and tap **Add to Home Screen**. If you don't see it, tap **Edit Actions…** and add it.
4. Keep the name "Gallery Guide" and tap **Add**.
5. **Open it once from the home screen while you have Wi-Fi or signal.** That first launch downloads everything for offline use.
   On the start screen you'll see "Saved for offline use — works without signal" when it's done.
6. In the museum it works without signal. The "View on the MFA collection site" link needs a connection.

The home-screen app has its own storage, separate from Safari. Deleting the icon deletes its offline copy; just add it again.

## Map guesses to check

Everything comes from the PDF's own drawing. These points were unclear and are best guesses:

1. **146 / 145, 141A / 141B (Level 1)** are one shape each in the PDF; split where the walls fall on Level 2.
2. **Shapes with several numbers** (walls drawn as lines inside one shape) are shown as one room with all its numbers:
   273 / 274, 279 / 280, 265 / 268, 238 / 238A, 239 / 238B, 278A–C, 212A–C, 213–215C, 159 / 160, 121A / 121B, 138A / 138B, G37–G39.
3. **Taste café and gallery 168** share one shape; Taste is shown as a label on it.
4. **155** is overlapped by a corridor shape in the PDF; it's kept as its own room.
5. **Level G/LG** is drawn about 4% smaller than Level 1 in the PDF; it's scaled up to line up with the floors above.
6. **Emergency exits** aren't on the MFA map. The app shows what the map has: emergency call boxes and the entrances.
7. **Gallery names** come from the collection site where known; the rest of the rooms show only their number.
8. **Floors** are shown as equal-height blocks; real ceiling heights aren't in the PDF.

## Sample data notes

- 24 works, all marked **On View** on collections.mfa.org (checked Oct 18–19, 2026), each with the gallery number shown there.
- **Images:** the MFA site blocks automated image downloads, so the app's offline images come from Wikimedia Commons
  (public-domain photos of the same paintings; several come from the MFA via Google Arts & Culture). The MFA's own image address is kept in `imageUrl`.
- Two works I first picked had no usable public-domain photo (Degas's *Little Dancer* and Veronese's *Atalanta*),
  so they were swapped for *At the Races in the Countryside* (255) and Rosso Fiorentino's *Dead Christ with Angels* (141B).
