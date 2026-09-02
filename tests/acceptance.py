"""Acceptance suite for the ornament placement.

The assertion this suite exists for: NO ornament ink may land inside a real
text LINE BOX, at any integer viewport width. It is written per-integer on
purpose. The defect it guards against (a lifted figure reaching into the mono
stack line between 736 and 765px) survived two rounds of review precisely
because earlier checks sampled chosen breakpoints - at 768px only a fraction
of a pixel of ink remained, and the peak at 736px was never sampled.

It is also a LINE BOX check, not a bounding-box check. A block box spans the
full column even when its last line ends early, so box overlap reports empty
space as a collision and, tuned around that noise, hides real ones.

Geometry is exact rather than sampled: each <line> is projected through the
SVG's own getScreenCTM (so it reflects what preserveAspectRatio actually did)
and clipped analytically against each line box inflated by half the stroke
width, since vector-effect:non-scaling-stroke puts stroke width in screen px.
Per-segment intervals are unioned, so overlapping line boxes cannot inflate
the total.

Usage:
    python3 acceptance.py                # 320..2560, every integer
    python3 acceptance.py --lo 700 --hi 800
Exit code is nonzero on any invasion.
"""
import sys, time, argparse, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser, Page

URL = ('file://' + os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '..', 'index.html')))
JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'invasion.js')).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lo', type=int, default=320)
    ap.add_argument('--hi', type=int, default=2560)
    ap.add_argument('--height', type=int, default=900)
    ap.add_argument('--settle', type=float, default=0.045)
    ap.add_argument('--url', default=URL)
    a = ap.parse_args()

    br = Browser()
    p = Page(br, width=1280, height=a.height)
    p.goto(a.url, settle=2.5)

    failures = []
    margin = (1e9, None, None)
    t0 = time.time()
    for w in range(a.lo, a.hi + 1):
        p.resize(w, a.height)
        time.sleep(a.settle)
        r = p.ev(JS)
        if r['w'] != w:
            failures.append(f'{w}px: viewport did not apply (got {r["w"]}px)')
            continue
        if r['segments'] == 0:
            failures.append(f'{w}px: no ornament segments found - suite blind')
            continue
        if r['stroke']['total'] > 0:
            keys = [k for k in r['stroke']['per'] if '@maxStrokeOpacity' not in k]
            failures.append(
                f'{w}px: {r["stroke"]["total"]:.2f}px of ornament ink inside '
                f'text line boxes -> {keys}')
        if w % 200 == 0:
            print(f'  ... {w}px ok ({r["textBoxes"]} line boxes, '
                  f'{r["segments"]} segments)', flush=True)
    p.close()
    br.stop()

    n = a.hi - a.lo + 1
    print(f'\nswept every integer width {a.lo}..{a.hi} ({n} widths) '
          f'in {time.time()-t0:.0f}s')
    if failures:
        print(f'FAIL: ornament ink inside text line boxes at '
              f'{len(failures)} widths')
        for f in failures[:40]:
            print('  -', f)
        if len(failures) > 40:
            print(f'  ... and {len(failures)-40} more')
        return 1
    print('PASS: 0 widths with ornament ink inside a text line box')
    return 0


if __name__ == '__main__':
    sys.exit(main())
