#!/usr/bin/env python3
"""
Generate the profile README's marks, buttons, taglines, social tiles and dividers
in the ScramDB "Collective" design system.

Constraints:

1. GitHub cannot load a webfont, so text is rasterised to PNG at 2x with Geist
   and Geist Mono baked in (retina-crisp). Text-free assets (mark, divider,
   separator) stay SVG.
2. Corners are 2px, borders 1px hairlines, edges crisp: the DS `sc-btn` look.
3. Dark and light variants use the DS dark and "Paper" light tokens, which is
   what the <picture> + prefers-color-scheme markup in the README switches on.

Requires: Pillow, rsvg-convert, and the scramdb-docs checkout (for the social
icon paths in react-icons).

Usage:  python3 -I assets/generate.py [path-to-scramdb-docs]
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent
DOCS_REPO = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'db/scramdb-docs')
ICONS = DOCS_REPO / 'website/node_modules/react-icons'
FONTS = Path.home() / '.local/share/fonts/geist'

# DS tokens per GitHub theme (tokens.css dark, "Paper" light).
THEMES = {
    'dark': dict(bg='#03060c', ink='#e9f0fb', muted='#74839d', accent='#6ce1d7',
                 bright='#bff8f3', ctrl='#56667f', line=(140, 180, 240, 33)),
    'light': dict(bg='#f5f7fa', ink='#0a1220', muted='#56657d', accent='#007a70',
                  bright='#007a70', ctrl='#7b889c', line=(20, 50, 95, 31)),
}

S = 2                 # raster scale
BTN_H = 44            # CSS px
BTN_PAD = 24
RADIUS = 2
LABEL_SIZE = 12
LABEL_TRACK = 0.1     # em
SOCIAL_GAP = 4        # transparent margin either side of a tile, CSS px

BUTTONS = [
    ('btn-product', 'Product', True),
    ('btn-docs', 'Documentation', False),
    ('btn-issues', 'Issues', False),
    ('btn-single-node', 'Deploy Single Node', False),
    ('btn-cluster', 'Deploy Cluster', False),
    ('btn-discord', 'Discord', False),
]

SOCIALS = [
    ('social-x', 'si', 'SiX'),
    ('social-linkedin', 'fa6', 'FaLinkedinIn'),
    ('social-github', 'si', 'SiGithub'),
    ('social-youtube', 'si', 'SiYoutube'),
    ('social-bluesky', 'si', 'SiBluesky'),
    ('social-instagram', 'si', 'SiInstagram'),
    ('social-discord', 'si', 'SiDiscord'),
]

# (slug, text, css px size, weight)
TAGLINES = [
    ('tagline', 'Programmable Distributed Hyperscale UTAP database', 22, 300),
    ('tagline-join', 'Build with us', 22, 200),
]

# MARKS.ramp from the design system bundle.
RAMP_INK = ('M10 2h3v3h-3zM14 2h3v3h-3zM6 6h3v3h-3zM14 6h3v3h-3zM2 10h3v3h-3zM10 10h3v3h-3z'
            'M6 14h3v3h-3zM14 14h3v3h-3zM10 18h3v3h-3zM14 18h3v3h-3z')
RAMP_ACC = 'M18 2h3v3h-3zM18 6h3v3h-3zM18 10h3v3h-3zM18 14h3v3h-3zM18 18h3v3h-3z'


def font(name, size, weight):
    f = ImageFont.truetype(str(FONTS / name), size)
    f.set_variation_by_axes([weight])
    return f


def spaced_width(text, f, track_px):
    return sum(f.getlength(c) for c in text) + track_px * (len(text) - 1)


def draw_spaced(d, x, y, text, f, fill, track_px):
    for c in text:
        d.text((x, y), c, font=f, fill=fill, anchor='ls')
        x += f.getlength(c) + track_px


def mix(fg, bg, a):
    f, b = (tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (fg, bg))
    return tuple(round(b[i] + (f[i] - b[i]) * a) for i in range(3))


def label_font():
    return font('GeistMono.ttf', LABEL_SIZE * S, 500)


def button_png(label, width, primary, t, out):
    """sc-btn: 2px radius, 1px border, mono uppercase label. Primary is an
    accent border over a 12% accent fill, the rest are ghost."""
    w, h = width * S, BTN_H * S
    fill, border, ink = ((mix(t['accent'], t['bg'], .12), t['accent'], t['bright'] if t is THEMES['dark'] else t['accent'])
                         if primary else (t['bg'], t['ctrl'], t['ink']))
    im = Image.new('RGB', (w, h), t['bg'])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=RADIUS * S, fill=fill, outline=border, width=S)
    f, text = label_font(), label.upper()
    track = LABEL_TRACK * LABEL_SIZE * S
    tw = spaced_width(text, f, track)
    # cap-height centred: baseline = middle + half the cap height
    cap = f.getbbox('H', anchor='ls')[1]
    draw_spaced(d, (w - tw) / 2, h / 2 - cap / 2, text, f, ink, track)
    im.save(out)


def tagline_png(text, size, weight, t, out):
    f = font('Geist.ttf', size * S, weight)
    l, top, r, b = f.getbbox(text, anchor='ls')
    pad = 6 * S
    im = Image.new('RGBA', (r - l + pad * 2, b - top + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - top), text, font=f, fill=t['ink'], anchor='ls')
    im.save(out)


def wordmark_png(t, out):
    size, track = 56, -0.04
    f = font('Geist.ttf', size * S, 400)
    text = 'ScramDB'
    tp = track * size * S
    tw = int(spaced_width(text, f, tp)) + 1
    top, bot = f.getbbox('S', anchor='ls')[1], f.getbbox('S', anchor='ls')[3]
    pad = 6 * S
    im = Image.new('RGBA', (tw + pad * 2, bot - top + pad * 2 + 4 * S), (0, 0, 0, 0))
    draw_spaced(ImageDraw.Draw(im), pad, pad - top, text, f, t['ink'], tp)
    im.save(out)


def extract_icon(family, name):
    src = (ICONS / family / 'index.mjs').read_text(encoding='utf8')
    m = re.search(r'function %s \(props\).{0,4000}?GenIcon\((\{.*?\})\)\(props\)' % name, src, re.S)
    if not m:
        raise SystemExit(f'icon {name} not found in react-icons/{family}')
    spec = json.loads(m.group(1))
    return spec['attr']['viewBox'], [c['attr']['d'] for c in spec['child'] if c['tag'] == 'path']


def social_png(family, name, t, out):
    """Square hairline tile, ink glyph, with a transparent gutter either side
    so adjacent tiles do not touch."""
    view_box, paths = extract_icon(family, name)
    _, _, vw, vh = (float(v) for v in view_box.split())
    glyph = 18
    k = glyph / max(vw, vh)
    box, gap = BTN_H, SOCIAL_GAP
    total = box + gap * 2
    d = ''.join(f'<path d="{p}" fill="{t["ink"]}"/>' for p in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{box}" viewBox="0 0 {total} {box}">'
           f'<rect x="{gap + .5}" y=".5" width="{box - 1}" height="{box - 1}" rx="{RADIUS}" '
           f'fill="{t["bg"]}" stroke="{t["ctrl"]}"/>'
           f'<g transform="translate({gap + (box - vw * k) / 2:.2f},{(box - vh * k) / 2:.2f}) scale({k:.4f})">{d}</g></svg>')
    rsvg(svg, out)


def rsvg(svg, out):
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
        f.write(svg)
        tmp = f.name
    subprocess.run(['rsvg-convert', '-z', str(S), tmp, '-o', str(out)], check=True, capture_output=True)
    Path(tmp).unlink()


def mark_svg(t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            f'shape-rendering="crispEdges"><path d="{RAMP_INK}" fill="{t["ink"]}"/>'
            f'<path d="{RAMP_ACC}" fill="{t["accent"]}"/></svg>')


def separator_svg(t):
    w = 14
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{BTN_H}" viewBox="0 0 {w} {BTN_H}" '
            f'shape-rendering="crispEdges"><rect x="{w // 2 - 1}" y="{BTN_H // 2 - 1}" width="3" height="3" '
            f'fill="{t["accent"]}" opacity=".55"/></svg>')


def divider_svg(t):
    """k-pixels: 3px squares on a 4px pitch, accent at .55."""
    w = 900
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="3" viewBox="0 0 {w} 3" '
            f'shape-rendering="crispEdges"><defs><pattern id="p" width="4" height="3" patternUnits="userSpaceOnUse">'
            f'<rect width="3" height="3" fill="{t["accent"]}" opacity=".55"/></pattern></defs>'
            f'<rect width="{w}" height="3" fill="url(#p)"/></svg>')


def text_width(label):
    f = label_font()
    return -(-int(spaced_width(label.upper(), f, LABEL_TRACK * LABEL_SIZE * S)) // S)


def main():
    if not shutil.which('rsvg-convert'):
        raise SystemExit('rsvg-convert is required')
    if not ICONS.exists():
        raise SystemExit(f'react-icons not found at {ICONS}')

    # One width for every button so both rows line up.
    common = max(text_width(label) for _, label, _ in BUTTONS) + BTN_PAD * 2
    n = 0
    for theme, t in THEMES.items():
        for slug, label, primary in BUTTONS:
            button_png(label, common, primary, t, ASSETS / f'{slug}-{theme}.png')
        for slug, family, name in SOCIALS:
            social_png(family, name, t, ASSETS / f'{slug}-{theme}.png')
        for slug, text, size, weight in TAGLINES:
            tagline_png(text, size, weight, t, ASSETS / f'{slug}-{theme}.png')
        wordmark_png(t, ASSETS / f'wordmark-{theme}.png')
        (ASSETS / f'btn-separator-{theme}.svg').write_text(separator_svg(t), encoding='utf8')
        (ASSETS / f'divider-{theme}.svg').write_text(divider_svg(t), encoding='utf8')
        # The default (light) mark keeps the original file name.
        mark = 'scramdb-mark.svg' if theme == 'light' else 'scramdb-mark-dark.svg'
        (ASSETS / mark).write_text(mark_svg(t), encoding='utf8')
        n += len(BUTTONS) + len(SOCIALS) + len(TAGLINES) + 4
    print(f'wrote {n} assets to {ASSETS}; uniform button width {common}px')


if __name__ == '__main__':
    main()
