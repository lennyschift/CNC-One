import { describe, expect, it } from "vitest";
import { PDFDocument, rgb } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import { findKeptLines, refineRect } from "./lineKeep";
import type { RasterSource } from "./rasterEncode";
import { runRedaction } from "./pipeline";
import { DEFAULT_EXPORT_SETTINGS, type RedactionRect } from "./types";
import { FONT_BYTES } from "./testing/dummyPdf";
import { findLeaks } from "./testing/independentScan";
import { scanBytesForTerms } from "./verify";
import { nodeRenderer, openPdf } from "./testing/nodePdfjs";

/** White RGBA canvas that tests can draw into. */
function canvas(w: number, h: number) {
  const data = new Uint8ClampedArray(w * h * 4).fill(255);
  const src: RasterSource = { width: w, height: h, readRows: (y0, y1) => data.subarray(y0 * w * 4, y1 * w * 4) };
  const px = (x: number, y: number, v = 0) => {
    const p = (y * w + x) * 4;
    data[p] = data[p + 1] = data[p + 2] = v;
  };
  const rect = (x0: number, y0: number, x1: number, y1: number, v = 0) => {
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) px(x, y, v);
  };
  return { src, px, rect };
}

const R = { x0: 40, y0: 30, x1: 100, y1: 60 };

describe("findKeptLines (pure pixel rules)", () => {
  it("keeps a thin line that runs through the area and continues on both sides", () => {
    const c = canvas(150, 100);
    c.rect(10, 45, 140, 46); // 1 px horizontal line across everything
    c.rect(70, 5, 71, 95); // 1 px vertical line across everything
    const lines = findKeptLines(c.src, R);
    expect(lines).toHaveLength(2);
    expect(lines.find((l) => l.rect.y1 - l.rect.y0 === 1 && l.rect.x1 - l.rect.x0 === 60)!.rect.y0).toBe(45);
    expect(lines.find((l) => l.rect.x1 - l.rect.x0 === 1)!.rect.y1 - R.y0).toBe(30);
    for (const l of lines) for (const st of l.strips) expect(st.color.r).toBeLessThan(10); // colour comes from the visible part outside
  });

  it("uses the colour of the visible line OUTSIDE the area, never pixels from inside", () => {
    const c = canvas(150, 100);
    c.rect(10, 45, 140, 46, 150); // gray line outside …
    c.rect(R.x0, 45, R.x1, 46, 0); // … but black inside the area
    const [line] = findKeptLines(c.src, R);
    expect(line!.strips[0]!.color.r).toBe(150);
  });

  it("redraws a thin line with its own profile: dark middle row, gray edge rows (not one averaged gray)", () => {
    const c = canvas(150, 100);
    c.rect(10, 44, 140, 45, 180); // gray edge row
    c.rect(10, 45, 140, 46, 0); // black middle row
    c.rect(10, 46, 140, 47, 180); // gray edge row
    const [line] = findKeptLines(c.src, R);
    expect(line!.strips.map((st) => st.color.r)).toEqual([180, 0, 180]);
    expect(line!.strips.map((st) => st.rect.y0)).toEqual([44, 45, 46]);
  });

  it("does NOT keep an underline that ends inside the area (it belongs to the removed text)", () => {
    const c = canvas(150, 100);
    c.rect(45, 50, 80, 51); // starts and ends inside
    expect(findKeptLines(c.src, R)).toEqual([]);
  });

  it("keeps the END of a line that runs in from one side and stops inside the area (cell border)", () => {
    const c = canvas(150, 100);
    c.rect(10, 45, 80, 46); // enters from the left, ends inside at x = 80
    const lines = findKeptLines(c.src, R);
    expect(lines).toHaveLength(1);
    expect(lines[0]!.rect).toEqual({ x0: R.x0, y0: 45, x1: 80, y1: 46 }); // exactly up to where it really ends
  });

  it("does NOT keep a short dash that merely touches the edge (no long continuation outside)", () => {
    const c = canvas(150, 100);
    c.rect(32, 45, 80, 46); // only 8 px outside the area
    expect(findKeptLines(c.src, R)).toEqual([]);
  });

  it("does NOT keep text-like rows (gaps), thick bars or filled blocks", () => {
    const c = canvas(150, 100);
    for (let x = 10; x < 140; x += 3) c.rect(x, 40, x + 2, 42); // dashed/text-like row with gaps every third pixel
    c.rect(10, 50, 140, 62); // 12 px thick bar across everything
    expect(findKeptLines(c.src, R)).toEqual([]);
  });

  it("at the page edge the line is verified from the side that exists", () => {
    const c = canvas(150, 100);
    c.rect(0, 45, 150, 46);
    const lines = findKeptLines(c.src, { x0: 0, y0: 30, x1: 60, y1: 60 });
    expect(lines).toHaveLength(1);
    expect(lines[0]!.rect.x1 - lines[0]!.rect.x0).toBe(60);
  });

  it("keeps a light-gray thin line (anti-aliased 0.25 pt line)", () => {
    const c = canvas(150, 100);
    c.rect(10, 45, 140, 46, 170);
    expect(findKeptLines(c.src, R)).toHaveLength(1);
  });
});

describe("refineRect (rectangle pulled tight around the real content)", () => {
  const BIG = { x0: 40, y0: 30, x1: 100, y1: 70 };

  it("shrinks to the content plus the margin, never beyond the original area", () => {
    const c = canvas(150, 100);
    c.rect(60, 40, 70, 46); // the "text"
    const { rect } = refineRect(c.src, BIG, 3);
    expect(rect).toEqual({ x0: 57, y0: 37, x1: 73, y1: 49 });
    const hugging = refineRect(c.src, { x0: 58, y0: 38, x1: 72, y1: 48 }, 6);
    expect(hugging.rect).toEqual({ x0: 58, y0: 38, x1: 72, y1: 48 }); // margin is clipped to the original area
  });

  it("covers ALL content, even very light gray, and several separate pieces", () => {
    const c = canvas(150, 100);
    c.rect(48, 35, 52, 38); // dark speck, top-left
    c.rect(90, 60, 94, 63, 245); // very light gray speck, bottom-right (still not white)
    const { rect } = refineRect(c.src, BIG, 2);
    expect(rect.x0).toBeLessThanOrEqual(48 - 2);
    expect(rect.y0).toBeLessThanOrEqual(35 - 2);
    expect(rect.x1).toBeGreaterThanOrEqual(94 + 2);
    expect(rect.y1).toBeGreaterThanOrEqual(63 + 2);
  });

  it("CNC One: also a barely visible speck (luminance 252) at the edge stays inside the painted area", () => {
    const c = canvas(150, 100);
    c.rect(60, 40, 70, 46); // the "text"
    c.rect(96, 66, 98, 68, 252); // faint speck near the corner of the drawn area
    const { rect } = refineRect(c.src, BIG, 2);
    expect(rect.x1).toBeGreaterThanOrEqual(98);
    expect(rect.y1).toBeGreaterThanOrEqual(68);
  });

  it("keeps the area unchanged when it holds no content", () => {
    const c = canvas(150, 100);
    expect(refineRect(c.src, BIG, 3)).toEqual({ rect: BIG, lines: [] });
  });

  it("a grid line is not counted as content (so it cannot stretch the area) and is re-drawn where it crosses", () => {
    const c = canvas(200, 100);
    c.rect(10, 43, 190, 44); // table line through everything
    c.rect(60, 38, 70, 49); // text blob crossing that line
    const { rect, lines } = refineRect(c.src, BIG, 3);
    expect(rect).toEqual({ x0: 57, y0: 35, x1: 73, y1: 52 }); // determined by the blob only, not by the long line
    expect(lines.length).toBeGreaterThanOrEqual(1);
    for (const l of lines) {
      expect(l.rect.y1 - l.rect.y0).toBe(1);
      expect(l.rect.y0).toBe(43);
    }
  });
});

/*
 * End to end on a made-up title-block cell: a text with a form line below it, a table line through it,
 * and an underline that ends with the text.
 */
const W = 400;
const H = 300;

async function buildCell(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const font = await doc.embedFont(FONT_BYTES, { subset: true });
  const page = doc.addPage([W, H]);
  const black = rgb(0, 0, 0);
  page.drawText("Geheimname", { x: 100, y: 150, size: 12, font, color: black });
  page.drawLine({ start: { x: 20, y: 145 }, end: { x: 380, y: 145 }, thickness: 0.5, color: black }); // cell line (y-down 155)
  page.drawLine({ start: { x: 250, y: 100 }, end: { x: 250, y: 220 }, thickness: 0.5, color: black }); // vertical cell border
  page.drawLine({ start: { x: 100, y: 141 }, end: { x: 170, y: 141 }, thickness: 0.5, color: black }); // underline of the text only (y-down 159)
  page.drawText("Bleibt stehen", { x: 40, y: 250, size: 10, font, color: black });
  return doc.save({ useObjectStreams: false });
}

const norm = (x0: number, y0: number, x1: number, y1: number) => ({ x0: x0 / W, y0: y0 / H, x1: x1 / W, y1: y1 / H });
const rect: RedactionRect = { id: "r", page: 1, source: "manual", reason: "t", kind: "manual", ...norm(90, 132, 270, 162) };

async function darkAt(bytes: Uint8Array, xPt: number, yPt: number): Promise<number> {
  const doc = await openPdf(bytes);
  const page = await doc.getPage(1);
  const r = await nodeRenderer.render(page, 4);
  const x = Math.round(xPt * 4);
  const y = Math.round(yPt * 4);
  const rows = r.readRows(y - 2, y + 3); // darkest value in a 5 px high strip
  let min = 255;
  for (let k = 0; k < 5; k++) min = Math.min(min, rows[(k * r.width + x) * 4]!);
  return min;
}

describe("redaction keeps the table grid", () => {
  it("re-draws the lines through the area, removes text and the text's own underline, passes all checks", async () => {
    const source = await buildCell();
    const doc = await openPdf(source);
    const res = await runRedaction({
      doc,
      rects: [rect],
      settings: { ...DEFAULT_EXPORT_SETTINGS, keepLines: true },
      manualTerms: ["geheimname"],
      renderer: nodeRenderer,
      openResult: openPdf,
      fontBytes: FONT_BYTES,
    });
    const failed = res.report.checks.filter((c) => c.status === "fail");
    expect(failed, JSON.stringify(failed)).toEqual([]);
    // the area is pulled tight around the text, so only the horizontal cell line still reaches it (the vertical one at x=250 does not)
    expect(res.report.linesKept).toBeGreaterThanOrEqual(1);
    expect(res.report.checks.some((c) => c.id === "lines-kept")).toBe(true);
    expect(findLeaks(res.bytes, ["Geheimname"])).toEqual([]);

    expect(await darkAt(res.bytes, 215, 155)).toBeLessThan(140); // cell line inside the area is back …
    expect(await darkAt(res.bytes, 250, 140)).toBeLessThan(140); // … and the vertical border
    expect(await darkAt(res.bytes, 130, 159)).toBeGreaterThan(240); // the text's own underline is NOT
    expect(await darkAt(res.bytes, 130, 147)).toBeGreaterThan(240); // where the text stood: white
    expect(await darkAt(res.bytes, 60, 155)).toBeLessThan(140); // line outside the area untouched
  }, 60_000);

  it("with the option off the area is plain white, lines are cut (as before) and all checks still pass", async () => {
    const source = await buildCell();
    const doc = await openPdf(source);
    const res = await runRedaction({
      doc,
      rects: [rect],
      settings: { ...DEFAULT_EXPORT_SETTINGS, keepLines: false },
      manualTerms: ["geheimname"],
      renderer: nodeRenderer,
      openResult: openPdf,
      fontBytes: FONT_BYTES,
    });
    expect(res.report.released).toBe(true);
    expect(res.report.linesKept).toBe(0);
    expect(await darkAt(res.bytes, 215, 155)).toBeGreaterThan(240);
  }, 60_000);

  it("documents the areas by kind in the protocol", async () => {
    const doc = await openPdf(await buildCell());
    const rects: RedactionRect[] = [
      rect,
      { ...rect, id: "b", kind: "logo", source: "auto", ...norm(280, 30, 330, 60) },
      { ...rect, id: "c", kind: undefined, source: "import", ...norm(280, 200, 330, 230) },
    ];
    const res = await runRedaction({ doc, rects, settings: DEFAULT_EXPORT_SETTINGS, manualTerms: [], renderer: nodeRenderer, openResult: openPdf, fontBytes: FONT_BYTES });
    expect(res.report.rectsByKind).toEqual({ manual: 1, logo: 1, import: 1 });
  }, 60_000);
});

describe("byte scan: no false alarms from binary data", () => {
  it("hundreds of short terms that are NOT in the document are never 'found' in fonts / compressed streams", async () => {
    const doc = await openPdf(await buildCell());
    const res = await runRedaction({ doc, rects: [rect], settings: DEFAULT_EXPORT_SETTINGS, manualTerms: [], renderer: nodeRenderer, openResult: openPdf, fontBytes: FONT_BYTES });
    const letters = "qxzjkvw";
    const terms: string[] = [];
    for (const a of letters) for (const b of letters) for (const c of letters) terms.push(a + b + c); // 343 three-letter terms
    for (const a of letters) for (const b of letters) terms.push(a + b); // 49 two-letter terms
    const scan = await scanBytesForTerms(res.bytes, terms);
    expect(scan.hitTermIndexes).toEqual([]);
  }, 60_000);

  it("but a real leak in a decoded stream or in the structure is still found", async () => {
    const d = await PDFDocument.create();
    d.setTitle("Geheimtitel");
    const page = d.addPage([100, 100]);
    page.drawText("x", { x: 1, y: 1 });
    const bytes = await d.save({ useObjectStreams: false });
    expect((await scanBytesForTerms(bytes, ["geheimtitel", "nichtdrin"])).hitTermIndexes).toEqual([0]);
  });

  it("text that SITS ON a table line: text gone, the line stays continuous underneath, with its own thickness", async () => {
    const doc = await PDFDocument.create();
    doc.registerFontkit(fontkit);
    const font = await doc.embedFont(FONT_BYTES, { subset: true });
    const page = doc.addPage([W, H]);
    const black = rgb(0, 0, 0);
    page.drawLine({ start: { x: 20, y: 150 }, end: { x: 380, y: 150 }, thickness: 0.9, color: black }); // y-down 150
    page.drawText("Geheimname", { x: 100, y: 150.4, size: 12, font, color: black }); // baseline resting on the line
    const bytes = await doc.save({ useObjectStreams: false });
    const src = await openPdf(bytes);
    const res = await runRedaction({
      doc: src,
      rects: [{ id: "r", page: 1, source: "manual", reason: "", kind: "manual", ...norm(90, 128, 190, 160) }],
      settings: { ...DEFAULT_EXPORT_SETTINGS, keepLines: true },
      manualTerms: ["geheimname"],
      renderer: nodeRenderer,
      openResult: openPdf,
      fontBytes: FONT_BYTES,
    });
    const failed = res.report.checks.filter((c) => c.status === "fail");
    expect(failed, JSON.stringify(failed)).toEqual([]);
    expect(findLeaks(res.bytes, ["Geheimname"])).toEqual([]);
    expect(await darkAt(res.bytes, 130, 150)).toBeLessThan(120); // under the text: the line is there
    expect(await darkAt(res.bytes, 95, 150)).toBeLessThan(120); // left of the text
    expect(await darkAt(res.bytes, 185, 150)).toBeLessThan(120); // right of the text
    expect(await darkAt(res.bytes, 130, 144)).toBeGreaterThan(240); // where the letters were: white
    expect(res.report.linesKept).toBeGreaterThanOrEqual(1);
  }, 60_000);
});
