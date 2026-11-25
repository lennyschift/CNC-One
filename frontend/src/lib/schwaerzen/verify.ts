import {
  PDFArray,
  PDFDict,
  PDFDocument,
  PDFName,
  PDFRawStream,
  PDFRef,
  decodePDFRawStream,
  type PDFObject,
} from "pdf-lib";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { blankPdfSyntax, blankStreamPayloads, decodeHexStrings, foldAsciiCase, indexOfBytes, termByteVariants } from "./byteSearch";
import { normToPixelRect } from "./geometry";
import { containsTerm, findSensitive, normalizeForMatch } from "./sensitive";
import type { PageRenderer } from "./renderer";
import type { CheckResult, FillColor, NormRect, SaveMode } from "./types";

/*
 * Post-save audit. Everything here looks at the WRITTEN bytes (re-opened),
 * never at the in-memory state that produced them. Check details never
 * contain drawing content or the sensitive terms themselves.
 */

/** Keys that must never occur anywhere in the output (actions, attachments, forms, metadata …). */
const FORBIDDEN_KEYS = new Set([
  "Annots",
  "AA",
  "OpenAction",
  "JS",
  "JavaScript",
  "EmbeddedFiles",
  "EmbeddedFile",
  "EF",
  "AF",
  "Filespec",
  "AcroForm",
  "XFA",
  "Metadata",
  "Outlines",
  "Names",
  "Dests",
  "URI",
  "URIs",
  "Launch",
  "OCProperties",
  "OC",
  "StructTreeRoot",
  "PieceInfo",
  "Thumb",
  "Encrypt",
]);

const ALLOWED_CATALOG_KEYS = new Set(["Type", "Pages"]);
// "Annots" is tolerated ONLY as an empty array (pdf-lib writes `/Annots []`); see verifyStructure.
const ALLOWED_PAGE_KEYS = new Set(["Type", "Parent", "MediaBox", "Contents", "Resources", "Annots"]);
const ALLOWED_INFO_KEYS = new Set(["Producer", "Creator", "CreationDate", "ModDate"]);

function keyName(name: PDFName): string {
  return name.decodeText();
}

function collectKeys(obj: PDFObject | undefined, out: Set<string>, depth = 0): void {
  if (!obj || depth > 12) return;
  if (obj instanceof PDFRawStream) {
    collectKeys(obj.dict, out, depth + 1);
    return;
  }
  if (obj instanceof PDFDict) {
    for (const [k, v] of obj.entries()) {
      out.add(keyName(k));
      collectKeys(v, out, depth + 1);
    }
    return;
  }
  if (obj instanceof PDFArray) {
    for (const v of obj.asArray()) collectKeys(v, out, depth + 1);
  }
}

function dictKeys(dict: PDFDict): string[] {
  return dict.entries().map(([k]) => keyName(k));
}

export interface StructureExpectation {
  pageCount: number;
  mode: SaveMode;
}

/** Structure / metadata audit of the written file via pdf-lib. */
export async function verifyStructure(bytes: Uint8Array, expect: StructureExpectation): Promise<CheckResult[]> {
  const checks: CheckResult[] = [];
  let doc: PDFDocument;
  try {
    doc = await PDFDocument.load(bytes, { updateMetadata: false, ignoreEncryption: false });
  } catch {
    return [{ id: "structure", label: "Dateistruktur", status: "fail", detail: "Die gespeicherte Datei lässt sich nicht erneut öffnen." }];
  }
  const ctx = doc.context;

  const pageCount = doc.getPageCount();
  checks.push({
    id: "pages",
    label: "Seitenzahl",
    status: pageCount === expect.pageCount ? "ok" : "fail",
    detail: `${pageCount} Seite(n) in der Ausgabe, ${expect.pageCount} erwartet.`,
  });

  // 1) Forbidden keys anywhere (annotations, attachments, form fields, JS, XMP, outlines …)
  const found = new Set<string>();
  const allKeys = new Set<string>();
  for (const [, obj] of ctx.enumerateIndirectObjects()) collectKeys(obj, allKeys);
  for (const k of allKeys) if (FORBIDDEN_KEYS.has(k) && k !== "Annots") found.add(k);
  if (ctx.trailerInfo.Encrypt) found.add("Encrypt");
  // Annotations: an empty /Annots array is harmless, any entry or any /Type /Annot object is not.
  for (const page of doc.getPages()) {
    const annots = page.node.lookupMaybe(PDFName.of("Annots"), PDFArray);
    if (annots && annots.size() > 0) found.add("Annots");
  }
  for (const [, obj] of ctx.enumerateIndirectObjects()) {
    if (obj instanceof PDFDict && obj.get(PDFName.of("Type")) === PDFName.of("Annot")) found.add("Annots");
  }
  checks.push({
    id: "forbidden-keys",
    label: "Keine Anmerkungen, Anhänge, Formulare, Skripte, Lesezeichen, XMP",
    status: found.size === 0 ? "ok" : "fail",
    detail: found.size === 0 ? "Keine verbotenen PDF-Schlüssel gefunden." : `Verbotene Schlüssel gefunden: ${[...found].sort().join(", ")}`,
  });

  // 2) Catalog + page dictionaries: strict whitelist
  const unexpected: string[] = [];
  for (const k of dictKeys(doc.catalog)) if (!ALLOWED_CATALOG_KEYS.has(k)) unexpected.push(`Katalog/${k}`);
  for (const page of doc.getPages()) {
    for (const k of dictKeys(page.node)) if (!ALLOWED_PAGE_KEYS.has(k)) unexpected.push(`Seite/${k}`);
  }
  checks.push({
    id: "whitelist",
    label: "Nur erwartete Seiten-/Katalogeinträge",
    status: unexpected.length === 0 ? "ok" : "fail",
    detail: unexpected.length === 0 ? "Keine unerwarteten Einträge." : `Unerwartet: ${[...new Set(unexpected)].join(", ")}`,
  });

  // 3) Info dictionary: only Producer/Creator/dates
  const infoRef = ctx.trailerInfo.Info;
  const info = infoRef instanceof PDFRef ? ctx.lookup(infoRef, PDFDict) : infoRef instanceof PDFDict ? infoRef : undefined;
  const badInfo = info ? dictKeys(info).filter((k) => !ALLOWED_INFO_KEYS.has(k)) : [];
  checks.push({
    id: "info",
    label: "Metadaten leer (nur Erzeuger + Datum)",
    status: badInfo.length === 0 ? "ok" : "fail",
    detail: badInfo.length === 0 ? "Info-Dictionary enthält nur Producer/Creator/Datum." : `Zusätzliche Metadaten: ${badInfo.join(", ")}`,
  });

  return checks;
}

export interface ByteScanResult {
  /** Indexes into the terms array that were found (never the terms themselves). */
  hitTermIndexes: number[];
  scannedStreams: number;
}

/**
 * Byte-level search for the sensitive terms in (a) the raw file WITHOUT stream payloads (structure, dictionaries,
 * strings, trailer), (b) the decoded contents of all `<hex>` strings and (c) every DECODED stream except pixel data
 * and font programs (so Flate-compressed content streams, CMaps and any other stream are searched in the clear).
 * Streams that cannot be decoded are searched raw. ASCII case-insensitive; tries Latin-1/UTF-8/UTF-16BE/UTF-16LE
 * encodings of each term. (Binary payloads are not searched as raw bytes: short terms would match by chance.)
 */
export async function scanBytesForTerms(bytes: Uint8Array, terms: readonly string[]): Promise<ByteScanResult> {
  const doc = await PDFDocument.load(bytes, { updateMetadata: false });
  // CNC One: PDF syntax (name tokens, keywords) is not drawing text — see blankPdfSyntax
  const structure = blankPdfSyntax(blankStreamPayloads(bytes));
  const buffers: Uint8Array[] = [foldAsciiCase(structure), foldAsciiCase(decodeHexStrings(structure))];
  let scannedStreams = 0;

  // Embedded font programs are binary glyph data (no text content): found via FontDescriptor → FontFile/FontFile2/FontFile3.
  const fontPrograms = new Set<string>();
  for (const [, obj] of doc.context.enumerateIndirectObjects()) {
    if (!(obj instanceof PDFDict) || obj.get(PDFName.of("Type")) !== PDFName.of("FontDescriptor")) continue;
    for (const key of ["FontFile", "FontFile2", "FontFile3"]) {
      const ref = obj.get(PDFName.of(key));
      if (ref instanceof PDFRef) fontPrograms.add(ref.toString());
    }
  }

  for (const [ref, obj] of doc.context.enumerateIndirectObjects()) {
    if (!(obj instanceof PDFRawStream)) continue;
    if (obj.dict.get(PDFName.of("Subtype")) === PDFName.of("Image")) continue; // our own pixel data
    if (fontPrograms.has(ref.toString())) continue;
    try {
      buffers.push(foldAsciiCase(decodePDFRawStream(obj).decode()));
    } catch {
      buffers.push(foldAsciiCase(obj.contents)); // undecodable → search it raw instead
    }
    scannedStreams++;
  }

  const hits: number[] = [];
  terms.forEach((term, idx) => {
    const found = termByteVariants(term).some((v) => {
      const folded = foldAsciiCase(v);
      return buffers.some((buf) => indexOfBytes(buf, folded) >= 0);
    });
    if (found) hits.push(idx);
  });
  return { hitTermIndexes: hits, scannedStreams };
}

/**
 * Text extraction of the written file through pdf.js (what a user's "Suchen"
 * would see): the items of every page, one string per item — the same
 * granularity the text-layer filter worked with.
 */
export async function extractAllText(doc: PDFDocumentProxy): Promise<string[][]> {
  const pages: string[][] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const items: string[] = [];
    for (const item of content.items) if ("str" in item && item.str.trim().length > 0) items.push(item.str);
    pages.push(items);
  }
  return pages;
}

const HIT_LABEL = { term: "Begriff", email: "E-Mail-Muster", phone: "Telefon-Muster" } as const;

export function verifyExtractedText(
  pageItems: readonly (readonly string[])[],
  terms: readonly string[],
  mode: SaveMode,
): CheckResult[] {
  if (mode === "rasterOnly") {
    const chars = pageItems.reduce((n, items) => n + items.join("").trim().length, 0);
    return [
      {
        id: "no-text",
        label: "Keine Textschicht (Maximal-Modus)",
        status: chars === 0 ? "ok" : "fail",
        detail: chars === 0 ? "Die Ausgabe enthält keinen extrahierbaren Text." : `Unerwartet: ${chars} Zeichen Text in der Ausgabe.`,
      },
    ];
  }

  const hitPages = new Set<number>();
  const kinds = new Set<string>();
  pageItems.forEach((items, i) => {
    // Per item (patterns like phone numbers would otherwise fire on innocent number chains) …
    for (const str of items) {
      const hit = findSensitive(str, terms);
      if (hit) {
        hitPages.add(i + 1);
        kinds.add(HIT_LABEL[hit]);
      }
    }
    // … and terms additionally across the whole page text (a term split over two items).
    const joined = normalizeForMatch(items.join(" "));
    if (terms.some((t) => containsTerm(joined, t))) {
      hitPages.add(i + 1);
      kinds.add(HIT_LABEL.term);
    }
  });

  return [
    {
      id: "text-extract",
      label: "Extrahierter Text ohne sensible Begriffe / E-Mail / Telefon",
      status: hitPages.size === 0 ? "ok" : "fail",
      detail:
        hitPages.size === 0
          ? `Geprüft gegen ${terms.length} Begriff(e) plus E-Mail-/Telefon-Muster.`
          : `Treffer (${[...kinds].join(", ")}) auf Seite(n): ${[...hitPages].sort((a, b) => a - b).join(", ")}`,
    },
  ];
}

/** Re-renders the written file and checks that the interior of every redaction rect is exactly the fill colour. */
export async function verifyRectPixels(
  outDoc: PDFDocumentProxy,
  rects: readonly (NormRect & { page: number })[],
  fill: FillColor,
  renderer: PageRenderer,
  /** Re-drawn table-line pieces per page (normalized): exempt from the "pure fill colour" test. */
  keepByPage: ReadonlyMap<number, readonly NormRect[]> = new Map(),
): Promise<CheckResult> {
  const RENDER_SCALE = 1.5;
  let checked = 0;
  let tooSmall = 0;
  let bad = 0;
  const badPages = new Set<number>();

  const pages = [...new Set(rects.map((r) => r.page))];
  for (const pageNo of pages) {
    const page = await outDoc.getPage(pageNo);
    const rendered = await renderer.render(page, RENDER_SCALE);
    try {
      const vp = page.getViewport({ scale: RENDER_SCALE });
      for (const r of rects.filter((x) => x.page === pageNo)) {
        // Shrink by 2px each side: resampling/anti-aliasing at the border must not cause false alarms.
        const px = normToPixelRect(r, vp.width, vp.height, rendered.width, rendered.height, 0);
        const x0 = px.x0 + 2;
        const y0 = px.y0 + 2;
        const x1 = px.x1 - 2;
        const y1 = px.y1 - 2;
        if (x1 <= x0 || y1 <= y0) {
          tooSmall++;
          continue;
        }
        checked++;
        const keepPx = (keepByPage.get(pageNo) ?? []).map((k) => normToPixelRect(k, vp.width, vp.height, rendered.width, rendered.height, 2));
        const rows = rendered.readRows(y0, y1);
        outer: for (let y = 0; y < y1 - y0; y++) {
          for (let x = x0; x < x1; x++) {
            if (keepPx.some((k) => x >= k.x0 && x < k.x1 && y + y0 >= k.y0 && y + y0 < k.y1)) continue;
            const p = (y * rendered.width + x) * 4;
            if (
              Math.abs(rows[p]! - fill.r) > 3 ||
              Math.abs(rows[p + 1]! - fill.g) > 3 ||
              Math.abs(rows[p + 2]! - fill.b) > 3
            ) {
              bad++;
              badPages.add(pageNo);
              break outer;
            }
          }
        }
      }
    } finally {
      rendered.dispose();
    }
  }

  if (bad > 0) {
    return {
      id: "rect-render",
      label: "Schwärzungen im gespeicherten Ergebnis vollflächig",
      status: "fail",
      detail: `${bad} Bereich(e) nicht einfarbig in der Füllfarbe (Seite ${[...badPages].join(", ")}).`,
    };
  }
  return {
    id: "rect-render",
    label: "Schwärzungen im gespeicherten Ergebnis vollflächig",
    status: "ok",
    detail: `${checked} Bereich(e) nachgerendert und einfarbig.${tooSmall > 0 ? ` ${tooSmall} sehr kleine Bereich(e) nur über die Raster-Prüfung abgedeckt.` : ""}`,
  };
}
