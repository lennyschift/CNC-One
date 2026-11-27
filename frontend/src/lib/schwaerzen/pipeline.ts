import type { PDFDocumentProxy } from "pdfjs-dist";
import { countRectsByKind } from "./kinds";
import { paintAreas } from "./paintAreas";
import { normToPixelRect, normToPt, overlapsWithMargin, planRenderScale, pxToPtRect } from "./geometry";
import { sha256Hex } from "./hash";
import { RedactedPdfBuilder } from "./pdfAssemble";
import { encodeRaster } from "./rasterEncode";
import type { PageRenderer } from "./renderer";
import { deriveTerms, normalizeForMatch } from "./sensitive";
import { toPageTextItems, type PageTextItem } from "./textItems";
import { EMPTY_DROP_COUNTS, addDropCounts, filterTextLayer } from "./textLayerFilter";
import {
  LIMITS,
  RedactionUserError,
  parseHexColor,
  type CheckResult,
  type DropCounts,
  type ExportSettings,
  type NormRect,
  type RedactionReport,
  type RedactionRect,
} from "./types";
import { extractAllText, scanBytesForTerms, verifyExtractedText, verifyRectPixels, verifyStructure } from "./verify";

export interface PipelineProgress {
  phase: "analyse" | "render" | "save" | "verify";
  page: number;
  pageCount: number;
}

export interface RunOptions {
  doc: PDFDocumentProxy;
  rects: readonly RedactionRect[];
  settings: ExportSettings;
  /** Already normalized terms typed in by the user (see parseManualTerms). */
  manualTerms: readonly string[];
  renderer: PageRenderer;
  /** Re-opens the freshly written bytes for the audit. */
  openResult: (bytes: Uint8Array) => Promise<PDFDocumentProxy>;
  /** Embedded font for the text layer; required unless mode is "rasterOnly". */
  fontBytes: ArrayBuffer | Uint8Array | null;
  onProgress?: (p: PipelineProgress) => void;
  signal?: AbortSignal;
  now?: () => Date;
}

export interface RunResult {
  bytes: Uint8Array;
  report: RedactionReport;
  /** Normalized terms derived from text under the rects (needed for the file-name check in the UI). */
  derivedTerms: string[];
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
}

function validateSettings(settings: ExportSettings): void {
  if (!Number.isFinite(settings.dpi) || settings.dpi < LIMITS.minDpi || settings.dpi > LIMITS.maxDpi) {
    throw new RedactionUserError(`Auflösung muss zwischen ${LIMITS.minDpi} und ${LIMITS.maxDpi} DPI liegen.`);
  }
  parseHexColor(settings.fillHex);
}

/**
 * The whole export: analyse text under the rects -> render each page ->
 * paint the rects -> encode raster -> (optionally) build the filtered text
 * layer -> assemble a NEW pdf -> re-open the written bytes and audit them.
 * The original document is only read.
 */
export async function runRedaction(opts: RunOptions): Promise<RunResult> {
  const { doc, rects, settings, renderer, signal } = opts;
  validateSettings(settings);
  if (settings.mode === "rasterText" && !opts.fontBytes) throw new RedactionUserError("Schrift für die Textschicht fehlt.");
  if (rects.length > LIMITS.maxRects) throw new RedactionUserError(`Zu viele Bereiche (max. ${LIMITS.maxRects}).`);
  const fill = parseHexColor(settings.fillHex);
  const pageCount = doc.numPages;
  if (pageCount > LIMITS.maxPages) throw new RedactionUserError(`Zu viele Seiten (max. ${LIMITS.maxPages}).`);
  const progress = (phase: PipelineProgress["phase"], page: number) => opts.onProgress?.({ phase, page, pageCount });

  const rectsByPage = new Map<number, RedactionRect[]>();
  for (const r of rects) {
    if (r.page < 1 || r.page > pageCount) continue;
    const list = rectsByPage.get(r.page) ?? [];
    list.push(r);
    rectsByPage.set(r.page, list);
  }
  const validRects = [...rectsByPage.values()].flat();

  // ── Phase A: text of every page + terms derived from what lies under the rects ─────────────
  const itemsByPage: PageTextItem[][] = [];
  const derivedStrings: string[] = [];
  for (let p = 1; p <= pageCount; p++) {
    throwIfAborted(signal);
    progress("analyse", p);
    const page = await doc.getPage(p);
    const vp1 = page.getViewport({ scale: 1 });
    const items =
      settings.mode === "rasterText" || (rectsByPage.get(p)?.length ?? 0) > 0
        ? toPageTextItems((await page.getTextContent()).items, vp1.transform)
        : [];
    itemsByPage.push(items);

    const pageRects = (rectsByPage.get(p) ?? []).map((r) => normToPt(r, vp1.width, vp1.height));
    for (const item of items) {
      if (pageRects.some((r) => overlapsWithMargin(item.bbox, r, LIMITS.textSafetyMarginPt))) derivedStrings.push(item.str);
    }
    // NOT page.cleanup(): getPage() returns the same object the page view renders with; cleaning it up would kill that render.
  }
  const derivedTerms = deriveTerms(derivedStrings);
  const allTerms = [...new Set([...opts.manualTerms.map(normalizeForMatch), ...derivedTerms])].filter((t) => t.length > 0);

  // ── Phase B: render, paint, encode, filter, assemble ──────────────────────────────────────
  const builder = await RedactedPdfBuilder.create({
    fontBytes: settings.mode === "rasterText" ? opts.fontBytes : null,
    now: opts.now?.(),
  });
  let dropped: DropCounts = { ...EMPTY_DROP_COUNTS };
  let kept = 0;
  let rasterMismatch = 0;
  let linesKept = 0;
  const keepNormByPage = new Map<number, NormRect[]>();
  const paintedNorm: (NormRect & { page: number })[] = [];
  const dpiEffectivePerPage: number[] = [];

  for (let p = 1; p <= pageCount; p++) {
    throwIfAborted(signal);
    progress("render", p);
    const page = await doc.getPage(p);
    const vp1 = page.getViewport({ scale: 1 });
    const plan = planRenderScale(vp1.width, vp1.height, settings.dpi);
    dpiEffectivePerPage.push(Math.round(plan.effectiveDpi));

    const rendered = await renderer.render(page, plan.scale);
    // CNC One: Linien kräftiger, bevor geschwärzt wird (bei 450 DPI ein Pixel)
    if (settings.linienStaerken) rendered.thicken?.(Math.max(1, Math.round(plan.effectiveDpi / 450)));
    try {
      const contentW = vp1.width * plan.scale;
      const contentH = vp1.height * plan.scale;
      const pxRects = (rectsByPage.get(p) ?? []).map((r) =>
        normToPixelRect(r, contentW, contentH, rendered.width, rendered.height, 1),
      );
      // "Sauberer Rand" (see paintAreas): one shared routine for saving and for the preview.
      const { painted, lines: keptLines } = paintAreas(rendered, pxRects, fill, settings.keepLines, plan.scale);
      linesKept += keptLines.length;
      for (const r of painted) paintedNorm.push({ page: p, x0: r.x0 / contentW, y0: r.y0 / contentH, x1: r.x1 / contentW, y1: r.y1 / contentH });
      if (keptLines.length > 0) {
        keepNormByPage.set(
          p,
          keptLines.map((l) => ({ x0: l.rect.x0 / contentW, y0: l.rect.y0 / contentH, x1: l.rect.x1 / contentW, y1: l.rect.y1 / contentH })),
        );
      }

      const raster = await encodeRaster(rendered, painted, fill, keptLines.map((l) => l.rect));
      rasterMismatch += raster.rectMismatchPixels;

      let textItems: PageTextItem[] = [];
      if (settings.mode === "rasterText") {
        const result = filterTextLayer({
          items: itemsByPage[p - 1]!,
          rectsPt: pxRects.map((r) => pxToPtRect(r, plan.scale)),
          ink: raster.ink,
          scale: plan.scale,
          pageWidthPt: vp1.width,
          pageHeightPt: vp1.height,
          terms: allTerms,
        });
        textItems = result.kept;
        dropped = addDropCounts(dropped, result.dropped);
      }
      const { textItemsWritten } = builder.addPage({
        widthPt: vp1.width,
        heightPt: vp1.height,
        raster,
        textItems,
      });
      kept += textItemsWritten;
    } finally {
      rendered.dispose();
      // NOT page.cleanup(): getPage() returns the same object the page view renders with; cleaning it up would kill that render.
    }
    itemsByPage[p - 1] = []; // free memory early
  }

  throwIfAborted(signal);
  progress("save", pageCount);
  const bytes = await builder.save();

  // ── Phase C: audit of the WRITTEN bytes ───────────────────────────────────────────────
  progress("verify", pageCount);
  const checks: CheckResult[] = [];

  checks.push(...(await verifyStructure(bytes, { pageCount, mode: settings.mode })));

  checks.push({
    id: "rect-raster",
    label: "Schwärzungen beim Erzeugen vollflächig eingebrannt",
    status: rasterMismatch === 0 ? "ok" : "fail",
    detail: rasterMismatch === 0 ? `${validRects.length} Bereich(e), alle Pixel exakt in der Füllfarbe.` : `${rasterMismatch} Pixel in Bereichen weichen von der Füllfarbe ab.`,
  });

  const scan = await scanBytesForTerms(bytes, allTerms);
  checks.push({
    id: "byte-scan",
    label: "Byte-Suche (Rohdatei + entpackte Streams) ohne sensible Begriffe",
    status: scan.hitTermIndexes.length === 0 ? "ok" : "fail",
    detail:
      scan.hitTermIndexes.length === 0
        ? `${allTerms.length} Begriff(e) in Rohdatei und ${scan.scannedStreams} entpackten Streams gesucht: kein Treffer.`
        : `${scan.hitTermIndexes.length} von ${allTerms.length} Begriffen in den Bytes gefunden.`,
  });

  const outDoc = await opts.openResult(bytes);
  try {
    checks.push(...verifyExtractedText(await extractAllText(outDoc), allTerms, settings.mode));
    if (validRects.length > 0) {
      checks.push(await verifyRectPixels(outDoc, paintedNorm, fill, renderer, keepNormByPage));
    }
  } finally {
    await outDoc.loadingTask.destroy();
  }

  if (settings.keepLines && linesKept > 0) {
    checks.push({
      id: "lines-kept",
      label: "Tabellenlinien in den Bereichen wieder eingezeichnet",
      status: "ok",
      detail: `${linesKept} Linienstück(e), einfarbig neu gezeichnet (keine Originalpixel aus den Bereichen).`,
    });
  }

  const rectsPerPage: Record<number, number> = {};
  for (const [p, list] of rectsByPage) rectsPerPage[p] = list.length;

  const pagesWithout = [];
  for (let p = 1; p <= pageCount; p++) if (!rectsByPage.has(p)) pagesWithout.push(p);
  if (validRects.length > 0 && pagesWithout.length > 0) {
    checks.push({
      id: "pages-without-rects",
      label: "Seiten ohne Schwärzung",
      status: "warn",
      detail: `Seite(n) ohne Bereich: ${pagesWithout.join(", ")} — Absicht?`,
    });
  } else if (validRects.length === 0) {
    checks.push({ id: "no-rects", label: "Keine Bereiche gesetzt", status: "warn", detail: "Es wurde nichts geschwärzt; die Datei wurde nur gerastert." });
  }

  if (allTerms.length === 0) {
    checks.push({
      id: "no-terms",
      label: "Keine sensiblen Begriffe hinterlegt",
      status: "warn",
      detail: "Text-/Byte-Prüfung kann nur E-Mail-/Telefon-Muster erkennen. Begriffe eintragen oder Bereiche über Text ziehen.",
    });
  }

  const reduced = dpiEffectivePerPage.filter((d) => d < settings.dpi);
  if (reduced.length > 0) {
    checks.push({
      id: "dpi",
      label: "Auflösung für große Formate verringert",
      status: "warn",
      detail: `Auf ${reduced.length} Seite(n) wurde die Auflösung wegen der Seitengröße auf ${Math.min(...reduced)}–${Math.max(...reduced)} DPI gesenkt.`,
    });
  }

  const report: RedactionReport = {
    createdAt: (opts.now?.() ?? new Date()).toISOString(),
    sha256: await sha256Hex(bytes),
    pageCount,
    rectCount: validRects.length,
    rectsPerPage,
    rectsByKind: countRectsByKind(validRects),
    linesKept,
    mode: settings.mode,
    dpiRequested: settings.dpi,
    dpiEffectivePerPage,
    fillHex: settings.fillHex,
    termCountManual: opts.manualTerms.length,
    termCountDerived: derivedTerms.length,
    textItemsKept: kept,
    textItemsDropped: dropped,
    checks,
    released: checks.every((c) => c.status !== "fail"),
  };
  return { bytes, report, derivedTerms };
}
