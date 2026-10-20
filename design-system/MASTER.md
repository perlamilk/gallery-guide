# Gallery Guide — design system

Built with the **apple-design** (HIG) and **ui-ux-pro-max** skills. This file is the source of truth;
`css/app.css` (`:root` tokens) and `js/config.js` (map colours) implement it.

## Thesis

A pocket guide that behaves like an iPhone map app and looks like the museum itself:
**the white cube** (white walls, black wall labels) and **the plaster architectural model**.
The map is the hero; everything else is quiet glass floating over it.

**Signature:** galleries that match a search *rise* out of the plaster model in **International Klein Blue**.
Klein blue is the only saturated colour in the app. It means "this is what you're looking for":
search matches, the selected room, your route, the one primary button on a screen.

## Colour

| Token | Light | Dark | Use | Contrast (on sheet) |
|---|---|---|---|---|
| `--bg` | `#F2F2EF` | `#0E0E0E` | map ground, page | — |
| `--surface` | `#FFFFFF` | `#1C1C1E` | sheet at full height, cards | — |
| `--ink` | `#111111` | `#F2F2F2` | primary text | 18.9 / 15.2 |
| `--ink-2` | `#5C5C5C` | `#ABABAB` | secondary text | 6.7 / 7.4 |
| `--ink-3` | `#6B6B6B` | `#9A9AA0` | tertiary text, captions | 5.3 / 6.1 |
| `--accent` | `#002FA7` | `#7C95FF` | Klein blue: matches, selection, route, primary button | 10.7 / 6.2 |
| `--danger` | `#C4001A` | `#FF6961` | delete only | — |

Map: plaster `#FBFBF9` galleries, warm-grey corridors, darker closed areas; lit rooms Klein blue.
Glass (functional layer only — tab bar, floor picker, map buttons, sheet at medium height):
`backdrop-filter: blur(24px) saturate(1.5)`, fill 72% white / 66% `#1C1C1E`, 1px hairline;
opaque under *Reduce Transparency*.

## Type

Apple's own pair, no web fonts:
- **New York** (`ui-serif`) — titles and artwork names, the museum's wall-label voice.
- **SF** (`system-ui`) — everything you tap or read in passing.

Scale (rem, 1rem = iOS Body 17pt and follows Dynamic Type): Large title 2.0 NY semibold ·
Title 1.53 NY semibold · Title 3 1.18 NY · Headline 1 SF semibold · Body 1 · Subhead 0.88 · Footnote 0.76 · Caption 0.71 (min 11pt).

## Layout

```
┌─────────────────────────────┐
│ MFA Boston        ● Visit   │  masthead (fades when sheet rises)
│ Level 2                     │
│                        [3]  │
│      3D plaster map    [2]  │  floor picker + recenter: glass, right edge
│                        [1]  │
│                        [◎]  │
│ ╭─────────────────────────╮ │
│ │  ───  (grabber)         │ │  sheet: glass at medium, opaque at large,
│ │ (⌕ Search the museum  ) │ │  3 detents, drag anywhere
│ │ Van Gogh  Monet  …      │ │
│ ╰─────────────────────────╯ │
│ ╭ Explore Tours Saved Visits╮│  tab bar: glass capsule, 4 tabs
└─────────────────────────────┘
```

## Navigation

Tab bar with four sections (HIG `tab-bars.md`: *Prefer a tab bar for navigation*):
**Explore** (search, works, places, facilities) · **Tours** · **Saved** (favorites) · **Visits** (visit in progress, diary).
The map stays behind every tab; each tab keeps its own place.

## Components

- Buttons: one filled Klein-blue button per view at most; others tinted grey or plain. Title-style capitalization.
- Lists: inset grouped (12pt radius, separators inset past the icon), 52pt rows, chevrons for drill-in.
- Pills scroll horizontally in one row (artists, filters).
- Toggles are iOS switches. Floor picker is a vertical list of floor numbers (HIG `maps.md`).

## Motion

One orchestrated moment: matching galleries rise and turn blue. Everything else is short (150–300 ms),
and Reduce Motion turns it off.

## Rejected from the generated system

ui-ux-pro-max suggested "Scroll-triggered storytelling" (a landing-page pattern) and Poiret One / Didact Gothic
(Art Deco, thin weights the HIG warns against). Kept from it: Minimalism & Swiss, gallery black and white.

## App shell (multi-museum, Oct 2026)

`index.html` is the app; the MFA 3D map guide is `guide.html` (close button returns to the MFA's museum page).
Tab bar: **Home · Museums · Collection · Discover** (single-word labels, filled icon when selected).

- **Home**: Continue at MFA card · Did you know? (Klein-blue card, New York italic) · Your Top Artists · Your Museum Map · Museums Nearby.
- **Museums**: search (filters as you type) · All / Favorites chips · list ⇄ map segmented control. Map: MapLibre + OpenFreeMap
  (Positron / Dark), clustered points (HIG maps: cluster overlapping points), selected point in Klein blue, "Search This Area".
- **Museum page**: hero photo with title, initials badge, links, Welcome (Wikipedia summary), Visit Information, Highlights.
- **Collection**: Library / Visits / Collections; toolbar (filter, sort, grid ⇄ list, Select); select mode with a floating action bar.
- **Discover**: popular artworks, museums, artists (ranked by Wikipedia language count), themes; artist and theme pages.

Open data: Wikidata (CC0) via `tools/build_open_data.py`, pictures from Wikimedia Commons, summaries from Wikipedia, always credited.
Location is asked for only when you tap "Show Museums Near Me" (HIG privacy). Touch targets ≥ 44 pt; pressed state = opacity.
