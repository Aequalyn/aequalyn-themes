#!/usr/bin/env python3
"""artgen: Aequalyn's own themes and wallpapers, drawn from a handful of colours.

Every picture is composed here as layered SVG (sky, glow, stars, nebulae, ridges,
trees, waves, dunes, aurora, city, flowing ribbons, the Aequalyn mark and name from
tools/brand/) from one to four seed colours, so
the themes, their palettes and their wallpapers all come from the same colours.

  stills  rendered at 3840x2160 with resvg, then given a fine film grain
  live    the same layers rendered at 1920x1080 and set in slow, seamless motion
          with ffmpeg: parallax sway, twinkling, drifting light (a loop: the last
          frame meets the first)

  python3 tools/artgen.py all              everything, into themes/ and wallpapers/
  python3 tools/artgen.py theme cosmos     one topic (its dark and light themes)
  python3 tools/artgen.py walls            the standalone wallpapers
  python3 tools/artgen.py palettes         rewrite only the themes' theme.json
  python3 tools/artgen.py preview cosmos   one quick 960x540 still per mood, into
                                           $ARTGEN_OUT (or the system's temp folder)

Needs: resvg, ImageMagick (magick), ffmpeg. Deterministic: the same seed draws the
same picture.
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W4, H4 = 3840, 2160
WL, HL = 1920, 1080
LIVE_SECONDS = 12
LIVE_FPS = 30

# ---- colour ----------------------------------------------------------------------------

def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return hexc([a[i] + (b[i] - a[i]) * t for i in range(3)])


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def to_hsl(h):
    r, g, b = (v / 255 for v in rgb(h))
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        hh = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        hh = (b - r) / d + 2
    else:
        hh = (r - g) / d + 4
    return hh / 6, s, l


def from_hsl(hh, s, l):
    def f(n):
        k = (n + hh * 12) % 12
        a = s * min(l, 1 - l)
        return l - a * max(-1, min(k - 3, 9 - k, 1))
    return hexc((f(0) * 255, f(8) * 255, f(4) * 255))


def shift(h, dh=0.0, ds=0.0, dl=0.0):
    hh, s, l = to_hsl(h)
    return from_hsl((hh + dh) % 1, max(0, min(1, s + ds)), max(0, min(1, l + dl)))


def readable(fg, bg, need):
    """fg nudged lighter or darker (away from bg) until it reads at `need` contrast"""
    hh, s, l = to_hsl(fg)
    up = lum(bg) < 0.2
    for _ in range(60):
        if contrast(from_hsl(hh, s, l), bg) >= need:
            break
        l = min(1, l + 0.02) if up else max(0, l - 0.02)
    return from_hsl(hh, s, l)

# ---- the topics ------------------------------------------------------------------------
# keys: 1 to 4 seed colours. Every theme, palette and picture of a topic comes from them.

TOPICS = {
    "cosmos": {"name": "Cosmos", "keys": ["#24206b", "#7a4fd6", "#e45ba8", "#45d4e6"], "scene": "cosmos",
               "about": "Deep space: a nebula in four colours, a ringed planet, a field of stars."},
    "canopy": {"name": "Canopy", "keys": ["#2f7a55", "#f0c36a"], "scene": "forest",
               "about": "A pine forest in layers of mist, under the moon or the morning sun."},
    "abyss": {"name": "Abyss", "keys": ["#0f5a80", "#4fd8c8"], "scene": "ocean",
              "about": "The open sea, wave over wave, a moon or a sun on the water."},
    "summit": {"name": "Summit", "keys": ["#6a80b0"], "scene": "peaks",
               "about": "One colour, many ridges: mountains fading into the distance."},
    "dune": {"name": "Dune", "keys": ["#eaa76a", "#c4543f", "#5e3c72"], "scene": "desert",
             "about": "Dunes in three colours, their shadow sides deep, a low sun."},
    "polar": {"name": "Polar", "keys": ["#3fe08f", "#2bb6cc", "#9d6cf2"], "scene": "aurora",
              "about": "The northern lights over snow, green to violet."},
    "metro": {"name": "Metro", "keys": ["#f2b544", "#3d6ff0"], "scene": "city",
              "about": "A city skyline, its windows lit warm against a blue hour."},
    "flux": {"name": "Flux", "keys": ["#ff6b6b", "#ffd166", "#18d1a0", "#4d96ff"], "scene": "flow",
             "about": "Four colours flowing into each other: ribbons and soft light."},
    "aequalyn": {"name": "Aequalyn", "keys": ["#24434a", "#4fc1b0", "#6fb7d8"], "scene": "brand",
                 "about": "The Aequalyn mark, or its name, in its own teal, with soft light and slow ripples."},
}

# standalone wallpapers: not part of any theme
WALLS = [
    {"id": "nebula-crimson", "scene": "cosmos", "keys": ["#3a0f2e", "#d6336c", "#ff9f43"], "mood": "night", "seed": 71},
    {"id": "glacier", "scene": "peaks", "keys": ["#8fc6e8"], "mood": "day", "seed": 12},
    {"id": "canyon-dusk", "scene": "desert", "keys": ["#d9824a", "#8a2f3c", "#2e2350"], "mood": "dusk", "seed": 33},
    {"id": "lagoon", "scene": "ocean", "keys": ["#13a3b8", "#bff3e8"], "mood": "day", "seed": 54},
    {"id": "snowpine", "scene": "forest", "keys": ["#5d7fa3", "#e8eef7"], "mood": "night", "seed": 8},
    {"id": "lavender-flow", "scene": "flow", "keys": ["#b39ddb", "#f8bbd0", "#80deea"], "mood": "day", "seed": 27},
    {"id": "emerald-aurora", "scene": "aurora", "keys": ["#22f5a0", "#0bb0ff"], "mood": "dusk", "seed": 91},
    {"id": "neon-city", "scene": "city", "keys": ["#ff4fd8", "#30e0ff"], "mood": "night", "seed": 64},
    {"id": "live-starfield", "scene": "cosmos", "keys": ["#101a3a", "#6c8cff", "#b06cff"], "mood": "night", "seed": 5, "live": True},
    {"id": "live-tide", "scene": "ocean", "keys": ["#0a3d62", "#3dc1d3"], "mood": "dusk", "seed": 19, "live": True},
]

# ---- the palette of a theme --------------------------------------------------------------

RED_DARK, RED_LIGHT = "#ef6b73", "#c8323e"


def palette(keys, variant):
    k = list(keys) + [None] * 4
    c1 = keys[0]
    # every colour after the first is an accent; fewer keys borrow neighbours on the wheel
    acc = keys[1] if len(keys) > 1 else shift(c1, 0.0, 0.15, 0.12)
    cyan = k[2] or shift(acc, 0.45, 0, 0)
    green = k[3] or shift(acc, -0.25, 0, 0)
    orange = shift(acc, 0.08, 0.05, 0.05) if len(keys) < 3 else shift(k[2], -0.12, 0, 0)
    # the surfaces: the first colour's hue, quietly, at set steps of lightness, so every
    # theme has the same clear steps whatever its colour
    hh, ss, _ = to_hsl(c1)
    def tone(l, sat):
        return from_hsl(hh, min(ss, sat), l)
    if variant == "dark":
        base = tone(0.075, 0.28)
        p = {
            "bgBase": base,
            "bgSurface": tone(0.105, 0.26),
            "bgHover": tone(0.135, 0.26),
            "bgSelected": tone(0.20, 0.34),
            "bgBorder": tone(0.19, 0.22),
        }
        text = mix("#ecebef", c1, 0.06)
        p["textPrimary"] = readable(text, base, 12)
        p["textSecondary"] = readable(mix(text, base, 0.28), base, 7)
        p["textMuted"] = readable(mix(text, base, 0.55), base, 3.2)
        for key, col in (("accentPrimary", acc), ("accentCyan", cyan), ("accentGreen", green),
                         ("accentOrange", orange), ("accentRed", RED_DARK)):
            p[key] = readable(col, base, 4.5)
    else:
        base = tone(0.955, 0.3)
        p = {
            "bgBase": base,
            "bgSurface": tone(0.925, 0.3),
            "bgHover": tone(0.895, 0.3),
            "bgSelected": tone(0.84, 0.38),
            "bgBorder": tone(0.82, 0.25),
        }
        text = mix("#1c1b22", c1, 0.12)
        p["textPrimary"] = readable(text, base, 12)
        p["textSecondary"] = readable(mix(text, base, 0.25), base, 7)
        p["textMuted"] = readable(mix(text, base, 0.5), base, 3.2)
        for key, col in (("accentPrimary", acc), ("accentCyan", cyan), ("accentGreen", green),
                         ("accentOrange", orange), ("accentRed", RED_LIGHT)):
            p[key] = readable(col, base, 4.5)
    return p

# ---- shapes ----------------------------------------------------------------------------

def ridge(rng, w, base, amp, harmonics=7, rough=1.15):
    """a periodic profile over the width (it tiles): (coef, phase) per harmonic"""
    cs = []
    for k in range(1, harmonics + 1):
        cs.append((amp * rng.uniform(0.35, 1.0) / (k ** rough), rng.uniform(0, 2 * math.pi), k))
    return lambda x: base + sum(a * math.sin(2 * math.pi * k * x / w + ph) for a, ph, k in cs)


def path_under(f, w, h, step=6, x0=0, x1=None):
    x1 = w if x1 is None else x1
    pts = ["M%.1f,%.1f" % (x0, h + 2)]
    x = x0
    while x <= x1:
        pts.append("L%.1f,%.1f" % (x, f(x)))
        x += step
    pts.append("L%.1f,%.1f Z" % (x1, h + 2))
    return " ".join(pts)


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.defs, self.body, self.n = [], [], 0

    def id(self, p="d"):
        self.n += 1
        return "%s%d" % (p, self.n)

    def lin(self, stops, x1=0, y1=0, x2=0, y2=1):
        i = self.id("g")
        s = "".join('<stop offset="%.3f" stop-color="%s" stop-opacity="%.3f"/>' % (o, c, a) for o, c, a in stops)
        self.defs.append('<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>' % (i, x1, y1, x2, y2, s))
        return "url(#%s)" % i

    def rad(self, stops, cx=0.5, cy=0.5, r=0.5):
        i = self.id("r")
        s = "".join('<stop offset="%.3f" stop-color="%s" stop-opacity="%.3f"/>' % (o, c, a) for o, c, a in stops)
        self.defs.append('<radialGradient id="%s" cx="%s" cy="%s" r="%s">%s</radialGradient>' % (i, cx, cy, r, s))
        return "url(#%s)" % i

    def blur(self, sd):
        i = self.id("b")
        self.defs.append('<filter id="%s" x="-50%%" y="-50%%" width="200%%" height="200%%"><feGaussianBlur stdDeviation="%.1f"/></filter>' % (i, sd))
        return "url(#%s)" % i

    def clouds(self, freq, octaves, seed, color, strength=1.0, bias=-0.45):
        """fractal noise as a soft cloud of one colour (alpha from the noise)"""
        i = self.id("n")
        r, g, b = (v / 255 for v in rgb(color))
        self.defs.append(
            '<filter id="%s" x="0" y="0" width="100%%" height="100%%" color-interpolation-filters="sRGB">'
            '<feTurbulence type="fractalNoise" baseFrequency="%.5f" numOctaves="%d" seed="%d" stitchTiles="stitch"/>'
            '<feColorMatrix type="matrix" values="0 0 0 0 %.4f  0 0 0 0 %.4f  0 0 0 0 %.4f  %.3f 0 0 0 %.3f"/>'
            '</filter>' % (i, freq, octaves, seed, r, g, b, 5.0 * strength, (bias - 2.1) * strength))
        return "url(#%s)" % i

    def add(self, s):
        self.body.append(s)

    def text(self):
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><defs>%s</defs>%s</svg>'
                % (self.w, self.h, self.w, self.h, "".join(self.defs), "".join(self.body)))

# ---- moods: the light of the scene -------------------------------------------------------
# night / dusk for the dark themes, day / dawn for the light ones

def sky_of(keys, mood):
    c1 = keys[0]
    c2 = keys[1] if len(keys) > 1 else shift(c1, 0.05, 0.1, 0.15)
    c3 = keys[2] if len(keys) > 2 else shift(c2, -0.06, 0, 0.1)
    if mood == "night":
        return [(0, mix(c1, "#020208", 0.88), 1), (0.55, mix(c1, "#05050d", 0.62), 1), (1, mix(c2, "#0a0a14", 0.55), 1)]
    if mood == "dusk":
        return [(0, mix(c1, "#06060e", 0.78), 1), (0.5, mix(c3, c1, 0.5), 1), (0.85, mix(c2, "#ffd9a8", 0.25), 1), (1, mix(c2, "#ffe7c4", 0.45), 1)]
    if mood == "dawn":
        return [(0, mix(c1, "#f4f1fb", 0.4), 1), (0.6, mix(c3, "#ffe9d6", 0.45), 1), (1, mix(c2, "#fff1e0", 0.35), 1)]
    return [(0, mix(c1, "#ffffff", 0.3), 1), (0.65, mix(c1, "#ffffff", 0.6), 1), (1, mix(c2, "#ffffff", 0.72), 1)]


def dark(mood):
    return mood in ("night", "dusk")

# ---- scenes ------------------------------------------------------------------------------
# each returns layers: [(name, svg_text, motion)] back to front. motion:
#   {"sway": px at 1920 wide, "period": seconds per sway, "phase": 0..1,
#    "pulse": 0..1 opacity swing, "cross": 0|1 (two takes crossfading over the loop)}


def layer_sky(keys, mood, w, h):
    s = Svg(w, h)
    s.add('<rect width="%d" height="%d" fill="%s"/>' % (w, h, s.lin(sky_of(keys, mood))))
    return s


def add_stars(s, rng, n, w, h, ymax, colors, big=0.04):
    for _ in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, ymax) ** 1.0
        r = rng.uniform(0.6, 1.7) * w / 3840 * 2
        if rng.random() < big:
            r *= 2.4
            s.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="0.18"/>' % (x, y, r * 4, rng.choice(colors)))
        s.add('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s" opacity="%.2f"/>' % (x, y, r, rng.choice(colors), rng.uniform(0.45, 1)))


def star_layers(rng, n, w, h, ymax, colors, big=0.04):
    """stars as two layers fading in turn: each star dims and brightens in its own half"""
    a, b = Svg(w, h), Svg(w, h)
    add_stars(a, rng, n // 2, w, h, ymax, colors, big)
    add_stars(b, rng, n - n // 2, w, h, ymax, colors, big)
    return [("stars-a", a.text(), {"pulse": 0.7, "phase": 0.0}), ("stars-b", b.text(), {"pulse": 0.7, "phase": 0.5})]


def add_glow(s, cx, cy, r, color, strength=0.55):
    s.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (cx, cy, r * 3.4, s.rad([(0, color, strength), (0.3, color, strength * 0.3), (1, color, 0)])))


def scene_cosmos(keys, mood, seed, w, h):
    rng = random.Random(seed)
    k = keys + [shift(keys[-1], 0.15, 0, 0)] * (4 - len(keys))
    layers = []
    sky = layer_sky(keys, "night" if dark(mood) else "dawn", w, h)
    layers.append(("sky", sky.text(), {}))
    # nebula: noise clouds in each colour, laid along a diagonal band
    neb = Svg(w, h)
    band = neb.lin([(0, "#fff", 0), (0.35, "#fff", 1), (0.65, "#fff", 1), (1, "#fff", 0)], 0, 0, 1, 1)
    mid = neb.id("m")
    neb.defs.append('<mask id="%s"><rect width="%d" height="%d" fill="%s"/></mask>' % (mid, w, h, band))
    neb.add('<g mask="url(#%s)">' % mid)
    for i, c in enumerate(k[1:]):
        col = c if dark(mood) else mix(c, "#ffffff", 0.35)
        neb.add('<rect width="%d" height="%d" filter="%s" opacity="%.2f"/>' % (
            w, h, neb.clouds(1.1 / w * (1 + i * 0.6), 5, seed + i * 7, col, 1.0, -0.5 - i * 0.05), 0.9 if dark(mood) else 0.6))
    neb.add('</g>')
    layers.append(("nebula", neb.text(), {"sway": 10, "period": 12, "pulse": 0.12}))
    if dark(mood):
        layers += star_layers(rng, int(900 * w / 3840), w, h, h, ["#ffffff", "#ffffff", mix(k[3], "#fff", 0.6), mix(k[2], "#fff", 0.6)])
    # a ringed planet, lit from the side
    pl = Svg(w, h)
    cx, cy, r = w * rng.uniform(0.68, 0.8), h * rng.uniform(0.3, 0.42), h * 0.16
    body = pl.rad([(0, mix(k[2], "#fff", 0.35), 1), (0.55, k[1], 1), (1, mix(k[0], "#000", 0.5), 1)], 0.32, 0.3, 0.85)
    ring = pl.lin([(0, k[3], 0), (0.3, mix(k[3], "#fff", 0.3), 0.85), (0.7, k[2], 0.7), (1, k[2], 0)], 0, 0, 1, 0)
    add_glow(pl, cx, cy, r * 0.5, k[2], 0.22)
    pl.add('<g transform="rotate(-18 %.1f %.1f)">' % (cx, cy))
    pl.add('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" stroke="%s" stroke-width="%.1f" opacity="0.55"/>' % (cx, cy, r * 2.1, r * 0.42, ring, r * 0.16))
    pl.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (cx, cy, r, body))
    clip = pl.id("c")
    pl.defs.append('<clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath>' % (clip, cx - r * 2.5, cy, r * 5, r * 2))
    pl.add('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" stroke="%s" stroke-width="%.1f" clip-path="url(#%s)"/>' % (cx, cy, r * 2.1, r * 0.42, ring, r * 0.16, clip))
    pl.add('</g>')
    layers.append(("planet", pl.text(), {"sway": 14, "period": 12, "phase": 0.25}))
    return layers


def ridge_layers(keys, mood, seed, w, h, n, top, spread, amp, colors_far_near, trees=False, snow=False):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        d = i / max(1, n - 1)                 # 0 far .. 1 near
        base = h * (top + spread * d)
        f = ridge(rng, w, base, h * amp * (0.6 + 0.8 * d), 8, 1.05 + 0.25 * d)
        col = mix(colors_far_near[0], colors_far_near[1], d ** 0.9)
        s = Svg(w, h)
        s.add('<path d="%s" fill="%s"/>' % (path_under(f, w, h), col))
        if snow and d < 0.6:
            # snow caps: the top of the ridge, lighter
            pts = []
            x = 0
            while x <= w:
                pts.append((x, f(x)))
                x += 8
            poly = " ".join("%.1f,%.1f" % p for p in pts) + " " + " ".join("%.1f,%.1f" % (x, y + h * 0.03 * (0.4 + 0.6 * abs(math.sin(x / 90.0)))) for x, y in reversed(pts))
            s.add('<polygon points="%s" fill="%s" opacity="0.6"/>' % (poly, mix(col, "#ffffff", 0.7)))
        if trees:
            tcol = mix(col, "#000000", 0.08 * d)
            x = rng.uniform(0, 30)
            while x < w:
                th = h * (0.03 + 0.07 * d) * rng.uniform(0.6, 1.25)
                tw = th * rng.uniform(0.28, 0.4)
                y = f(x) + h * 0.006
                s.add('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="%s"/>' % (x - tw / 2, y, x, y - th, x + tw / 2, y, tcol))
                x += tw * rng.uniform(0.45, 1.1)
        out.append((s, d))
    return out


def scene_forest(keys, mood, seed, w, h):
    rng = random.Random(seed)
    c1, c2 = keys[0], keys[1] if len(keys) > 1 else shift(keys[0], 0.1, 0, 0.3)
    layers = [("sky", layer_sky(keys, mood, w, h).text(), {})]
    g = Svg(w, h)
    sx, sy = w * rng.uniform(0.25, 0.75), h * (0.28 if dark(mood) else 0.32)
    if dark(mood):
        layers += star_layers(rng, int(260 * w / 3840), w, h, h * 0.55, ["#ffffff", mix(c2, "#fff", 0.7)], 0.02)
        add_glow(g, sx, sy, h * 0.05, mix(c2, "#ffffff", 0.6), 0.35)
        g.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (sx, sy, h * 0.045, mix(c2, "#fffbe8", 0.75)))
    else:
        add_glow(g, sx, sy, h * 0.07, mix(c2, "#ffffff", 0.3), 0.35)
        g.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (sx, sy, h * 0.05, mix(c2, "#fffdf4", 0.6)))
    layers.append(("light", g.text(), {"pulse": 0.1}))
    sky_h = sky_of(keys, mood)[-1][1]
    far = mix(c1, sky_h, 0.72)
    near = mix(c1, "#030806", 0.82) if dark(mood) else mix(c1, "#10301f", 0.35)
    rl = ridge_layers(keys, mood, seed + 1, w, h, 5, 0.5, 0.36, 0.05, (far, near), trees=True)
    for i, (s, d) in enumerate(rl):
        layers.append(("ridge%d" % i, s.text(), {"sway": 4 + 22 * d, "period": 12, "phase": 0.1 * i}))
        if i < len(rl) - 1:
            fog = Svg(w, h)
            fy = h * (0.55 + 0.33 * d)
            fog.add('<rect y="%.1f" width="%d" height="%.1f" fill="%s"/>' % (fy - h * 0.06, w, h * 0.12, fog.lin([(0, sky_h, 0), (0.5, sky_h, 0.35 if dark(mood) else 0.4), (1, sky_h, 0)])))
            layers.append(("fog%d" % i, fog.text(), {"sway": 30 + 20 * d, "period": 12, "phase": 0.5 + 0.1 * i, "pulse": 0.15}))
    return layers


def scene_ocean(keys, mood, seed, w, h):
    rng = random.Random(seed)
    c1, c2 = keys[0], keys[1] if len(keys) > 1 else shift(keys[0], 0.08, 0, 0.25)
    layers = [("sky", layer_sky(keys, mood, w, h).text(), {})]
    horizon = h * 0.58
    g = Svg(w, h)
    sx = w * rng.uniform(0.3, 0.7)
    sy = horizon - h * (0.2 if dark(mood) else 0.24)
    lightc = mix(c2, "#fffbe8", 0.7)
    if dark(mood):
        layers += star_layers(rng, int(320 * w / 3840), w, h, horizon * 0.85, ["#ffffff", mix(c2, "#fff", 0.6)], 0.02)
    add_glow(g, sx, sy, h * 0.05, lightc, 0.4)
    g.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (sx, sy, h * 0.05, lightc))
    layers.append(("light", g.text(), {"pulse": 0.08}))
    sea = Svg(w, h)
    deep = mix(c1, "#01060c", 0.75) if dark(mood) else mix(c1, "#e8f6fb", 0.25)
    sea.add('<rect y="%.1f" width="%d" height="%.1f" fill="%s"/>' % (horizon, w, h - horizon, sea.lin([(0, mix(c2, deep, 0.55), 1), (1, deep, 1)])))
    # the light's path on the water
    sea.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" filter="%s"/>' % (
        sx - h * 0.09, horizon, h * 0.18, h - horizon, sea.lin([(0, lightc, 0.55), (1, lightc, 0.05)]), sea.blur(h * 0.012)))
    layers.append(("sea", sea.text(), {}))
    n = 7
    for i in range(n):
        d = i / (n - 1)
        y0 = horizon + (h - horizon) * (0.04 + 0.96 * d ** 1.6)
        f = ridge(rng, w, y0, h * (0.004 + 0.02 * d), 9, 0.9)
        s = Svg(w, h)
        top = mix(c2, deep, 0.35 + 0.4 * (1 - d)) if dark(mood) else mix(c2, "#ffffff", 0.35 * (1 - d))
        s.add('<path d="%s" fill="%s"/>' % (path_under(f, w, h), s.lin([(0, top, 1), (0.15, mix(top, deep, 0.6), 1), (1, deep, 1)])))
        # foam on the crests, as a thin light line
        crest = " ".join("%s%.1f,%.1f" % ("M" if x == 0 else "L", x, f(x)) for x in range(0, w + 1, 6))
        s.add('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" opacity="%.2f"/>' % (crest, mix(c2, "#ffffff", 0.6), 1 + 3 * d, 0.25 + 0.4 * d))
        layers.append(("wave%d" % i, s.text(), {"sway": 6 + 40 * d, "period": 6 + 6 * (1 - d), "phase": rng.random()}))
    return layers


def scene_peaks(keys, mood, seed, w, h):
    rng = random.Random(seed)
    c1 = keys[0]
    layers = [("sky", layer_sky(keys, mood, w, h).text(), {})]
    g = Svg(w, h)
    sx, sy = w * rng.uniform(0.2, 0.8), h * 0.24
    if dark(mood):
        layers += star_layers(rng, int(400 * w / 3840), w, h, h * 0.6, ["#ffffff", mix(c1, "#fff", 0.6)], 0.02)
        add_glow(g, sx, sy, h * 0.04, mix(c1, "#ffffff", 0.75), 0.3)
        g.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (sx, sy, h * 0.035, mix(c1, "#ffffff", 0.85)))
    else:
        add_glow(g, sx, sy, h * 0.07, "#ffffff", 0.35)
    layers.append(("light", g.text(), {"pulse": 0.06}))
    sky_h = sky_of(keys, mood)[-1][1]
    far = mix(c1, sky_h, 0.65)
    near = mix(c1, "#05070c", 0.8) if dark(mood) else mix(c1, "#1b2335", 0.45)
    for i, (s, d) in enumerate(ridge_layers(keys, mood, seed + 3, w, h, 6, 0.38, 0.42, 0.11, (far, near), snow=not dark(mood) or mood == "dusk")):
        layers.append(("ridge%d" % i, s.text(), {"sway": 3 + 26 * d, "period": 12, "phase": 0.08 * i}))
    return layers


def scene_desert(keys, mood, seed, w, h):
    rng = random.Random(seed)
    k = keys + [shift(keys[-1], -0.08, 0, -0.15)] * (3 - len(keys))
    layers = [("sky", layer_sky([k[2], k[0], k[1]], mood, w, h).text(), {})]
    g = Svg(w, h)
    sx, sy = w * rng.uniform(0.3, 0.7), h * (0.42 if mood in ("dusk", "dawn") else 0.26)
    sunc = mix(k[0], "#fff3dc", 0.5)
    if dark(mood):
        layers += star_layers(rng, int(220 * w / 3840), w, h, h * 0.45, ["#ffffff"], 0.01)
    add_glow(g, sx, sy, h * 0.08, sunc, 0.5)
    g.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (sx, sy, h * 0.07, sunc))
    layers.append(("sun", g.text(), {"pulse": 0.1}))
    n = 5
    for i in range(n):
        d = i / (n - 1)
        f = ridge(rng, w, h * (0.52 + 0.36 * d), h * (0.05 + 0.04 * d), 5, 1.6)
        lit = mix(k[0], "#fff2e2", 0.25 * (1 - d)) if not dark(mood) else mix(k[0], k[2], 0.3 + 0.35 * d)
        shade = mix(k[1], k[2], 0.35 + 0.5 * d)
        s = Svg(w, h)
        # a dune: its crest catching the light, falling into shadow lower down
        s.add('<path d="%s" fill="%s"/>' % (path_under(f, w, h), s.lin([(0, lit, 1), (0.18, mix(lit, shade, 0.5), 1), (0.55, shade, 1), (1, mix(shade, "#000000", 0.25), 1)])))
        # the wind's ripples in the sand, following the dune's shape
        for r in range(1, 5):
            off = h * 0.018 * r * (0.6 + 0.8 * d)
            line = " ".join("%s%.1f,%.1f" % ("M" if x == 0 else "L", x, f(x) + off + h * 0.003 * math.sin(x / (40 + 30 * d) + r)) for x in range(0, w + 1, 8))
            s.add('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" opacity="%.2f"/>' % (line, mix(lit, "#ffffff", 0.3), 0.8 + d, 0.18 - 0.03 * r))
        layers.append(("dune%d" % i, s.text(), {"sway": 3 + 20 * d, "period": 12, "phase": 0.12 * i}))
    return layers


def scene_aurora(keys, mood, seed, w, h):
    rng = random.Random(seed)
    k = keys + [shift(keys[-1], 0.12, 0, 0)] * (3 - len(keys))
    sky_mood = "night" if dark(mood) else "dawn"
    layers = [("sky", layer_sky([mix(k[0], "#0a1a2a", 0.7)] + k[1:], sky_mood, w, h).text(), {})]
    if dark(mood):
        layers += star_layers(rng, int(700 * w / 3840), w, h, h * 0.8, ["#ffffff", mix(k[0], "#fff", 0.7)], 0.03)
    for j in range(2):
        a = Svg(w, h)
        for i, c in enumerate(k):
            # a curtain: bright along its lower edge, fading up into the dark, with fine rays
            f = ridge(rng, w, h * (0.34 + 0.08 * i), h * 0.1, 4, 0.9)
            tall = h * (0.2 + 0.08 * rng.random())
            col = c if dark(mood) else mix(c, "#ffffff", 0.15)
            pts = []
            x = -40
            while x <= w + 40:
                pts.append((x, f(x)))
                x += 12
            poly = " ".join("%.1f,%.1f" % (x, y - tall * (0.7 + 0.3 * math.sin(x / 210.0 + i))) for x, y in pts) + " " + " ".join("%.1f,%.1f" % (x, y) for x, y in reversed(pts))
            a.add('<polygon points="%s" fill="%s" filter="%s" opacity="%.2f"/>' % (
                poly, a.lin([(0, col, 0), (0.7, col, 0.35), (0.94, mix(col, "#ffffff", 0.35), 0.85), (1, col, 0)]), a.blur(h * 0.008), 0.85 if dark(mood) else 0.55))
            for _ in range(int(140 * w / 3840)):
                x = rng.uniform(0, w)
                ht = tall * rng.uniform(0.4, 1.0)
                a.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="%.2f" filter="%s"/>' % (
                    x, f(x) - ht, w * 0.0014, ht, a.lin([(0, col, 0), (1, mix(col, "#ffffff", 0.4), 1)]), rng.uniform(0.08, 0.28), a.blur(1.5)))
        layers.append(("aurora%d" % j, a.text(), {"sway": 40 + 30 * j, "period": 12, "phase": 0.5 * j, "pulse": 0.35, "cross": j}))
    sky_h = sky_of(k, sky_mood)[-1][1]
    snowfar = mix(sky_h, "#dfe9f2", 0.35 if dark(mood) else 0.6)
    snownear = mix("#0c1622", "#1b2a3a", 0.5) if dark(mood) else "#f2f6fb"
    for i, (s, d) in enumerate(ridge_layers(k, mood, seed + 9, w, h, 3, 0.72, 0.16, 0.04, (snowfar, snownear))):
        layers.append(("hill%d" % i, s.text(), {"sway": 4 + 16 * d, "period": 12}))
    return layers


def scene_city(keys, mood, seed, w, h):
    rng = random.Random(seed)
    c1, c2 = keys[0], keys[1] if len(keys) > 1 else shift(keys[0], 0.55, 0, 0)
    sky_keys = [c2, mix(c2, c1, 0.4), c1]
    layers = [("sky", layer_sky(sky_keys, mood, w, h).text(), {})]
    if dark(mood):
        layers += star_layers(rng, int(180 * w / 3840), w, h, h * 0.4, ["#ffffff"], 0.01)
    sky_h = sky_of(sky_keys, mood)[-1][1]
    for li, depth in enumerate((0.0, 0.5, 1.0)):
        s = Svg(w, h)
        col = mix(mix(c2, "#04060c", 0.7) if dark(mood) else mix(c2, "#3a4458", 0.5), sky_h, 0.55 * (1 - depth))
        x = rng.uniform(-40, 0)
        ground = h * (0.86 + 0.04 * depth)
        while x < w:
            bw = w * rng.uniform(0.025, 0.06) * (0.8 + 0.5 * depth)
            bh = h * rng.uniform(0.12, 0.42) * (0.55 + 0.6 * depth)
            top = ground - bh
            s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x, top, bw, h - top, col))
            if rng.random() < 0.25:
                s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x + bw * 0.45, top - h * 0.04, bw * 0.08, h * 0.04, col))
            if dark(mood) or mood == "dawn":
                cw = max(3.0, bw / 9)
                for wx in range(int(bw // (cw * 1.7))):
                    for wy in range(int(bh // (cw * 2.2))):
                        if rng.random() < (0.35 if dark(mood) else 0.08):
                            lc = c1 if rng.random() < 0.8 else mix(c1, "#ffffff", 0.5)
                            s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="%.2f"/>' % (
                                x + cw * 0.6 + wx * cw * 1.7, top + cw + wy * cw * 2.2, cw, cw * 1.2, lc, rng.uniform(0.5, 0.95) * (0.5 + 0.5 * depth)))
            x += bw * rng.uniform(1.0, 1.35)
        haze = Svg(w, h)
        haze.add('<rect y="%.1f" width="%d" height="%.1f" fill="%s"/>' % (h * 0.6, w, h * 0.4, haze.lin([(0, sky_h, 0), (1, mix(c1, sky_h, 0.7) if dark(mood) else sky_h, 0.35 * (1 - depth))])))
        layers.append(("city%d" % li, s.text(), {"sway": 3 + 12 * depth, "period": 12, "pulse": 0.12 if dark(mood) and li == 2 else 0}))
        layers.append(("haze%d" % li, haze.text(), {"pulse": 0.15}))
    return layers


def scene_flow(keys, mood, seed, w, h):
    rng = random.Random(seed)
    k = keys + [shift(keys[i % len(keys)], 0.18 * (i + 1), 0, 0) for i in range(4 - len(keys))]
    base = mix(k[0], "#07070c", 0.85) if dark(mood) else mix(k[0], "#fbfaf7", 0.9)
    s0 = Svg(w, h)
    s0.add('<rect width="%d" height="%d" fill="%s"/>' % (w, h, base))
    layers = [("base", s0.text(), {})]
    blobs = Svg(w, h)
    bl = blobs.blur(h * 0.09)
    for i, c in enumerate(k):
        cx, cy = w * (0.15 + 0.7 * rng.random()), h * (0.15 + 0.7 * rng.random())
        r = h * rng.uniform(0.3, 0.5)
        blobs.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="%.2f" filter="%s"/>' % (cx, cy, r, c, 0.75 if dark(mood) else 0.55, bl))
    layers.append(("blobs", blobs.text(), {"sway": 50, "period": 12, "pulse": 0.15}))
    for j in range(2):
        rib = Svg(w, h)
        for i in range(9):
            t = i / 8
            f = ridge(rng, w, h * (0.25 + 0.5 * t), h * 0.18, 3, 0.8)
            col = rib.lin([(0, k[i % 4], 0.0), (0.3, k[i % 4], 0.85), (0.7, k[(i + 1) % 4], 0.85), (1, k[(i + 1) % 4], 0)], 0, 0, 1, 0)
            d = " ".join("%s%.1f,%.1f" % ("M" if x == -20 else "L", x, f(x)) for x in range(-20, w + 21, 10))
            rib.add('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" opacity="%.2f"/>' % (d, col, h * rng.uniform(0.004, 0.018), 0.55 if dark(mood) else 0.45))
        layers.append(("ribbons%d" % j, rib.text(), {"sway": 30 + 25 * j, "period": 12, "phase": 0.5 * j, "cross": j}))
    return layers


# ---- the brand: the Aequalyn mark and name -----------------------------------------------
# tools/brand/: the æ mark (strokes, as the shell's ae-mark.svg) and the wordmark (one path)

BRAND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand")
MARK_BOX = (100, 130, 320, 200)        # the mark's viewBox: x, y, width, height
MARK_RING = (188.8, 225.3, 64)         # the round of its "a": centre (after its 20.5 shift), radius


def mark_svg(cx, cy, height, color):
    """the æ mark, `height` tall, centred on (cx, cy)"""
    x0, y0, mw, mh = MARK_BOX
    k = height / mh
    tx, ty = cx - (x0 + mw / 2) * k, cy - (y0 + mh / 2) * k
    return ('<g transform="translate(%.2f %.2f) scale(%.5f)"><g transform="translate(0 20.5)" fill="none" stroke="%s" stroke-width="29.7">'
            '<circle cx="188.8" cy="204.8" r="64"/><path d="M252.8 204.8v78.8" stroke-linecap="butt"/>'
            '<path d="M380.8 204.8A64 64 0 1 0 365.8 245.9" stroke-linecap="round"/><path d="M252.8 204.8h128"/></g></g>'
            % (tx, ty, k, color))


def mark_ring(cx, cy, height):
    """where the round of the mark's "a" lands, and its radius, for the mark drawn so"""
    x0, y0, mw, mh = MARK_BOX
    k = height / mh
    rx, ry, r = MARK_RING
    return cx + (rx - x0 - mw / 2) * k, cy + (ry - y0 - mh / 2) * k, r * k


_WORD = None


def word_svg(cx, cy, width, color):
    """the wordmark, `width` wide, centred on (cx, cy)"""
    global _WORD
    if _WORD is None:
        import re
        src = open(os.path.join(BRAND, "aequalyn-wordmark.svg")).read()
        m = re.search(r'<path transform="translate\(([^)]*)\)" d="([^"]+)"', src)
        _WORD = (m.group(1), m.group(2))
    tr, d = _WORD
    k = width / 728
    return ('<g transform="translate(%.2f %.2f) scale(%.5f)"><path transform="translate(%s)" d="%s" fill="%s"/></g>'
            % (cx - 364 * k, cy - 89.5 * k, k, tr, d, color))


def scene_brand(keys, mood, seed, w, h):
    rng = random.Random(seed)
    c1, acc = keys[0], keys[1]
    c3 = keys[2] if len(keys) > 2 else shift(acc, 0.1, 0, 0)
    night = dark(mood)
    # one of the two on each picture, never both: the mark on the main picture (night,
    # day, and the live loops), the name on the second (dusk, dawn); in the middle, a
    # little above it (clear of the ribbons, and of a dock at the bottom)
    with_mark = mood in ("night", "day")
    cx, cy = w * 0.5, h * 0.46
    mh = h * 0.34                       # the mark's height
    ww = w * 0.46                       # the name's width
    ink = "#f3f6f3" if night else "#142a30"
    name_ink = mix(acc, "#ffffff", 0.45) if night else "#24434a"
    if with_mark:
        rcx, rcy, rr = mark_ring(cx, cy, mh)
        def logo_of(color):
            return mark_svg(cx, cy, mh, color)
    else:
        # the ripples from the middle of the name
        rcx, rcy, rr = cx, cy, ww * 0.11
        def logo_of(color):
            return word_svg(cx, cy, ww, color)

    # the ground: deep teal near black, or a light teal-tinted white; dusk and dawn warmer
    s0 = Svg(w, h)
    if mood == "night":
        sky = [(0, mix(c1, "#03070a", 0.80), 1), (1, mix(c1, "#010304", 0.90), 1)]
    elif mood == "dusk":
        sky = [(0, mix(c1, "#04080c", 0.78), 1), (0.7, mix(c1, "#0b0d14", 0.70), 1), (1, mix(acc, "#3a2430", 0.75), 1)]
    elif mood == "day":
        sky = [(0, mix(c1, "#f8fbfa", 0.94), 1), (1, mix(acc, "#ffffff", 0.84), 1)]
    else:
        sky = [(0, mix(c1, "#fbf8f4", 0.93), 1), (1, mix("#ffd9bf", "#ffffff", 0.55), 1)]
    s0.add('<rect width="%d" height="%d" fill="%s"/>' % (w, h, s0.lin(sky)))
    vig = s0.rad([(0, "#000000", 0), (0.65, "#000000", 0), (1, "#000000", 0.45 if night else 0.08)], 0.5, 0.5, 0.75)
    s0.add('<rect width="%d" height="%d" fill="%s"/>' % (w, h, vig))
    layers = [("base", s0.text(), {})]

    # soft light in the theme's colours, drifting
    glow = Svg(w, h)
    bl = glow.blur(h * 0.10)
    spots = [(rcx, rcy, h * 0.42, acc), (w * rng.uniform(0.1, 0.3), h * rng.uniform(0.6, 0.9), h * 0.40, c3),
             (w * rng.uniform(0.7, 0.92), h * rng.uniform(0.1, 0.35), h * 0.36, mix(acc, c3, 0.5))]
    for x, y, r, c in spots:
        glow.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="%.2f" filter="%s"/>'
                 % (x, y, r, c, 0.30 if night else 0.22, bl))
    layers.append(("glow", glow.text(), {"sway": 36, "period": 12, "pulse": 0.18}))

    # ripples from the round of the "a": two sets between each other, crossfading over the
    # loop, so they seem to breathe outwards
    for j in range(2):
        rings = Svg(w, h)
        step = rr * 0.62
        for i in range(1, 15):
            r = rr + step * (i + 0.5 * j)
            fade = max(0.0, 1 - i / 14)
            rings.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.1f" opacity="%.3f"/>'
                      % (rcx, rcy, r, acc if night else c1, h * 0.0016, (0.30 if night else 0.20) * fade))
        layers.append(("rings%d" % j, rings.text(), {"cross": j}))

    # ribbons along the bottom, flowing
    for j in range(2):
        rib = Svg(w, h)
        for i in range(6):
            t = i / 5
            f = ridge(rng, w, h * (0.80 + 0.10 * t), h * 0.06, 3, 0.8)
            col = rib.lin([(0, acc, 0.0), (0.35, acc if i % 2 else c3, 0.8), (0.7, c3 if i % 2 else acc, 0.8), (1, c3, 0.0)], 0, 0, 1, 0)
            d = " ".join("%s%.1f,%.1f" % ("M" if x == -20 else "L", x, f(x)) for x in range(-20, w + 21, 10))
            rib.add('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" opacity="%.2f"/>'
                    % (d, col, h * rng.uniform(0.0015, 0.005), 0.55 if night else 0.42))
        layers.append(("ribbons%d" % j, rib.text(), {"sway": 34 + 20 * j, "period": 12, "phase": 0.5 * j, "cross": j}))

    # a halo behind it, breathing
    halo = Svg(w, h)
    hb = halo.blur(h * 0.035)
    halo.add('<g opacity="%.2f" filter="%s">%s</g>' % (0.75 if night else 0.35, hb, logo_of(acc)))
    layers.append(("halo", halo.text(), {"pulse": 0.45, "period": 6}))

    # the mark or the name, still
    logo = Svg(w, h)
    logo.add(logo_of(ink if with_mark else name_ink))
    layers.append(("logo", logo.text(), {}))
    return layers


SCENES = {"cosmos": scene_cosmos, "forest": scene_forest, "ocean": scene_ocean, "peaks": scene_peaks,
          "desert": scene_desert, "aurora": scene_aurora, "city": scene_city, "flow": scene_flow,
          "brand": scene_brand}

# ---- rendering -------------------------------------------------------------------------------

def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise SystemExit("failed: %s\n%s" % (" ".join(cmd[:6]), r.stderr[-2000:]))
    return r.stdout


def render_layers(layers, w, h, tmp, tag):
    """each layer to a PNG with alpha"""
    def one(item):
        i, (name, svg, motion) = item
        sp = os.path.join(tmp, "%s-%02d-%s.svg" % (tag, i, name))
        pp = sp[:-4] + ".png"
        with open(sp, "w") as fh:
            fh.write(svg)
        run(["resvg", "-w", str(w), "-h", str(h), sp, pp])
        return pp, motion
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        return list(ex.map(one, enumerate(layers)))


def still(scene, keys, mood, seed, out, w=W4, h=H4):
    """the layers composed into one picture, with a fine grain, as a JPEG"""
    layers = SCENES[scene](keys, mood, seed, w, h)
    with tempfile.TemporaryDirectory() as tmp:
        pngs = render_layers(layers, w, h, tmp, "s")
        flat = os.path.join(tmp, "flat.png")
        cmd = ["magick"] + [p for p, _ in pngs[:1]]
        for p, _ in pngs[1:]:
            cmd += [p, "-composite"]
        # grain: a fine gaussian noise, barely there, so gradients never band
        cmd += ["-seed", str(seed), "-attenuate", "0.08", "+noise", "Gaussian", flat]
        run(cmd)
        run(["magick", flat, "-strip", "-sampling-factor", "4:2:0", "-quality", "90", out])


def live(scene, keys, mood, seed, out):
    """the layers in slow seamless motion: an mp4 loop of LIVE_SECONDS"""
    w, h, T = WL, HL, LIVE_SECONDS
    layers = SCENES[scene](keys, mood, seed, w, h)
    with tempfile.TemporaryDirectory() as tmp:
        pngs = render_layers(layers, w, h, tmp, "l")
        # every layer is drawn a little wider than the screen so it can sway
        pad = 64
        inputs, chains = [], []
        for i, (p, m) in enumerate(pngs):
            inputs += ["-loop", "1", "-framerate", str(LIVE_FPS), "-t", str(T), "-i", p]
        chains.append("[0:v]format=rgba,scale=%d:%d[base]" % (w, h))
        prev = "base"
        for i, (p, m) in enumerate(pngs[1:], start=1):
            sway = m.get("sway", 0)
            period = m.get("period", T)
            ph = m.get("phase", 0)
            # the period divides the loop exactly, so the last frame meets the first
            per = T / max(1, round(T / period)) if period else T
            lbl = "l%d" % i
            f = ["format=rgba", "pad=%d:%d:%d:0:color=0x00000000" % (w + 2 * pad, h, pad)]
            # the edge columns copied out so the sway never shows an empty strip
            f.append("fillborders=left=%d:right=%d:mode=smear" % (pad, pad))
            # its opacity over the loop (pulse, crossfade), sent to a cheap filter frame by
            # frame: a whole-layer value, so no per-pixel work
            a, cross = m.get("pulse", 0), m.get("cross")
            if a or cross is not None:
                lines = []
                steps = T * 15
                for n in range(steps + 1):
                    t = n * T / steps
                    v = 1.0
                    if a:
                        v *= 1 - a / 2 + a / 2 * math.sin(2 * math.pi * (t / per + ph))
                    if cross is not None:
                        v *= 0.5 + 0.5 * math.cos(2 * math.pi * t / T + cross * math.pi)
                    lines.append("%.4f colorchannelmixer@c%d aa %.4f;" % (t, i, max(0.0, min(1.0, v))))
                cf = os.path.join(tmp, "cmd%d.txt" % i)
                with open(cf, "w") as fh:
                    fh.write("\n".join(lines) + "\n")
                f.append("sendcmd=f=%s" % cf)
                f.append("colorchannelmixer@c%d=aa=1" % i)
            chains.append("[%d:v]%s[%s]" % (i, ",".join(f), lbl))
            x = "-%d+%.2f*sin(2*PI*(t/%.4f+%.3f))" % (pad, sway * w / 1920, per, ph) if sway else "-%d" % pad
            nxt = "o%d" % i
            chains.append("[%s][%s]overlay=x='%s':y=0:format=auto:shortest=1[%s]" % (prev, lbl, x, nxt))
            prev = nxt
        chains.append("[%s]format=yuv420p[out]" % prev)
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y"] + inputs + [
            "-filter_complex", ";".join(chains), "-map", "[out]", "-t", str(T), "-r", str(LIVE_FPS),
            "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
        run(cmd)

# ---- what goes where -------------------------------------------------------------------------

def topic(tid):
    t = TOPICS[tid]
    for variant in ("dark", "light"):
        theme_id = tid if variant == "dark" else tid + "-day"
        d = os.path.join(ROOT, "themes", theme_id)
        bg = os.path.join(d, "backgrounds")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(bg)
        moods = ("night", "dusk") if variant == "dark" else ("day", "dawn")
        seed = sum(map(ord, tid)) * 7
        for i, mood in enumerate(moods, start=1):
            print("  %s: %s" % (theme_id, mood), flush=True)
            still(t["scene"], t["keys"], mood, seed + i * 101, os.path.join(bg, "%d-%s-%s.jpg" % (i, mood, tid)))
        print("  %s: live" % theme_id, flush=True)
        live(t["scene"], t["keys"], moods[0], seed + 101, os.path.join(bg, "3-live-%s-%s.mp4" % (moods[0], tid)))
        run(["magick", os.path.join(bg, "1-%s-%s.jpg" % (moods[0], tid)), "-resize", "960x540^", "-gravity", "center",
             "-extent", "960x540", "-quality", "85", os.path.join(d, "preview.jpg")])
    write_meta(tid)


def write_meta(tid):
    t = TOPICS[tid]
    for variant in ("dark", "light"):
        d = os.path.join(ROOT, "themes", tid if variant == "dark" else tid + "-day")
        meta = {
            "name": t["name"] + ("" if variant == "dark" else " Day"),
            "family": "Aequalyn Nature" if t["scene"] not in ("flow", "city", "brand") else "Aequalyn",
            "author": "Aequalyn",
            "variant": variant,
            "about": t["about"],
            "colors": t["keys"],
            "palette": palette(t["keys"], variant),
        }
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "theme.json"), "w") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")


def walls():
    d = os.path.join(ROOT, "wallpapers")
    os.makedirs(d, exist_ok=True)
    for wp in WALLS:
        print("  wallpaper: %s" % wp["id"], flush=True)
        if wp.get("live"):
            live(wp["scene"], wp["keys"], wp["mood"], wp["seed"], os.path.join(d, "%s.mp4" % wp["id"]))
        else:
            still(wp["scene"], wp["keys"], wp["mood"], wp["seed"], os.path.join(d, "%s-%s.jpg" % (wp["id"], wp["mood"])))


def preview(tid):
    t = TOPICS[tid]
    for mood in ("night", "dusk", "day", "dawn"):
        out = os.path.join(os.environ.get("ARTGEN_OUT", tempfile.gettempdir()), "artgen-%s-%s.jpg" % (tid, mood))
        still(t["scene"], t["keys"], mood, 7, out, 960, 540)
        print(out)


def main():
    a = sys.argv[1:]
    for tool in ("resvg", "magick", "ffmpeg"):
        if not shutil.which(tool):
            raise SystemExit("artgen needs %s" % tool)
    if not a:
        print(__doc__)
    elif a[0] == "all":
        for tid in TOPICS:
            print(tid, flush=True)
            topic(tid)
        walls()
    elif a[0] == "theme":
        for tid in a[1:]:
            topic(tid)
    elif a[0] == "palettes":
        for tid in (a[1:] or TOPICS):
            write_meta(tid)
    elif a[0] == "walls":
        walls()
    elif a[0] == "preview":
        for tid in a[1:]:
            preview(tid)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
