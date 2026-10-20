// Visual and behavioural constants shared by the map and the UI.
// Map colours mirror the CSS tokens in css/app.css (light and dark); change both together.

export const THEMES = {
  // the plaster architectural model: white galleries, warm-grey corridors, Klein blue for what you're looking for
  light: {
    paper: 0xf2f2ef,
    roomTop: 0xfbfbf9,
    roomSide: 0xd9d9d3,
    serviceTop: 0xe9e9e4,
    serviceSide: 0xd3d3cc,
    spaceTop: 0xeeebe4,
    spaceSide: 0xd6d1c6,
    closedTop: 0xdcdcd6,
    closedSide: 0xcfcfc8,
    edge: 0x9a9a93,
    accent: 0x002fa7,      // International Klein Blue — matches --accent
    accentSide: 0x00227a,
    selected: 0x001a5e,
    selectedPlain: 0xe3e3dd,
    shadow: 0.13,
    note: '#6b6b6b',
    area: '#002fa7',
    label: '#1f1f1f',
    labelOnAccent: '#ffffff',
    markerBg: '#ffffff',
    markerInk: '#111111',
    markerRing: '#d4d4cf',
    door: 0xa9a9a2,
    visitedTop: 0xd6def5,
  },
  dark: {
    paper: 0x0e0e0e,
    roomTop: 0x3a3a3c,
    roomSide: 0x242426,
    serviceTop: 0x262628,
    serviceSide: 0x1a1a1c,
    spaceTop: 0x45403a,
    spaceSide: 0x2e2a26,
    closedTop: 0x18181a,
    closedSide: 0x121214,
    edge: 0x6e6e73,
    accent: 0x5470ff,
    accentSide: 0x2e46c2,
    selected: 0x9db0ff,
    selectedPlain: 0x4a4a4e,
    shadow: 0.35,
    note: '#9a9aa0',
    area: '#7c95ff',
    label: '#f2f2f2',
    labelOnAccent: '#ffffff',
    markerBg: '#2c2c2e',
    markerInk: '#f2f2f2',
    markerRing: '#48484a',
    door: 0x7a7a80,
    visitedTop: 0x2f3a70,
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
  display: 'ui-serif, "New York", "Iowan Old Style", Georgia, serif',  // Apple's New York on iPhone
};
