import zlib from "node:zlib";
import { describe, expect, it } from "vitest";
import { encodeRaster, type RasterSource } from "./rasterEncode";

/** Undo the PNG "Up" predictor exactly as a PDF reader would (Predictor 15, Colors 3, 8 bit). */
function decode(deflated: Uint8Array, width: number, height: number, channels = 3): Uint8Array {
  const raw = zlib.inflateSync(deflated);
  const rowBytes = width * channels;
  expect(raw.length).toBe(height * (rowBytes + 1));
  const out = new Uint8Array(height * rowBytes);
  for (let y = 0; y < height; y++) {
    expect(raw[y * (rowBytes + 1)]).toBe(2); // filter type "Up"
    for (let i = 0; i < rowBytes; i++) {
      const above = y === 0 ? 0 : out[(y - 1) * rowBytes + i]!;
      out[y * rowBytes + i] = (raw[y * (rowBytes + 1) + 1 + i]! + above) & 255;
    }
  }
  return out;
}

function makeSource(width: number, height: number, pixel: (x: number, y: number) => [number, number, number, number]): RasterSource {
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) data.set(pixel(x, y), (y * width + x) * 4);
  }
  return { width, height, readRows: (y0, y1) => data.subarray(y0 * width * 4, y1 * width * 4) };
}

describe("encodeRaster", () => {
  it("round-trips pixels exactly (also across several bands) and builds the ink map", async () => {
    const width = 700; // > 1 band of rows for the ~2 MB band size when height is large
    const height = 900;
    const src = makeSource(width, height, (x, y) => [(x * 7) & 255, (y * 13) & 255, ((x + y) * 3) & 255, 255]);
    const enc = await encodeRaster(src, [], { r: 0, g: 0, b: 0 });
    const back = decode(enc.deflated, width, height);
    for (const [x, y] of [[0, 0], [699, 0], [0, 899], [123, 456], [699, 899]] as const) {
      const p = (y * width + x) * 3;
      expect([back[p], back[p + 1], back[p + 2]]).toEqual([(x * 7) & 255, (y * 13) & 255, ((x + y) * 3) & 255]);
    }
    expect(enc.rectMismatchPixels).toBe(0);
    expect(enc.ink.data.length).toBe(width * height);
  });

  it("marks dark pixels as ink and light ones as background", async () => {
    const src = makeSource(10, 10, (x) => (x < 5 ? [0, 0, 0, 255] : [255, 255, 255, 255]));
    const enc = await encodeRaster(src, [], { r: 0, g: 0, b: 0 });
    expect(enc.ink.data[0]).toBe(1);
    expect(enc.ink.data[9]).toBe(0);
  });

  it("flags redaction rectangles that are not exactly the fill colour", async () => {
    const fill = { r: 0, g: 0, b: 0 };
    const good = makeSource(20, 20, () => [0, 0, 0, 255]);
    expect((await encodeRaster(good, [{ x0: 2, y0: 2, x1: 10, y1: 10 }], fill)).rectMismatchPixels).toBe(0);
    // one slightly-off pixel inside the rect
    const bad = makeSource(20, 20, (x, y) => (x === 5 && y === 5 ? [0, 0, 3, 255] : [0, 0, 0, 255]));
    expect((await encodeRaster(bad, [{ x0: 2, y0: 2, x1: 10, y1: 10 }], fill)).rectMismatchPixels).toBe(1);
    // …but the same pixel outside the rect is not a problem
    expect((await encodeRaster(bad, [{ x0: 8, y0: 8, x1: 10, y1: 10 }], fill)).rectMismatchPixels).toBe(0);
  });

  it("composites transparent pixels over white (no see-through hole)", async () => {
    const src = makeSource(4, 4, () => [0, 0, 0, 0]);
    const enc = await encodeRaster(src, [], { r: 0, g: 0, b: 0 });
    expect(enc.colorSpace).toBe("gray"); // transparent = white = gray
    expect(Array.from(decode(enc.deflated, 4, 4, 1).subarray(0, 1))).toEqual([255]);
    expect(enc.ink.data.every((v) => v === 0)).toBe(true);
  });

  it("stores a black-and-white page with ONE channel, losslessly and at a third of the data", async () => {
    const w = 120;
    const h = 80;
    const src = makeSource(w, h, (x, y) => {
      const v = (x * 5 + y * 3) % 256; // an arbitrary gray gradient with R = G = B
      return [v, v, v, 255];
    });
    const enc = await encodeRaster(src, [], { r: 255, g: 255, b: 255 });
    expect(enc.colorSpace).toBe("gray");
    const back = decode(enc.deflated, w, h, 1);
    for (const [x, y] of [[0, 0], [119, 0], [0, 79], [57, 31], [119, 79]] as const) expect(back[y * w + x]).toBe((x * 5 + y * 3) % 256);
    const rgb = await encodeRaster(makeSource(w, h, (x, y) => [(x * 5 + y * 3) % 256, 7, 9, 255]), [], { r: 255, g: 255, b: 255 });
    expect(rgb.colorSpace).toBe("rgb");
    expect(zlib.inflateSync(enc.deflated).length * 3).toBeLessThan(zlib.inflateSync(rgb.deflated).length * 1.05);
  });

  it("one slightly coloured pixel anywhere switches the whole page to RGB (no colour is ever lost)", async () => {
    const src = makeSource(50, 50, (x, y) => (x === 49 && y === 49 ? [200, 100, 100, 255] : [200, 200, 200, 255]));
    const enc = await encodeRaster(src, [], { r: 255, g: 255, b: 255 });
    expect(enc.colorSpace).toBe("rgb");
    const back = decode(enc.deflated, 50, 50, 3);
    const p = (49 * 50 + 49) * 3;
    expect([back[p], back[p + 1], back[p + 2]]).toEqual([200, 100, 100]);
  });

  it("the 'pure fill colour' check also works on one-channel pages", async () => {
    const bad = makeSource(20, 20, (x, y) => (x === 5 && y === 5 ? [3, 3, 3, 255] : [255, 255, 255, 255]));
    expect((await encodeRaster(bad, [{ x0: 2, y0: 2, x1: 10, y1: 10 }], { r: 255, g: 255, b: 255 })).rectMismatchPixels).toBe(1);
  });
});

