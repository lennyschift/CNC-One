import type { PxRect } from "./geometry";
import type { RasterSource } from "./rasterEncode";
import type { FillColor } from "./types";

/*
 * Keeps the grid of a title block intact. A redaction rectangle would cut every
 * table line that runs into it. A line piece is re-drawn ONLY if it
 *   - is thin (≤ MAX_THICK px, i.e. ≈ 2 pt at 300 DPI),
 *   - is dark from the rectangle's edge inward (a run that starts at the edge), and
 *   - continues as a long dark run just OUTSIDE the rectangle (so it belongs to the grid, not to the removed content).
 * It is drawn from the edge up to where it really ends — through the whole rectangle if it runs through, or as a stub if
 * it ends inside (cell border). Text, an underline that ends with the text, logo shapes and filled bars fail these tests.
 * The line is drawn row by row in the colours its visible part has OUTSIDE the rectangle — no pixel from inside
 * the rectangle is ever copied, so nothing of the removed content can come back this way.
 *
 * `refineRect` additionally pulls a rectangle tight around the ink that is really there (minus grid lines), so that
 * fewer lines are touched in the first place.
 */

/** One pixel row/column of a line piece with its own colour (a thin line is several rows: dark middle, gray edges). */
export interface LineStrip {
  rect: PxRect;
  color: FillColor;
}

export interface KeptLine {
  /** Bounding box of the whole piece (what is exempt from the "pure fill colour" checks). */
  rect: PxRect;
  /** What is actually drawn: one strip per pixel row/column, each in the colour its visible part has OUTSIDE the area. */
  strips: LineStrip[];
}

/** Pixels per pt the pixel limits below were chosen for (300 DPI). They scale with the real resolution. */
const REF_PX_PER_PT = 300 / 72;
/** Share of the outside pixels that must be dark. */
const OUT_COVER = 0.9;
/** Luminance below this counts as line ink (thin anti-aliased lines are light gray). */
const DARK = 200;

interface Limits {
  /** Length of the dark run that must continue OUTSIDE the rectangle (≈ 4 pt). */
  outLen: number;
  /** Thickest line (≈ 2.2 pt) that counts as a line, not as a filled bar. */
  maxThick: number;
  /** Minimum length of the part inside the rectangle that is worth re-drawing (≈ 0.5 pt). */
  minRun: number;
  /** Rows/columns of one line may differ by this much in run length (≈ 0.7 pt). */
  tol: number;
}

function limitsFor(pxPerPt: number): Limits {
  const k = pxPerPt / REF_PX_PER_PT;
  return {
    outLen: Math.max(8, Math.round(16 * k)),
    maxThick: Math.max(4, Math.round(9 * k)),
    minRun: Math.max(2, Math.round(2 * k)),
    tol: Math.max(2, Math.round(3 * k)),
  };
}

const lum = (r: number, g: number, b: number) => 0.299 * r + 0.587 * g + 0.114 * b;

interface Reader {
  isDark: (x: number, y: number) => boolean;
  color: (samples: [number, number][]) => FillColor;
}

function makeReader(src: RasterSource, y0: number, y1: number): Reader {
  const rows = src.readRows(y0, y1);
  const at = (x: number, y: number) => (y - y0) * src.width * 4 + x * 4;
  const pixel = (x: number, y: number): [number, number, number] => {
    const p = at(x, y);
    const a = rows[p + 3]! / 255;
    return [rows[p]! * a + 255 * (1 - a), rows[p + 1]! * a + 255 * (1 - a), rows[p + 2]! * a + 255 * (1 - a)];
  };
  return {
    isDark: (x, y) => {
      const [r, g, b] = pixel(x, y);
      return lum(r, g, b) < DARK;
    },
    color: (samples) => {
      let r = 0;
      let g = 0;
      let b = 0;
      for (const [x, y] of samples) {
        const p = pixel(x, y);
        r += p[0];
        g += p[1];
        b += p[2];
      }
      const n = Math.max(1, samples.length);
      return { r: Math.round(r / n), g: Math.round(g / n), b: Math.round(b / n) };
    },
  };
}

/** Groups consecutive qualifying rows/columns whose run lengths are similar into bands [from, to) with their shortest run. */
function bands(runs: number[], offset: number, L: Limits): { from: number; to: number; run: number }[] {
  const out: { from: number; to: number; run: number }[] = [];
  let start = -1;
  let min = 0;
  let max = 0;
  const close = (end: number) => {
    if (start >= 0) out.push({ from: offset + start, to: offset + end, run: min });
    start = -1;
  };
  for (let i = 0; i < runs.length; i++) {
    const r = runs[i]!;
    if (r < L.minRun) {
      close(i);
      continue;
    }
    if (start >= 0 && Math.abs(r - min) > L.tol && Math.abs(r - max) > L.tol) close(i);
    if (start < 0) {
      start = i;
      min = r;
      max = r;
    } else {
      min = Math.min(min, r);
      max = Math.max(max, r);
    }
  }
  close(runs.length);
  return out;
}

/** Finds the table-line pieces to re-draw inside `rect` (pixels of the ORIGINAL render, taken before it was painted over). */
export function findKeptLines(src: RasterSource, rect: PxRect, pxPerPt = REF_PX_PER_PT): KeptLine[] {
  const L = limitsFor(pxPerPt);
  const w = rect.x1 - rect.x0;
  const h = rect.y1 - rect.y0;
  if (w < 2 || h < 2) return [];
  const ry0 = Math.max(0, rect.y0 - L.outLen);
  const ry1 = Math.min(src.height, rect.y1 + L.outLen);
  const rd = makeReader(src, ry0, ry1);
  const out: KeptLine[] = [];

  const outsideDark = (pts: [number, number][]) => pts.filter(([x, y]) => rd.isDark(x, y)).length >= OUT_COVER * pts.length;

  // ── horizontal lines: for every row, the dark run starting at the left / right edge ───────────
  const leftRuns: number[] = [];
  const rightRuns: number[] = [];
  for (let y = rect.y0; y < rect.y1; y++) {
    let left = 0;
    if (rect.x0 - L.outLen >= 0 && outsideDark(Array.from({ length: L.outLen }, (_, k) => [rect.x0 - 1 - k, y] as [number, number]))) {
      while (left < w && rd.isDark(rect.x0 + left, y)) left++;
    }
    let right = 0;
    if (rect.x1 + L.outLen <= src.width && outsideDark(Array.from({ length: L.outLen }, (_, k) => [rect.x1 + k, y] as [number, number]))) {
      while (right < w && rd.isDark(rect.x1 - 1 - right, y)) right++;
    }
    leftRuns.push(left);
    rightRuns.push(right);
  }
  for (const b of bands(leftRuns, rect.y0, L)) {
    if (b.to - b.from > L.maxThick) continue;
    const strips: LineStrip[] = [];
    for (let y = b.from; y < b.to; y++) {
      const samples: [number, number][] = [];
      for (let k = 1; k <= 4; k++) samples.push([rect.x0 - k, y]);
      strips.push({ rect: { x0: rect.x0, y0: y, x1: rect.x0 + b.run, y1: y + 1 }, color: rd.color(samples) });
    }
    out.push({ rect: { x0: rect.x0, y0: b.from, x1: rect.x0 + b.run, y1: b.to }, strips });
  }
  for (const b of bands(rightRuns, rect.y0, L)) {
    if (b.to - b.from > L.maxThick) continue;
    const strips: LineStrip[] = [];
    for (let y = b.from; y < b.to; y++) {
      const samples: [number, number][] = [];
      for (let k = 0; k < 4; k++) samples.push([rect.x1 + k, y]);
      strips.push({ rect: { x0: rect.x1 - b.run, y0: y, x1: rect.x1, y1: y + 1 }, color: rd.color(samples) });
    }
    out.push({ rect: { x0: rect.x1 - b.run, y0: b.from, x1: rect.x1, y1: b.to }, strips });
  }

  // ── vertical lines: for every column, the dark run starting at the top / bottom edge ──────────
  const topRuns: number[] = [];
  const bottomRuns: number[] = [];
  for (let x = rect.x0; x < rect.x1; x++) {
    let top = 0;
    if (rect.y0 - L.outLen >= 0 && outsideDark(Array.from({ length: L.outLen }, (_, k) => [x, rect.y0 - 1 - k] as [number, number]))) {
      while (top < h && rd.isDark(x, rect.y0 + top)) top++;
    }
    let bottom = 0;
    if (rect.y1 + L.outLen <= src.height && outsideDark(Array.from({ length: L.outLen }, (_, k) => [x, rect.y1 + k] as [number, number]))) {
      while (bottom < h && rd.isDark(x, rect.y1 - 1 - bottom)) bottom++;
    }
    topRuns.push(top);
    bottomRuns.push(bottom);
  }
  for (const b of bands(topRuns, rect.x0, L)) {
    if (b.to - b.from > L.maxThick) continue;
    const strips: LineStrip[] = [];
    for (let x = b.from; x < b.to; x++) {
      const samples: [number, number][] = [];
      for (let k = 1; k <= 4; k++) samples.push([x, rect.y0 - k]);
      strips.push({ rect: { x0: x, y0: rect.y0, x1: x + 1, y1: rect.y0 + b.run }, color: rd.color(samples) });
    }
    out.push({ rect: { x0: b.from, y0: rect.y0, x1: b.to, y1: rect.y0 + b.run }, strips });
  }
  for (const b of bands(bottomRuns, rect.x0, L)) {
    if (b.to - b.from > L.maxThick) continue;
    const strips: LineStrip[] = [];
    for (let x = b.from; x < b.to; x++) {
      const samples: [number, number][] = [];
      for (let k = 0; k < 4; k++) samples.push([x, rect.y1 + k]);
      strips.push({ rect: { x0: x, y0: rect.y1 - b.run, x1: x + 1, y1: rect.y1 }, color: rd.color(samples) });
    }
    out.push({ rect: { x0: b.from, y0: rect.y1 - b.run, x1: b.to, y1: rect.y1 }, strips });
  }
  // a line that runs through is found from both sides: keep one piece, drop pieces lying inside another
  const inside = (a: PxRect, b: PxRect) => a.x0 >= b.x0 && a.y0 >= b.y0 && a.x1 <= b.x1 && a.y1 <= b.y1;
  return out.filter((p, i) => !out.some((q, j) => j !== i && inside(p.rect, q.rect) && (!inside(q.rect, p.rect) || j < i)));
}

/** Everything that is not (almost) pure white counts as ink for the shrink-wrap, so even very light gray content
 * (watermarks, light cell shading, faint stamps) stays covered. CNC One: 254 instead of 250 — a pixel with luminance
 * 250…253 is faint but visible and must never be left between the tight area and the area the user drew. */
const INK = 254;

/**
 * Pulls `rect` tight around the content inside it: the bounding box of everything that is not white and not a grid-line
 * piece (see findKeptLines), plus `marginPx`. Never larger than `rect`. If there is no such content, `rect` is kept.
 * Returns the (possibly smaller) area to paint and the line pieces to re-draw inside it.
 */
export function refineRect(
  src: RasterSource,
  rect: PxRect,
  marginPx: number,
  pxPerPt = REF_PX_PER_PT,
): { rect: PxRect; lines: KeptLine[] } {
  const grid = findKeptLines(src, rect, pxPerPt);
  const rows = src.readRows(rect.y0, rect.y1);
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (let y = rect.y0; y < rect.y1; y++) {
    for (let x = rect.x0; x < rect.x1; x++) {
      if (grid.some((g) => x >= g.rect.x0 && x < g.rect.x1 && y >= g.rect.y0 && y < g.rect.y1)) continue;
      const p = ((y - rect.y0) * src.width + x) * 4;
      const a = rows[p + 3]! / 255;
      const l = lum(rows[p]! * a + 255 * (1 - a), rows[p + 1]! * a + 255 * (1 - a), rows[p + 2]! * a + 255 * (1 - a));
      if (l >= INK) continue;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  if (x1 < x0) return { rect, lines: grid };
  const tight: PxRect = {
    x0: Math.max(rect.x0, x0 - marginPx),
    y0: Math.max(rect.y0, y0 - marginPx),
    x1: Math.min(rect.x1, x1 + 1 + marginPx),
    y1: Math.min(rect.y1, y1 + 1 + marginPx),
  };
  return { rect: tight, lines: findKeptLines(src, tight, pxPerPt) };
}
