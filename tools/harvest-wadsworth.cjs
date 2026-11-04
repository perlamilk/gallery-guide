// Wadsworth Atheneum "On View" harvester (Node + Playwright, Chromium).
//   node tools/harvest-wadsworth.cjs path/to/onview.jsonl        (LIMIT=20 for a short test)
// The museum's collection site (Argus, 5058.sydneyplus.com) has no API and no link per record: it opens
// the "On View" tab and walks the records with the site's own Next-record pager, one page load at a time
// with a pause between them, and writes one JSON line per work (all fields the record shows).
// About 4 s per work: the ~2,200 works take 2–3 hours. Then run tools/fetch_wadsworth_images.py and
// tools/build_wadsworth.py.
const { chromium } = require('playwright');
const fs = require('fs');
const OUT = process.argv[2] || 'onview.jsonl';
const PAUSE = 2500;
const done = new Set(fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l).n) : []);
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15 (personal museum guide)' });
  await p.route(/\.(png|jpe?g|gif|woff2?)(\?|$)|ViewImage\.aspx|Theme\.aspx/, r => r.abort());
  await p.goto('https://5058.sydneyplus.com/argus/final/Portal/Public.aspx?lang=en-US', { waitUntil: 'networkidle', timeout: 120000 });
  await p.click('text=On View');
  await p.waitForTimeout(6000);
  const total = +(await p.locator('[id$=panels_tp4]').innerText()).match(/Found ([\d,]+) record/)[1].replace(/,/g, '');
  console.log("total", total); const LIMIT = +(process.env.LIMIT || total);
  // open the first record, or START=<n> to continue an earlier run (appends to the same file)
  const START = +(process.env.START || 1);
  if (START > 1) {
    // the Jump to Record box is folded away: set it and press its Go link directly
    await p.locator('[id$=panels_tp4] input[id$=jumpToRecordTextLast]').first().evaluate((el, v) => { el.value = v; }, String(START));
    await p.locator('[id$=panels_tp4] a[id$=jumpToRecordLinkLast]').first().dispatchEvent('click');
    await p.waitForTimeout(8000);
  }
  const opened = await p.locator(`[id$=panels_tp4] [aria-current="page"][aria-label="Record ${START}"]`).count();
  if (!opened) {
    const cell = p.locator('[id$=panels_tp4] .lc-header-view').filter({ hasText: new RegExp(`Record ${START}\\b`) }).first();
    await (await cell.count() ? cell.locator('.lc-header-view__header a') : p.locator('[id$=panels_tp4] .lc-header-view__header a')).first().click();
  }
  await p.waitForTimeout(5000);
  const read = () => p.evaluate(() => {
    const panel = document.querySelector('[id$=panels_tp4]');
    const out = {};
    const prompts = panel.querySelectorAll('span.Prompt');
    for (const s of prompts) {
      const k = s.textContent.trim().replace(/:$/, '');
      const td = s.closest('td');
      const v = td?.nextElementSibling?.innerText?.trim();
      if (k && v && !(k in out)) out[k] = v;
    }
    const img = [...panel.querySelectorAll('img')].map(i => i.getAttribute('src')).find(s => s && /field=DerivedIma&/.test(s));
    out._img = img || null;
    const txt = panel.innerText;
    const a = txt.indexOf('ARTIST/MAKER INFORMATION:'), z = txt.indexOf('Object Type:', a);
    if (a >= 0) out._maker = txt.slice(a + 25, z > a ? z : a + 600).trim();
    const cur = panel.querySelector('[aria-current="page"][aria-label^="Record "]');
    out._n = cur ? +cur.getAttribute('aria-label').slice(7) : null;
    return out;
  });
  let n = START, fails = 0;
  while (n <= Math.min(total, LIMIT)) {
    let r = await read();
    if (r._n !== n) { await p.waitForTimeout(3000); r = await read(); }
    if (r._n === n && !done.has(n)) { fs.appendFileSync(OUT, JSON.stringify({ n, ...r }) + '\n'); }
    if (n % 50 === 0) console.log(new Date().toISOString(), n, r['Object ID'], r['Title']);
    if (n === total || n === LIMIT) break;
    const next = p.locator(`[id$=panels_tp4] a[aria-label="Record ${n + 1}"]`).first();
    try {
      await next.click({ timeout: 20000 });
      await p.waitForFunction(k => document.querySelector('[id$=panels_tp4] [aria-current="page"][aria-label="Record ' + k + '"]'), n + 1, { timeout: 60000 });
      n++; fails = 0;
    } catch (e) {
      fails++; console.log('fail at', n, e.message.slice(0, 120));
      if (fails > 5) break;
      await p.waitForTimeout(30000 * fails);
      continue;
    }
    await p.waitForTimeout(PAUSE);
  }
  console.log('end at', n);
  await b.close();
})();
