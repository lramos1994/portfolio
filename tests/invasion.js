// Returns exact ink length (px) of ornament <line> geometry falling inside
// real text LINE BOXES, projected through getScreenCTM into document coords.
// Clipping is analytic (Liang-Barsky) with per-segment interval union, so
// overlapping line boxes cannot double-count.
(() => {
  const boxes = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    if (!(n.textContent || '').trim()) continue;
    if (n.parentElement && n.parentElement.closest('svg')) continue;
    const cs = getComputedStyle(n.parentElement);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const rect of r.getClientRects()) {
      if (rect.width > 0.5 && rect.height > 0.5)
        boxes.push({
          l: rect.left, t: rect.top + window.scrollY,
          r: rect.right, b: rect.bottom + window.scrollY,
          cls: n.parentElement.className || n.parentElement.tagName,
          txt: (n.textContent || '').trim().slice(0, 34)
        });
    }
  }

  const segs = [];
  document.querySelectorAll('.ornament').forEach(svg => {
    const scs = getComputedStyle(svg);
    if (scs.display === 'none' || scs.visibility === 'hidden' ||
        parseFloat(scs.opacity) === 0) return;
    const m = svg.getScreenCTM();
    if (!m) return;
    const cls = [...svg.classList].filter(c => c !== 'ornament')[0];
    svg.querySelectorAll('line').forEach(ln => {
      const ls = getComputedStyle(ln);
      if (parseFloat(ls.strokeOpacity) === 0 || ls.display === 'none') return;
      // vector-effect: non-scaling-stroke => stroke-width is already screen px
      const sw = parseFloat(ls.strokeWidth) || 1;
      const pt = (x, y) => ({
        x: m.a * x + m.c * y + m.e,
        y: m.b * x + m.d * y + m.f + window.scrollY
      });
      const a = pt(+ln.getAttribute('x1'), +ln.getAttribute('y1'));
      const b = pt(+ln.getAttribute('x2'), +ln.getAttribute('y2'));
      segs.push({cls, x1: a.x, y1: a.y, x2: b.x, y2: b.y,
                 sw, so: parseFloat(ls.strokeOpacity)});
    });
  });

  // Liang-Barsky clip of param interval [0,1] against an axis-aligned box
  function clip(s, l, t, r, bt) {
    const dx = s.x2 - s.x1, dy = s.y2 - s.y1;
    let t0 = 0, t1 = 1;
    const p = [-dx, dx, -dy, dy];
    const q = [s.x1 - l, r - s.x1, s.y1 - t, bt - s.y1];
    for (let i = 0; i < 4; i++) {
      if (p[i] === 0) { if (q[i] < 0) return null; continue; }
      const u = q[i] / p[i];
      if (p[i] < 0) { if (u > t1) return null; if (u > t0) t0 = u; }
      else { if (u < t0) return null; if (u < t1) t1 = u; }
    }
    return t1 > t0 ? [t0, t1] : null;
  }

  function unionLen(iv, len) {
    if (!iv.length) return 0;
    iv.sort((a, b) => a[0] - b[0]);
    let tot = 0, cs = iv[0][0], ce = iv[0][1];
    for (let i = 1; i < iv.length; i++) {
      if (iv[i][0] > ce) { tot += ce - cs; cs = iv[i][0]; ce = iv[i][1]; }
      else if (iv[i][1] > ce) ce = iv[i][1];
    }
    return (tot + ce - cs) * len;
  }

  // pad = 0 -> centerline test; pad = sw/2 -> the painted stroke edge
  function measure(pad) {
    const per = {};
    let total = 0;
    for (const s of segs) {
      const len = Math.hypot(s.x2 - s.x1, s.y2 - s.y1);
      if (!len) continue;
      const p = pad ? s.sw / 2 : 0;
      const iv = [];
      let worst = null;
      for (const bx of boxes) {
        const c = clip(s, bx.l - p, bx.t - p, bx.r + p, bx.b + p);
        if (c) { iv.push(c); worst = bx; }
      }
      const ink = unionLen(iv, len);
      if (ink > 0) {
        const k = s.cls + ' -> [' + worst.cls + '] "' + worst.txt + '"';
        per[k] = (per[k] || 0) + ink;
        total += ink;
        per[k + ' @maxStrokeOpacity'] = Math.max(
          per[k + ' @maxStrokeOpacity'] || 0, s.so);
      }
    }
    return {total: Math.round(total * 100) / 100, per};
  }

  return {
    w: window.innerWidth,
    textBoxes: boxes.length,
    segments: segs.length,
    center: measure(false),
    stroke: measure(true)
  };
})()
