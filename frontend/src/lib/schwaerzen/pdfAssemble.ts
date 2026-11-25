import {
  PDFDocument,
  PDFName,
  PDFNumber,
  PDFRawStream,
  TextRenderingMode,
  beginText,
  concatTransformationMatrix,
  drawObject,
  endText,
  popGraphicsState,
  pushGraphicsState,
  setCharacterSqueeze,
  setFontAndSize,
  setTextMatrix,
  setTextRenderingMode,
  showText,
  type PDFFont,
  type PDFOperator,
} from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import type { EncodedRaster } from "./rasterEncode";
import { multiplyMatrix, type PageTextItem } from "./textItems";

/** CNC One: kein sprechender Erzeuger-Text — Wörter darin („local“, „tool“ …) ergäben in der Byte-Suche Fehlalarme. */
export const PRODUCER = "-";

export interface AssemblePage {
  widthPt: number;
  heightPt: number;
  raster: EncodedRaster;
  /** Already filtered, see textLayerFilter.ts. Ignored in "raster only" builds. */
  textItems: readonly PageTextItem[];
}

/**
 * Builds the output PDF from scratch (the original is never modified, never
 * saved incrementally, none of its objects are copied): one full-page RGB
 * image per page plus — optionally — an invisible (render mode 3) text layer
 * of the pre-filtered items, so search / copy still work in Chrome, Edge,
 * Acrobat and Foxit. The Info dictionary carries only Producer/Creator and
 * the dates; no XMP, no outline, no annotations, no attachments.
 */
export class RedactedPdfBuilder {
  private readonly doc: PDFDocument;
  private readonly font: PDFFont | null;
  private readonly glyphSet: Set<number> | null;

  private constructor(doc: PDFDocument, font: PDFFont | null, glyphSet: Set<number> | null) {
    this.doc = doc;
    this.font = font;
    this.glyphSet = glyphSet;
  }

  static async create(opts: { fontBytes: ArrayBuffer | Uint8Array | null; now?: Date }): Promise<RedactedPdfBuilder> {
    const doc = await PDFDocument.create({ updateMetadata: false });
    const now = opts.now ?? new Date();
    doc.setProducer(PRODUCER);
    doc.setCreator(PRODUCER);
    doc.setCreationDate(now);
    doc.setModificationDate(now);

    let font: PDFFont | null = null;
    let glyphSet: Set<number> | null = null;
    if (opts.fontBytes) {
      doc.registerFontkit(fontkit);
      font = await doc.embedFont(opts.fontBytes, { subset: true });
      glyphSet = new Set(font.getCharacterSet());
    }
    return new RedactedPdfBuilder(doc, font, glyphSet);
  }

  /** Text safe to encode with the embedded font: unsupported / control characters are dropped. */
  private cleanText(s: string): string {
    if (!this.glyphSet) return "";
    let out = "";
    for (const ch of s) {
      const cp = ch.codePointAt(0)!;
      if (cp < 0x20 || (cp >= 0x7f && cp < 0xa0)) continue;
      if (this.glyphSet.has(cp)) out += ch;
    }
    return out.trim();
  }

  addPage(p: AssemblePage): { textItemsWritten: number } {
    const { doc } = this;
    const context = doc.context;

    const imageStream = PDFRawStream.of(
      context.obj({
        Type: PDFName.of("XObject"),
        Subtype: PDFName.of("Image"),
        Width: PDFNumber.of(p.raster.width),
        Height: PDFNumber.of(p.raster.height),
        ColorSpace: PDFName.of(p.raster.colorSpace === "gray" ? "DeviceGray" : "DeviceRGB"),
        BitsPerComponent: PDFNumber.of(8),
        Filter: PDFName.of("FlateDecode"),
        DecodeParms: {
          Predictor: PDFNumber.of(15),
          Colors: PDFNumber.of(p.raster.colorSpace === "gray" ? 1 : 3),
          BitsPerComponent: PDFNumber.of(8),
          Columns: PDFNumber.of(p.raster.width),
        },
        Length: PDFNumber.of(p.raster.deflated.length),
      }),
      p.raster.deflated,
    );
    const imageRef = context.register(imageStream);

    const page = doc.addPage([p.widthPt, p.heightPt]);
    const imageName = page.node.newXObject("Im0", imageRef);
    const ops: PDFOperator[] = [
      pushGraphicsState(),
      concatTransformationMatrix(p.widthPt, 0, 0, p.heightPt, 0, 0),
      drawObject(imageName),
      popGraphicsState(),
    ];

    let written = 0;
    if (this.font) {
      const fontName = page.node.newFontDictionary(this.font.name, this.font.ref);
      // Flip: page space (origin top-left, y down) -> PDF user space (origin bottom-left, y up).
      const flip = [1, 0, 0, -1, 0, p.heightPt] as const;
      for (const item of p.textItems) {
        const text = this.cleanText(item.str);
        if (text.length === 0) continue;
        const natural = this.font.widthOfTextAtSize(text, 1);
        const m = multiplyMatrix(flip, item.matrix);
        const naturalPt = natural * Math.hypot(m[0], m[1]);
        if (!(naturalPt > 0) || !(item.widthPt > 0)) continue;
        const squeeze = Math.min(400, Math.max(10, (item.widthPt / naturalPt) * 100));

        ops.push(
          beginText(),
          setTextRenderingMode(TextRenderingMode.Invisible),
          setFontAndSize(fontName, 1),
          setCharacterSqueeze(squeeze),
          setTextMatrix(m[0], m[1], m[2], m[3], m[4], m[5]),
          showText(this.font.encodeText(text)),
          endText(),
        );
        written++;
      }
    }
    page.pushOperators(...ops);
    return { textItemsWritten: written };
  }

  async save(): Promise<Uint8Array> {
    // No object streams: dictionary keys stay plainly visible for the post-save audit.
    return this.doc.save({ useObjectStreams: false, addDefaultPage: false });
  }
}
