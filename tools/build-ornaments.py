#!/usr/bin/env python3
"""Generate the four corner ornament assets from one source envelope.

Run:  python3 tools/build-ornaments.py

Reads  tools/env-source.svg      (the authored bottom-right envelope)
Writes assets/env-line-{tl,tr,bl,br}.svg

Everything the browser needs is baked in here rather than applied at
runtime, because the ornaments are loaded through <object> and an
<object>-loaded SVG is a separate document: the host page's CSS does not
cascade into it, and over file:// its JS cannot reach into it either.
Whatever is not in the file cannot be added later.

Four transformations happen, and each one exists for a stated reason:

1. COLOUR IS STRIPPED to currentColor. The four corners must be the same
   drawing in every respect except palette, so no colour is baked in.

2. GEOMETRY IS REFLECTED, not transformed at render time. A CSS
   transform on the host element was tried and rejected: mirroring the
   drawing also mirrors its opacity ramp and its stroke weighting, so in
   three of the four corners the figure ends up pointing away from the
   text instead of back at it. Reflecting the coordinates keeps the ramp
   pointing inward in all four.

3. THE BACK LAYER IS OFFSET INWARD. In the source it carries
   translate(5,7), which for a bottom-right envelope pushes it toward the
   corner — so the back layer, not the front, is what touches the edge,
   and the front (the layer you actually read) floats 6-8 units inside.
   The offset is negated per corner here so the shadow falls away from
   the vertex and the front is the layer that lands on the corner.

4. THE VIEWBOX IS CROPPED to the FRONT layer's ink, inflated by half the
   widest stroke. Half a stroke is not slack: a line is centred on its
   coordinates, so cropping to the exact centreline would slice the
   fattest ray lengthwise at the edge. That half-stroke is the minimum
   that still renders whole, and at RENDER_PX it is well under a pixel.

Stroke widths are pre-multiplied for RENDER_PX. They have to be: the
reveal animation needs pathLength="1" to normalize every line to the same
dash length, and pathLength normalization and vector-effect:
non-scaling-stroke are mutually exclusive — non-scaling-stroke pushes the
dash back into screen pixels and the single dasharray stops being
correct. Losing non-scaling-stroke means stroke width now scales with the
drawing, so it is compensated here instead. CHANGING .ornament's WIDTH IN
THE CSS WITHOUT CHANGING RENDER_PX AND RE-RUNNING THIS SCRIPT WILL MAKE
THE STROKES WRONG.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(HERE, 'env-source.svg')
OUT_DIR = os.path.join(ROOT, 'assets')

# Must match the rendered width of .ornament in index.html.
RENDER_PX = 550.0

# The shadow offset, in source units, as authored. Applied inward.
OFFSET_X, OFFSET_Y = 5.0, 7.0

DURATION_MS = 900
STAGGER_MS = 12

# flip_x, flip_y relative to the source (which is drawn bottom-right).
CORNERS = {
    'br': (False, False),
    'bl': (True, False),
    'tr': (False, True),
    'tl': (True, True),
}

LINE_RE = re.compile(r'<line\b[^>]*/>')
COORD_RE = re.compile(r'(x1|y1|x2|y2)="([-0-9.]+)"')
WIDTH_RE = re.compile(r'stroke-width="([-0-9.]+)"')

STYLE_TEMPLATE = """  <style>
    /* The reveal lives HERE, inside the asset, on purpose.

       This file is loaded through &lt;object&gt;, which makes it its own
       document: the host page's CSS does not cascade in, and over
       file:// the host page's JS cannot reach in either (opaque origin
       =&gt; contentDocument is null). A script-driven reveal on the page
       side silently did nothing whenever the page was opened straight
       from disk. Owning the animation removes that dependency.

       It runs on document load, and the page turns that into a scroll
       trigger by leaving `data` unset until the corner is in view, so
       "loaded" and "seen" are the same moment.

       pathLength="1" is what lets the dash be written in CSS at all: it
       normalizes every line to length 1 regardless of its real geometry,
       so ONE dasharray is correct for all of them at any rendered size.
       It only works because these lines carry no vector-effect:
       non-scaling-stroke, which would push the dash back into screen
       pixels and break the normalization. */
    line {
      stroke-dasharray: 1;
      stroke-dashoffset: 1;
      animation: draw %(duration)dms cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
    }

    @keyframes draw {
      to { stroke-dashoffset: 0; }
    }

    /* One shot, no loop, and nothing at all if less motion was asked
       for: the resting state of this drawing is a FINISHED drawing. */
    @media (prefers-reduced-motion: reduce) {
      line {
        animation: none;
        stroke-dashoffset: 0;
      }
    }
  </style>"""


def fmt(value):
    value = round(value, 3)
    return str(int(value)) if value == int(value) else str(value)


def parse_lines(block):
    """Return [(fragment, {x1,y1,x2,y2}, stroke_width), ...] for a block."""
    out = []
    for fragment in LINE_RE.findall(block):
        coords = {k: float(v) for k, v in COORD_RE.findall(fragment)}
        width = float(WIDTH_RE.search(fragment).group(1))
        out.append((fragment, coords, width))
    return out


def build(source, corner):
    flip_x, flip_y = CORNERS[corner]

    head, rest = source.split('<g data-layer="back"', 1)
    back_block, front_block = rest.split('<g data-layer="front">', 1)
    view = [float(v) for v in re.search(r'viewBox="([^"]+)"', source).group(1).split()]
    src_w, src_h = view[2], view[3]

    # The source viewBox only matters as the mirror axis; it is discarded
    # after the crop below.
    def place(coords, offset):
        out = {}
        for name, value in coords.items():
            horizontal = name in ('x1', 'x2')
            value += offset[0] if horizontal else offset[1]
            if horizontal and flip_x:
                value = src_w - value
            elif not horizontal and flip_y:
                value = src_h - value
            out[name] = value
        return out

    # Reason (3): the authored translate(5,7) points at the vertex. Negate
    # it per axis so the shadow falls away from the corner instead.
    offset = (-OFFSET_X, -OFFSET_Y)

    back = [(f, place(c, offset), w) for f, c, w in parse_lines(back_block)]
    front = [(f, place(c, (0.0, 0.0)), w) for f, c, w in parse_lines(front_block)]

    # Reason (4): crop to the FRONT layer only. The back is inset by
    # construction, so it cannot be clipped by a crop taken from the front.
    pad = max(w for _, _, w in front) / 2.0 * (src_w / RENDER_PX)
    xs = [c[k] for _, c, _ in front for k in ('x1', 'x2')]
    ys = [c[k] for _, c, _ in front for k in ('y1', 'y2')]
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    out_w, out_h = max_x - min_x, max_y - min_y

    stroke_scale = out_w / RENDER_PX

    def render(entries, start_index):
        chunks = []
        for i, (fragment, coords, width) in enumerate(entries):
            new = fragment
            new = COORD_RE.sub(lambda m: '%s="%s"' % (
                m.group(1),
                fmt(coords[m.group(1)] - (min_x if m.group(1) in ('x1', 'x2') else min_y)),
            ), new)
            new = WIDTH_RE.sub(
                lambda m: 'stroke-width="%s"' % fmt(width * stroke_scale), new)
            new = new.replace(' vector-effect="non-scaling-stroke"', '')
            new = re.sub(r'\s*style="stroke:oklch\([^"]*\)"', '', new)
            new = re.sub(r'stroke="#[0-9a-fA-F]{6}"', 'stroke="currentColor"', new)
            new = new.replace('<line ', '<line pathLength="1" style="animation-delay:%dms" '
                              % ((start_index + i) * STAGGER_MS))
            chunks.append('      ' + new)
        return '\n'.join(chunks)

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s"'
        ' fill="none" role="presentation" aria-hidden="true" focusable="false"'
        ' shape-rendering="geometricPrecision" color="#8b4a2f"'
        ' data-envelope="env-line-%s" data-corner="%s">\n'
        '  <title>Line envelope ornament, %s corner</title>\n'
        '%s\n'
        '  <g fill="none" stroke-linecap="butt">\n'
        '    <g data-layer="back" opacity="0.35">\n'
        '%s\n'
        '    </g>\n'
        '    <g data-layer="front">\n'
        '%s\n'
        '    </g>\n'
        '  </g>\n'
        '</svg>\n'
    ) % (
        fmt(out_w), fmt(out_h), fmt(out_w), fmt(out_h),
        corner, corner, corner,
        STYLE_TEMPLATE % {'duration': DURATION_MS},
        render(back, 0),
        render(front, 0),
    )


def main():
    source = open(SOURCE).read()
    for corner in ('tl', 'tr', 'bl', 'br'):
        path = os.path.join(OUT_DIR, 'env-line-%s.svg' % corner)
        svg = build(source, corner)
        open(path, 'w').write(svg)
        view = re.search(r'viewBox="([^"]+)"', svg).group(1)
        print('wrote %s  viewBox=%s' % (os.path.relpath(path, ROOT), view))


if __name__ == '__main__':
    main()
