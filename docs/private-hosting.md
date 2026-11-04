# Private hosting (Cloudflare Pages + Cloudflare Access)

Since November 2026 the repository is private, so GitHub Pages (free plan) no longer serves the app.
The app is hosted on Cloudflare Pages instead, behind a Cloudflare Access login that only lets in the
owner's email address. Both are free.

## How it fits together

- **Cloudflare Pages** is connected to this GitHub repository. Every push to `main` is published within
  a minute or two. No build step: build command empty, output directory `/`.
- **Cloudflare Access** (part of Cloudflare Zero Trust) sits in front of the `*.pages.dev` address. A visitor
  must type the allowed email address and the one-time code Cloudflare emails them. The session lasts
  one month, then the login is asked again (only when online; offline the app keeps working from its cache).
- `tools/publish.sh` still pushes to `main`. It now waits for the "Cloudflare Pages" check on the commit
  instead of fetching the live site, because the live site needs a login.

## App changes that make the login work

- `<link rel="manifest" ... crossorigin="use-credentials">` in `index.html` and `guide.html`: without it the
  browser fetches the manifest without the login cookie, Access refuses it, and the home-screen icon and name break.
- `sw.js` `networkFirst`: when a data file comes back as an error (for example the login expired), the saved
  copy is used. A page load that Access redirects is passed through so the login screen can appear.

## Setup (done once, in the Cloudflare dashboard)

1. **Pages:** Workers & Pages → Create → Pages → Connect to Git → pick `perlamilk/gallery-guide`.
   Production branch `main`, framework preset None, build command empty, output directory `/`.
2. **Access:** Zero Trust → Access → Applications → Add an application → Self-hosted.
   Domain: the project's `<name>.pages.dev` address, and a second entry `*.<name>.pages.dev` for previews.
   Session duration: 1 month. Policy: Allow, Include → Emails → the owner's address.
   Login method: One-time PIN (on by default).
3. Turn off GitHub Pages and make the repository private (Settings → General → Danger Zone).

## Notes

- Installing on a phone means a new address, so it is a new home-screen app. The visit diary and favorites
  are stored per address (IndexedDB) and don't carry over from the old GitHub Pages install.
- Preview deployments of other branches (`<branch>.<name>.pages.dev`) are covered by the wildcard entry.
