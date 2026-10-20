// Visual and behavioural constants shared by the map and the UI.
// Map colours mirror the CSS tokens in css/app.css (light and dark); change both together.

export const THEMES = {
  light: {
    paper: 0xf3f1ec,       // background, gallery-wall white
    roomTop: 0xfcfbf8,     // gallery floor seen from above
    roomSide: 0xd9d3c8,    // gallery walls
    serviceTop: 0xe9e5dd,  // corridors and passages
    serviceSide: 0xd2cbbe,
    spaceTop: 0xf3e9da,    // named spaces: courtyards, cafés, shops, auditoriums
    spaceSide: 0xdccdb6,
    closedTop: 0xdcd7ce,   // areas closed to visitors (grey on the PDF)
    closedSide: 0xccc6bb,
    edge: 0x8f877a,        // outline on top of each room
    accent: 0x2b44c9,      // ultramarine: matches --accent
    accentSide: 0x1e329a,
    selected: 0x15226b,
    selectedPlain: 0xe6dfd1,
    shadow: 0.12,
    note: '#7d766b',
    area: '#2b44c9',
    label: '#3a362f',
    labelOnAccent: '#ffffff',
    markerBg: '#ffffff',
    markerInk: '#2a2722',
    markerRing: '#d6cfc2',
    door: 0xa69d8e,        // thresholds between rooms
    visitedTop: 0xd2daf6,  // rooms checked off in the visit diary
  },
  dark: {
    paper: 0x171612,
    roomTop: 0x45423b,     // galleries: clearly lighter than corridors and closed areas
    roomSide: 0x2a2823,
    serviceTop: 0x2c2a25,
    serviceSide: 0x1f1d19,
    spaceTop: 0x54493a,
    spaceSide: 0x352e25,
    closedTop: 0x1f1e1a,
    closedSide: 0x191814,
    edge: 0x7a7365,
    accent: 0x4a63f0,
    accentSide: 0x2b3fae,
    selected: 0x8fa0ff,
    selectedPlain: 0x45423b,
    shadow: 0.35,
    note: '#8f897e',
    area: '#8fa0ff',
    label: '#ece7de',
    labelOnAccent: '#ffffff',
    markerBg: '#2e2c27',
    markerInk: '#ece7de',
    markerRing: '#4a463f',
    door: 0x6f685c,
    visitedTop: 0x323d78,
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
  serviceHeight: 0.14,  // corridors
  spaceHeight: 0.3,     // named spaces
  closedHeight: 0.06,   // closed areas
  markerSize: 1.7,      // facility icons, scene units
  markerLift: 1.6,      // how high facility icons float
};

export const FONTS = {
  display: '"Instrument Serif", "Iowan Old Style", Georgia, serif',
};
