import type { PDFDocumentProxy } from "pdfjs-dist";
import type { PageRenderer } from "./renderer";
import { clusterBoundaries } from "./snapRange";
import type { AutoRect } from "./textDetect";

/** Pixels per pt of the render used to look for the gaps between letters (≈ 288 DPI). */
const SNAP_PX_PER_PT = 4;
/** Luminance below this is ink. */
const INK_BELOW = 200;
/** A hair of room beyond the gap centre so the edge pixels of the keyword's outer letters are surely inside. */
const HAIR_PT = 0.25;

/**
 * A keyword in the middle of a longer text item was only ESTIMATED by the text rules. Here the page is rendered once and
 * every such rectangle is pulled onto the real letter boundaries (see snapRange) — but only where the letter groups can be
 * matched one-to-one with the characters. Otherwise the conservative estimate stays. Never fails: if a page cannot be rendered its rectangles simply stay as estimated.
 */
export async function refineSnappedRects(
  doc: PDFDocumentProxy,
  rects: readonly AutoRect[],
  renderer: PageRenderer,
  signal?: AbortSignal,
): Promise<AutoRect[]> {
  const out = rects.map((r) => ({ ...r }));
  const pages = [...new Set(out.filter((r) => r.snap).map((r) => r.page))];
  for (const p of pages) {
    if (signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
    try {
      const page = await doc.getPage(p);
      const vp = page.getViewport({ scale: 1 });
      const rendered = await renderer.render(page, SNAP_PX_PER_PT);
      try {
        for (const r of out) {
          if (r.page !== p || !r.snap) continue;
          const sn = r.snap;
          const S = SNAP_PX_PER_PT;
          const x0 = Math.max(0, Math.floor((sn.itemX0 - 1) * S));
          const x1 = Math.min(rendered.width, Math.ceil((sn.itemX1 + 1) * S));
          const y0 = Math.max(0, Math.floor(sn.bandTop * S));
          const y1 = Math.min(rendered.height, Math.ceil(sn.bandBottom * S));
          if (x1 <= x0 || y1 <= y0) continue;
          const rows = rendered.readRows(y0, y1);
          const ink = new Uint16Array(x1 - x0); // ink pixels per column in the letter band
          for (let y = 0; y < y1 - y0; y++) {
            for (let x = x0; x < x1; x++) {
              const q = (y * rendered.width + x) * 4;
              const a = rows[q + 3]! / 255;
              const lum = 0.299 * (rows[q]! * a + 255 * (1 - a)) + 0.587 * (rows[q + 1]! * a + 255 * (1 - a)) + 0.114 * (rows[q + 2]! * a + 255 * (1 - a));
              if (lum < INK_BELOW) ink[x - x0]!++;
            }
          }
          // exact only if the letter groups match the characters one-to-one; otherwise the generous estimate stays
          const res = clusterBoundaries({ ink, originPt: x0 / S, pxPerPt: S, chars: sn.chars, from: sn.from, to: sn.to, itemX0: sn.itemX0, itemX1: sn.itemX1 });
          if (res) {
            r.x0 = Math.max(0, (res.start - HAIR_PT) / vp.width);
            r.x1 = Math.min(1, (res.end + HAIR_PT) / vp.width);
          }
        }
      } finally {
        rendered.dispose();
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      /* keep the estimates of this page */
    }
  }
  return out.map(({ snap: _snap, ...rest }) => {
    void _snap;
    return rest;
  });
}
