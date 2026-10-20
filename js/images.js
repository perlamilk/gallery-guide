// Artwork pictures, shared by the app (index.html) and the MFA guide (guide.html).
// Sample works have one file each (`image`); the full collection packs small images into a few
// large files (`img: {p, o, l}` = file, offset, length), read piece by piece as they scroll into view.

export const BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';

const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// A Wikimedia Commons picture at a given width (the server makes the small version).
export const commons = (file, width = 600) =>
  `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${width}`;

export function imgHTML(a, cls, alt = '') {
  if (a.image) return `<img class="${cls}" src="${a.image}" alt="${escape(alt)}" loading="lazy" decoding="async">`;
  if (a.img) return `<img class="${cls}" src="${BLANK}" alt="${escape(alt)}" data-pack="${a.img.p}" data-o="${a.img.o}" data-l="${a.img.l}">`;
  return `<span class="${cls} img-empty" aria-hidden="true"></span>`;
}

const packedURLs = new Map();
function packedImage(p, o, l) {
  const key = `${p}:${o}`;
  if (!packedURLs.has(key)) {
    packedURLs.set(key, (async () => {
      const res = await fetch(p, { headers: { Range: `bytes=${o}-${o + l - 1}` } });
      const blob = await res.blob();
      const part = res.status === 206 ? blob : blob.slice(o, o + l);
      return URL.createObjectURL(new Blob([part], { type: 'image/jpeg' }));
    })().catch(err => { packedURLs.delete(key); throw err; }));
  }
  return packedURLs.get(key);
}
const imageObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  for (const e of entries) if (e.isIntersecting) { imageObserver.unobserve(e.target); loadPacked(e.target); }
}, { rootMargin: '300px' }) : null;
function loadPacked(img) {
  const { pack, o, l } = img.dataset;
  packedImage(pack, Number(o), Number(l)).then(url => { img.src = url; }).catch(() => img.classList.add('img-empty'));
}
export function hydrateImages(root) {
  for (const img of root.querySelectorAll('img[data-pack]:not([data-seen])')) {
    img.dataset.seen = '1';
    if (imageObserver) imageObserver.observe(img); else loadPacked(img);
  }
}

const blobURLs = new Map();
export function blobURL(key, blob) {
  if (!blob) return BLANK;
  if (!blobURLs.has(key)) blobURLs.set(key, URL.createObjectURL(blob));
  return blobURLs.get(key);
}

