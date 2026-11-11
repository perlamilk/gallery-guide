// What to Notice: a guided look at a painting, one detail at a time.
// Full-screen, like a photo viewer (HIG modality: full screen for photos and multistep tasks),
// with a clear way out (✕, swipe down, Esc). Each step zooms the picture to a region
// (fractions of the picture: [x, y, w, h]); swipe or use Back / Next (HIG gestures: never gesture-only).
// Data: data/notice.json (MFA, plus the general guide); other museums keep theirs next to their
// artworks (data/met/notice.json), named by the notice field in js/site.js.

const DEFAULT = 'data/notice.json';
const docs = new Map();
export function noticeData(src = DEFAULT) {
  if (!docs.has(src)) docs.set(src, fetch(src).then(r => (r.ok ? r.json() : null)).catch(() => null));
  return docs.get(src);
}

export async function hasNotice(id, src = DEFAULT) {
  return !!(await noticeData(src))?.works?.[id];
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// open({ id }) for a work, or open({ general: true }) for the seven-question guide.
export async function openNotice({ id = null, general = false, title = '', artist = '', src = DEFAULT } = {}) {
  const doc = await noticeData(src);
  const work = id ? doc?.works?.[id] : null;
  const guide = general ? (await noticeData(DEFAULT))?.general : null;
  if (!work && !guide) return;
  const steps = work ? work.steps : guide.steps;
  const heading = work ? title : guide.title;
  const returnFocus = document.activeElement;

  const el = document.createElement('div');
  el.className = 'notice';
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-modal', 'true');
  el.setAttribute('aria-label', `What to Notice: ${heading}`);
  el.innerHTML = `
    <div class="notice__bar">
      <button class="notice__close" type="button" aria-label="Close">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
      <div class="notice__head"><p class="notice__eyebrow">What to Notice</p><p class="notice__title">${esc(heading)}</p></div>
      <span class="notice__count" aria-hidden="true"></span>
    </div>
    ${work ? `<div class="notice__stage"><div class="notice__frame"><img class="notice__img" src="${esc(work.image)}" alt="${esc(heading)}"></div></div>`
      : `<div class="notice__stage notice__stage--text"><span class="notice__big" aria-hidden="true"></span></div>`}
    <div class="notice__panel">
      <div class="notice__dots" role="tablist" aria-label="Steps">${steps.map((s, i) => `<button type="button" role="tab" aria-label="Step ${i + 1}: ${esc(s.title)}" data-i="${i}"></button>`).join('')}</div>
      <div class="notice__copy" aria-live="polite"><h2 class="notice__step"></h2><p class="notice__text"></p></div>
      <div class="notice__nav">
        <button class="notice__btn notice__btn--ghost" type="button" data-prev>Back</button>
        <button class="notice__btn" type="button" data-next>Next</button>
      </div>
      ${work ? `<p class="notice__credit">Picture: ${esc(work.credit ?? 'Wikimedia Commons')} · Written for this app, not by the museum</p>` : ''}
    </div>`;
  document.body.appendChild(el);
  document.documentElement.classList.add('notice-open');

  const img = el.querySelector('.notice__img');
  const frame = el.querySelector('.notice__frame');
  const stage = el.querySelector('.notice__stage');
  let i = 0;

  function layout(animate) {
    if (!img || !img.naturalWidth) return;
    const SW = stage.clientWidth, SH = stage.clientHeight;
    const IW = img.naturalWidth, IH = img.naturalHeight;
    const fit = Math.min(SW / IW, SH / IH);
    const DW = IW * fit, DH = IH * fit;
    frame.style.width = `${DW}px`;
    frame.style.height = `${DH}px`;
    const r = steps[i].r;
    let k = 1, tx = (SW - DW) / 2, ty = (SH - DH) / 2;
    if (r) {
      const [x, y, w, h] = r;
      k = Math.max(1, Math.min(5, Math.min((SW * 0.92) / (w * DW), (SH * 0.92) / (h * DH))));
      tx = SW / 2 - (x + w / 2) * DW * k;
      ty = SH / 2 - (y + h / 2) * DH * k;
      // keep the picture covering the stage where it can, so no empty gaps at the edges
      const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
      tx = DW * k >= SW ? clamp(tx, SW - DW * k, 0) : (SW - DW * k) / 2;
      ty = DH * k >= SH ? clamp(ty, SH - DH * k, 0) : (SH - DH * k) / 2;
    }
    frame.style.transition = animate && !reduceMotion() ? 'transform .7s cubic-bezier(.32, .72, 0, 1)' : 'none';
    frame.style.transform = `translate(${tx}px, ${ty}px) scale(${k})`;
  }

  function show(n, animate = true) {
    i = Math.max(0, Math.min(steps.length - 1, n));
    const s = steps[i];
    el.querySelector('.notice__step').textContent = s.title;
    el.querySelector('.notice__text').textContent = s.text;
    el.querySelector('.notice__count').textContent = `${i + 1} / ${steps.length}`;
    const big = el.querySelector('.notice__big');
    if (big) big.textContent = String(i + 1);
    el.querySelectorAll('.notice__dots button').forEach((b, j) => b.setAttribute('aria-selected', String(j === i)));
    el.querySelector('[data-prev]').disabled = i === 0;
    el.querySelector('[data-next]').textContent = i === steps.length - 1 ? 'Done' : 'Next';
    layout(animate);
  }

  function close() {
    window.removeEventListener('resize', onResize);
    document.removeEventListener('keydown', onKey);
    document.documentElement.classList.remove('notice-open');
    el.classList.add('notice--out');
    setTimeout(() => el.remove(), reduceMotion() ? 0 : 220);
    returnFocus?.focus?.();
  }

  const onResize = () => layout(false);
  const onKey = e => {
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') show(i + 1);
    else if (e.key === 'ArrowLeft') show(i - 1);
  };
  window.addEventListener('resize', onResize);
  document.addEventListener('keydown', onKey);

  el.addEventListener('click', e => {
    if (e.target.closest('.notice__close')) return close();
    if (e.target.closest('[data-prev]')) return show(i - 1);
    if (e.target.closest('[data-next]')) return i === steps.length - 1 ? close() : show(i + 1);
    const dot = e.target.closest('[data-i]');
    if (dot) return show(Number(dot.dataset.i));
  });

  // swipe left/right between steps, down on the picture to close
  let start = null;
  el.addEventListener('touchstart', e => { const t = e.touches[0]; start = { x: t.clientX, y: t.clientY, onStage: !!e.target.closest('.notice__stage') }; }, { passive: true });
  el.addEventListener('touchend', e => {
    if (!start) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - start.x, dy = t.clientY - start.y;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) show(i + (dx < 0 ? 1 : -1));
    else if (start.onStage && dy > 90 && Math.abs(dy) > Math.abs(dx) * 1.5) close();
    start = null;
  }, { passive: true });

  if (img) img.complete ? show(0, false) : img.addEventListener('load', () => show(0, false), { once: true });
  show(0, false);
  el.querySelector('.notice__close').focus({ preventScroll: true });
}
