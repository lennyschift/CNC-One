import type { Rect } from "./coordinates";
import { LIMITS, type NormRect } from "./types";

/** Integer pixel rectangle; x1/y1 are exclusive. */
export interface PxRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

/** Sorts corners and clamps to the page (0..1). */
export function normalizeNormRect(r: NormRect): NormRect {
  return {
    x0: clamp01(Math.min(r.x0, r.x1)),
    y0: clamp01(Math.min(r.y0, r.y1)),
    x1: clamp01(Math.max(r.x0, r.x1)),
    y1: clamp01(Math.max(r.y0, r.y1)),
  };
}

/** Normalized rect -> pt rect (origin top-left, y down), for a page of wPt x hPt points. */
export function normToPt(r: NormRect, wPt: number, hPt: number): Rect {
  return { x0: r.x0 * wPt, y0: r.y0 * hPt, x1: r.x1 * wPt, y1: r.y1 * hPt };
}

/**
 * Normalized rect -> whole-pixel rect on a canvas whose *content* spans
 * `contentW x contentH` (float, = page size * scale) inside a backing store
 * of `maxW x maxH` pixels. Rounds **outwards** (floor/ceil) and then grows by
 * `expandPx`, so anti-aliased edges can never leave a partly-dark border
 * next to the fill; the result is always clamped to the canvas.
 */
export function normToPixelRect(
  r: NormRect,
  contentW: number,
  contentH: number,
  maxW: number,
  maxH: number,
  expandPx = 1,
): PxRect {
  const x0 = Math.max(0, Math.floor(r.x0 * contentW) - expandPx);
  const y0 = Math.max(0, Math.floor(r.y0 * contentH) - expandPx);
  const x1 = Math.min(maxW, Math.ceil(r.x1 * contentW) + expandPx);
  const y1 = Math.min(maxH, Math.ceil(r.y1 * contentH) + expandPx);
  return { x0, y0, x1: Math.max(x1, x0), y1: Math.max(y1, y0) };
}

export function pxToPtRect(p: PxRect, scale: number): Rect {
  return { x0: p.x0 / scale, y0: p.y0 / scale, x1: p.x1 / scale, y1: p.y1 / scale };
}

/** True if `a` and `b` overlap once `b` is grown by `margin` on every side. */
export function overlapsWithMargin(a: Rect, b: Rect, margin: number): boolean {
  return a.x0 < b.x1 + margin && a.x1 > b.x0 - margin && a.y0 < b.y1 + margin && a.y1 > b.y0 - margin;
}

export interface RenderPlan {
  scale: number;
  effectiveDpi: number;
  widthPx: number;
  heightPx: number;
  /** true when the requested DPI had to be lowered (canvas / memory limits). */
  reduced: boolean;
}

/**
 * Picks the render scale for a page of wPt x hPt points: the requested DPI,
 * lowered if the page would exceed the canvas guard rails (very large
 * formats like A1/A0). The effective DPI is reported to the user.
 */
export function planRenderScale(wPt: number, hPt: number, requestedDpi: number): RenderPlan {
  const requested = requestedDpi / 72;
  const bySide = LIMITS.maxSidePixels / Math.max(wPt, hPt);
  const byArea = Math.sqrt(LIMITS.maxPixelsPerPage / (wPt * hPt));
  const scale = Math.min(requested, bySide, byArea);
  return {
    scale,
    effectiveDpi: scale * 72,
    widthPx: Math.ceil(wPt * scale),
    heightPx: Math.ceil(hPt * scale),
    reduced: scale < requested - 1e-9,
  };
}
