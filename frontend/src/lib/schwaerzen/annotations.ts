import type { PDFDocumentProxy } from "pdfjs-dist";
import type { AutoRect } from "./textDetect";

/*
 * CNC One: Anmerkungen, Stempel und Formularfelder.
 *
 * pdf.js zeichnet beim Rendern das sichtbare Erscheinungsbild von Anmerkungen mit (Stempel „Freigegeben Hr. …“,
 * Freitext-Kommentare, ausgefüllte Formularfelder). Diese Texte stehen NICHT im Textlayer der Seite — die Wort-Regeln
 * sehen sie also nicht, im fertigen Bild wären sie aber lesbar. Deshalb wird jede Anmerkung mit sichtbarem Text als
 * Bereich vorgeschlagen; ihr Text kommt außerdem zu den Prüfbegriffen der Nachprüfung.
 * Reine Verweise (Link), Popups und Notiz-Symbole (Text: nur ein Symbol, der Inhalt ist im Bild nicht zu sehen) nicht.
 */

const OHNE_SICHTBAREN_TEXT = new Set(["Link", "Popup", "Text"]);
const IMMER = new Set(["Stamp", "FreeText", "Widget", "Caret", "Ink"]);

interface PdfjsAnnotation {
  subtype?: string;
  rect?: number[];
  hasAppearance?: boolean;
  noView?: boolean;
  hidden?: boolean;
  contentsObj?: { str?: string };
  titleObj?: { str?: string };
  fieldValue?: unknown;
  textContent?: string[];
}

export interface AnnotationResult {
  rects: AutoRect[];
  /** Texte der vorgeschlagenen Anmerkungen (für die Byte- und Textprüfung), nicht normalisiert. */
  texts: string[];
  /** Seiten mit Anmerkungen, die ins Bild kommen. */
  pages: number[];
}

function texte(a: PdfjsAnnotation): string[] {
  const out = [a.contentsObj?.str, a.titleObj?.str, ...(Array.isArray(a.textContent) ? a.textContent : [])];
  if (typeof a.fieldValue === "string") out.push(a.fieldValue);
  else if (Array.isArray(a.fieldValue)) out.push(...a.fieldValue.map(String));
  return out.map((s) => (s ?? "").trim()).filter((s) => s.length > 0);
}

export async function detectAnnotations(doc: PDFDocumentProxy, signal?: AbortSignal): Promise<AnnotationResult> {
  const rects: AutoRect[] = [];
  const texts: string[] = [];
  const pages: number[] = [];
  for (let p = 1; p <= doc.numPages; p++) {
    if (signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
    const page = await doc.getPage(p);
    const vp = page.getViewport({ scale: 1 });
    let liste: PdfjsAnnotation[] = [];
    try {
      liste = (await page.getAnnotations({ intent: "display" })) as PdfjsAnnotation[];
    } catch {
      continue;
    }
    let sichtbar = 0;
    for (const a of liste) {
      const art = a.subtype ?? "";
      if (!a.rect || a.rect.length !== 4 || a.noView || a.hidden || OHNE_SICHTBAREN_TEXT.has(art)) continue;
      const t = texte(a);
      if (!IMMER.has(art) && !(a.hasAppearance && t.length)) continue;
      if (art === "Widget" && !t.length && !a.hasAppearance) continue;
      const [x0, y0] = vp.convertToViewportPoint(a.rect[0]!, a.rect[1]!);
      const [x1, y1] = vp.convertToViewportPoint(a.rect[2]!, a.rect[3]!);
      const r = {
        x0: Math.max(0, Math.min(x0!, x1!) / vp.width - 0.002),
        y0: Math.max(0, Math.min(y0!, y1!) / vp.height - 0.002),
        x1: Math.min(1, Math.max(x0!, x1!) / vp.width + 0.002),
        y1: Math.min(1, Math.max(y0!, y1!) / vp.height + 0.002),
      };
      if (r.x1 - r.x0 <= 0 || r.y1 - r.y0 <= 0) continue;
      const name = art === "Widget" ? "Formularfeld" : art === "Stamp" ? "Stempel" : art === "FreeText" ? "Freitext" : `Anmerkung (${art})`;
      rects.push({ page: p, ...r, reason: `${name} im PDF`, kind: "annotation" });
      texts.push(...t);
      sichtbar++;
    }
    if (sichtbar) pages.push(p);
  }
  return { rects, texts, pages };
}
