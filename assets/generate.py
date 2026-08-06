#!/usr/bin/env python3
"""
Generate the profile README's buttons, taglines and social tiles.

Three constraints drive every decision here:

1. GitHub cannot load a webfont, so SVG <text> would fall back to whatever the
   viewer happens to have. Text assets are therefore rasterised to PNG at 2x
   with Satoshi baked in, which is also why the reference layout we follow uses
   PNG buttons. Text-free assets (divider, separator) stay SVG.
2. The brand has no rounded corners anywhere. Every rectangle is square: the
   site's CSS sets border-radius: 0 in nine places and reserves 50% for status
   dots. Do not add an rx here.
3. Light and dark variants genuinely differ (label colour flips), which is what
   the <picture> + prefers-color-scheme markup in the README is for.

Widths are measured by rendering each label and trimming it, then every button
in a row is padded to a common width so the rows line up.

Requires: rsvg-convert, ImageMagick, and Satoshi visible to fontconfig
(see install-fonts below).

Usage:  python3 assets/generate.py [path-to-scramdb-docs]
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
DOCS_REPO = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'projects/scramdb-docs')
ICONS = DOCS_REPO / 'website/node_modules/react-icons'

FONT_BOLD = 'Satoshi Black'
FONT_MED = 'Satoshi Medium'

# --scram-gradient: indigo -> violet -> orange.
GRADIENT = [('0%', '#6366F1'), ('55%', '#A855F7'), ('100%', '#F97316')]

# Foreground per GitHub theme. --scram-fg for dark, the site's deepest base for light.
FG = {'dark': '#F1F5F9', 'light': '#0B1020'}
DIM = {'dark': '#64748B', 'light': '#94A3B8'}

BTN_H = 44          # button box height in CSS px before the 2x raster
BTN_PAD = 30        # horizontal padding either side of the label
LABEL_SIZE = 15
SCALE = 2           # raster at 2x so the PNG stays crisp on retina

BUTTONS = [
    ('btn-product', 'Product'),
    ('btn-docs', 'Documentation'),
    ('btn-issues', 'Issues'),
    ('btn-single-node', 'Deploy Single Node'),
    ('btn-cluster', 'Deploy Cluster'),
    ('btn-discord', 'Discord'),
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

TAGLINES = [
    ('tagline', 'Programmable Distributed Hyperscale UTAP database', 20, FONT_BOLD),
    ('tagline-join', 'Build with us', 20, FONT_BOLD),
]


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def grad(gid):
    stops = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in GRADIENT)
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">{stops}</linearGradient>'


def svg_to_png(svg, out, scale=SCALE):
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
        f.write(svg)
        tmp = f.name
    run(['rsvg-convert', '-z', str(scale), tmp, '-o', str(out)])
    Path(tmp).unlink()


def measure(text, font, size):
    """Render the label alone and trim it, so the button is sized from real
    Satoshi metrics rather than a guess that could clip a descender."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="200">'
        f'<text x="10" y="120" font-family="{font}" font-size="{size}" fill="#000">{text}</text></svg>'
    )
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / 'm.png'
        svg_to_png(svg, png, scale=1)
        out = subprocess.run(['magick', str(png), '-trim', '-format', '%w %h', 'info:'],
                             check=True, capture_output=True, text=True).stdout
    w, h = (int(v) for v in out.split())
    return w, h


def button_svg(label, width, theme):
    """Square button: gradient hairline border, transparent fill, label in the
    theme foreground."""
    gid, b = 'g', 1.5
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{BTN_H}" '
        f'viewBox="0 0 {width} {BTN_H}">'
        f'<defs>{grad(gid)}</defs>'
        f'<rect x="{b / 2}" y="{b / 2}" width="{width - b}" height="{BTN_H - b}" '
        f'fill="none" stroke="url(#{gid})" stroke-width="{b}"/>'
        f'<text x="{width / 2}" y="{BTN_H / 2}" fill="{FG[theme]}" font-size="{LABEL_SIZE}" '
        f'font-family="{FONT_BOLD}" text-anchor="middle" dominant-baseline="central">{label}</text>'
        f'</svg>'
    )


def text_svg(text, size, font, theme, pad=6):
    w, h = measure(text, font, size)
    width, height = w + pad * 2, h + pad * 2
    return width, (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<text x="{width / 2}" y="{height / 2}" fill="{FG[theme]}" font-size="{size}" '
        f'font-family="{font}" text-anchor="middle" dominant-baseline="central">{text}</text>'
        f'</svg>'
    )


def wordmark_svg(theme):
    text, size = 'ScramDB', 46
    w, h = measure(text, FONT_BOLD, size)
    width, height = w + 16, h + 20
    gid = 'g'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<defs>{grad(gid)}</defs>'
        f'<text x="{width / 2}" y="{height / 2}" fill="url(#{gid})" font-size="{size}" '
        f'font-family="{FONT_BOLD}" text-anchor="middle" dominant-baseline="central">{text}</text>'
        f'</svg>'
    )


def extract_icon(family, name):
    src = (ICONS / family / 'index.mjs').read_text(encoding='utf8')
    m = re.search(r'function %s \(props\).{0,4000}?GenIcon\((\{.*?\})\)\(props\)' % name, src, re.S)
    if not m:
        raise SystemExit(f'icon {name} not found in react-icons/{family}')
    spec = json.loads(m.group(1))
    return spec['attr']['viewBox'], [c['attr']['d'] for c in spec['child'] if c['tag'] == 'path']


def social_svg(family, name, theme):
    view_box, paths = extract_icon(family, name)
    _, _, vw, vh = (float(v) for v in view_box.split())
    box, glyph, gid, b = BTN_H, 19, 'g', 1.5
    scale = glyph / max(vw, vh)
    tx, ty = (box - vw * scale) / 2, (box - vh * scale) / 2
    d = ''.join(f'<path d="{p}" fill="{FG[theme]}"/>' for p in paths)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{box}" height="{box}" '
        f'viewBox="0 0 {box} {box}">'
        f'<defs>{grad(gid)}</defs>'
        f'<rect x="{b / 2}" y="{b / 2}" width="{box - b}" height="{box - b}" '
        f'fill="none" stroke="url(#{gid})" stroke-width="{b}"/>'
        f'<g transform="translate({tx:.2f},{ty:.2f}) scale({scale:.4f})">{d}</g>'
        f'</svg>'
    )


def separator_svg(theme):
    w = 14
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{BTN_H}" '
        f'viewBox="0 0 {w} {BTN_H}"><rect x="{w / 2 - 0.5}" y="12" width="1" '
        f'height="{BTN_H - 24}" fill="{DIM[theme]}"/></svg>'
    )


def divider_svg():
    w, h, gid = 900, 2, 'g'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<defs>{grad(gid)}</defs><rect width="{w}" height="{h}" fill="url(#{gid})" opacity="0.5"/></svg>'
    )


def main():
    for tool in ('rsvg-convert', 'magick'):
        if not shutil.which(tool):
            raise SystemExit(f'{tool} is required')
    if not ICONS.exists():
        raise SystemExit(f'react-icons not found at {ICONS}')

    # One width for every button, measured from the longest label, so both rows
    # are the same total width and the grid actually lines up.
    rows = [['btn-product', 'btn-docs', 'btn-issues'],
            ['btn-single-node', 'btn-cluster', 'btn-discord']]
    common = max(measure(label, FONT_BOLD, LABEL_SIZE)[0] for _, label in BUTTONS) + BTN_PAD * 2
    widths = {slug: common for slug, _ in BUTTONS}

    n = 0
    for theme in ('dark', 'light'):
        for slug, label in BUTTONS:
            svg_to_png(button_svg(label, widths[slug], theme), ASSETS / f'{slug}-{theme}.png')
            n += 1
        for slug, family, name in SOCIALS:
            svg_to_png(social_svg(family, name, theme), ASSETS / f'{slug}-{theme}.png')
            n += 1
        for slug, text, size, font in TAGLINES:
            _, svg = text_svg(text, size, font, theme)
            svg_to_png(svg, ASSETS / f'{slug}-{theme}.png')
            n += 1
        (ASSETS / f'btn-separator-{theme}.svg').write_text(separator_svg(theme), encoding='utf8')
        n += 1
    # The wordmark is a gradient fill and the mark is multi-colour art on
    # transparency: both read on either theme, so a dark/light pair would be two
    # identical files pretending to differ. One asset, plain <img> in the README.
    svg_to_png(wordmark_svg('dark'), ASSETS / 'wordmark.png')
    n += 1
    (ASSETS / 'divider.svg').write_text(divider_svg(), encoding='utf8')
    print(f'wrote {n + 1} assets to {ASSETS}')
    print(f"uniform button width: {common}px")


if __name__ == '__main__':
    main()
