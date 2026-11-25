import { describe, expect, it } from "vitest";
import { PDFDocument, rgb } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { runRedaction } from "./pipeline";
import { auditTermsFromRules, type RuleSet } from "./rules";
import { defaultRuleSet } from "./testing/testRegeln";
import { normalizeForMatch } from "./sensitive";
import { detectTextOnDocument, type AutoRect } from "./textDetect";
import { toPageTextItems } from "./textItems";
import { DEFAULT_EXPORT_SETTINGS, type RedactionRect } from "./types";
import { FONT_BYTES } from "./testing/dummyPdf";
import { findLeaks } from "./testing/independentScan";
import { nodeRenderer, openPdf } from "./testing/nodePdfjs";

/*
 * A made-up title block (all names invented) exercising every text rule at once,
 * incl. counter-examples that must NOT be proposed.
 */

const W = 842;
const H = 595;

async function textWidth(text: string, size: number): Promise<number> {
  const d = await PDFDocument.create();
  d.registerFontkit(fontkit);
  return (await d.embedFont(FONT_BYTES)).widthOfTextAtSize(text, size);
}

async function buildDrawing(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const font = await doc.embedFont(FONT_BYTES, { subset: true });
  const page = doc.addPage([W, H]);
  const t = (s: string, x: number, y: number, size: number) => page.drawText(s, { x, y, size, font, color: rgb(0, 0, 0) });

  // revision table: header + 3 rows (+ description to the right) + unrelated text far below in the same column
  t("Geaendert", 30, 540, 7);
  t("Beschreibung", 120, 540, 7);
  [["A1", "Maß geändert"], ["B2", "Toleranz neu"], ["C3", "Oberfläche"]].forEach(([c, d], i) => {
    t(c!, 36, 526 - i * 13, 9);
    t(d!, 120, 526 - i * 13, 9);
  });
  t("Werkstoffbehandlung", 30, 420, 9);

  // title block
  t("Name", 600, 120, 7);
  t("Erika Beispiel", 600, 100, 10);
  t("Telefon/Phone", 700, 120, 7);
  t("+49 89 123456", 700, 100, 10);
  t("erika.beispiel@firma-test.example", 300, 70, 8);
  t("AFR GmbH Musterweg 5", 30, 45, 10);
  t("VW 1234", 300, 45, 10);
  t("VW1234", 300, 30, 10); // must NOT match "VW"
  t("Namenlos", 400, 30, 10); // must NOT match header "Name"

  // normal drawing content that must stay untouched
  t("Zeichnung Bauteil 4711", 200, 300, 14);
  t("Ø20 ±0,05", 200, 260, 10);
  page.drawLine({ start: { x: 20, y: 200 }, end: { x: 300, y: 200 }, thickness: 1, color: rgb(0, 0, 0) });
  return doc.save({ useObjectStreams: false });
}

interface Item {
  str: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

async function items(doc: PDFDocumentProxy): Promise<Item[]> {
  const page = await doc.getPage(1);
  const vp = page.getViewport({ scale: 1 });
  return toPageTextItems((await page.getTextContent()).items, vp.transform).map((i) => ({ str: i.str, ...i.bbox }));
}

const pt = (r: AutoRect) => ({ x0: r.x0 * W, y0: r.y0 * H, x1: r.x1 * W, y1: r.y1 * H });
const covers = (r: AutoRect, i: Item, slack = 0) => {
  const p = pt(r);
  const cy = (i.y0 + i.y1) / 2;
  return p.x0 <= i.x0 + slack && p.x1 >= i.x1 - slack && p.y0 <= cy && p.y1 >= cy;
};
const touches = (r: AutoRect, i: Item) => {
  const p = pt(r);
  const cy = (i.y0 + i.y1) / 2;
  return p.x0 < i.x1 && p.x1 > i.x0 && p.y0 <= cy && p.y1 >= cy;
};

describe("automatic detection on a made-up title block", () => {
  it("proposes exactly the expected areas, with reasons", async () => {
    const doc = await openPdf(await buildDrawing());
    const all = await items(doc);
    const find = (s: string) => all.find((i) => i.str === s)!;
    const { rects, pagesWithoutText } = await detectTextOnDocument(doc, defaultRuleSet());
    expect(pagesWithoutText).toEqual([]);

    const by = (kind: string) => rects.filter((r) => r.kind === kind);

    // header → text below
    expect(by("header").some((r) => covers(r, find("Erika Beispiel")) && r.reason.includes("Name"))).toBe(true);
    expect(by("header").some((r) => covers(r, find("+49 89 123456")))).toBe(true);
    // revision table: all three rows (code + the description right of it is NOT in the narrow column)
    for (const c of ["A1", "B2", "C3"]) expect(by("changeTable").some((r) => covers(r, find(c)))).toBe(true);
    // (directly consecutive rows are merged into ONE block, as in the Python tool)
    expect(by("changeTable").length).toBeGreaterThanOrEqual(1);
    expect(by("changeTable").length).toBeLessThanOrEqual(3);
    // e-mail by "@"
    expect(by("email").some((r) => covers(r, find("erika.beispiel@firma-test.example")))).toBe(true);
    // direct keywords
    expect(by("keyword").some((r) => r.reason.includes("AFR GmbH"))).toBe(true);
    expect(by("keyword").some((r) => r.reason.includes("VW"))).toBe(true);

    // must stay untouched
    for (const s of ["Zeichnung Bauteil 4711", "Ø20 ±0,05", "Werkstoffbehandlung", "VW1234", "Namenlos", "Beschreibung", "Maß geändert"]) {
      expect(rects.some((r) => touches(r, find(s))), s).toBe(false);
    }
    // the headers themselves are not blacked out (only what is below them)
    for (const s of ["Name", "Telefon/Phone", "Geaendert"]) expect(rects.some((r) => covers(r, find(s))), s).toBe(false);
  });

  it("covers the keyword inside a longer item completely, without swallowing the rest", async () => {
    const doc = await openPdf(await buildDrawing());
    const all = await items(doc);
    const line = all.find((i) => i.str.startsWith("AFR GmbH"))!;
    const { rects } = await detectTextOnDocument(doc, defaultRuleSet());
    const r = pt(rects.find((x) => x.reason.includes("AFR GmbH"))!);
    const kwWidth = await textWidth("AFR GmbH", 10);
    const lineWidth = await textWidth("AFR GmbH Musterweg 5", 10);
    expect(r.x0).toBeLessThanOrEqual(line.x0 + 0.1); // starts at the item start (30), allowing the margin to the left
    expect(r.x1).toBeGreaterThanOrEqual(line.x0 + kwWidth); // covers the whole keyword …
    expect(r.x1).toBeLessThan(line.x0 + lineWidth - 20); // … but leaves "Musterweg 5" mostly visible
  });

  it("keyword matching is whole-word and case-insensitive", async () => {
    const doc = await openPdf(await buildDrawing());
    const rules: RuleSet = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: ["vw", "name"], detectEmail: false };
    const { rects } = await detectTextOnDocument(doc, rules);
    const vw = rects.filter((r) => r.reason.includes("vw"));
    expect(vw.length).toBe(1); // "VW 1234" yes, "VW1234" no
    expect(rects.filter((r) => r.reason.includes("name")).length).toBe(1); // the header word "Name", not "Namenlos"
  });

  it("without any rule nothing is proposed; switching rules off removes their proposals", async () => {
    const doc = await openPdf(await buildDrawing());
    const none: RuleSet = { ...defaultRuleSet(), headerKeywords: [], changeTableKeywords: [], directKeywords: [], detectEmail: false };
    expect((await detectTextOnDocument(doc, none)).rects).toEqual([]);
  });

  it("end to end: proposals → export with WHITE fill → checked file without any leftover", async () => {
    const source = await buildDrawing();
    const doc = await openPdf(source);
    const rules = defaultRuleSet();
    const { rects: auto } = await detectTextOnDocument(doc, rules);
    const rects: RedactionRect[] = auto.map((a, i) => ({ ...a, id: `a${i}`, source: "auto" }));

    const result = await runRedaction({
      doc,
      rects,
      settings: { ...DEFAULT_EXPORT_SETTINGS, mode: "rasterText" }, // white by default; text layer on so "stays searchable" can be checked
      manualTerms: auditTermsFromRules(rules).map(normalizeForMatch),
      renderer: nodeRenderer,
      openResult: openPdf,
      fontBytes: FONT_BYTES,
    });
    expect(DEFAULT_EXPORT_SETTINGS.fillHex).toBe("#ffffff");
    const failed = result.report.checks.filter((c) => c.status === "fail");
    expect(failed, JSON.stringify(failed)).toEqual([]);
    expect(findLeaks(result.bytes, ["Erika", "Beispiel", "erika.beispiel", "firma-test", "AFR GmbH", "AFR", "123456", "Musterweg"])).toEqual([]);

    // what is not redacted stays searchable
    const out = await openPdf(result.bytes);
    const text = (await (await out.getPage(1)).getTextContent()).items.map((i) => ("str" in i ? i.str : "")).join(" ");
    for (const keep of ["Zeichnung Bauteil 4711", "Werkstoffbehandlung", "Beschreibung"]) expect(text).toContain(keep);
    for (const gone of ["Erika", "AFR", "@", "Musterweg", "123456"]) expect(text).not.toContain(gone);
  }, 60_000);
});

describe("the app's real default (raster only)", () => {
  it("the default save mode writes no text at all", () => {
    expect(DEFAULT_EXPORT_SETTINGS.mode).toBe("rasterOnly");
  });
});
