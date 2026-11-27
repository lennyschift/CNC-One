/**
 * Shared types + hard limits for the redaction ("Zeichnung schwärzen") feature.
 *
 * Coordinates: every user-facing rectangle is stored *normalized* (0..1,
 * origin top-left) relative to the page **as displayed** (i.e. after page
 * rotation and CropBox are applied). This is the same convention as the JSON
 * hand-over format of the old Python tool (`per_page` -> `[x0,y0,x1,y1]`) and
 * makes rectangles independent of zoom / render DPI.
 */

/** "rasterOnly" = image only, no text at all — the ONLY mode the app offers and saves (default).
 *  "rasterText" = image + strictly filtered invisible text layer: still implemented and tested, but no longer reachable from the UI. */
export type SaveMode = "rasterText" | "rasterOnly";

export interface NormRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** Which rule produced an area ("manual" = drawn or added by hand). */
export type RuleKind = "keyword" | "header" | "changeTable" | "labelRight" | "email" | "phone" | "logo" | "annotation" | "manual";

export interface RedactionRect extends NormRect {
  id: string;
  /** 1-based page number. */
  page: number;
  /** "auto" = proposed by the rules; becomes "manual" as soon as the user moves/resizes it. */
  source: "manual" | "import" | "auto";
  /** Short human-readable reason shown in the list, e.g. "Stichwort ‚AFR‘" or "Logo 87 %". */
  reason: string;
  kind?: RuleKind;
}

export interface FillColor {
  r: number;
  g: number;
  b: number;
}

export interface ExportSettings {
  dpi: number;
  /** "#rrggbb" */
  fillHex: string;
  mode: SaveMode;
  /**
   * Re-draw plain table lines (thin lines that run through an area and continue on both sides) so redactions do not
   * leave gaps in the title-block grid. Only constant-colour lines are drawn, never original pixels.
   */
  keepLines: boolean;
  /**
   * CNC One: Linien beim Rastern um ein Pixel kräftiger zeichnen (nur im Export, vor dem Schwärzen). Haarlinien sind im
   * Original in jeder Vergrößerung einen Bildschirmpixel breit, im Rasterbild nur einen Bildpixel — verkleinert angezeigt
   * wirkt die Zeichnung sonst blass.
   */
  linienStaerken?: boolean;
}

export const DEFAULT_EXPORT_SETTINGS: ExportSettings = {
  // 450 DPI + lossless one-channel storage of black-and-white pages: noticeably sharper than 300 at a modest file size
  dpi: 450,
  // White in the saved file: nobody receiving the drawing should see WHERE something was removed.
  // (On screen the areas are shown black so they stay visible while editing.)
  fillHex: "#ffffff",
  mode: "rasterOnly",
  keepLines: true,
  linienStaerken: true,
};

export const LIMITS = {
  maxPdfBytes: 150 * 1024 * 1024,
  maxPages: 100,
  maxRects: 5000,
  maxRectFileBytes: 2 * 1024 * 1024,
  minDpi: 100,
  maxDpi: 600,
  /** Canvas backing-store guard rails (memory + browser canvas limits). */
  maxPixelsPerPage: 60_000_000,
  maxSidePixels: 16_000,
  maxTerms: 300,
  maxTermLength: 200,
  /** Safety margin (pt) around a redaction rect within which text is never kept. */
  textSafetyMarginPt: 3,
} as const;

export function parseHexColor(hex: string): FillColor {
  const m = /^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(hex);
  if (!m) throw new Error(`Ungültige Füllfarbe: ${hex}`);
  return { r: parseInt(m[1]!, 16), g: parseInt(m[2]!, 16), b: parseInt(m[3]!, 16) };
}

export type CheckStatus = "ok" | "warn" | "fail";

export interface CheckResult {
  id: string;
  label: string;
  status: CheckStatus;
  /** Never contains drawing content or the sensitive terms themselves. */
  detail: string;
}

export interface DropCounts {
  overlap: number;
  invisible: number;
  outOfPage: number;
  badSize: number;
  sensitive: number;
  emailPhone: number;
  emptyAfterClean: number;
}

/** Protocol of one export run — metadata only, no drawing content, no sensitive strings. */
export interface RedactionReport {
  createdAt: string;
  sha256: string | null;
  pageCount: number;
  rectCount: number;
  rectsPerPage: Record<number, number>;
  /** Areas by kind ("keyword", "logo", "manual", "import" …) — documents how the redaction came about. */
  rectsByKind: Record<string, number>;
  /** Number of table-line pieces re-drawn inside areas (0 if the option is off). */
  linesKept: number;
  mode: SaveMode;
  dpiRequested: number;
  dpiEffectivePerPage: number[];
  fillHex: string;
  termCountManual: number;
  termCountDerived: number;
  textItemsKept: number;
  textItemsDropped: DropCounts;
  checks: CheckResult[];
  /** true = no check failed. */
  released: boolean;
}

/** Errors whose (German) message is safe and useful to show to the user. Everything else is shown generically. */
export class RedactionUserError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RedactionUserError";
  }
}
