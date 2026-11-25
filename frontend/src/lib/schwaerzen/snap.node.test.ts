import { describe, expect, it } from "vitest";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import { clusterBoundaries, inkClusters } from "./snapRange";
import { refineSnappedRects } from "./snapRefine";
import { defaultRuleSet } from "./testing/testRegeln";
import { detectTextOnDocument } from "./textDetect";
import { FONT_BYTES } from "./testing/dummyPdf";
import { nodeRenderer, openPdf } from "./testing/nodePdfjs";

describe("clusterBoundaries (pure)", () => {
  // 10 letters of 4 pt at 10 px/pt, 1 pt gap between them: ink 40 px, gap 10 px … starting at x = 100 pt
  const px = 10;
  const origin = 100;
  const ink = new Uint8Array(10 * 50);
  for (let l = 0; l < 10; l++) for (let i = 0; i < 40; i++) ink[l * 50 + i] = 1;
  const edge = (l: number) => origin + (l * 50) / px;
  const gapCentre = (l: number) => origin + (l * 50 - 5) / px;
  const base = { ink, originPt: origin, pxPerPt: px, itemX0: origin, itemX1: edge(9) + 4 };

  it("finds the letter groups", () => {
    expect(inkClusters(ink)).toHaveLength(10);
  });

  it("character k is group k: boundaries are the gap centres around letters 3..5", () => {
    const r = clusterBoundaries({ ...base, chars: "ABCDEFGHIJ", from: 3, to: 6 });
    expect(r!.start).toBeCloseTo(gapCentre(3), 5);
    expect(r!.end).toBeCloseTo(gapCentre(6), 5);
  });

  it("spaces are not counted as letters", () => {
    // "ABCDE FGHI" has 9 visible letters -> 9 groups
    const nine = new Uint8Array(9 * 50);
    for (let l = 0; l < 9; l++) for (let i = 0; i < 40; i++) nine[l * 50 + i] = 1;
    const r = clusterBoundaries({ ...base, ink: nine, itemX1: edge(8) + 4, chars: "ABCDE FGHI", from: 6, to: 8 });
    expect(r!.start).toBeCloseTo(gapCentre(5), 5); // F is the 6th visible letter (index 5)
    expect(r!.end).toBeCloseTo(gapCentre(7), 5);
  });

  it("at the item's outer edges the item bounds are used", () => {
    const r = clusterBoundaries({ ...base, chars: "ABCDEFGHIJ", from: 0, to: 3 });
    expect(r!.start).toBeLessThanOrEqual(origin);
    expect(r!.end).toBeCloseTo(gapCentre(3), 5);
    const t = clusterBoundaries({ ...base, chars: "ABCDEFGHIJ", from: 7, to: 10 });
    expect(t!.end).toBeGreaterThanOrEqual(edge(9) + 4);
  });

  it("returns null (= keep the estimate) when letters touch and the counts differ", () => {
    const touching = new Uint8Array(ink);
    touching.fill(1, 40, 60); // letters 0 and 1 merge, letters 1 and 2 …
    expect(clusterBoundaries({ ...base, ink: touching, chars: "ABCDEFGHIJ", from: 3, to: 6 })).toBeNull();
    expect(clusterBoundaries({ ...base, ink: new Uint8Array(500).fill(1), chars: "ABCDEFGHIJ", from: 3, to: 6 })).toBeNull();
  });
});

/** Real glyph positions of a string drawn with the embedded font. */
async function layout(prefix: string, word: string, size: number) {
  const d = await PDFDocument.create();
  d.registerFontkit(fontkit);
  const f = await d.embedFont(FONT_BYTES);
  return { start: f.widthOfTextAtSize(prefix, size), end: f.widthOfTextAtSize(prefix + word, size) };
}

describe("keyword in the middle of a longer text item", () => {
  const W = 400;
  const H = 200;
  const X = 30;
  const SIZE = 11;
  const PREFIX = "Zeichnung (";
  const TEXT = `${PREFIX}AFR-Q-VPV) Ende`;

  async function build(): Promise<Uint8Array> {
    const doc = await PDFDocument.create();
    doc.registerFontkit(fontkit);
    const font = await doc.embedFont(FONT_BYTES, { subset: true });
    const page = doc.addPage([W, H]);
    page.drawText(TEXT, { x: X, y: 100, size: SIZE, font, color: rgb(0, 0, 0) });
    return doc.save({ useObjectStreams: false });
  }

  it("the rectangle hugs the real letters A-F-R instead of the generous estimate", async () => {
    const doc = await openPdf(await build());
    const rules = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: ["AFR"], detectEmail: false };
    const { rects } = await detectTextOnDocument(doc, rules);
    expect(rects).toHaveLength(1);
    expect(rects[0]!.snap).toBeDefined(); // it IS a keyword inside a longer item

    const { start, end } = await layout(PREFIX, "AFR", SIZE);
    const realStart = X + start;
    const realEnd = X + end;
    const est = { x0: rects[0]!.x0 * W, x1: rects[0]!.x1 * W };

    const [refined] = await refineSnappedRects(doc, rects, nodeRenderer);
    const x0 = refined!.x0 * W;
    const x1 = refined!.x1 * W;
    expect(refined!.snap).toBeUndefined();
    // covers the whole word …
    expect(x0).toBeLessThanOrEqual(realStart + 0.3);
    expect(x1).toBeGreaterThanOrEqual(realEnd - 0.3);
    // … and no more than ~1.3 pt beyond it on either side (the neighbours "(" and "-" are ≈ 6 pt wide)
    expect(realStart - x0).toBeLessThan(1.3);
    expect(x1 - realEnd).toBeLessThan(1.3);
    // clearly tighter than the estimate before
    expect(x1 - x0).toBeLessThan(est.x1 - est.x0);
  });

  it("falls back to the estimate if the page cannot be rendered", async () => {
    const doc = await openPdf(await build());
    const rules = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: ["AFR"], detectEmail: false };
    const { rects } = await detectTextOnDocument(doc, rules);
    const broken = { render: async () => Promise.reject(new Error("kaputt")) };
    const [r] = await refineSnappedRects(doc, rects, broken);
    expect(r!.x0).toBeCloseTo(rects[0]!.x0, 9);
    expect(r!.x1).toBeCloseTo(rects[0]!.x1, 9);
    expect(r!.snap).toBeUndefined();
  });

  it("a keyword that fills a whole item is not touched (already exact)", async () => {
    const doc = await PDFDocument.create();
    doc.registerFontkit(fontkit);
    const font = await doc.embedFont(FONT_BYTES, { subset: true });
    const page = doc.addPage([W, H]);
    page.drawText("AFR", { x: X, y: 100, size: SIZE, font });
    const src = await openPdf(await doc.save({ useObjectStreams: false }));
    const rules = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: ["AFR"], detectEmail: false };
    const { rects } = await detectTextOnDocument(src, rules);
    expect(rects[0]!.snap).toBeUndefined();
  });
});

describe("monospace text (every letter equally wide)", () => {
  it("covers exactly A-F-R of \"Teil: 4711 g (AFR-Q-VPV) Ende\"", async () => {
    const W = 400;
    const X = 20;
    const SIZE = 12;
    const text = "Teil: 4711 g (AFR-Q-VPV) Ende";
    const doc = await PDFDocument.create();
    const font = await doc.embedFont(StandardFonts.Courier);
    doc.addPage([W, 120]).drawText(text, { x: X, y: 60, size: SIZE, font });
    const src = await openPdf(await doc.save({ useObjectStreams: false }));
    const rules = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: ["AFR"], detectEmail: false };
    const { rects } = await detectTextOnDocument(src, rules);
    const [r] = await refineSnappedRects(src, rects, nodeRenderer);
    const cw = font.widthOfTextAtSize("A", SIZE);
    const realStart = X + text.indexOf("AFR") * cw;
    const realEnd = realStart + 3 * cw;
    expect(r!.x0 * W).toBeLessThanOrEqual(realStart + 0.3);
    expect(r!.x1 * W).toBeGreaterThanOrEqual(realEnd - 0.3);
    expect(realStart - r!.x0 * W).toBeLessThan(2.2);
    expect(r!.x1 * W - realEnd).toBeLessThan(2.2);
  });
});
