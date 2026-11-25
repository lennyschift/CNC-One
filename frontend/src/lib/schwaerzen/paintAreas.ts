import type { PxRect } from "./geometry";
import { refineRect, type KeptLine } from "./lineKeep";
import type { RenderedPage } from "./renderer";
import type { FillColor } from "./types";

/** Margin (pt) kept around the content when an area is pulled tight. */
export const TIGHT_MARGIN_PT = 1.2;

export interface PaintResult {
  /** What was really painted (the areas, pulled tight if `tight`). */
  painted: PxRect[];
  /** Table-line pieces re-drawn on top (constant colour). */
  lines: KeptLine[];
}

/**
 * THE one place that decides how areas end up in the picture — used for saving AND for the preview, so the preview shows
 * exactly what is saved. With `tight` each area is pulled tight around the content really inside it, table lines running
 * into it are found on the ORIGINAL render (before anything is painted) and re-drawn as plain constant-colour lines.
 * Without it the areas are painted as they are.
 */
export function paintAreas(rendered: RenderedPage, areas: readonly PxRect[], fill: FillColor, tight: boolean, pxPerPt: number): PaintResult {
  const marginPx = Math.max(2, Math.round(TIGHT_MARGIN_PT * pxPerPt));
  const painted: PxRect[] = [];
  const lines: KeptLine[] = [];
  for (const area of areas) {
    if (tight) {
      const refined = refineRect(rendered, area, marginPx, pxPerPt);
      painted.push(refined.rect);
      lines.push(...refined.lines);
    } else {
      painted.push(area);
    }
  }
  rendered.fillRects(painted, fill);
  for (const line of lines) for (const strip of line.strips) rendered.fillRects([strip.rect], strip.color);
  return { painted, lines };
}
