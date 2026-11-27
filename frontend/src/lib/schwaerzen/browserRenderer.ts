import type { PageRenderer, RenderedPage } from "./renderer";

/** Eine Leinwand als Seite, auf die gemalt und aus der Pixel gelesen werden können. */
export function wrapCanvas(canvas: HTMLCanvasElement): RenderedPage {
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas 2D nicht verfügbar.");
  return {
    canvas,
    width: canvas.width,
    height: canvas.height,
    readRows(y0, y1) {
      return ctx.getImageData(0, y0, canvas.width, y1 - y0).data;
    },
    fillRects(rects, fill) {
      ctx.save();
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = `rgb(${fill.r},${fill.g},${fill.b})`;
      for (const r of rects) ctx.fillRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
      ctx.restore();
    },
    thicken(radius) {
      if (!ctx || radius < 1) return;
      // Kopie, dann mit „darken“ (Minimum je Farbkanal) versetzt darüber: dunkle Linien werden breiter, Weiß bleibt Weiß
      const kopie = document.createElement("canvas");
      kopie.width = canvas.width;
      kopie.height = canvas.height;
      kopie.getContext("2d")?.drawImage(canvas, 0, 0);
      ctx.save();
      ctx.globalCompositeOperation = "darken";
      for (let dx = -radius; dx <= radius; dx++) {
        for (let dy = -radius; dy <= radius; dy++) if (dx || dy) ctx.drawImage(kopie, dx, dy);
      }
      ctx.restore();
      kopie.width = 0;
      kopie.height = 0;
    },
    dispose() {
      canvas.width = 0;
      canvas.height = 0;
    },
  };
}

/**
 * Rendert Seiten in eine eigene, nicht angezeigte Leinwand (nur im Browser). Weißer Grund vorab: eine durchsichtige
 * Stelle kann so nie ein „Loch“ ergeben. Anmerkungen (Stempel, Kommentare) werden wie im PDF-Programm mitgezeichnet —
 * sie sind damit im Prüfbild sichtbar und werden von der Erkennung eigens vorgeschlagen (siehe annotations.ts).
 */
export const browserRenderer: PageRenderer = {
  async render(page, scale): Promise<RenderedPage> {
    const canvas = document.createElement("canvas");
    const viewport = page.getViewport({ scale });
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (ctx) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    await page.render({ canvas, viewport }).promise;
    return wrapCanvas(canvas);
  },
};
