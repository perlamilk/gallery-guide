# Museum Guide: project brief

Grazi's personal, ad-free gallery guide for her iPhone. It's a web app you add to the home screen.

- **Live:** https://perlamilk.github.io/gallery-guide/ (GitHub repo `perlamilk/gallery-guide`)
- **Code:** `~/Downloads/Claude/mfa-guide`. Plain HTML/CSS/JS with no build step: `index.html` is the shell (Home, Museums, Collection, Discover) and `guide.html` is the MFA 3D map guide.
- **Publish:** `tools/publish.sh "message"`. It bumps `sw.js` VERSION, rebuilds the offline pack list, pushes, and waits until the site is live. It stops if the repo has commits made elsewhere.

## Rules Grazi set
- Never send her email or personal details to outside services. The User-Agent is `GalleryGuidePersonal/1.0 (personal museum guide app)`.
- Use the ui-ux-pro-max and apple-design skills on every UI change.
- Don't work around a site's protections. The MFA site blocks scripted reading; the harvester stops by itself when blocked.
- Download from Wikimedia politely: 1280 or 960 px thumbnails, a pause of several seconds between requests, and back off on 429.
- Use only well-established facts in texts, and mark interpretations as such.
- Grazi writes in Portuguese, but the app stays in English.
- Museum Wi-Fi is bad, so anything new for the MFA must go into the offline pack (`tools/build_pack.py` runs on publish).

## Where things stand (v32, 2026-11-03)
- **MFA works:** 3,411 of the 7,695 on view.
  - 2,851 come from the MFA harvest.
  - 560 come from Wikidata (`dataSource: "Wikidata"`). These have no gallery number yet.
- **What to Notice:** 165 works, in `data/notice.json`, with hi-res pictures in `data/notice/`.
- **Offline pack:** about 71 MB.
- **Email:** a data request to the MFA is drafted in `email-to-mfa.md`. Grazi sends it herself.

## Next
- More What to Notice batches: the remaining new paintings, then other MFA paintings.
- Fill in the missing works and galleries if the MFA answers the email.
- Add museums beyond the MFA.
