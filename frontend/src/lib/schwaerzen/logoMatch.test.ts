import { describe, expect, it } from "vitest";
import { findLogoHits, inZone, searchSizes, resizeArea, scaleList, scoreLogoAtRegion, trimMargins, type GrayImage } from "./logoMatch";

// A made-up, asymmetric "logo" (frame + disc + bars) defined as a function, so it can be rasterized at ANY size.
function dark(u: number, v: number): boolean {
  const frame = u < 0.07 || u > 0.93 || v < 0.1 || v > 0.9;
  const disc = (u - 0.28) ** 2 + ((v - 0.5) * 0.66) ** 2 < 0.04;
  const bar = (cx: number, top: number) => Math.abs(u - cx) < 0.035 && v > top && v < 0.82;
  return frame || disc || bar(0.58, 0.25) || bar(0.7, 0.4) || bar(0.82, 0.55);
}

function blank(w: number, h: number): GrayImage {
  return { width: w, height: h, data: new Float32Array(w * h).fill(255) };
}

/** Draws the logo into [x,y,w,h] (px) with 3×3 supersampling. */
function drawLogo(img: GrayImage, x: number, y: number, w: number, h: number, ink = 0, paper = -1) {
  for (let py = Math.floor(y); py < Math.ceil(y + h); py++) {
    for (let px = Math.floor(x); px < Math.ceil(x + w); px++) {
      if (px < 0 || py < 0 || px >= img.width || py >= img.height) continue;
      let cover = 0;
      for (let sy = 0; sy < 3; sy++) for (let sx = 0; sx < 3; sx++) {
        const u = (px + (sx + 0.5) / 3 - x) / w;
        const v = (py + (sy + 0.5) / 3 - y) / h;
        if (u >= 0 && u <= 1 && v >= 0 && v <= 1 && dark(u, v)) cover++;
      }
      const base = paper >= 0 ? paper : img.data[py * img.width + px]!;
      img.data[py * img.width + px] = base + (ink - base) * (cover / 9);
    }
  }
}

function distractors(img: GrayImage) {
  const rect = (x0: number, y0: number, x1: number, y1: number, v = 0) => {
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) img.data[y * img.width + x] = v;
  };
  for (let i = 0; i < 12; i++) rect(60, 200 + i * 40, 1400, 202 + i * 40); // long lines
  for (let i = 0; i < 40; i++) rect(900 + (i % 8) * 70, 700 + Math.floor(i / 8) * 40, 900 + (i % 8) * 70 + 30 + (i * 7) % 25, 712 + Math.floor(i / 8) * 40); // text-like blocks
  rect(1000, 80, 1008, 140); // a bar
}

const PAGE_W_PT = 842;
const PAGE_H_PT = 595;
const SS = 2; // page px per pt in these tests
const TEMPLATE_W = 240; // px at "300 DPI" → 57.6 pt
const TEMPLATE_H = 160;

function templateImage(): GrayImage {
  const t = blank(TEMPLATE_W, TEMPLATE_H);
  drawLogo(t, 0, 0, TEMPLATE_W, TEMPLATE_H);
  return t;
}

function pageWith(logos: { xPt: number; yPt: number; scale: number }[]): GrayImage {
  const p = blank(PAGE_W_PT * SS, PAGE_H_PT * SS);
  distractors(p);
  for (const l of logos) drawLogo(p, l.xPt * SS, l.yPt * SS, (TEMPLATE_W / (300 / 72)) * l.scale * SS, (TEMPLATE_H / (300 / 72)) * l.scale * SS);
  return p;
}

// 70 %: real matches score 83–99 %, the made-up block pattern of the distractors reaches ~60 % (look-alikes exist!)
const opts = { threshold: 0.7, pageWidthPt: PAGE_W_PT, pageHeightPt: PAGE_H_PT, templateWidth: TEMPLATE_W, templateHeight: TEMPLATE_H };

function centerPt(h: { x0: number; y0: number; x1: number; y1: number }) {
  return { x: ((h.x0 + h.x1) / 2) * PAGE_W_PT, y: ((h.y0 + h.y1) / 2) * PAGE_H_PT, w: (h.x1 - h.x0) * PAGE_W_PT };
}

describe("logo matching (synthetic, made-up logo)", () => {
  it("resizeArea keeps the mean and the size", () => {
    const img: GrayImage = { width: 8, height: 4, data: Float32Array.from({ length: 32 }, (_, i) => i * 8) };
    const small = resizeArea(img, 4, 2);
    expect(small.width).toBe(4);
    expect(small.height).toBe(2);
    const mean = (g: GrayImage) => g.data.reduce((a, b) => a + b, 0) / g.data.length;
    expect(mean(small)).toBeCloseTo(mean(img), 3);
  });

  it("covers 10 % … 300 % in steps", () => {
    const s = scaleList();
    expect(s[0]).toBeCloseTo(0.1);
    expect(s[s.length - 1]!).toBeGreaterThan(2.4);
    expect(s.length).toBeLessThan(40);
  });

  it.each([1.0, 0.6, 1.7])("finds the logo at scale %s, box within a few pt of the truth", (scale) => {
    const truth = { xPt: 300, yPt: 60, scale };
    const wPt = (TEMPLATE_W / (300 / 72)) * scale;
    const hPt = (TEMPLATE_H / (300 / 72)) * scale;
    const t0 = performance.now();
    const hits = findLogoHits(pageWith([truth]), templateImage(), opts);
    const ms = Math.round(performance.now() - t0);
    expect(hits.length, `ms=${ms}`).toBeGreaterThanOrEqual(1);
    const c = centerPt(hits[0]!);
    expect(Math.abs(c.x - (truth.xPt + wPt / 2))).toBeLessThan(4);
    expect(Math.abs(c.y - (truth.yPt + hPt / 2))).toBeLessThan(4);
    expect(Math.abs(c.w - wPt) / wPt).toBeLessThan(0.1);
    expect(hits[0]!.score).toBeGreaterThan(0.8);
    console.log(`scale ${scale}: ${ms} ms, score ${hits[0]!.score.toFixed(3)}`);
  }, 60_000);

  it("search resolution follows the paper size (A4/A3 unchanged, A1 gets more, capped)", () => {
    expect(searchSizes(842).fine).toBe(1536);
    expect(searchSizes(1191).fine).toBe(1536);
    expect(searchSizes(2384).fine).toBeGreaterThan(2400);
    expect(searchSizes(9000).fine).toBeLessThanOrEqual(2560);
    expect(searchSizes(2384).render).toBeGreaterThan(searchSizes(2384).fine);
  });

  it("finds the same logo (same size in mm) on an A1 sheet, rendered like the app renders it", () => {
    const wPt = 2384;
    const hPt = 1684;
    const px = searchSizes(wPt).render / wPt; // px per pt
    const page = blank(Math.round(wPt * px), Math.round(hPt * px));
    // text-like clutter at A1 scale
    for (let i = 0; i < 60; i++) {
      const y = Math.round((100 + i * 22) * px);
      const x0 = Math.round(900 * px);
      for (let yy = y; yy < y + Math.round(7 * px); yy++) for (let x = x0; x < x0 + Math.round((200 + (i * 37) % 300) * px); x++) page.data[yy * page.width + x] = 0;
    }
    const logoW = TEMPLATE_W / (300 / 72); // 57.6 pt: the same physical size as in the A3 tests
    const logoH = TEMPLATE_H / (300 / 72);
    const at = { x: 1700, y: 1450 };
    drawLogo(page, at.x * px, at.y * px, logoW * px, logoH * px);
    const hits = findLogoHits(page, templateImage(), { ...opts, pageWidthPt: wPt, pageHeightPt: hPt });
    expect(hits.length).toBeGreaterThanOrEqual(1);
    const h = hits[0]!;
    expect(Math.abs(((h.x0 + h.x1) / 2) * wPt - (at.x + logoW / 2))).toBeLessThan(6);
    expect(Math.abs(((h.y0 + h.y1) / 2) * hPt - (at.y + logoH / 2))).toBeLessThan(6);
    expect(h.score).toBeGreaterThan(0.8);
  }, 120_000);

  it("finds two logos on one page", () => {
    const hits = findLogoHits(pageWith([{ xPt: 60, yPt: 40, scale: 1 }, { xPt: 600, yPt: 420, scale: 0.8 }]), templateImage(), opts);
    expect(hits.length).toBeGreaterThanOrEqual(2);
    const cs = hits.slice(0, 2).map(centerPt).sort((a, b) => a.x - b.x);
    expect(cs[0]!.x).toBeLessThan(200);
    expect(cs[1]!.x).toBeGreaterThan(550);
  }, 60_000);

  it("finds nothing on a page with only lines and blocks", () => {
    expect(findLogoHits(pageWith([]), templateImage(), opts)).toEqual([]);
  }, 60_000);

  it("finds nothing with a flat (empty) template", () => {
    expect(findLogoHits(pageWith([{ xPt: 100, yPt: 100, scale: 1 }]), blank(TEMPLATE_W, TEMPLATE_H), opts)).toEqual([]);
  }, 60_000);

  const placed = (xPt: number, yPt: number, scale = 1) => ({ xPt, yPt, scale });
  const wOf = (scale: number) => (TEMPLATE_W / (300 / 72)) * scale;

  it("finds a logo printed INVERTED (light on dark) and says so", () => {
    const p = pageWith([]);
    drawLogo(p, 300 * SS, 60 * SS, wOf(1) * SS, ((TEMPLATE_H / (300 / 72)) * SS), 255, 40);
    const hits = findLogoHits(p, templateImage(), opts);
    expect(hits[0]!.variant).toBe("invert");
    expect(hits[0]!.score).toBeGreaterThan(0.8);
  }, 60_000);

  it("finds a logo that is only gray instead of black (different print density)", () => {
    const p = pageWith([]);
    drawLogo(p, 300 * SS, 60 * SS, wOf(1) * SS, (TEMPLATE_H / (300 / 72)) * SS, 120);
    expect(findLogoHits(p, templateImage(), opts)[0]!.score).toBeGreaterThan(0.8);
  }, 60_000);

  it("a template file with a wide white margin still matches and the box is the LOGO, not the padding", () => {
    const padded = blank(400, 300);
    drawLogo(padded, 80, 70, TEMPLATE_W, TEMPLATE_H); // logo in the middle of white padding
    const hits = findLogoHits(pageWith([placed(300, 60)]), padded, { ...opts, templateWidth: 400, templateHeight: 300 });
    expect(hits.length).toBeGreaterThanOrEqual(1);
    expect(Math.abs(centerPt(hits[0]!).w - wOf(1)) / wOf(1)).toBeLessThan(0.12);
    expect(Math.abs(centerPt(hits[0]!).x - (300 + wOf(1) / 2))).toBeLessThan(5);
  }, 60_000);

  it("trimMargins removes light padding but never a dark/coloured border of the logo", () => {
    const padded = blank(400, 300);
    drawLogo(padded, 80, 70, TEMPLATE_W, TEMPLATE_H);
    const t = trimMargins(padded);
    expect(t.img.width).toBeLessThan(260);
    expect(t.rw).toBeLessThan(0.7);
    const framed = templateImage(); // the logo's own black frame touches the edge: must stay untouched
    expect(trimMargins(framed).img.width).toBe(framed.width);
    const darkPaper = blank(200, 100);
    darkPaper.data.fill(30); // the whole background is dark ink: a filled logo background, not padding
    drawLogo(darkPaper, 20, 10, 160, 80, 255);
    expect(trimMargins(darkPaper).img.width).toBe(200);
  });

  it("search zone: a logo outside the zone is ignored, inside it is found", () => {
    const p = pageWith([placed(100, 450)]); // bottom-left
    expect(findLogoHits(p, templateImage(), { ...opts, zone: "top" })).toEqual([]);
    expect(findLogoHits(p, templateImage(), { ...opts, zone: "bottom" }).length).toBeGreaterThanOrEqual(1);
    expect(inZone("corners", 0.5, 0.5)).toBe(false);
    expect(inZone("corners", 0.1, 0.9)).toBe(true);
    expect(inZone("all", 0.5, 0.5)).toBe(true);
  }, 60_000);

  it("diagnosis: high score where the real logo is, low where it is not", () => {
    const p = pageWith([placed(300, 60)]);
    const common = { pageWidthPt: PAGE_W_PT, pageHeightPt: PAGE_H_PT, templateWidth: TEMPLATE_W, templateHeight: TEMPLATE_H };
    const w = wOf(1);
    const h = (TEMPLATE_H / (300 / 72));
    const at = (x: number, y: number) => ({ x0: x / PAGE_W_PT, y0: y / PAGE_H_PT, x1: (x + w) / PAGE_W_PT, y1: (y + h) / PAGE_H_PT });
    const best = (r: ReturnType<typeof scoreLogoAtRegion>) => Math.max(...r.map((x) => x.score));
    expect(best(scoreLogoAtRegion(p, templateImage(), at(300, 60), common))).toBeGreaterThan(0.8);
    expect(best(scoreLogoAtRegion(p, templateImage(), at(500, 350), common))).toBeLessThan(0.5);
    expect(scoreLogoAtRegion(p, templateImage(), at(300, 60), common).map((r) => r.variant).sort()).toEqual(["edge", "gray", "invert"]);
  }, 60_000);

  describe("text-heavy page with a wordmark logo (the real-world case)", () => {
    // wordmark = bold letter blocks of different widths on one line, like a customer name set in a heavy font
    const wordmark = (w: number, h: number): GrayImage => {
      const t = blank(w, h);
      let x = 0.04;
      for (const ww of [0.12, 0.09, 0.14, 0.1, 0.12, 0.11, 0.13]) {
        for (let py = Math.round(h * 0.2); py < Math.round(h * 0.8); py++) {
          for (let px = Math.round(w * x); px < Math.round(w * (x + ww)); px++) t.data[py * w + px] = 0;
        }
        x += ww + 0.025;
      }
      return t;
    };
    const textPage = (): GrayImage => {
      const p = blank(PAGE_W_PT * SS, PAGE_H_PT * SS);
      for (let r = 0; r < 14; r++) {
        let cx = 100 + (r % 3) * 20;
        for (let i = 0; i < 18 + (r % 5); i++) {
          const w = 8 + ((i * 7) % 15);
          for (let yy = 300 + r * 60; yy < 314 + r * 60; yy++) for (let xx = cx; xx < cx + w; xx++) p.data[yy * p.width + xx] = 20;
          cx += w + 6;
        }
      }
      return p;
    };
    const W300 = 300;
    const H300 = 90;
    const wordOpts = { ...opts, threshold: 0.45, templateWidth: W300, templateHeight: H300 };

    it.each([1.0, 0.93, 1.07, 0.8])("finds the wordmark at size %s between the page's own text lines and ranks it first", (scale) => {
      const p = textPage();
      const tw = Math.round((W300 / (300 / 72)) * scale * SS);
      const th = Math.round((H300 / (300 / 72)) * scale * SS);
      const logoTpl = wordmark(tw, th);
      for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) if (logoTpl.data[y * tw + x]! < 128) p.data[(160 + y) * p.width + 1000 + x] = 0;
      const hits = findLogoHits(p, wordmark(W300, H300), wordOpts);
      expect(hits.length).toBeGreaterThanOrEqual(1);
      const c = centerPt(hits[0]!);
      expect(Math.abs(c.x - (500 + tw / SS / 2))).toBeLessThan(6);
      expect(Math.abs(c.y - (80 + th / SS / 2))).toBeLessThan(6);
      expect(hits[0]!.score).toBeGreaterThan(0.8);
      // every other hit is a look-alike and ranks below the real one
      for (const h of hits.slice(1)) expect(h.score).toBeLessThan(hits[0]!.score);
    }, 60_000);

    it("a thin one-line look-alike in white space (far less ink than the logo) is not accepted, a faint real one is", () => {
      const tw = Math.round((W300 / (300 / 72)) * SS);
      const th = Math.round((H300 / (300 / 72)) * SS);
      const mark = wordmark(tw, th);
      const thin = blank(PAGE_W_PT * SS, PAGE_H_PT * SS);
      // same block pattern, but only a hair-thin bar (≈ 10 % of the logo's ink)
      for (let y = Math.round(th * 0.47); y < Math.round(th * 0.53); y++) {
        for (let x = 0; x < tw; x++) if (mark.data[Math.round(th * 0.5) * tw + x]! < 128) thin.data[(160 + y) * thin.width + 1000 + x] = 0;
      }
      expect(findLogoHits(thin, wordmark(W300, H300), { ...wordOpts, threshold: 0.3 })).toEqual([]);
      // the real thing at ~55 % ink (gray print) is still accepted
      const faint = blank(PAGE_W_PT * SS, PAGE_H_PT * SS);
      for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) if (mark.data[y * tw + x]! < 128) faint.data[(160 + y) * faint.width + 1000 + x] = 110;
      expect(findLogoHits(faint, wordmark(W300, H300), { ...wordOpts, threshold: 0.45 }).length).toBeGreaterThanOrEqual(1);
    }, 60_000);

    it("with the default limit the look-alike text lines do not become 'logos' when the real logo is absent", () => {
      const hits = findLogoHits(textPage(), wordmark(W300, H300), { ...wordOpts, threshold: 0.5 });
      expect(hits).toEqual([]);
    }, 60_000);
  });
});
