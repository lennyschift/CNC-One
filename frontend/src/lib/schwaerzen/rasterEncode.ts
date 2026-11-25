import type { PxRect } from "./geometry";
import type { FillColor } from "./types";

/** Anything we can read RGBA pixel rows from (a canvas in the browser, a buffer in tests). */
export interface RasterSource {
  width: number;
  height: number;
  /** RGBA rows y0..y1 (exclusive), tightly packed: (y1-y0) * width * 4 bytes. */
  readRows(y0: number, y1: number): Uint8ClampedArray | Uint8Array;
}

export interface InkMap {
  width: number;
  height: number;
  /** 1 = "dark" pixel (visible ink), 0 = light/background. Row-major. */
  data: Uint8Array;
}

export interface EncodedRaster {
  width: number;
  height: number;
  /**
   * "gray" if every pixel has R = G = B (a black-and-white drawing): stored with ONE channel, which is lossless and a third
   * of the data. Otherwise "rgb".
   */
  colorSpace: "gray" | "rgb";
  /** zlib stream of the rows with PNG "Up" predictor (PDF FlateDecode, Predictor 15, Colors 1 or 3). */
  deflated: Uint8Array;
  ink: InkMap;
  /** Pixels inside a redaction rect that were NOT exactly the fill colour (must be 0). */
  rectMismatchPixels: number;
}

/** Luminance below this counts as visible ink for the text-layer visibility test. */
const INK_LUMINANCE_MAX = 190;
const TARGET_BAND_BYTES = 2_000_000;

/** True if every pixel (composited over white) has R, G and B within 1 level of each other. */
function isGrayscale(src: RasterSource, bandRows: number): boolean {
  const { width, height } = src;
  for (let y0 = 0; y0 < height; y0 += bandRows) {
    const y1 = Math.min(height, y0 + bandRows);
    const rgba = src.readRows(y0, y1);
    for (let p = 0, n = (y1 - y0) * width * 4; p < n; p += 4) {
      let r = rgba[p]!;
      let g = rgba[p + 1]!;
      let b = rgba[p + 2]!;
      const a = rgba[p + 3]!;
      if (a !== 255) {
        r = (r * a + 255 * (255 - a)) / 255;
        g = (g * a + 255 * (255 - a)) / 255;
        b = (b * a + 255 * (255 - a)) / 255;
      }
      if (Math.abs(r - g) > 1 || Math.abs(g - b) > 1) return false;
    }
  }
  return true;
}

/**
 * One pass over the finished page image (after the rectangles were painted):
 *  1. builds the compressed image stream (PNG-Up predictor + deflate; 1 channel for black-and-white pages, else RGB),
 *  2. builds a 1-byte-per-pixel "ink" map (used to prove text is really visible),
 *  3. verifies that every pixel inside every redaction rect equals the fill colour.
 * Processed in horizontal bands so peak memory stays small even for A1/A0.
 */
export async function encodeRaster(
  src: RasterSource,
  pixelRects: readonly PxRect[],
  fill: FillColor,
  /** Pixels inside these rectangles (re-drawn table lines) are exempt from the "must equal the fill colour" check. */
  ignoreRects: readonly PxRect[] = [],
): Promise<EncodedRaster> {
  const { width, height } = src;
  const bandRows = Math.max(1, Math.min(256, Math.floor(TARGET_BAND_BYTES / (width * 4))));
  const ink = new Uint8Array(width * height);
  let mismatch = 0;

  const cs = new CompressionStream("deflate");
  const writer = cs.writable.getWriter();
  const compressed = new Response(cs.readable).arrayBuffer();

  const gray = isGrayscale(src, bandRows);
  const channels = gray ? 1 : 3;
  const rowBytes = width * channels;
  let prevRow = new Uint8Array(rowBytes); // "row above" for the Up predictor; zeros for row 0
  const cur = new Uint8Array(rowBytes);

  try {
    for (let y0 = 0; y0 < height; y0 += bandRows) {
      const y1 = Math.min(height, y0 + bandRows);
      const rgba = src.readRows(y0, y1);
      const out = new Uint8Array((y1 - y0) * (rowBytes + 1));
      let o = 0;

      for (let y = y0; y < y1; y++) {
        let p = (y - y0) * width * 4;
        for (let x = 0; x < width; x++, p += 4) {
          let r = rgba[p]!;
          let g = rgba[p + 1]!;
          let b = rgba[p + 2]!;
          const a = rgba[p + 3]!;
          if (a !== 255) {
            // Composite over white so a transparent canvas can never leak a "hole".
            r = Math.round((r * a + 255 * (255 - a)) / 255);
            g = Math.round((g * a + 255 * (255 - a)) / 255);
            b = Math.round((b * a + 255 * (255 - a)) / 255);
          }
          if (gray) {
            cur[x] = g;
          } else {
            const i = x * 3;
            cur[i] = r;
            cur[i + 1] = g;
            cur[i + 2] = b;
          }
          if (0.299 * r + 0.587 * g + 0.114 * b < INK_LUMINANCE_MAX) ink[y * width + x] = 1;
        }

        out[o++] = 2; // PNG filter type "Up"
        for (let i = 0; i < rowBytes; i++) out[o++] = (cur[i]! - prevRow[i]!) & 255;
        prevRow.set(cur);

        for (const rect of pixelRects) {
          if (y < rect.y0 || y >= rect.y1) continue;
          for (let x = rect.x0; x < rect.x1; x++) {
            if (ignoreRects.some((g) => x >= g.x0 && x < g.x1 && y >= g.y0 && y < g.y1)) continue;
            if (gray) {
              if (cur[x] !== fill.g) mismatch++;
            } else {
              const i = x * 3;
              if (cur[i] !== fill.r || cur[i + 1] !== fill.g || cur[i + 2] !== fill.b) mismatch++;
            }
          }
        }
      }
      await writer.write(out);
    }
    await writer.close();
  } catch (err) {
    await writer.abort(err).catch(() => undefined);
    throw err;
  }

  prevRow = new Uint8Array(0);
  return {
    width,
    height,
    colorSpace: gray ? "gray" : "rgb",
    deflated: new Uint8Array(await compressed),
    ink: { width, height, data: ink },
    rectMismatchPixels: mismatch,
  };
}
