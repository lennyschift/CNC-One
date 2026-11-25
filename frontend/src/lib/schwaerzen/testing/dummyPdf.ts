// Builds synthetic drawings with HIDDEN content for the tests. All names,
// words and "secrets" are invented — no customer data, ever.
import fs from "node:fs";
import path from "node:path";
import fontkit from "@pdf-lib/fontkit";
import {
  PDFDocument,
  PDFName,
  PDFOperator,
  PDFString,
  TextRenderingMode,
  beginText,
  degrees,
  endText,
  rgb,
  setFontAndSize,
  setTextMatrix,
  setTextRenderingMode,
  showText,
} from "pdf-lib";

export const FONT_BYTES = new Uint8Array(
  fs.readFileSync(path.resolve(import.meta.dirname, "./NotoSans-Regular.ttf")),
);

/** Every string that must NOT survive redaction / hiding. */
export const SECRETS = {
  white: "GEHEIMWEISS",
  tiny: "GEHEIMWINZIG",
  mode3: "GEHEIMMODEDREI",
  ocg: "GEHEIMEBENE",
  attachment: "GEHEIMANHANGINHALT",
  attachmentName: "GEHEIMANHANG.txt",
  annotation: "GEHEIMANMERKUNG",
  form: "GEHEIMFORMULAR",
  title: "GEHEIMTITEL",
  author: "GEHEIMAUTOR",
  keywords: "GEHEIMSCHLAGWORT",
  /** Visible in the original but covered by a rectangle in the tests: */
  name: "Mustermann",
  address: "Musterweg",
} as const;

/** Visible words that must stay searchable. */
export const KEPT_WORDS = ["Zeichnung", "Werkstoff", "1.4301", "Blatt"] as const;

export interface DummyOptions {
  rotate?: 0 | 90 | 180 | 270;
  crop?: { x: number; y: number; width: number; height: number };
  /** Add all hidden extras (white/tiny/mode-3/OCG text, attachment, annotation, form field, metadata). */
  hidden?: boolean;
}

export const PAGE_W = 400;
export const PAGE_H = 300;

export async function buildDummyPdf(opts: DummyOptions = {}): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const font = await doc.embedFont(FONT_BYTES, { subset: true });
  const page = doc.addPage([PAGE_W, PAGE_H]);
  const black = rgb(0, 0, 0);

  const draw = (text: string, x: number, y: number, size: number) =>
    page.drawText(text, { x, y, size, font, color: black });

  // Visible content
  draw("Zeichnung Bauteil 4711", 30, 255, 14);
  draw("Werkstoff 1.4301", 30, 220, 12);
  draw("Konstrukteur:", 30, 60, 10);
  draw(SECRETS.name, 100, 60, 10);
  draw(`Muster GmbH ${SECRETS.address} 5`, 30, 40, 10);
  draw("Blatt 1 von 1", 200, 30, 10);
  page.drawLine({ start: { x: 20, y: 200 }, end: { x: 280, y: 200 }, thickness: 1, color: black });

  if (opts.hidden) {
    const context = doc.context;

    // 1) white text on white
    page.drawText(SECRETS.white, { x: 30, y: 180, size: 12, font, color: rgb(1, 1, 1) });
    // 2) tiny text
    page.drawText(SECRETS.tiny, { x: 30, y: 165, size: 0.5, font, color: black });
    // 3) invisible text (render mode 3, like an OCR layer)
    const fontKey = page.node.newFontDictionary(font.name, font.ref);
    page.pushOperators(
      beginText(),
      setTextRenderingMode(TextRenderingMode.Invisible),
      setFontAndSize(fontKey, 12),
      setTextMatrix(1, 0, 0, 1, 30, 145),
      showText(font.encodeText(SECRETS.mode3)),
      endText(),
    );
    // 4) content in an optional-content group that is switched OFF
    const ocg = context.register(context.obj({ Type: PDFName.of("OCG"), Name: PDFString.of("Versteckt") }));
    doc.catalog.set(
      PDFName.of("OCProperties"),
      context.obj({ OCGs: [ocg], D: { OFF: [ocg], Order: [ocg] } }),
    );
    const props = context.obj({ MC0: ocg });
    const resources = page.node.Resources();
    resources?.set(PDFName.of("Properties"), props);
    page.pushOperators(
      PDFOperator.of("BDC" as never, [PDFName.of("OC"), PDFName.of("MC0")]),
      beginText(),
      setFontAndSize(fontKey, 12),
      setTextMatrix(1, 0, 0, 1, 30, 125),
      showText(font.encodeText(SECRETS.ocg)),
      endText(),
      PDFOperator.of("EMC" as never),
    );
    // 5) file attachment
    await doc.attach(new TextEncoder().encode(SECRETS.attachment), SECRETS.attachmentName, { mimeType: "text/plain" });
    // 6) annotation
    const annot = context.register(
      context.obj({
        Type: PDFName.of("Annot"),
        Subtype: PDFName.of("Text"),
        Rect: [10, 10, 30, 30],
        Contents: PDFString.of(SECRETS.annotation),
      }),
    );
    page.node.set(PDFName.of("Annots"), context.obj([annot]));
    // 7) form field
    const field = doc.getForm().createTextField("feld1");
    field.setText(SECRETS.form);
    field.addToPage(page, { x: 300, y: 100, width: 80, height: 20 });
    // 8) document metadata
    doc.setTitle(SECRETS.title);
    doc.setAuthor(SECRETS.author);
    doc.setKeywords([SECRETS.keywords]);
    doc.setSubject(SECRETS.keywords);
  }

  if (opts.crop) page.setCropBox(opts.crop.x, opts.crop.y, opts.crop.width, opts.crop.height);
  if (opts.rotate) page.setRotation(degrees(opts.rotate));
  return doc.save({ useObjectStreams: false });
}
