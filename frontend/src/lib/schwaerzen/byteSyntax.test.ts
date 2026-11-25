import { describe, expect, it } from "vitest";
import { blankPdfSyntax, foldAsciiCase, indexOfBytes } from "./byteSearch";
import { scanBytesForTerms } from "./verify";
import { RedactedPdfBuilder } from "./pdfAssemble";

const enc = (s: string) => new TextEncoder().encode(s);
const has = (buf: Uint8Array, t: string) => indexOfBytes(foldAsciiCase(buf), foldAsciiCase(enc(t))) >= 0;

// CNC One: Wörter, die zufällig PDF-Schlüsseln gleichen („Width“, „Size“, „Type“ in zweisprachigen Schriftfeldern),
// dürfen in der Byte-Suche keinen Fehlalarm auslösen — echte Zeichenketten aber weiterhin gefunden werden.
describe("blankPdfSyntax", () => {
  it("leert Namen und Schlüsselwörter, lässt Zeichenketten stehen", () => {
    const out = blankPdfSyntax(enc("1 0 obj\n<< /Type /XObject /Width 10 /Title (Geheim/Width) >>\nendobj\nxref\ntrailer"));
    expect(has(out, "width")).toBe(true); // nur noch die in der Zeichenkette
    expect(has(out, "xobject")).toBe(false);
    expect(has(out, "type")).toBe(false);
    expect(has(out, "trailer")).toBe(false);
    expect(has(out, "geheim/width")).toBe(true);
  });

  it("eine echte, nur aus Bildern bestehende Ausgabe meldet PDF-Wörter und den Erzeuger nicht als Treffer", async () => {
    const b = await RedactedPdfBuilder.create({ fontBytes: null });
    const w = 4;
    const raster = { width: w, height: w, colorSpace: "gray" as const, deflated: new Uint8Array(await new Response(new Blob([new Uint8Array((w + 1) * w)]).stream().pipeThrough(new CompressionStream("deflate"))).arrayBuffer()), ink: { width: w, height: w, data: new Uint8Array(w * w) }, rectMismatchPixels: 0 };
    b.addPage({ widthPt: 100, heightPt: 50, raster, textItems: [] });
    const bytes = await b.save();
    const r = await scanBytesForTerms(bytes, ["width", "size", "type", "mediabox", "columns", "local", "browser", "tool"]);
    expect(r.hitTermIndexes).toEqual([]);
  });
});
