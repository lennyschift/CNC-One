import type { PDFDocumentProxy } from "pdfjs-dist";
import { browserRenderer } from "./browserRenderer";
import { detectLogosOnDocument } from "./logoDetect";
import { detectAnnotations } from "./annotations";
import { refineSnappedRects } from "./snapRefine";
import type { LogoTemplate, RuleSet } from "./rules";
import { detectTextOnDocument, type AutoRect } from "./textDetect";
import type { RuleKind } from "./types";

export { KIND_LABEL } from "./kinds";

export interface DetectionProgress {
  phase: "text" | "logo";
  page: number;
  pageCount: number;
}

export interface DetectionSummary {
  rects: AutoRect[];
  counts: Record<RuleKind, number>;
  /** Plain-language notes for the user (scans, unreadable logos …). */
  notes: string[];
  /** CNC One: texts of annotations/stamps/form fields that are painted into the image (audit terms). */
  annotationTexts: string[];
}

const EMPTY_COUNTS: Record<RuleKind, number> = { keyword: 0, header: 0, changeTable: 0, labelRight: 0, email: 0, phone: 0, logo: 0, annotation: 0, manual: 0 };

/** Everything the rules can find in one document: text rules + logos. */
export async function runDetection(opts: {
  doc: PDFDocumentProxy;
  rules: RuleSet;
  /** Logos from the connected logo folder (kept outside the saved rules). */
  extraLogos?: readonly LogoTemplate[];
  signal?: AbortSignal;
  onProgress?: (p: DetectionProgress) => void;
}): Promise<DetectionSummary> {
  const { doc, rules, signal } = opts;
  const pageCount = doc.numPages;
  const notes: string[] = [];

  const text = await detectTextOnDocument(doc, rules, {
    signal,
    onPage: (page) => opts.onProgress?.({ phase: "text", page, pageCount }),
  });
  const allLogos = [...rules.logos, ...(opts.extraLogos ?? [])];
  const logos = await detectLogosOnDocument(doc, allLogos, { threshold: rules.logoThreshold }, rules.logoOptions, {
    signal,
    onPage: (page) => opts.onProgress?.({ phase: "logo", page, pageCount }),
  });
  notes.push(...logos.problems);

  const hasLogos = allLogos.some((l) => l.enabled);
  if (text.pagesWithoutText.length > 0) {
    notes.push(
      `Seite ${text.pagesWithoutText.join(", ")}: kein Text gefunden (gescannte Seite?). Stichwörter und Kopfzeilen können dort nicht erkannt werden${hasLogos ? "" : " — bitte von Hand schwärzen oder Logos hinterlegen"}.`,
    );
  }

  if (text.pagesWithLittleText.length > 0) {
    notes.push(
      `Seite ${text.pagesWithLittleText.join(", ")}: sehr wenig Text im PDF. Falls die Beschriftung als Linien gezeichnet ist (CAD-Schrift), erkennen die Wort-Regeln dort nichts — Logos und Handschwärzung funktionieren trotzdem.`,
    );
  }

  // keywords inside longer text items: from an estimate to the real letter boundaries (falls back to the estimate)
  const textRects = await refineSnappedRects(doc, text.rects, browserRenderer, signal).catch((err) => {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    return text.rects.map(({ snap: _snap, ...rest }) => (void _snap, rest));
  });
  // CNC One: stamps, free text and filled form fields are painted into the image but are not in the text layer
  const annots = await detectAnnotations(doc, signal);
  if (annots.pages.length > 0) notes.push(`Seite ${annots.pages.join(", ")}: Stempel, Formularfelder oder Anmerkungen im PDF – sie stehen im Bild und sind als Bereich vorgeschlagen.`);
  const rects = [...textRects, ...logos.rects, ...annots.rects];
  const counts = { ...EMPTY_COUNTS };
  for (const r of rects) counts[r.kind]++;
  return { rects, counts, notes, annotationTexts: annots.texts };
}
