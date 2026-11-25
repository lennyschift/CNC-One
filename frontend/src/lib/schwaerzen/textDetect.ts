import type { PDFDocumentProxy } from "pdfjs-dist";
import type { RuleSet } from "./rules";
import { detectTextRules, type SnapInfo } from "./textRules";
import { toPageTextItems } from "./textItems";
import type { RuleKind } from "./types";

/** An automatic proposal in the app's normalized page coordinates. */
export interface AutoRect {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  reason: string;
  kind: RuleKind;
  /** Keyword inside a longer item: positions to be made exact (then dropped). */
  snap?: SnapInfo;
}

export interface TextDetectionResult {
  rects: AutoRect[];
  /** Pages that contain no extractable text at all (scans — text rules cannot work there). */
  pagesWithoutText: number[];
  /** Pages with only a few text items: usually the lettering is drawn as lines (CAD) and the text rules see nothing. */
  pagesWithLittleText: number[];
}

const LITTLE_TEXT_ITEMS = 8;

/** Runs the text rules over every page. Reads the document only. */
export async function detectTextOnDocument(
  doc: PDFDocumentProxy,
  rules: RuleSet,
  opts: { signal?: AbortSignal; onPage?: (page: number) => void } = {},
): Promise<TextDetectionResult> {
  const rects: AutoRect[] = [];
  const pagesWithoutText: number[] = [];
  const pagesWithLittleText: number[] = [];
  for (let p = 1; p <= doc.numPages; p++) {
    if (opts.signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
    opts.onPage?.(p);
    const page = await doc.getPage(p);
    // NOT page.cleanup(): getPage() returns the same object the page view renders with; cleaning it up would kill that render.
    {
      const vp = page.getViewport({ scale: 1 });
      const items = toPageTextItems((await page.getTextContent()).items, vp.transform);
      if (items.length === 0) pagesWithoutText.push(p);
      else if (items.length < LITTLE_TEXT_ITEMS) pagesWithLittleText.push(p);
      for (const d of detectTextRules({ items, pageWidthPt: vp.width, pageHeightPt: vp.height, rules })) {
        rects.push({
          page: p,
          x0: d.rect.x0 / vp.width,
          y0: d.rect.y0 / vp.height,
          x1: d.rect.x1 / vp.width,
          y1: d.rect.y1 / vp.height,
          reason: d.reason,
          kind: d.kind,
          snap: d.snap,
        });
      }
    }
  }
  return { rects, pagesWithoutText, pagesWithLittleText };
}
