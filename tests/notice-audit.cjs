// What to Notice audit: run with `node tests/notice-audit.cjs` from the app folder.
// Fails (exit code 1) on problems that break a guide: a missing picture, a guide for a work that
// isn't in artworks.json, a file left out of the offline pack, a zoom region outside the picture.
// Warns about guides whose work has no gallery, or a gallery the map doesn't draw.
const fs = require('node:fs');
const read = f => JSON.parse(fs.readFileSync(f, 'utf8'));

const notice = read('data/notice.json').works;
const art = new Map(read('data/artworks.json').artworks.map(a => [a.id, a]));
const pack = read('data/pack-mfa.json');
const inPack = new Set(pack.files.map(f => f.u));
const rooms = new Set();
for (const floor of read('data/floors.json').floors)
  for (const r of floor.rooms) if (r.kind === 'gallery') [r.id, ...(r.aliases ?? [])].forEach(id => rooms.add(id));
// the app files a lettered alcove ("219A") under its main gallery when the map has that one
const onMap = g => rooms.has(g) || rooms.has(String(g).match(/^(\d+)[A-Za-z.]/)?.[1]);

const errors = [], warnings = [];
for (const [id, w] of Object.entries(notice)) {
  const a = art.get(id);
  const name = a ? `${id} ${a.title}` : id;
  if (!w.image || !fs.existsSync(w.image)) errors.push(`${name}: picture ${w.image ?? '(none)'} is missing`);
  else if (!inPack.has(w.image)) errors.push(`${name}: ${w.image} is not in the offline pack (run tools/build_pack.py)`);
  if (!a) { errors.push(`${id}: not in artworks.json, so the guide is never listed`); continue; }
  if (a.onView === false) errors.push(`${name}: work is marked not on view, so the guide is hidden`);
  const pic = a.image ?? a.img?.p;
  if (pic && !inPack.has(pic)) errors.push(`${name}: artwork picture ${pic} is not in the offline pack`);
  if (!w.steps?.length) errors.push(`${name}: no steps`);
  (w.steps ?? []).forEach((s, i) => {
    if (!s.title || !s.text) errors.push(`${name}: step ${i + 1} has no title or text`);
    const r = s.r;
    if (r && (r.length !== 4 || r.some(v => v < 0 || v > 1) || r[0] + r[2] > 1.001 || r[1] + r[3] > 1.001))
      errors.push(`${name}: step ${i + 1} zoom region ${JSON.stringify(r)} falls outside the picture`);
  });
  if (!a.gallery) warnings.push(`${name}: no gallery or floor`);
  else if (!onMap(a.gallery)) warnings.push(`${name}: gallery ${a.gallery} isn't drawn on the map`);
}
if (pack.notice !== Object.keys(notice).length)
  errors.push(`offline pack lists ${pack.notice} guides but notice.json has ${Object.keys(notice).length} (run tools/build_pack.py)`);
for (const f of fs.readdirSync('data/notice'))
  if (!Object.values(notice).some(w => w.image === `data/notice/${f}`)) warnings.push(`data/notice/${f} isn't used by any guide`);

if (warnings.length) console.log(`${warnings.length} warnings:\n  ` + warnings.join('\n  '));
if (errors.length) { console.error(`${errors.length} errors:\n  ` + errors.join('\n  ')); process.exitCode = 1; }
else console.log(`${Object.keys(notice).length} What to Notice guides checked: pictures, offline pack and zoom regions OK.`);
