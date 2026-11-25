import { describe, expect, it } from "vitest";
import { detectTextRules } from "./textRules";
import type { PageTextItem } from "./textItems";

/** Made-up title block of another customer: revision row ABOVE its header, "Gez."/"Gepr." with the values to the RIGHT. */
const FS = 8;
function item(str: string, x: number, baseline: number): PageTextItem {
  const w = str.length * FS * 0.55;
  return {
    str,
    matrix: [FS, 0, 0, -FS, x, baseline],
    bbox: { x0: x, y0: baseline - FS, x1: x + w, y1: baseline + 2 },
    fontSize: FS,
    widthPt: w,
  };
}

const W = 400;
const H = 340;
const items: PageTextItem[] = [
  // revision row (grows upward: sits above the header row)
  item("A", 30, 240),
  item("8105", 60, 240),
  item("Aufhaengegewinde", 110, 240),
  item("15.02.2012", 250, 240),
  item("SCHUBERTM", 320, 240),
  // its header row
  item("Vers.", 30, 262),
  item("Mit.-Nr.", 60, 262),
  item("Aenderungstext", 110, 262),
  item("Datum", 250, 262),
  item("Name", 320, 262),
  // Gez. / Gepr. rows
  item("Gez.", 200, 284),
  item("17.10.2011", 250, 284),
  item("SCHUBERTM", 320, 284),
  item("Gepr.", 200, 306),
  item("15.02.12", 250, 306),
  item("SCHUBERTM", 320, 306),
  item("Erzeugersystem", 200, 328),
  item("ProE", 320, 328),
];

const none = { directKeywords: [], headerKeywords: [], changeTableKeywords: [], detectEmail: false, detectPhone: false };
const run = (extra: object) => detectTextRules({ items, pageWidthPt: W, pageHeightPt: H, rules: { ...none, ...extra } });
const covers = (r: { x0: number; x1: number; y0: number; y1: number }, x: number, y: number) => r.x0 <= x && r.x1 >= x && r.y0 <= y && r.y1 >= y;

describe("rules for other customers' title blocks", () => {
  it("column ABOVE a heading: the revision rows over 'Name', not the rows below it", () => {
    const d = run({ columnAboveKeywords: ["Name"] });
    expect(d.length).toBeGreaterThan(0);
    expect(d.every((x) => x.kind === "changeTable")).toBe(true);
    expect(d.some((x) => covers(x.rect, 340, 236))).toBe(true); // "SCHUBERTM" of the revision row
    expect(d.some((x) => covers(x.rect, 340, 280))).toBe(false); // the Gez. row lies BELOW the heading
    expect(d.some((x) => covers(x.rect, 270, 236))).toBe(false); // other column
  });

  it("label → values to the right: Gez./Gepr. date and name, but nothing else", () => {
    const d = run({ labelRightKeywords: ["Gez.", "Gepr."] });
    expect(d.every((x) => x.kind === "labelRight")).toBe(true);
    for (const y of [280, 302]) {
      expect(d.some((x) => covers(x.rect, 270, y))).toBe(true); // date
      expect(d.some((x) => covers(x.rect, 345, y))).toBe(true); // name
    }
    expect(d.some((x) => covers(x.rect, 210, 280))).toBe(false); // the label itself stays
    expect(d.some((x) => covers(x.rect, 345, 324))).toBe(false); // "Erzeugersystem … ProE" is not a Gez./Gepr. row
    expect(d.some((x) => covers(x.rect, 345, 236))).toBe(false);
  });

  it("a gap wider than 5 font sizes ends the row of fields; at most 3 fields", () => {
    const far = [...items, item("Fern", 500, 284)]; // 500 − (320 + 49.5) = 130 pt gap
    const d = detectTextRules({ items: far, pageWidthPt: 600, pageHeightPt: H, rules: { ...none, labelRightKeywords: ["Gez."] } });
    expect(d.some((x) => covers(x.rect, 510, 280))).toBe(false);
    const many = [item("Gez.", 20, 50), item("a", 50, 50), item("b", 70, 50), item("c", 90, 50), item("d", 110, 50)];
    const e = detectTextRules({ items: many, pageWidthPt: W, pageHeightPt: H, rules: { ...none, labelRightKeywords: ["Gez."] } });
    expect(e).toHaveLength(3);
  });

  it("rest of the label's own item: 'Gez. 17.10.2011' as ONE item", () => {
    const one = [item("Gez. 17.10.2011", 200, 284)];
    const d = detectTextRules({ items: one, pageWidthPt: W, pageHeightPt: H, rules: { ...none, labelRightKeywords: ["Gez."] } });
    expect(d).toHaveLength(1);
    expect(d[0]!.rect.x0).toBeGreaterThan(200 + 3); // the label stays outside
    expect(d[0]!.rect.x1).toBeGreaterThan(200 + 15 * FS * 0.5);
  });

  it("without these rules nothing new is proposed (old rule sets keep working)", () => {
    expect(run({})).toEqual([]);
  });
});
