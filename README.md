# aequalyn-themes

Themes for Aequalyn. Each theme is a palette plus backgrounds that belong to it.

| | | |
| --- | --- | --- |
| ![](themes/lumen/preview.jpg) **Lumen** | ![](themes/basalt/preview.jpg) **Basalt** | ![](themes/ember/preview.jpg) **Ember** |
| ![](themes/tidal/preview.jpg) **Tidal** | ![](themes/meadow/preview.jpg) **Meadow** (light) | ![](themes/nocturne/preview.jpg) **Nocturne** (pack) |

## Drawn here

Nine topics, each a dark theme and a light one ("Day"), drawn by
`tools/artgen.py` from one to four colours: the colours make the palette and every
picture of the theme. Each theme has two 4K stills (night and dusk, or day and dawn,
so the time-of-day wallpaper mode finds them) and a 1080p live loop.

| | | | |
| --- | --- | --- | --- |
| ![](themes/cosmos/preview.jpg) **Cosmos** · 4 colours | ![](themes/canopy/preview.jpg) **Canopy** · 2 | ![](themes/abyss/preview.jpg) **Abyss** · 2 | ![](themes/summit/preview.jpg) **Summit** · 1 |
| ![](themes/dune/preview.jpg) **Dune** · 3 | ![](themes/polar/preview.jpg) **Polar** · 3 | ![](themes/metro/preview.jpg) **Metro** · 2 | ![](themes/flux/preview.jpg) **Flux** · 4 |
| ![](themes/cosmos-day/preview.jpg) **Cosmos Day** | ![](themes/canopy-day/preview.jpg) **Canopy Day** | ![](themes/abyss-day/preview.jpg) **Abyss Day** | ![](themes/summit-day/preview.jpg) **Summit Day** |
| ![](themes/dune-day/preview.jpg) **Dune Day** | ![](themes/polar-day/preview.jpg) **Polar Day** | ![](themes/metro-day/preview.jpg) **Metro Day** | ![](themes/flux-day/preview.jpg) **Flux Day** |

**Aequalyn** and **Aequalyn Day** carry the Aequalyn mark (night and day) or its name
(dusk and dawn), never both, from `tools/brand/`, in the project's own teal, over soft
light, ripples and flowing ribbons. Each picture has a live loop too: four stills and
four loops in all.

| | |
| --- | --- |
| ![](themes/aequalyn/preview.jpg) **Aequalyn** · 3 colours | ![](themes/aequalyn-day/preview.jpg) **Aequalyn Day** |

## Ported

| |
| --- |
| ![](themes/spectral/preview.jpg) **Spectral** by qempexe · the full neon spectrum on a near-black base, six 4K stills and two live loops |

`wallpapers/` holds wallpapers of their own, not part of any theme: stills at 4K and
two live loops. They show in every wallpaper picker.

```sh
python3 tools/artgen.py all            # every theme and wallpaper (needs resvg, magick, ffmpeg)
python3 tools/artgen.py theme cosmos   # one topic, dark and light
python3 tools/artgen.py walls          # the wallpapers of their own
```

Live wallpapers move with `mpvpaper`; without it they show as a still.

## Format

```
themes/<id>/
├── theme.json      name, family, author, variant, palette (and, for drawn ones, about, colors)
├── backgrounds/    images or videos, used in name order
└── preview.jpg     card image in the picker (optional; defaults to the first background)
```

`palette` uses the shell's keys: `bgBase bgSurface bgHover bgSelected bgBorder
textPrimary textSecondary textMuted accentPrimary accentCyan accentGreen
accentOrange accentRed`. It may also carry `borderColors`, two or more colours the
window borders run through (Spectral's six-colour gradient); without it they run from
`accentPrimary` to `accentCyan`.

Leave `palette` out and the theme is a **pack**: it brings backgrounds and
the colours come from whichever background is showing.

Folder themes work unchanged: a `colors.toml` (accent, foreground,
background, color0–15) is mapped onto the palette.

```sh
aequalyn-themes install <git-url>
aequalyn-themes set <id>
```

Others' themes install from the Store, reviewed ([aequalyn-market](https://github.com/Aequalyn/aequalyn-market)). User themes go in `~/.config/aequalyn/themes/` and override shipped ones with the same id.
The wallpapers of their own are installed to `~/.local/share/aequalyn/wallpapers/`.

## Documentation

- `SECURITY.md` — security model and concerns.
- `SKILL.md` — development/install skill reference.
- `THEMES.md` — theme format and usage.
