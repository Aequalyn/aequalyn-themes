# aequalyn-themes

Themes for Aequalyn. Each theme is a palette plus backgrounds that belong to it.

| | | |
| --- | --- | --- |
| ![](themes/lumen/preview.jpg) **Lumen** | ![](themes/basalt/preview.jpg) **Basalt** | ![](themes/ember/preview.jpg) **Ember** |
| ![](themes/tidal/preview.jpg) **Tidal** | ![](themes/meadow/preview.jpg) **Meadow** (light) | ![](themes/nocturne/preview.jpg) **Nocturne** (pack) |

## Format

```
themes/<id>/
├── theme.json      name, family, author, variant, palette
├── backgrounds/    images or videos, used in name order
└── preview.jpg     card image in Atelier (optional; defaults to the first background)
```

`palette` uses the shell's keys: `bgBase bgSurface bgHover bgSelected bgBorder
textPrimary textSecondary textMuted accentPrimary accentCyan accentGreen
accentOrange accentRed`.

Leave `palette` out and the theme is a **pack**: it brings backgrounds and
the colours come from whichever background is showing.

Omarchy themes work unchanged: a `colors.toml` (accent, foreground,
background, color0–15) is mapped onto the palette.

```sh
aequalyn-themes install https://github.com/<user>/omarchy-<name>-theme
aequalyn-themes set <id>
```

User themes go in `~/.config/aequalyn/themes/` and override shipped ones with the same id.
