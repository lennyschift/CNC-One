import type { Rect } from "./coordinates";

export type Matrix = [number, number, number, number, number, number];

/**
 * A pdf.js text item mapped into the *displayed page* coordinate system
 * (scale 1 => 1 unit = 1 pt, origin top-left, y down, rotation and CropBox
 * already applied by the pdf.js viewport transform).
 */
export interface PageTextItem {
  str: string;
  /** Text space (1 unit = 1 em) -> displayed page space (y down). */
  matrix: Matrix;
  /**
   * Bounding box in displayed page space. Deliberately generous: extends
   * below the baseline (descenders) and slightly above the em box, so both
   * the overlap test and the "is there visible ink" test cover whole glyphs.
   */
  bbox: Rect;
  /** Font size in pt as displayed. */
  fontSize: number;
  /** Advance width of the whole item in pt as displayed. */
  widthPt: number;
}

interface RawTextItem {
  str: string;
  transform: number[];
  width: number;
  height: number;
}

function isRawTextItem(item: unknown): item is RawTextItem {
  if (typeof item !== "object" || item === null) return false;
  const i = item as Partial<RawTextItem>;
  return (
    typeof i.str === "string" &&
    Array.isArray(i.transform) &&
    i.transform.length === 6 &&
    i.transform.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    typeof i.width === "number" &&
    Number.isFinite(i.width) &&
    typeof i.height === "number" &&
    Number.isFinite(i.height)
  );
}

/** m1 ∘ m2 — apply m2 first, then m1 (same convention as pdf.js `Util.transform`). */
export function multiplyMatrix(m1: readonly number[], m2: readonly number[]): Matrix {
  const [a1, b1, c1, d1, e1, f1] = m1 as [number, number, number, number, number, number];
  const [a2, b2, c2, d2, e2, f2] = m2 as [number, number, number, number, number, number];
  return [
    a1 * a2 + c1 * b2,
    b1 * a2 + d1 * b2,
    a1 * c2 + c1 * d2,
    b1 * c2 + d1 * d2,
    a1 * e2 + c1 * f2 + e1,
    b1 * e2 + d1 * f2 + f1,
  ];
}

function applyToPoint(m: readonly number[], x: number, y: number): { x: number; y: number } {
  return { x: m[0]! * x + m[2]! * y + m[4]!, y: m[1]! * x + m[3]! * y + m[5]! };
}

/**
 * Converts raw pdf.js `getTextContent()` items into page-space items.
 *
 * Note (see textExtraction.ts): pdf.js `item.width/height` are already true
 * PDF-space lengths, the font size is baked into `transform`'s a/b/c/d — so
 * only the matrix's *direction* is used to place the box, never its magnitude.
 */
export function toPageTextItems(rawItems: readonly unknown[], viewportTransform: readonly number[]): PageTextItem[] {
  const out: PageTextItem[] = [];
  const vt = viewportTransform;
  const viewScale = Math.hypot(vt[0]!, vt[1]!) || 1;

  for (const raw of rawItems) {
    if (!isRawTextItem(raw)) continue;
    if (raw.str.trim().length === 0) continue;

    const [a, b, c, d, e, f] = raw.transform as [number, number, number, number, number, number];
    const magX = Math.hypot(a, b);
    const magY = Math.hypot(c, d);
    if (magX === 0 && magY === 0) continue;

    const dirX = magX > 0 ? { x: a / magX, y: b / magX } : { x: 1, y: 0 };
    const dirY = magY > 0 ? { x: c / magY, y: d / magY } : { x: 0, y: 1 };
    const h = raw.height > 0 ? raw.height : magY;
    const w = Math.max(raw.width, 0);

    // Local (along-baseline, up) extents: a bit of descender room below the
    // baseline and a little headroom above the em box.
    const lo = -0.28 * h;
    const hi = 1.05 * h;
    const corners = [
      [0, lo],
      [w, lo],
      [w, hi],
      [0, hi],
    ].map(([s, t]) =>
      applyToPoint(vt, e + s! * dirX.x + t! * dirY.x, f + s! * dirX.y + t! * dirY.y),
    );
    const xs = corners.map((p) => p.x);
    const ys = corners.map((p) => p.y);
    const bbox: Rect = { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };

    const matrix = multiplyMatrix(vt, raw.transform);
    out.push({
      str: raw.str,
      matrix,
      bbox,
      fontSize: Math.hypot(matrix[2], matrix[3]),
      widthPt: w * viewScale,
    });
  }
  return out;
}
