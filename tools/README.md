# Tools

## serve.py

Local preview with caching off: `python3 tools/serve.py` → http://localhost:8770

## Planned: weekly on-view scraper (not built yet)

Goal: regenerate `data/artworks.json` (and `data/images/`) every week from the MFA's online collection,
keeping every work currently marked **On View**.

What the prototype work established:

- Search results: `https://collections.mfa.org/search/objects/*/<term>?filter=onview%3Atrue&page=N`
  (12 per page; object links look like `/objects/<id>/<slug>`).
- Object pages carry everything the app needs, in elements with these classes:
  `.titleField`, `.peopleField`, `.displayDateField`, `.mediumField .detailFieldValue`,
  `.invnolineField .detailFieldValue` (accession), `.classificationsField .detailFieldValue` (type),
  and `.onviewField`, whose text reads e.g. `ON VIEW Sidney and Esther Rabb Gallery (Gallery 255)`.
- The image is `img[src*="/preview"]` → `/internal/media/dispatcher/<mediaId>/preview`.
- The site sits behind a bot-protection layer (AWS WAF): plain `curl` / `fetch` from a script gets **403**.
  A scraper has to run in a real browser (e.g. Playwright) at a gentle pace, or use an official
  data feed if the MFA offers one. Don't work around the protection; ask the MFA if bulk access is needed.

Suggested shape:

1. `tools/scrape-mfa.mjs` (Playwright): walk the on-view search for the Europe collection
   (or all collections), visit each object page, and parse the fields above.
2. Map `gallery` → `floor` with `data/floors.json`; fill `type`, `country`, `period`.
3. Download and resize images to `data/images/<id>.jpg` (max 800 px, JPEG q≈80).
4. Write `data/artworks.json` and bump `VERSION` in `sw.js`.
5. Schedule weekly with a GitHub Actions workflow (`.github/workflows/update-artworks.yml`,
   `on: schedule: - cron: "0 9 * * 1"`) that runs the script and commits the changes.
   GitHub Pages then republishes automatically.

The app needs no changes for this: everything goes through `js/data.js`.

## Planned: routes and filters

- **Filters:** `museum.search(query, { period, country, type })` in `js/data.js` already accepts exact-match filters;
  only the chips/UI are missing.
- **Routes:** add a `doors` list per floor in `floors.json` (pairs of room ids that connect), then run a
  shortest-path search over that graph and draw the path in `map3d.js` as a line just above the room tops.

## Safe publication

`publish.sh` requires a **clean Git checkout at the repository root**. Commit local
changes first. Loose app folders and `.git/gg-last-publish` markers cannot prove
synchronization; `FORCE_AFTER_MERGE` no longer bypasses validation.

Before publishing, fetch and merge/rebase `origin/main` **in the source checkout**,
resolve conflicts, and review the resulting files. The publisher independently
fetches remote `main` into its separate cache and requires that exact commit to be
an ancestor of the source commit. A new cache has the same checks as an old cache.
If the remote has new data/code, publication stops until that history is incorporated.
Simply updating the cache or creating a marker does not satisfy this check.

```bash
git fetch origin
git merge origin/main
# Review data and code, resolve any conflicts, then commit your changes.
bash tools/publish.sh --dry-run "Describe the update"
# Only when ready to publish:
bash tools/publish.sh "Describe the update"
```

Dry run fetches and prepares a temporary candidate commit, shows its diff statistics,
and exits **without pushing or contacting Pages**. Both modes use only the validated
source commit in an isolated temporary worktree. Ignored files are not deployed;
untracked or uncommitted files cause a stop. Submodules are unsupported and rejected.
The source service-worker version stays unchanged; the candidate gets the bump.
The cache checkout stays unchanged too. `CLONE` can select a separate publication
cache, which must have an `origin` pointing to the intended repository; it must not
be the source checkout.

The final push uses an exact lease on the fetched remote main, rejecting a concurrent
update or rewind. The candidate already descends from that main; the lease is never
used to permit divergent history. There is no marker-based override, destructive
folder synchronization, or automatic merge. Intentional changes/deletions committed
after incorporating main remain publishable, so review the source commits and the
reported diff before publishing. Git ancestry cannot judge an intentional bad edit.

Run the integration tests with:

```bash
python3 -m unittest discover -s tests -p 'test_publish.py'
node tests/harvest-integrity.cjs
```

Publication tests use disposable local bare Git repositories and stubs for GitHub
and Pages. They never publish the real site.
