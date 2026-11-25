import type { PDFPageProxy } from "pdfjs-dist";
import type { PxRect } from "./geometry";
import type { RasterSource } from "./rasterEncode";
import type { FillColor } from "./types";

/** A rendered page that we can paint rectangles onto and read pixels from. */
export interface RenderedPage extends RasterSource {
  /** Browser only: the canvas holding the pixels (the preview shows it directly). */
  canvas?: HTMLCanvasElement;
  fillRects(rects: readonly PxRect[], fill: FillColor): void;
  dispose(): void;
}

/**
 * Abstraction over "draw a pdf.js page into a pixel buffer", so the pipeline
 * is identical in the browser (HTMLCanvas) and in the automated tests
 * (@napi-rs/canvas in Node).
 */
export interface PageRenderer {
  render(page: PDFPageProxy, scale: number): Promise<RenderedPage>;
}
