// Facility icons, drawn as 24×24 line pictograms. Used both on the 3D map (via canvas Path2D)
// and in the interface (as inline SVG), so they always match.
// `words` are what people might type in the search box (English and Portuguese).

const circle = (cx, cy, r) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

export const FACILITIES = {
  restroom: {
    short: 'Restrooms',
    label: 'Restrooms',
    words: 'restroom restrooms toilet toilets bathroom wc banheiro banheiros sanitario',
    paths: [circle(7.5, 4.5, 1.7), 'M7.5 8 4.8 15h5.4zM6.4 15v5.5M8.6 15v5.5', circle(16.5, 4.5, 1.7),
            'M14.6 8h3.8v7h-3.8zM15.4 15v5.5M17.6 15v5.5', 'M12 3v18'],
  },
  'restroom-all': {
    short: 'All-Gender',
    label: 'All-Gender Restroom',
    words: 'restroom toilet bathroom wc everyone all gender banheiro unissex',
    paths: [circle(12, 4.5, 1.8), 'M10 8h4v7h-4zM10.8 15v5.5M13.2 15v5.5'],
  },
  elevator: {
    short: 'Elevator',
    label: 'Elevator',
    words: 'elevator lift elevador accessible acessivel',
    paths: ['M5 3h14v18H5z', 'm9 9.5 3-3 3 3M9 14.5l3 3 3-3'],
  },
  stairs: {
    short: 'Stairs',
    label: 'Stairs',
    words: 'stairs stair staircase escada escadas',
    paths: ['M3 20h5v-5h5v-5h5V5h3'],
  },
  dining: {
    short: 'Café',
    label: 'Café & Dining',
    words: 'cafe café coffee dining restaurant food eat lunch cafeteria restaurante comida lanche',
    paths: ['M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10', 'M17 3c-2.2 1-3.5 4-3.5 8H17v10'],
  },
  shop: {
    short: 'Shop',
    label: 'Shop',
    words: 'shop store gift bookstore loja livraria souvenir',
    paths: ['M5 8h14l-1.2 13H6.2z', 'M9 8V6.5a3 3 0 0 1 6 0V8'],
  },
  info: {
    short: 'Info',
    label: 'Information',
    words: 'information info help desk visitor center informacao ajuda',
    paths: [circle(12, 12, 9), 'M12 11v6', 'M12 7.6v.4'],
  },
  nursing: {
    short: 'Nursing',
    label: 'Nursing Room',
    words: 'nursing baby mother lactation amamentacao bebe fraldario',
    paths: ['M9 9.5h6V20a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 9 20z', 'M10 9.5V7h4v2.5M12 7V3.5'],
  },
  entrance: {
    short: 'Entrance',
    label: 'Accessible Entrance',
    words: 'entrance entry exit door accessible wheelchair entrada saida porta acessivel cadeira',
    paths: [circle(10.5, 4.5, 1.7), 'M10.5 7.5v5.5h5l2.2 5.5', 'M10.5 10h4', 'M7.8 10.6a5.2 5.2 0 1 0 7.4 6.6'],
  },
  emergency: {
    short: 'Emergency',
    label: 'Emergency Call Box',
    words: 'emergency help phone call security emergencia socorro telefone seguranca',
    paths: ['M5 4h3l1.5 4-2 1.5a10 10 0 0 0 5 5l1.5-2 4 1.5v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z', 'M17.5 3v6M14.5 6h6'],
  },
  water: {
    short: 'Water',
    label: 'Water Fountain',
    words: 'water fountain drink bebedouro agua',
    paths: ['M12 3.5s5.5 6 5.5 10.2a5.5 5.5 0 0 1-11 0C6.5 9.5 12 3.5 12 3.5z'],
  },
  coat: {
    short: 'Coat Check',
    label: 'Coat Check',
    words: 'coat check cloakroom bag locker guarda volumes casaco chapelaria',
    paths: ['M12 8.5a2 2 0 1 1 2-2c0 1.1-2 1.4-2 2.8L3.5 16h17z'],
  },
};

export function facilitySVG(type, { size = 20 } = {}) {
  const f = FACILITIES[type];
  if (!f) return '';
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${f.paths.map(d => `<path d="${d}"/>`).join('')}</svg>`;
}

// Draw a facility pictogram into a 2D canvas context, centred in a box of `size` pixels.
export function drawFacility(ctx, type, x, y, size, color, lineWidth = 1.7) {
  const f = FACILITIES[type];
  if (!f) return;
  ctx.save();
  ctx.translate(x - size / 2, y - size / 2);
  ctx.scale(size / 24, size / 24);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  for (const d of f.paths) ctx.stroke(new Path2D(d));
  ctx.restore();
}
