import type { Rect } from "./coordinates";
import { overlapsWithMargin } from "./geometry";
import type { InkMap } from "./rasterEncode";
import { findSensitive } from "./sensitive";
import { LIMITS, type DropCounts } from "./types";
import type { PageTextItem } from "./textItems";

export const EMPTY_DROP_COUNTS: DropCounts = {
  overlap: 0,
  invisible: 0,
  outOfPage: 0,
  badSize: 0,
  sensitive: 0,
  emailPhone: 0,
  emptyAfterClean: 0,
};

export function addDropCounts(a: DropCounts, b: DropCounts): DropCounts {
  return {
    overlap: a.overlap + b.overlap,
    invisible: a.invisible + b.invisible,
    outOfPage: a.outOfPage + b.outOfPage,
    badSize: a.badSize + b.badSize,
    sensitive: a.sensitive + b.sensitive,
    emailPhone: a.emailPhone + b.emailPhone,
    emptyAfterClean: a.emptyAfterClean + b.emptyAfterClean,
  };
}

/** Sizes (pt, as displayed) outside this range are treated as decoy/garbage text. */
const MIN_FONT_PT = 3;
const MAX_FONT_PT = 150;
/** An item counts as visible if its box holds at least this many dark pixels … */
const MIN_INK_PIXELS = 3;
/** … or at least this fraction of its box area. */
const MIN_INK_FRACTION = 0.004;

function inkInBox(ink: InkMap, box: Rect, scale: number): { dark: number; area: number } {
  const x0 = Math.max(0, Math.floor(box.x0 * scale));
  const y0 = Math.max(0, Math.floor(box.y0 * scale));
  const x1 = Math.min(ink.width, Math.ceil(box.x1 * scale));
  const y1 = Math.min(ink.height, Math.ceil(box.y1 * scale));
  let dark = 0;
  for (let y = y0; y < y1; y++) {
    const row = y * ink.width;
    for (let x = x0; x < x1; x++) dark += ink.data[row + x]!;
  }
  return { dark, area: Math.max(0, x1 - x0) * Math.max(0, y1 - y0) };
}

export interface FilterInput {
  items: readonly PageTextItem[];
  /** Redaction rects of this page in pt (origin top-left), already grown to whole pixels. */
  rectsPt: readonly Rect[];
  ink: InkMap;
  /** Pixels per pt of `ink`. */
  scale: number;
  pageWidthPt: number;
  pageHeightPt: number;
  /** Normalized sensitive terms (see sensitive.ts). */
  terms: readonly string[];
}

export interface FilterResult {
  kept: PageTextItem[];
  dropped: DropCounts;
}

/**
 * Decides which original text items may enter the invisible text layer. An
 * item is kept ONLY if ALL of these hold (see SCHWAERZEN-BRIEFING §4):
 *  1. no overlap with any redaction rect (+ safety margin) — partly covered items are dropped whole,
 *  2. its box in the FINISHED raster holds real ink (drops white/hidden/OCR-only text),
 *  3. inside the page, sensible font size,
 *  4. matches no sensitive term and no e-mail / phone pattern.
 */
export function filterTextLayer(input: FilterInput): FilterResult {
  const dropped: DropCounts = { ...EMPTY_DROP_COUNTS };
  const kept: PageTextItem[] = [];
  const margin = LIMITS.textSafetyMarginPt;

  for (const item of input.items) {
    if (input.rectsPt.some((r) => overlapsWithMargin(item.bbox, r, margin))) {
      dropped.overlap++;
      continue;
    }

    const b = item.bbox;
    const tol = 2;
    if (b.x0 < -tol || b.y0 < -tol || b.x1 > input.pageWidthPt + tol || b.y1 > input.pageHeightPt + tol) {
      dropped.outOfPage++;
      continue;
    }
    if (!(item.fontSize >= MIN_FONT_PT && item.fontSize <= MAX_FONT_PT) || !(item.widthPt > 0)) {
      dropped.badSize++;
      continue;
    }

    const { dark, area } = inkInBox(input.ink, b, input.scale);
    if (dark < Math.max(MIN_INK_PIXELS, area * MIN_INK_FRACTION)) {
      dropped.invisible++;
      continue;
    }

    const hit = findSensitive(item.str, input.terms);
    if (hit === "term") {
      dropped.sensitive++;
      continue;
    }
    if (hit !== null) {
      dropped.emailPhone++;
      continue;
    }

    kept.push(item);
  }
  return { kept, dropped };
}
