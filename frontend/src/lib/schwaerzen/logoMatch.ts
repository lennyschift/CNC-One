/*
 * Logo detection: multi-scale template matching with zero-mean normalized
 * cross-correlation (like cv2.matchTemplate TM_CCOEFF_NORMED), in plain
 * TypeScript — no OpenCV, no network. Pure functions (the Web Worker is a thin
 * wrapper), so they are unit-testable in Node.
 *
 * Two stages: (1) FFT correlation on a COARSE page image (long side 512 px)
 * over all scales finds candidates fast; (2) every candidate is refined by
 * direct correlation on a finer image (long side 1024 px) around the coarse
 * position and over nearby scales, which gives the final box and score.
 */

export interface GrayImage {
  width: number;
  height: number;
  /** 0..255 */
  data: Float32Array;
}

/**
 * How a template matched: gray = same brightness pattern, invert = inverted (dark logo vs. light logo on dark),
 * edge = same outlines regardless of fill/colour/polarity (like the Canny variant of the Python tool).
 */
export type LogoVariant = "gray" | "invert" | "edge";

export interface LogoHit {
  /** Box as fractions (0..1) of the page, origin top-left. */
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  score: number;
  /** Scale relative to the template's original pixel size at 300 DPI. */
  scale: number;
  variant: LogoVariant;
}

/**
 * Resolution of the two search stages. It follows the PAPER SIZE, not a fixed pixel count: a logo has the same size in mm on
 * an A3 and on an A1 sheet (the title block is standardised), so on an A1 page it must get as many pixels as on A3 —
 * with a fixed 1536 px for the long side it got half as many and fine strokes were lost. Capped for memory
 * (the integral images need 16 bytes per pixel per variant).
 */
export const MIN_FINE_LONG_SIDE = 1536; // A3 and smaller
export const MAX_FINE_LONG_SIDE = 2560; // ≈ A1 at 1.07 px/pt, larger sheets get a little less
const FINE_PX_PER_PT = 1.1;
export function searchSizes(longPt: number): { coarse: number; fine: number; render: number } {
  const fine = Math.round(Math.min(MAX_FINE_LONG_SIDE, Math.max(MIN_FINE_LONG_SIDE, longPt * FINE_PX_PER_PT)));
  return { coarse: Math.round(fine / 3), fine, render: Math.round((fine * 4) / 3) };
}
/** Same range as the Python tool: 10 % … 300 % of the template's 300-DPI pixel size. */
const SCALE_MIN = 0.1;
const SCALE_MAX = 3.0;
/** Size steps of the coarse search: a wordmark tolerates only a few % of size error, so the grid is fine. */
const SCALE_STEP = 1.1;
/** How many coarse candidates are examined in detail (text-heavy pages have hundreds of look-alike peaks). */
const MAX_REFINE = 40;
/** The inverted comparison is the least specific one (every dark text line correlates a little): it must beat the limit by this much. */
const INVERT_EXTRA = 0.1;
/**
 * A real logo carries about as much ink as its template. A window of white space with one text line has far less, a
 * dense block far more — even if the pattern correlates. Ratio of 'darkness' (255 − mean brightness) window / template.
 */
const INK_RATIO_MIN = 0.45;
const INK_RATIO_MAX = 2.2;
const MIN_TEMPLATE_PX = 9;
/** Windows (and templates) flatter than this (gray-level std-dev) are ignored: noise-only "matches". */
const MIN_STD = 4;
/** Edge-magnitude images have a smaller value range. */
const MIN_STD_EDGE = 1.5;

// ── resampling ─────────────────────────────────────────────────────────────────────────────

interface Taps {
  idx: Int32Array;
  w: Float32Array;
  start: Int32Array;
  count: Int32Array;
}

/** Per-target-pixel source taps: box average when shrinking, linear interpolation when enlarging. */
function makeTaps(srcN: number, dstN: number): Taps {
  const ratio = srcN / dstN;
  const idx: number[] = [];
  const w: number[] = [];
  const start = new Int32Array(dstN);
  const count = new Int32Array(dstN);
  for (let i = 0; i < dstN; i++) {
    start[i] = idx.length;
    if (ratio > 1) {
      const a = i * ratio;
      const b = (i + 1) * ratio;
      for (let s = Math.floor(a); s < Math.min(srcN, Math.ceil(b)); s++) {
        const overlap = Math.min(b, s + 1) - Math.max(a, s);
        if (overlap > 0) {
          idx.push(s);
          w.push(overlap / ratio);
        }
      }
    } else {
      const c = (i + 0.5) * ratio - 0.5;
      const s0 = Math.min(srcN - 1, Math.max(0, Math.floor(c)));
      const s1 = Math.min(srcN - 1, s0 + 1);
      const f = Math.min(1, Math.max(0, c - s0));
      idx.push(s0, s1);
      w.push(1 - f, f);
    }
    count[i] = idx.length - start[i]!;
  }
  return { idx: Int32Array.from(idx), w: Float32Array.from(w), start, count };
}

export function resizeArea(src: GrayImage, dw: number, dh: number): GrayImage {
  dw = Math.max(1, Math.round(dw));
  dh = Math.max(1, Math.round(dh));
  if (dw === src.width && dh === src.height) return src;
  const tx = makeTaps(src.width, dw);
  const ty = makeTaps(src.height, dh);
  const tmp = new Float32Array(dw * src.height);
  for (let y = 0; y < src.height; y++) {
    const row = y * src.width;
    for (let x = 0; x < dw; x++) {
      let acc = 0;
      for (let k = tx.start[x]!, e = k + tx.count[x]!; k < e; k++) acc += src.data[row + tx.idx[k]!]! * tx.w[k]!;
      tmp[y * dw + x] = acc;
    }
  }
  const out = new Float32Array(dw * dh);
  for (let y = 0; y < dh; y++) {
    for (let x = 0; x < dw; x++) {
      let acc = 0;
      for (let k = ty.start[y]!, e = k + ty.count[y]!; k < e; k++) acc += tmp[ty.idx[k]! * dw + x]! * ty.w[k]!;
      out[y * dw + x] = acc;
    }
  }
  return { width: dw, height: dh, data: out };
}

// ── FFT ───────────────────────────────────────────────────────────────────────────────────

const fftCache = new Map<number, { rev: Uint32Array; cos: Float64Array; sin: Float64Array }>();

function fftTables(n: number) {
  let t = fftCache.get(n);
  if (t) return t;
  const bits = Math.log2(n);
  const rev = new Uint32Array(n);
  for (let i = 0; i < n; i++) {
    let r = 0;
    for (let b = 0; b < bits; b++) if (i & (1 << b)) r |= 1 << (bits - 1 - b);
    rev[i] = r;
  }
  const cos = new Float64Array(n / 2);
  const sin = new Float64Array(n / 2);
  for (let i = 0; i < n / 2; i++) {
    cos[i] = Math.cos((2 * Math.PI * i) / n);
    sin[i] = Math.sin((2 * Math.PI * i) / n);
  }
  t = { rev, cos, sin };
  fftCache.set(n, t);
  return t;
}

/** In-place radix-2 FFT of length n (power of two). `sign` = -1 forward, +1 inverse (unnormalized). */
function fft1d(re: Float64Array, im: Float64Array, n: number, sign: 1 | -1): void {
  const { rev, cos, sin } = fftTables(n);
  for (let i = 0; i < n; i++) {
    const j = rev[i]!;
    if (j > i) {
      const tr = re[i]!;
      re[i] = re[j]!;
      re[j] = tr;
      const ti = im[i]!;
      im[i] = im[j]!;
      im[j] = ti;
    }
  }
  for (let size = 2; size <= n; size <<= 1) {
    const half = size >> 1;
    const step = n / size;
    for (let start = 0; start < n; start += size) {
      for (let k = 0, t = 0; k < half; k++, t += step) {
        const wr = cos[t]!;
        const wi = sign * sin[t]!;
        const a = start + k;
        const b = a + half;
        const xr = re[b]! * wr - im[b]! * wi;
        const xi = re[b]! * wi + im[b]! * wr;
        re[b] = re[a]! - xr;
        im[b] = im[a]! - xi;
        re[a] = re[a]! + xr;
        im[a] = im[a]! + xi;
      }
    }
  }
}

function fft2d(re: Float64Array, im: Float64Array, nx: number, ny: number, sign: 1 | -1): void {
  for (let y = 0; y < ny; y++) fft1d(re.subarray(y * nx, (y + 1) * nx), im.subarray(y * nx, (y + 1) * nx), nx, sign);
  const cr = new Float64Array(ny);
  const ci = new Float64Array(ny);
  for (let x = 0; x < nx; x++) {
    for (let y = 0; y < ny; y++) {
      cr[y] = re[y * nx + x]!;
      ci[y] = im[y * nx + x]!;
    }
    fft1d(cr, ci, ny, sign);
    for (let y = 0; y < ny; y++) {
      re[y * nx + x] = cr[y]!;
      im[y * nx + x] = ci[y]!;
    }
  }
}

const pow2 = (n: number) => 2 ** Math.ceil(Math.log2(Math.max(2, n)));

// ── integral images ───────────────────────────────────────────────────────────────────────

interface Integral {
  w: number;
  sum: Float64Array;
  sq: Float64Array;
}

function integral(img: GrayImage): Integral {
  const w = img.width + 1;
  const sum = new Float64Array(w * (img.height + 1));
  const sq = new Float64Array(w * (img.height + 1));
  for (let y = 0; y < img.height; y++) {
    let rs = 0;
    let rq = 0;
    for (let x = 0; x < img.width; x++) {
      const v = img.data[y * img.width + x]!;
      rs += v;
      rq += v * v;
      sum[(y + 1) * w + x + 1] = sum[y * w + x + 1]! + rs;
      sq[(y + 1) * w + x + 1] = sq[y * w + x + 1]! + rq;
    }
  }
  return { w, sum, sq };
}

/** Σ(I−μ)² and ΣI over the window at (x,y) of size tw×th. */
function windowStats(ii: Integral, x: number, y: number, tw: number, th: number): { varSum: number; sum: number } {
  const w = ii.w;
  const a = y * w + x;
  const b = y * w + x + tw;
  const c = (y + th) * w + x;
  const d = (y + th) * w + x + tw;
  const s = ii.sum[d]! - ii.sum[b]! - ii.sum[c]! + ii.sum[a]!;
  const q = ii.sq[d]! - ii.sq[b]! - ii.sq[c]! + ii.sq[a]!;
  return { varSum: q - (s * s) / (tw * th), sum: s };
}

// ── edge image ───────────────────────────────────────────────────────────────────────────

/** Sobel gradient magnitude (0 at the border). Insensitive to fill colour and polarity. */
export function edgeMagnitude(img: GrayImage): GrayImage {
  const { width: w, height: h, data: d } = img;
  const out = new Float32Array(w * h);
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const gx = d[i - w + 1]! + 2 * d[i + 1]! + d[i + w + 1]! - d[i - w - 1]! - 2 * d[i - 1]! - d[i + w - 1]!;
      const gy = d[i + w - 1]! + 2 * d[i + w]! + d[i + w + 1]! - d[i - w - 1]! - 2 * d[i - w]! - d[i - w + 1]!;
      out[i] = Math.sqrt(gx * gx + gy * gy) / 4;
    }
  }
  return { width: w, height: h, data: out };
}

/** Two passes of a 3×3 box blur (σ ≈ 1.2 px): the coarse search must not collapse when the size is a few % off. */
export function softBlur(img: GrayImage): GrayImage {
  let cur = img;
  for (let pass = 0; pass < 2; pass++) {
    const { width: w, height: h, data: d } = cur;
    const tmp = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const a = d[y * w + Math.max(0, x - 1)]!;
        const c = d[y * w + Math.min(w - 1, x + 1)]!;
        tmp[y * w + x] = (a + d[y * w + x]! + c) / 3;
      }
    }
    const out = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
      const y0 = Math.max(0, y - 1) * w;
      const y1 = Math.min(h - 1, y + 1) * w;
      for (let x = 0; x < w; x++) out[y * w + x] = (tmp[y0 + x]! + tmp[y * w + x]! + tmp[y1 + x]!) / 3;
    }
    cur = { width: w, height: h, data: out };
  }
  return cur;
}

// ── template preparation ─────────────────────────────────────────────────────────────────

/**
 * Cuts away uniform margins (transparent/white padding around a logo file). The padding is not part of the logo, but it
 * would be compared against whatever lies around the logo in the drawing (table lines, other text) and lower every score.
 * Returns the cropped image plus the kept fractions of width/height (to correct the template's original size).
 */
export function trimMargins(img: GrayImage): { img: GrayImage; rw: number; rh: number } {
  const { width: w, height: h, data: d } = img;
  // background = most common (16-level) brightness on the border
  const hist = new Uint32Array(17);
  const bump = (v: number) => hist[Math.min(16, Math.round(v / 16))]!++;
  for (let x = 0; x < w; x++) {
    bump(d[x]!);
    bump(d[(h - 1) * w + x]!);
  }
  for (let y = 0; y < h; y++) {
    bump(d[y * w]!);
    bump(d[y * w + w - 1]!);
  }
  let bin = 0;
  for (let k = 1; k <= 16; k++) if (hist[k]! > hist[bin]!) bin = k;
  const bg = bin * 16;
  // Only light paper around the logo is padding. A dark/coloured border (frame, filled background) is PART of the logo.
  if (bg < 190) return { img, rw: 1, rh: 1 };
  const TOL = 20;
  const rowIsBg = (y: number) => {
    let off = 0;
    for (let x = 0; x < w; x++) if (Math.abs(d[y * w + x]! - bg) > TOL) off++;
    return off <= w * 0.004;
  };
  const colIsBg = (x: number, y0: number, y1: number) => {
    let off = 0;
    for (let y = y0; y < y1; y++) if (Math.abs(d[y * w + x]! - bg) > TOL) off++;
    return off <= (y1 - y0) * 0.004;
  };
  let top = 0;
  let bottom = h;
  while (top < bottom - 1 && rowIsBg(top)) top++;
  while (bottom > top + 1 && rowIsBg(bottom - 1)) bottom--;
  let left = 0;
  let right = w;
  while (left < right - 1 && colIsBg(left, top, bottom)) left++;
  while (right > left + 1 && colIsBg(right - 1, top, bottom)) right--;
  const m = 2; // keep a hair of margin
  top = Math.max(0, top - m);
  left = Math.max(0, left - m);
  bottom = Math.min(h, bottom + m);
  right = Math.min(w, right + m);
  const cw = right - left;
  const ch = bottom - top;
  if (cw < 12 || ch < 12 || (cw === w && ch === h)) return { img, rw: 1, rh: 1 };
  const out = new Float32Array(cw * ch);
  for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) out[y * cw + x] = d[(top + y) * w + left + x]!;
  return { img: { width: cw, height: ch, data: out }, rw: cw / w, rh: ch / h };
}

// ── templates ─────────────────────────────────────────────────────────────────────────────

interface ZeroMeanTemplate {
  w: number;
  h: number;
  data: Float32Array;
  /** sqrt(Σ T0²) */
  norm: number;
}

function zeroMean(t: GrayImage, minStd: number): ZeroMeanTemplate | null {
  const n = t.width * t.height;
  let mean = 0;
  for (let i = 0; i < n; i++) mean += t.data[i]!;
  mean /= n;
  const data = new Float32Array(n);
  let sq = 0;
  for (let i = 0; i < n; i++) {
    const v = t.data[i]! - mean;
    data[i] = v;
    sq += v * v;
  }
  if (Math.sqrt(sq / n) < minStd) return null;
  return { w: t.width, h: t.height, data, norm: Math.sqrt(sq) };
}

// ── coarse stage ─────────────────────────────────────────────────────────────────────────

class CoarseIndex {
  readonly img: GrayImage;
  private readonly minStd: number;
  private readonly nx: number;
  private readonly ny: number;
  private readonly fre: Float64Array;
  private readonly fim: Float64Array;
  private readonly ii: Integral;

  constructor(img: GrayImage, minStd: number) {
    this.img = img;
    this.minStd = minStd;
    this.nx = pow2(img.width);
    this.ny = pow2(img.height);
    let mean = 0;
    for (let i = 0; i < img.data.length; i++) mean += img.data[i]!;
    mean /= img.data.length;
    const centered: GrayImage = { width: img.width, height: img.height, data: img.data.map((v) => v - mean) };
    this.ii = integral(centered);
    this.fre = new Float64Array(this.nx * this.ny);
    this.fim = new Float64Array(this.nx * this.ny);
    for (let y = 0; y < img.height; y++) {
      for (let x = 0; x < img.width; x++) this.fre[y * this.nx + x] = centered.data[y * img.width + x]!;
    }
    fft2d(this.fre, this.fim, this.nx, this.ny, -1);
  }

  /** Signed NCC map for all positions where the template fits completely. */
  match(tpl: ZeroMeanTemplate): { map: Float32Array; mw: number; mh: number } | null {
    const { img, nx, ny } = this;
    if (tpl.w >= img.width || tpl.h >= img.height) return null;
    const re = new Float64Array(nx * ny);
    const im = new Float64Array(nx * ny);
    for (let y = 0; y < tpl.h; y++) {
      for (let x = 0; x < tpl.w; x++) re[y * nx + x] = tpl.data[y * tpl.w + x]!;
    }
    fft2d(re, im, nx, ny, -1);
    // page · conj(template)
    for (let i = 0; i < re.length; i++) {
      const pr = this.fre[i]!;
      const pi = this.fim[i]!;
      const tr = re[i]!;
      const ti = -im[i]!;
      re[i] = pr * tr - pi * ti;
      im[i] = pr * ti + pi * tr;
    }
    fft2d(re, im, nx, ny, 1);
    const scaleInv = 1 / (nx * ny);

    const mw = img.width - tpl.w + 1;
    const mh = img.height - tpl.h + 1;
    const n = tpl.w * tpl.h;
    const map = new Float32Array(mw * mh);
    for (let y = 0; y < mh; y++) {
      for (let x = 0; x < mw; x++) {
        const { varSum } = windowStats(this.ii, x, y, tpl.w, tpl.h);
        if (varSum < n * this.minStd * this.minStd) continue; // flat window
        map[y * mw + x] = (re[y * nx + x]! * scaleInv) / (tpl.norm * Math.sqrt(varSum));
      }
    }
    return { map, mw, mh };
  }
}

// ── fine stage ───────────────────────────────────────────────────────────────────────────

class FineIndex {
  readonly img: GrayImage;
  private readonly ii: Integral;
  private readonly minStd: number;
  constructor(img: GrayImage, minStd: number) {
    this.img = img;
    this.minStd = minStd;
    this.ii = integral(img);
  }

  /** Mean brightness of a window (0..255). */
  windowMean(x: number, y: number, w: number, h: number): number {
    return windowStats(this.ii, x, y, w, h).sum / (w * h);
  }

  /** Direct signed NCC at one position; 0 if the window is flat, NaN if it lies (partly) outside the image. */
  ncc(tpl: ZeroMeanTemplate, x: number, y: number): number {
    const { img } = this;
    if (x < 0 || y < 0 || x + tpl.w > img.width || y + tpl.h > img.height) return NaN;
    const { varSum } = windowStats(this.ii, x, y, tpl.w, tpl.h);
    if (varSum < tpl.w * tpl.h * this.minStd * this.minStd) return 0;
    let acc = 0;
    for (let ty = 0; ty < tpl.h; ty++) {
      const pr = (y + ty) * img.width + x;
      const tr = ty * tpl.w;
      for (let tx = 0; tx < tpl.w; tx++) acc += img.data[pr + tx]! * tpl.data[tr + tx]!;
    }
    // Σ I·T0 needs no window-mean term because T0 has zero mean.
    return acc / (tpl.norm * Math.sqrt(varSum));
  }
}

// ── shared setup ─────────────────────────────────────────────────────────────────────────

export interface FindLogoOptions {
  /** Minimum final (fine-stage) score, e.g. 0.45. */
  threshold: number;
  /** Page size in pt (to relate template pixels at 300 DPI to the page). */
  pageWidthPt: number;
  pageHeightPt: number;
  /** Original template size in px (at 300 DPI); the passed template image may be smaller. */
  templateWidth: number;
  templateHeight: number;
  maxHits?: number;
  /** Search only here (centre of the logo inside the zone). Default: whole page. */
  zone?: LogoZone;
  /** Which comparisons to use (default: all three). */
  variants?: readonly LogoVariant[];
  signal?: { aborted: boolean };
  /** Test/diagnosis hook: the coarse candidates that go into the detailed check (best first). */
  onCandidates?: (c: { variant: LogoVariant; scale: number; score: number; xFrac: number; yFrac: number }[]) => void;
}

/** Where on the page a logo may be searched. Most customers put the logo in the title block / a corner. */
export type LogoZone = "all" | "top" | "bottom" | "left" | "right" | "corners";

/** Is the point (fractions of the page) inside the zone? */
export function inZone(zone: LogoZone | undefined, fx: number, fy: number): boolean {
  switch (zone) {
    case "top":
      return fy < 0.5;
    case "bottom":
      return fy >= 0.5;
    case "left":
      return fx < 0.5;
    case "right":
      return fx >= 0.5;
    case "corners":
      return (fx < 0.35 || fx > 0.65) && (fy < 0.35 || fy > 0.65);
    default:
      return true;
  }
}

export const ALL_VARIANTS: readonly LogoVariant[] = ["gray", "invert", "edge"];

export function scaleList(): number[] {
  const out: number[] = [];
  for (let s = SCALE_MIN; s <= SCALE_MAX * 1.0001; s *= SCALE_STEP) out.push(Number(s.toFixed(4)));
  return out;
}

const iou = (a: { x0: number; y0: number; x1: number; y1: number }, b: { x0: number; y0: number; x1: number; y1: number }) => {
  const iw = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0);
  const ih = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
  if (iw <= 0 || ih <= 0) return 0;
  const inter = iw * ih;
  return inter / ((a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter);
};

interface Setup {
  template: GrayImage;
  /** Template size in original px after trimming the margins. */
  tw0: number;
  th0: number;
  coarseGray: CoarseIndex;
  coarseEdge: CoarseIndex | null;
  fineGray: FineIndex;
  fineEdge: FineIndex | null;
  fCoarse: number;
  fFine: number;
  ratio: number;
}

function setup(page: GrayImage, templateIn: GrayImage, opts: FindLogoOptions, withEdge: boolean): Setup {
  const longPt = Math.max(opts.pageWidthPt, opts.pageHeightPt);
  const aspect = page.width / page.height;
  const sized = (longSide: number) => (aspect >= 1 ? [longSide, longSide / aspect] : [longSide * aspect, longSide]) as [number, number];
  const sizes = searchSizes(longPt);
  const [cw, chh] = sized(sizes.coarse);
  const [fw, fh] = sized(sizes.fine);
  const coarseImg = resizeArea(page, cw, chh);
  const fineImg = resizeArea(page, fw, fh);
  const trimmed = trimMargins(templateIn);
  const long = (i: GrayImage) => Math.max(i.width, i.height);
  return {
    template: trimmed.img,
    tw0: opts.templateWidth * trimmed.rw,
    th0: opts.templateHeight * trimmed.rh,
    coarseGray: new CoarseIndex(softBlur(coarseImg), MIN_STD / 2),
    coarseEdge: withEdge ? new CoarseIndex(softBlur(edgeMagnitude(coarseImg)), MIN_STD_EDGE / 2) : null,
    fineGray: new FineIndex(fineImg, MIN_STD),
    fineEdge: withEdge ? new FineIndex(edgeMagnitude(fineImg), MIN_STD_EDGE) : null,
    // px per template-original-pixel, assuming the template was cut from a 300-DPI render
    fCoarse: long(coarseImg) / longPt / (300 / 72),
    fFine: long(fineImg) / longPt / (300 / 72),
    ratio: fineImg.width / coarseImg.width,
  };
}

/**
 * Template as seen by one comparison at a given pixel size (edge variant: outlines of the resized template).
 * `soft` = the same blur the coarse page image gets, so both stay comparable.
 */
function preparedTemplate(s: Setup, variant: LogoVariant, tw: number, th: number, soft = false): ZeroMeanTemplate | null {
  const resized = resizeArea(s.template, tw, th);
  if (variant === "edge") {
    const e = edgeMagnitude(resized);
    return zeroMean(soft ? softBlur(e) : e, soft ? MIN_STD_EDGE / 2 : MIN_STD_EDGE);
  }
  return zeroMean(soft ? softBlur(resized) : resized, soft ? MIN_STD / 2 : MIN_STD);
}

const sign = (v: LogoVariant) => (v === "invert" ? -1 : 1);

/**
 * Best score in a window around (baseX, baseY): signed NCC, flipped for the inverted comparison. Big templates are first
 * scanned with a coarser step (cost grows with template area × window), then polished at full resolution.
 */
function fineBest(
  s: Setup,
  variant: LogoVariant,
  zm: ZeroMeanTemplate,
  baseX: number,
  baseY: number,
  win: number,
): { score: number; x: number; y: number } {
  const idx = variant === "edge" ? s.fineEdge! : s.fineGray;
  const area = zm.w * zm.h;
  const stride = area > 40000 ? 3 : area > 15000 ? 2 : 1;
  let best = { score: -2, x: baseX, y: baseY };
  const scan = (cx: number, cy: number, radius: number, step: number) => {
    for (let dy = -radius; dy <= radius; dy += step) {
      for (let dx = -radius; dx <= radius; dx += step) {
        const raw = idx.ncc(zm, cx + dx, cy + dy);
        if (Number.isNaN(raw)) continue; // outside the page: never a match
        const v = raw * sign(variant);
        if (v > best.score) best = { score: v, x: cx + dx, y: cy + dy };
      }
    }
  };
  scan(baseX, baseY, win, stride);
  if (stride > 1) scan(best.x, best.y, stride - 1, 1);
  return best;
}

interface Candidate {
  variant: LogoVariant;
  scale: number;
  cx: number;
  cy: number;
  cw: number;
  ch: number;
  score: number;
}

/**
 * Detailed check of one coarse candidate. The coarse stage is blurred and therefore tolerant: it finds the right PLACE but
 * can be off in size by 30 %. So the size is searched again here (small windows, cheap), then the best size is examined
 * with a full window.
 */
function refineCandidate(
  s: Setup,
  c: Candidate,
  variant: LogoVariant,
  sizeAt: (scale: number, f: number) => readonly [number, number],
): { score: number; x: number; y: number; w: number; h: number; scale: number } | null {
  const kind = variant === "edge" ? "edge" : "gray";
  const cxF = (c.cx + c.cw / 2) * s.ratio;
  const cyF = (c.cy + c.ch / 2) * s.ratio;

  // 1) size search at the candidate's centre
  let bestScale = c.scale;
  let bestV = -2;
  for (let m = 0.7; m <= 1.46; m *= 1.07) {
    const scale = c.scale * m;
    const [tw, th] = sizeAt(scale, s.fFine);
    if (tw < MIN_TEMPLATE_PX || th < MIN_TEMPLATE_PX) continue;
    const zm = preparedTemplate(s, kind, tw, th);
    if (!zm) continue;
    const r = fineBest(s, variant, zm, Math.round(cxF - tw / 2), Math.round(cyF - th / 2), 3);
    if (r.score > bestV) {
      bestV = r.score;
      bestScale = scale;
    }
  }

  // 2) full-window check at three sizes around the best one
  let best: { score: number; x: number; y: number; w: number; h: number; scale: number } | null = null;
  for (const mult of [0.96, 1, 1.04]) {
    const scale = bestScale * mult;
    const [tw, th] = sizeAt(scale, s.fFine);
    if (tw < MIN_TEMPLATE_PX || th < MIN_TEMPLATE_PX) continue;
    const zm = preparedTemplate(s, kind, tw, th);
    if (!zm) continue;
    const win = Math.max(6, Math.round(0.06 * Math.max(tw, th)));
    const r = fineBest(s, variant, zm, Math.round(cxF - tw / 2), Math.round(cyF - th / 2), win);
    if (!best || r.score > best.score) best = { ...r, w: tw, h: th, scale };
  }
  return best;
}

/** Same amount of ink as the template (see INK_RATIO_*). Not applied to the inverted comparison (its paper is dark). */
function inkDensityOk(s: Setup, b: { x: number; y: number; w: number; h: number; variant: LogoVariant }): boolean {
  if (b.variant === "invert") return true;
  const tpl = resizeArea(s.template, b.w, b.h).data;
  let sum = 0;
  for (let i = 0; i < tpl.length; i++) sum += tpl[i]!;
  const tplDark = 255 - sum / tpl.length;
  if (tplDark < 3) return true; // an (almost) all-white template says nothing about ink
  const winDark = 255 - s.fineGray.windowMean(b.x, b.y, b.w, b.h);
  const ratio = winDark / tplDark;
  return ratio >= INK_RATIO_MIN && ratio <= INK_RATIO_MAX;
}

/**
 * Finds a logo on a page. `page` is a gray render of the page (any resolution
 * ≥ ~1024 px long side is fine; it is resampled internally). Returns hits
 * best-first, boxes as page fractions.
 */
export function findLogoHits(page: GrayImage, template: GrayImage, opts: FindLogoOptions): LogoHit[] {
  const variants = opts.variants ?? ALL_VARIANTS;
  const s = setup(page, template, opts, variants.includes("edge"));
  const thresholdCoarse = Math.max(0.2, opts.threshold - 0.15);
  const maxHits = opts.maxHits ?? 8;
  const sizeAt = (scale: number, f: number) => [Math.round(s.tw0 * scale * f), Math.round(s.th0 * scale * f)] as const;
  const candidates: Candidate[] = [];

  const coarseSize = s.coarseGray.img;
  const grayVariants = variants.filter((v) => v !== "edge");
  for (const scale of scaleList()) {
    if (opts.signal?.aborted) return [];
    const [tw, th] = sizeAt(scale, s.fCoarse);
    if (tw < MIN_TEMPLATE_PX || th < MIN_TEMPLATE_PX || tw >= coarseSize.width || th >= coarseSize.height) continue;

    // the gray map serves both the normal and the inverted comparison (inverted = negative peaks)
    const passes: { variants: LogoVariant[]; index: CoarseIndex; kind: "gray" | "edge" }[] = [];
    if (grayVariants.length > 0) passes.push({ variants: grayVariants, index: s.coarseGray, kind: "gray" });
    if (variants.includes("edge") && s.coarseEdge) passes.push({ variants: ["edge"], index: s.coarseEdge, kind: "edge" });

    for (const pass of passes) {
      const zm = preparedTemplate(s, pass.kind, tw, th, true);
      if (!zm) continue;
      const res = pass.index.match(zm);
      if (!res) continue;
      for (const variant of pass.variants) {
        const sg = sign(variant);
        const map = pass.variants.length > 1 || opts.zone ? res.map.slice() : res.map; // peaks are blanked out below
        if (opts.zone && opts.zone !== "all") {
          for (let i = 0; i < map.length; i++) {
            const fx = ((i % res.mw) + tw / 2) / coarseSize.width;
            const fy = (Math.floor(i / res.mw) + th / 2) / coarseSize.height;
            if (!inZone(opts.zone, fx, fy)) map[i] = 0;
          }
        }
        for (let k = 0; k < 6; k++) {
          let best = -1;
          let bi = -1;
          for (let i = 0; i < map.length; i++) {
            const v = map[i]! * sg;
            if (v > best) {
              best = v;
              bi = i;
            }
          }
          if (best < thresholdCoarse) break;
          const x = bi % res.mw;
          const y = Math.floor(bi / res.mw);
          candidates.push({ variant, scale, cx: x, cy: y, cw: tw, ch: th, score: best });
          for (let yy = Math.max(0, y - (th >> 1)); yy < Math.min(res.mh, y + (th >> 1) + 1); yy++) {
            for (let xx = Math.max(0, x - (tw >> 1)); xx < Math.min(res.mw, x + (tw >> 1) + 1); xx++) map[yy * res.mw + xx] = 0;
          }
        }
      }
    }
  }

  // global suppression of coarse candidates, best first
  candidates.sort((a, b) => b.score - a.score);
  const kept: Candidate[] = [];
  for (const c of candidates) {
    const box = { x0: c.cx, y0: c.cy, x1: c.cx + c.cw, y1: c.cy + c.ch };
    if (kept.some((k) => iou(box, { x0: k.cx, y0: k.cy, x1: k.cx + k.cw, y1: k.cy + k.ch }) > 0.25)) continue;
    kept.push(c);
    if (kept.length >= MAX_REFINE) break;
  }

  opts.onCandidates?.(kept.map((c) => ({ variant: c.variant, scale: c.scale, score: c.score, xFrac: (c.cx + c.cw / 2) / coarseSize.width, yFrac: (c.cy + c.ch / 2) / coarseSize.height })));

  // refine every candidate on the finer image
  const fineImg = s.fineGray.img;
  const hits: LogoHit[] = [];
  for (const c of kept) {
    if (opts.signal?.aborted) return [];
    // an edge candidate is also checked as plain gray (the better one counts); inverted stays inverted
    const variantsToTry: LogoVariant[] = c.variant === "edge" ? ["edge", "gray"] : [c.variant];
    let best: { score: number; x: number; y: number; w: number; h: number; scale: number; variant: LogoVariant } | null = null;
    for (const variant of variantsToTry) {
      const r = refineCandidate(s, c, variant, sizeAt);
      if (r && (!best || r.score > best.score)) best = { ...r, variant };
    }
    if (best && best.score >= opts.threshold + (best.variant === "invert" ? INVERT_EXTRA : 0) && inkDensityOk(s, best)) {
      hits.push({
        x0: best.x / fineImg.width,
        y0: best.y / fineImg.height,
        x1: (best.x + best.w) / fineImg.width,
        y1: (best.y + best.h) / fineImg.height,
        score: best.score,
        scale: best.scale,
        variant: best.variant,
      });
    }
  }

  hits.sort((a, b) => b.score - a.score);
  const finalHits: LogoHit[] = [];
  for (const h of hits) {
    if (finalHits.some((k) => iou(h, k) > 0.3)) continue;
    finalHits.push(h);
    if (finalHits.length >= maxHits) break;
  }
  return finalHits;
}

// ── diagnosis ────────────────────────────────────────────────────────────────────────────

export interface RegionScore {
  variant: LogoVariant;
  /** Best score the template reaches at the marked place (≤ 1; can be negative). */
  score: number;
  scale: number;
}

/**
 * "Why was my logo not found?": the best score each comparison reaches INSIDE the area the user marked as the real logo
 * (template size is tried around the size of that area, small shifts are allowed). Compare with the threshold and with
 * the hits found elsewhere (findLogoHits with a low threshold).
 */
export function scoreLogoAtRegion(
  page: GrayImage,
  template: GrayImage,
  region: { x0: number; y0: number; x1: number; y1: number },
  opts: Omit<FindLogoOptions, "threshold">,
): RegionScore[] {
  const s = setup(page, template, { ...opts, threshold: 0 }, true);
  const img = s.fineGray.img;
  const rx0 = region.x0 * img.width;
  const rx1 = region.x1 * img.width;
  const ry0 = region.y0 * img.height;
  const ry1 = region.y1 * img.height;
  const rw = rx1 - rx0;
  const rh = ry1 - ry0;
  const cx = (rx0 + rx1) / 2;
  const cy = (ry0 + ry1) / 2;
  const out: RegionScore[] = [];
  for (const variant of ALL_VARIANTS) {
    let best: RegionScore = { variant, score: -2, scale: 0 };
    // scales whose template width is within 55 % … 180 % of the marked area's width
    for (let scale = SCALE_MIN; scale <= SCALE_MAX * 1.0001; scale *= 1.07) {
      const tw = Math.round(s.tw0 * scale * s.fFine);
      const th = Math.round(s.th0 * scale * s.fFine);
      if (tw < MIN_TEMPLATE_PX || th < MIN_TEMPLATE_PX || tw < rw * 0.55 || tw > rw * 1.8) continue;
      if (tw >= img.width || th >= img.height) continue;
      const zm = preparedTemplate(s, variant === "edge" ? "edge" : "gray", tw, th);
      if (!zm) continue;
      const r = fineBest(s, variant, zm, Math.round(cx - tw / 2), Math.round(cy - th / 2), Math.max(4, Math.round(0.12 * Math.max(rw, rh))));
      if (r.score > best.score) best = { variant, score: r.score, scale };
    }
    out.push(best);
  }
  return out;
}

/** RGBA (any alpha) → gray over white, like the Python tool's RGBA→RGB-on-white→L conversion. */
export function rgbaToGray(rgba: Uint8ClampedArray | Uint8Array, width: number, height: number): GrayImage {
  const data = new Float32Array(width * height);
  for (let i = 0, p = 0; i < data.length; i++, p += 4) {
    const a = rgba[p + 3]! / 255;
    const r = rgba[p]! * a + 255 * (1 - a);
    const g = rgba[p + 1]! * a + 255 * (1 - a);
    const b = rgba[p + 2]! * a + 255 * (1 - a);
    data[i] = 0.299 * r + 0.587 * g + 0.114 * b;
  }
  return { width, height, data };
}
