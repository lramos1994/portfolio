# Ornament placement acceptance suite

One assertion, and it is the one that keeps being violated:

> No ornament ink may land inside a real text **line box**, at any integer
> viewport width.

## Run it

    python3 tests/acceptance.py                 # 320..2560, every integer (~2 min)
    python3 tests/acceptance.py --lo 700 --hi 800

Exit code is nonzero on any invasion, so it can gate a merge.

Requires a Chromium binary and `requests` + `websocket-client`. The binary is
looked up at `$CHROME_BIN`, falling back to the local Playwright install at
`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`.

## Why it is written this way

**Per integer, not per breakpoint.** This defect survived two rounds of review
because earlier checks sampled 360/768/1280/1920. The collision band was
736-765px: its peak at 736px was never sampled, and by 768px only a fraction
of a pixel of ink was left, invisible in a full-page screenshot. Sampling
chosen widths cannot find a defect that lives between them.

**Line boxes, not bounding boxes.** A block box spans the full column even
when its last line ends early, so bounding-box overlap reports empty space as
a collision. A check tuned to tolerate that noise goes blind to real hits.
Line boxes come from `Range.getClientRects()` on the actual text nodes.

**Exact geometry, not point sampling.** Each `<line>` is projected through the
SVG's own `getScreenCTM()` — so the check reflects what `preserveAspectRatio`
actually did, not what the markup intended — and clipped analytically
(Liang-Barsky) against each line box inflated by half the stroke width. The
inflation matters: these lines use `vector-effect: non-scaling-stroke`, so the
stroke width is in screen pixels. Per-segment intervals are unioned, so
overlapping line boxes cannot inflate the reported total.

The suite reports both a centerline figure and a stroke-edge figure. The
stroke-edge figure is the one that gates, because it is what gets painted.

## Verifying the suite still bites

A green suite means nothing until it has been shown to fail. It was validated
against commit `8d0110a`, which carries the known defect:

    git show 8d0110a:index.html > /tmp/bad/index.html   # + copy assets/
    python3 tests/acceptance.py --lo 700 --hi 800 --url file:///tmp/bad/index.html

That must report failures across 736-765px and exit 1. If it passes, the
suite has gone blind — fix the suite before trusting any green run.
