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
│   ├── map3d.js            the 3D map (three.js): rooms, labels, gestures, camera
│   ├── data.js             loads + searches the JSON (the only code that reads data)
│   └── config.js           map colours and sizes (mirror the CSS tokens)
├── data/
│   ├── artworks.json       ← the artworks. Replace this file to update the guide
│   ├── floors.json         ← room shapes per floor, traced from the MFA map PDF
│   └── images/             artwork images, one per work (<id>.jpg)
├── fonts/                  Instrument Serif (display type), bundled for offline use
├── icons/                  app icons
├── vendor/                 three.js r170 + OrbitControls (bundled for offline use)
└── tools/
    ├── serve.py            local preview server (no caching)
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

Room outlines are in **PDF points** from page 1 of `mfa-boston-map_2025-12.pdf` (x to the right, y down),
so a correction can be read straight off the printed map. Per floor:

- `rooms[].poly` — the outline corners. `kind` is `gallery` or `service` (elevators, passages).
- `rooms[].name` — the gallery's name if known.
- `homeView` — the rooms the map frames when it opens or when you tap Recenter.
- `offset` — lines the floors up with each other (the PDF draws them in different places on the page).

To add a floor, add another entry to `floors` with its rooms. The floor switcher picks it up automatically.

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

The room shapes come straight from the white gallery shapes in the PDF. These points were unclear and are best guesses:

1. **146 / 145 (Level 1)** are drawn as one shape. I split them where 246/245 split on Level 2.
2. **141A / 141B (Level 1)** are one shape in the PDF. Same approach, aligned with 241A/241B.
3. **153 (Level 1)** runs into the staircase hall in the PDF; I cut it at the edge of 148.
4. **Elevator block** between 244 and 243A (and between 144 and 143): treated as an elevator lobby, not a gallery.
5. **Small unlabeled spaces** between 254 and 249 (and 154 and 148): treated as passages.
6. **249 and 148** contain the grand staircase but have gallery numbers, so they're tappable galleries.
7. **Grey area between 152 and 146 (Level 1)** is grey on the map (not open to visitors), so it isn't drawn.
8. **237–239 / 137–138** are left off: the MFA lists American art in 239, so they belong to another area.
9. **Gallery names** appear only for the 11 rooms whose name I saw on the MFA site.
10. **Floors** are shown as equal-height blocks; real ceiling heights aren't in the PDF.

## Sample data notes

- 21 works, all marked **On View** on collections.mfa.org on Oct 18, 2026, each with the gallery number shown there.
- **Images:** the MFA site blocks automated image downloads, so the app's offline images come from Wikimedia Commons
  (public-domain photos of the same paintings; several come from the MFA via Google Arts & Culture). The MFA's own image address is kept in `imageUrl`.
- Two works I first picked had no usable public-domain photo (Degas's *Little Dancer* and Veronese's *Atalanta*),
  so they were swapped for *At the Races in the Countryside* (255) and Rosso Fiorentino's *Dead Christ with Angels* (141B).
