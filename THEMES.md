# Aequalyn Themes — format and usage

Themes for Aequalyn: a palette plus backgrounds that belong to it.

## Format

```
themes/<id>/
├── theme.json      name, family, author, variant, palette (and optionally about, colors)
├── backgrounds/    images or videos, used in name order
└── preview.jpg     card image in the picker (optional; defaults to first background)
```

`palette` keys: `bgBase bgSurface bgHover bgSelected bgBorder textPrimary textSecondary
textMuted accentPrimary accentCyan accentGreen accentOrange accentRed`. Optional
`borderColors` (two or more colours for window borders).

Leave `palette` out → the theme is a **pack**: backgrounds only, colours come from
whichever background is showing.

Folder themes (a `colors.toml` with accent/foreground/background/color0–15) are mapped
onto the palette.

## Commands

```sh
aequalyn-themes install <git-url>
aequalyn-themes set <id>
aequalyn-themes list
```

User themes go in `~/.config/aequalyn/themes/` and override shipped ones with the same
id. Wallpapers of their own install to `~/.local/share/aequalyn/wallpapers/`.

## Security

Themes are data: no scripts, executables or symlinks; no config writes; no absolute
paths or remote URLs; images sniffed by magic bytes and size-capped. See `SECURITY.md`.
