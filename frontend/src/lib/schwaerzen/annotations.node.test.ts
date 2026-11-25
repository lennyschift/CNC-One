import { describe, expect, it } from "vitest";
import { detectAnnotations } from "./annotations";
import { runRedaction } from "./pipeline";
import { normalizeForMatch } from "./sensitive";
import { DEFAULT_EXPORT_SETTINGS, type RedactionRect } from "./types";
import { SECRETS, buildDummyPdf } from "./testing/dummyPdf";
import { nodeRenderer, openPdf } from "./testing/nodePdfjs";

// CNC One: ausgefüllte Formularfelder (und Stempel/Freitext) zeichnet pdf.js ins Bild, im Textlayer stehen sie nicht.
describe("Anmerkungen und Formularfelder", () => {
  it("schlägt das sichtbare Formularfeld vor, nicht das reine Notiz-Symbol, und liefert seinen Text als Prüfbegriff", async () => {
    const doc = await openPdf(await buildDummyPdf({ hidden: true }));
    try {
      const r = await detectAnnotations(doc);
      expect(r.rects.map((x) => x.reason)).toEqual(["Formularfeld im PDF"]);
      expect(r.rects[0]!.kind).toBe("annotation");
      expect(r.texts).toContain(SECRETS.form);
      expect(r.texts).not.toContain(SECRETS.annotation); // Notiz (Text-Anmerkung): Inhalt steht nicht im Bild
      expect(r.pages).toEqual([1]);
    } finally {
      await doc.loadingTask.destroy();
    }
  });

  it("mit dem Vorschlag geschwärzt: das Feld ist im Ergebnis weiß und die Prüfung bestanden", async () => {
    const bytes = await buildDummyPdf({ hidden: true });
    const doc = await openPdf(bytes);
    try {
      const a = await detectAnnotations(doc);
      const rects: RedactionRect[] = a.rects.map((x, i) => ({ ...x, id: `a${i}`, source: "auto" }));
      const result = await runRedaction({
        doc,
        rects,
        settings: { ...DEFAULT_EXPORT_SETTINGS, dpi: 150 },
        manualTerms: a.texts.map(normalizeForMatch),
        renderer: nodeRenderer,
        openResult: openPdf,
        fontBytes: null,
      });
      expect(result.report.released).toBe(true);
      expect(result.report.rectsByKind).toEqual({ annotation: 1 });
      expect(result.report.checks.find((c) => c.id === "rect-render")?.status).toBe("ok");
    } finally {
      await doc.loadingTask.destroy();
    }
  });
});
