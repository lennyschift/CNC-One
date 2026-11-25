import { describe, expect, it } from "vitest";
import { PDFDocument } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { runRedaction, type RunResult } from "./pipeline";
import { toPageTextItems } from "./textItems";
import { extractAllText, scanBytesForTerms, verifyStructure } from "./verify";
import { DEFAULT_EXPORT_SETTINGS, type ExportSettings, type NormRect, type RedactionRect } from "./types";
import { FONT_BYTES, KEPT_WORDS, PAGE_H, PAGE_W, SECRETS, buildDummyPdf, type DummyOptions } from "./testing/dummyPdf";
import { findLeaks } from "./testing/independentScan";
import { nodeRenderer, openPdf } from "./testing/nodePdfjs";

/*
 * End-to-end: synthetic drawings WITH hidden content -> redact -> the written
 * file is re-opened, rendered and scanned byte by byte with an independent
 * scanner. "Beweis statt Vertrauen": every hiding trick from the briefing is
 * present in the input, and the negative controls prove the tricks work
 * (i.e. the secrets really ARE in the original).
 */

const HIDDEN_SECRETS = [
  SECRETS.white,
  SECRETS.tiny,
  SECRETS.mode3,
  SECRETS.ocg,
  SECRETS.attachment,
  SECRETS.attachmentName,
  SECRETS.annotation,
  SECRETS.form,
  SECRETS.title,
  SECRETS.author,
  SECRETS.keywords,
];
const COVERED = [SECRETS.name, SECRETS.address, "Muster GmbH"];

let idCounter = 0;
const rectOf = (page: number, r: NormRect): RedactionRect => ({
  ...r,
  id: `r${++idCounter}`,
  page,
  source: "manual",
  reason: "test",
});

/** Independent (pdf.js-free) mapping of an unrotated PDF point into the displayed page, in pt, y down. */
function toDisplayed(x: number, y: number, o: DummyOptions): { x: number; y: number } {
  const c = o.crop ?? { x: 0, y: 0, width: PAGE_W, height: PAGE_H };
  const x0 = x - c.x;
  const y0 = c.y + c.height - y;
  switch (o.rotate ?? 0) {
    case 90:
      return { x: c.height - y0, y: x0 };
    case 180:
      return { x: c.width - x0, y: c.height - y0 };
    case 270:
      return { x: y0, y: c.width - x0 };
    default:
      return { x: x0, y: y0 };
  }
}

/** Displayed-space box (pt) of a glyph run authored at (x, baselineY) with the given advance width and cap height. */
function glyphBox(x: number, baselineY: number, widthPt: number, heightPt: number, o: DummyOptions) {
  const a = toDisplayed(x, baselineY, o);
  const b = toDisplayed(x + widthPt, baselineY + heightPt, o);
  return { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) };
}

async function measure(text: string, size: number): Promise<number> {
  const d = await PDFDocument.create();
  d.registerFontkit(fontkit);
  return (await d.embedFont(FONT_BYTES)).widthOfTextAtSize(text, size);
}

async function pageItems(doc: PDFDocumentProxy) {
  const page = await doc.getPage(1);
  const vp = page.getViewport({ scale: 1 });
  return { items: toPageTextItems((await page.getTextContent()).items, vp.transform), vp };
}

/** Tight normalized rect around the pdf.js item whose text contains `needle` (optionally only its left `fraction`). */
async function rectAroundItem(doc: PDFDocumentProxy, needle: string, fraction = 1): Promise<NormRect> {
  const { items, vp } = await pageItems(doc);
  const item = items.find((i) => i.str.includes(needle));
  if (!item) throw new Error(`Item not found: ${needle}`);
  const w = item.bbox.x1 - item.bbox.x0;
  return {
    x0: (item.bbox.x0 - 1) / vp.width,
    y0: (item.bbox.y0 - 1) / vp.height,
    x1: (item.bbox.x0 + w * fraction + 1) / vp.width,
    y1: (item.bbox.y1 + 1) / vp.height,
  };
}

interface Run {
  source: Uint8Array;
  result: RunResult;
  texts: string[][];
  out: PDFDocumentProxy;
  o: DummyOptions;
}

async function redact(o: DummyOptions, settings: Partial<ExportSettings> = {}, manualTerms: string[] = []): Promise<Run> {
  const source = await buildDummyPdf(o);
  const doc = await openPdf(source);
  const rects = [
    rectOf(1, await rectAroundItem(doc, SECRETS.name)),
    // Covers only the LEFT part of "Muster GmbH Musterweg 5": the item is partly under the rect.
    rectOf(1, await rectAroundItem(doc, "Muster GmbH", 0.35)),
  ];
  const result = await runRedaction({
    doc,
    rects,
    // these tests look for the redaction by darkness, so they use black explicitly (the app default is white)
    settings: { ...DEFAULT_EXPORT_SETTINGS, fillHex: "#000000", mode: "rasterText", ...settings }, // the app only saves "rasterOnly"; the text-layer filter stays tested
    manualTerms,
    renderer: nodeRenderer,
    openResult: openPdf,
    fontBytes: FONT_BYTES,
  });
  const out = await openPdf(result.bytes);
  return { source, result, texts: await extractAllText(out), out, o };
}

async function darkFraction(out: PDFDocumentProxy, box: { x0: number; y0: number; x1: number; y1: number }) {
  const page = await out.getPage(1);
  const scale = 3;
  const rendered = await nodeRenderer.render(page, scale);
  const x0 = Math.floor(box.x0 * scale);
  const x1 = Math.ceil(box.x1 * scale);
  const y0 = Math.floor(box.y0 * scale);
  const y1 = Math.ceil(box.y1 * scale);
  const rows = rendered.readRows(y0, y1);
  let dark = 0;
  let black = 0;
  let n = 0;
  for (let y = 0; y < y1 - y0; y++) {
    for (let x = x0; x < x1; x++) {
      const p = (y * rendered.width + x) * 4;
      n++;
      if (rows[p]! < 128) dark++;
      if (rows[p]! < 8 && rows[p + 1]! < 8 && rows[p + 2]! < 8) black++;
    }
  }
  return { dark: dark / n, black: black / n };
}

const VARIANTS: [string, DummyOptions][] = [
  ["upright page", {}],
  ["page rotated 90°", { rotate: 90 }],
  ["page rotated 180°", { rotate: 180 }],
  ["page rotated 270°", { rotate: 270 }],
  ["CropBox with offset", { crop: { x: 20, y: 20, width: 260, height: 260 } }],
  ["CropBox + rotation 90°", { crop: { x: 20, y: 20, width: 260, height: 260 }, rotate: 90 }],
];

describe("negative controls: the hiding tricks are really present in the original", () => {
  it("original bytes and pdf.js text contain every hidden secret", async () => {
    const source = await buildDummyPdf({ hidden: true });
    const leaks = findLeaks(source, HIDDEN_SECRETS);
    // Text drawn white/tiny/invisible/in an OFF layer is inside the (deflated) content stream as glyph ids, so
    // only metadata, attachment, annotation and form value show up as plain strings; the text ones via pdf.js:
    for (const s of [SECRETS.attachment, SECRETS.annotation, SECRETS.form, SECRETS.title, SECRETS.author]) {
      expect(leaks, s).toContain(s);
    }
    const doc = await openPdf(source);
    const text = (await extractAllText(doc)).flat().join(" ");
    expect(text).toContain(SECRETS.white);
    expect(text).toContain(SECRETS.mode3);
    expect(text).toContain(SECRETS.tiny);
  });

  it("the production verifier flags a poisoned file (annotations, attachments, form, metadata …)", async () => {
    const source = await buildDummyPdf({ hidden: true });
    const checks = await verifyStructure(source, { pageCount: 1, mode: "rasterText" });
    const byId = Object.fromEntries(checks.map((c) => [c.id, c]));
    expect(byId["forbidden-keys"]!.status).toBe("fail");
    expect(byId["whitelist"]!.status).toBe("fail");
    expect(byId["info"]!.status).toBe("fail");
    const scan = await scanBytesForTerms(source, ["geheimtitel", "geheimanhanginhalt"]);
    expect(scan.hitTermIndexes.length).toBe(2);
  });
});

describe.each(VARIANTS)("redaction end-to-end — %s", (_name, variant) => {
  const o: DummyOptions = { ...variant, hidden: true };
  let run: Run;

  it("runs and releases the file", async () => {
    run = await redact(o);
    const failed = run.result.report.checks.filter((c) => c.status === "fail");
    expect(failed, JSON.stringify(failed)).toEqual([]);
    expect(run.result.report.released).toBe(true);
    expect(run.result.report.pageCount).toBe(1);
    expect(run.result.report.sha256).toMatch(/^[0-9a-f]{64}$/);
  }, 60_000);

  it("no hidden secret and no redacted text survives — independent byte scan", () => {
    expect(findLeaks(run.result.bytes, [...HIDDEN_SECRETS, ...COVERED])).toEqual([]);
  });

  it("no hidden secret and no redacted text is extractable", () => {
    const text = run.texts.flat().join(" ");
    for (const s of [...HIDDEN_SECRETS, ...COVERED]) expect(text).not.toContain(s);
  });

  it("visible, non-redacted text stays searchable", () => {
    const text = run.texts.flat().join(" ");
    for (const w of KEPT_WORDS) expect(text, w).toContain(w);
    expect(run.result.report.textItemsKept).toBeGreaterThanOrEqual(3);
  });

  it("the covered name is fully black where it REALLY sits (coordinates checked without pdf.js)", async () => {
    const w = await measure(SECRETS.name, 10);
    const box = glyphBox(100 + 0.5, 60 + 0.5, w - 1, 6.5, o);
    const f = await darkFraction(run.out, box);
    expect(f.black).toBeGreaterThan(0.99);
  });

  it("uncovered content is still visible (not one big black page)", async () => {
    const w = await measure("Zeichnung Bauteil 4711", 14);
    const f = await darkFraction(run.out, glyphBox(30, 255, w, 10, o));
    expect(f.dark).toBeGreaterThan(0.03);
    expect(f.black).toBeLessThan(0.7);
  });

  it("output has no rotation/CropBox and the displayed page size", async () => {
    const page = await run.out.getPage(1);
    const vp = page.getViewport({ scale: 1 });
    const c = o.crop ?? { width: PAGE_W, height: PAGE_H };
    const swap = o.rotate === 90 || o.rotate === 270;
    expect(vp.rotation).toBe(0);
    expect(vp.width).toBeCloseTo(swap ? c.height : c.width, 1);
    expect(vp.height).toBeCloseTo(swap ? c.width : c.height, 1);
  });
});

describe("modes and settings", () => {
  it("raster-only mode writes no text at all and still passes every check", async () => {
    const run = await redact({ hidden: true }, { mode: "rasterOnly" });
    expect(run.result.report.released).toBe(true);
    expect(run.texts.flat().join("").trim()).toBe("");
    expect(run.result.report.textItemsKept).toBe(0);
    expect(findLeaks(run.result.bytes, [...HIDDEN_SECRETS, ...COVERED])).toEqual([]);
  }, 60_000);

  it("a manual sensitive term removes visible text elsewhere from the text layer", async () => {
    const run = await redact({ hidden: false }, {}, ["bauteil"]);
    const text = run.texts.flat().join(" ");
    expect(text).not.toContain("Bauteil");
    expect(text).toContain("Werkstoff");
    expect(run.result.report.textItemsDropped.sensitive).toBeGreaterThan(0);
  }, 60_000);

  it("a different fill colour and DPI are honoured and verified", async () => {
    const run = await redact({ hidden: false }, { fillHex: "#202020", dpi: 150 });
    expect(run.result.report.dpiEffectivePerPage).toEqual([150]);
    expect(run.result.report.released).toBe(true);
  }, 60_000);

  it("the default is WHITE: the redacted name is gone and the area is pure white (nobody sees where)", async () => {
    const run = await redact({ hidden: false }, { fillHex: DEFAULT_EXPORT_SETTINGS.fillHex });
    expect(DEFAULT_EXPORT_SETTINGS.fillHex).toBe("#ffffff");
    expect(run.result.report.released).toBe(true);
    const w = await measure(SECRETS.name, 10);
    const f = await darkFraction(run.out, glyphBox(100 + 0.5, 60 + 0.5, w - 1, 6.5, {}));
    expect(f.dark).toBe(0); // not a single dark pixel where the name was
    expect(findLeaks(run.result.bytes, [SECRETS.name])).toEqual([]);
  }, 60_000);

  it("rejects out-of-range DPI", async () => {
    const source = await buildDummyPdf();
    const doc = await openPdf(source);
    await expect(
      runRedaction({
        doc,
        rects: [],
        settings: { ...DEFAULT_EXPORT_SETTINGS, dpi: 5000 },
        manualTerms: [],
        renderer: nodeRenderer,
        openResult: openPdf,
        fontBytes: FONT_BYTES,
      }),
    ).rejects.toThrow(/DPI/);
  });

  it("does not modify the original document bytes", async () => {
    const source = await buildDummyPdf({ hidden: true });
    const copy = source.slice();
    const doc = await openPdf(source);
    await runRedaction({
      doc,
      rects: [],
      settings: DEFAULT_EXPORT_SETTINGS,
      manualTerms: [],
      renderer: nodeRenderer,
      openResult: openPdf,
      fontBytes: FONT_BYTES,
    });
    expect(Buffer.from(source).equals(Buffer.from(copy))).toBe(true);
  }, 60_000);
});
