// Visual and behavioural constants shared by the map and the UI.
// Map colours mirror the CSS tokens in css/app.css (light and dark); change both together.

export const THEMES = {
  light: {
    paper: 0xf3f1ec,       // background, gallery-wall white
    roomTop: 0xfcfbf8,     // gallery floor seen from above
    roomSide: 0xd9d3c8,    // gallery walls
    serviceTop: 0xe7e3db,  // elevators, passages
    serviceSide: 0xcfc8bb,
    edge: 0x8f877a,        // outline on top of each room
    accent: 0x2b44c9,      // ultramarine: matches --accent
    accentSide: 0x1e329a,
    selected: 0x15226b,
    selectedPlain: 0xe6dfd1,
    shadow: 0.12,
    note: '#7d766b',
    label: '#3a362f',
    labelOnAccent: '#ffffff',
  },
  dark: {
    paper: 0x171612,
    roomTop: 0x2e2c27,
    roomSide: 0x1f1d19,
    serviceTop: 0x25231f,
    serviceSide: 0x1a1915,
    edge: 0x5f594f,
    accent: 0x4a63f0,
    accentSide: 0x2b3fae,
    selected: 0x8fa0ff,
    selectedPlain: 0x45423b,
    shadow: 0.35,
    note: '#8f897e',
    label: '#d9d3c8',
    labelOnAccent: '#ffffff',
  },
};

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
export const currentTheme = () => (darkQuery.matches ? THEMES.dark : THEMES.light);
export const onThemeChange = fn => darkQuery.addEventListener('change', () => fn(currentTheme()));

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export const MAP = {
  scale: 0.1,            // scene units per PDF point
  roomHeight: 0.45,
  roomHeightLit: 1.15,   // rooms rise when they contain a match
  serviceHeight: 0.18,
};

export const FONTS = {
  display: '"Instrument Serif", "Iowan Old Style", Georgia, serif',
};
