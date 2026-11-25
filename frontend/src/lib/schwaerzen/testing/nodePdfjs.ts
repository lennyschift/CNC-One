// Node-only helpers for the automated tests: real pdf.js (legacy build) + real
// rendering through @napi-rs/canvas. NOT part of the browser bundle.
import path from "node:path";
import { createCanvas } from "@napi-rs/canvas";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";
import type { PageRenderer, RenderedPage } from "../renderer";

// pdf.js insists on a forward slash at the end, also on Windows.
const STANDARD_FONTS = path.resolve(import.meta.dirname, "../../../../node_modules/pdfjs-dist/standard_fonts").replaceAll("\\", "/") + "/";

export async function openPdf(bytes: Uint8Array): Promise<PDFDocumentProxy> {
  const task = pdfjs.getDocument({
    data: new Uint8Array(bytes), // pdf.js takes ownership of the buffer
    standardFontDataUrl: STANDARD_FONTS,
    verbosity: 0,
  });
  return (await task.promise) as unknown as PDFDocumentProxy;
}

export const nodeRenderer: PageRenderer = {
  async render(page: PDFPageProxy, scale: number): Promise<RenderedPage> {
    const viewport = page.getViewport({ scale });
    const width = Math.ceil(viewport.width);
    const height = Math.ceil(viewport.height);
    const canvas = createCanvas(width, height);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    await page.render({ canvas: canvas as unknown as HTMLCanvasElement, viewport }).promise;

    return {
      width,
      height,
      readRows(y0, y1) {
        return ctx.getImageData(0, y0, width, y1 - y0).data;
      },
      fillRects(rects, fill) {
        ctx.fillStyle = `rgb(${fill.r},${fill.g},${fill.b})`;
        for (const r of rects) ctx.fillRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
      },
      dispose() {
        /* garbage collected */
      },
    };
  },
};
