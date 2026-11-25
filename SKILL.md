---
name: aequalyn-themes
description: Themes for Aequalyn: palette + backgrounds, artgen generator, install/set commands.
---

# Aequalyn Themes — skill

## Overview

Themes for Aequalyn. Each theme is a palette plus backgrounds that belong to it.
96 themes under `themes/`, 10 standalone wallpapers under `wallpapers/`, one generator
`tools/artgen.py`, brand assets in `tools/brand/`.

## Themes

- **Drawn topics (9)**, each with a dark theme and a "Day" light theme = 18 themes:
  Cosmos (4 colours), Canopy (2), Abyss (2), Summit (1), Dune (3), Polar (3), Metro (2),
  Flux (4), Aequalyn (3, brand). Each dark theme: `1-night-<id>.jpg`, `2-dusk-<id>.jpg`,
  `3-live-night-<id>.mp4` (Aequalyn ships four stills + four loops). Each Day theme:
  `1-day-<id>.jpg`, `2-dawn-<id>.jpg`, `3-live-day-<id>.mp4`. Scenes: cosmos, forest,
  ocean, peaks, desert, aurora, city, flow, brand. Family = "Aequalyn Nature" except
  Flux/Metro/Aequalyn = "Aequalyn".
- **Gradients (36)**, each dark and "Day" = 72 themes, from `GRADIENTS` in artgen: one colour
  (6), two (12), three (12) or the three shades of a metal or stone (6, `one_hue()`). Scene `gradient` (the brand scene with the mark and the name in
  the gradient); four files each, named as Aequalyn's (`1-night-`, `2-dusk-`, `3-live-night-`,
  `4-live-dusk-`; Day: day and dawn). `gradient_palette()`: the gradient's colours are the
  accents and `borderColors`; green and red stay green and red.
- **Handcrafted single-variant themes (5):** Basalt, Ember, Lumen (dark); Meadow (light);
  Tidal (dark). Two 4K stills each, no live loops, family "Aequalyn".
- **Pack (1):** Nocturne — 3 stills, no palette; colours come from the showing background.

## Format

```
themes/<id>/
├── theme.json      name, family, author, variant, palette (drawn: + about, colors)
├── backgrounds/    images/videos used in name order
└── preview.jpg     card image (optional; defaults to first background)
```

- `palette` keys: `bgBase bgSurface bgHover bgSelected bgBorder textPrimary textSecondary
  textMuted accentPrimary accentCyan accentGreen accentOrange accentRed`; optional
  `borderColors` (>=2 colours; otherwise accentPrimary→accentCyan).
- Omit `palette` → pack.
- Folder themes with `colors.toml` (accent/foreground/background/color0–15) map onto the
  palette.
- User themes: `~/.config/aequalyn/themes/` (override shipped by id). Wallpapers of their
  own: `~/.local/share/aequalyn/wallpapers/`.

## Commands

```sh
aequalyn-themes install <git-url>
aequalyn-themes set <id>
aequalyn-themes list
aequalyn-themes remove <id>
```

## tools/artgen.py

Python 3 generator; deterministic (same seed → same picture). Requires `resvg`,
ImageMagick `magick`, `ffmpeg` (checked at startup). Commands:

- `all` — every theme + wallpapers
- `theme <id>…` — one topic (dark+light)
- `walls` — standalone wallpapers
- `live <id>…` — only live loops
- `palettes` — rewrite theme.json only
- `preview <id>…` — quick 960×540 stills into `$ARTGEN_OUT` or temp

Mechanics: 9 topics in `TOPICS` with 1–4 seed colours + scene; 10 standalone `WALLS`
entries. `palette(keys, variant)` derives 13 palette keys from seed colours (HSL tone
steps, readable() contrast nudging; reds fixed `#ef6b73`/`#c8323e`). Scenes render
layered SVG (sky, glow, stars, nebulae, ridges, trees, waves, dunes, aurora, city,
ribbons, brand mark/name) via `Svg` helper. `still()`: resvg renders each layer to PNG
at 3840×2160, magick composites in order, adds Gaussian grain (attenuate 0.08), outputs
JPEG quality 90. `live()`: layers at 1920×1080; ffmpeg applies per-layer sway
(sinusoidal, padded+smear borders), pulse opacity, crossfade; libx264 slow preset CRF 21,
12 s, 30 fps, seamless loop. `topic()` regenerates theme dirs (rmtree), writes 2 stills
+ live loops + `preview.jpg` (960×540 center crop) + `theme.json`. Brand assets:
`tools/brand/ae-mark.svg`, `aequalyn-wordmark.svg`; mark on night/day + live loops, name
on dusk/dawn. Parallel layer rendering with `ThreadPoolExecutor`.

## Wallpapers

`wallpapers/`: 8 stills at 4K (nebula-crimson-night, glacier-day, canyon-dusk-dusk,
lagoon-day, snowpine-night, lavender-flow-day, emerald-aurora-dusk, neon-city-night) +
2 live loops (live-starfield.mp4, live-tide.mp4). Shown in every wallpaper picker. Live
ones need `mpvpaper` to move; otherwise still.

## Security

Themes are data: no scripts, executables or symlinks; no config writes; no absolute
paths or remote URLs; images sniffed by magic bytes and size-capped. See `SECURITY.md`
and `aequalyn/Security.md` / `aequalyn-market`'s guidelines.

## References

- Aequalyn themes: https://github.com/Aequalyn/aequalyn-themes
- Aequalyn core: https://github.com/Aequalyn/aequalyn
- Aequalyn shell: https://github.com/Aequalyn/aequalyn-shell
- Aequalyn market: https://github.com/Aequalyn/aequalyn-market
