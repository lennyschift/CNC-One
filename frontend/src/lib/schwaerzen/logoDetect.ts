import type { PDFDocumentProxy } from "pdfjs-dist";
import { browserRenderer } from "./browserRenderer";
import { searchSizes, type LogoHit } from "./logoMatch";
import { DEFAULT_LOGO_MAX_HITS, type LogoOptions, type LogoTemplate } from "./rules";
import type { AutoRect } from "./textDetect";
import type { DiagnoseResult, WorkerRequest, WorkerResponse, WorkerTemplate } from "./logoWorker";

/**
 * Extra margin around a found logo box: the size is searched in steps, so the box can be a few % smaller than the logo.
 * At least 6 pt, and 10 % of the logo's size for big logos. (White margin costs nothing: areas are pulled tight again
 * around what is really there when saving — but anything of the logo that lies in the margin is covered.)
 */
const LOGO_MARGIN_MIN_PT = 6;
const LOGO_MARGIN_FRACTION = 0.1;

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Logo-Bild nicht lesbar"));
    img.src = dataUrl;
  });
}

export function toGrayBytes(rgba: Uint8ClampedArray | Uint8Array, n: number): Uint8Array {
  const out = new Uint8Array(n);
  for (let i = 0, p = 0; i < n; i++, p += 4) {
    const a = rgba[p + 3]! / 255; // transparent = white
    const r = rgba[p]! * a + 255 * (1 - a);
    const g = rgba[p + 1]! * a + 255 * (1 - a);
    const b = rgba[p + 2]! * a + 255 * (1 - a);
    out[i] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  return out;
}

async function prepareTemplate(logo: LogoTemplate, defaults: { threshold: number }, options: Record<string, LogoOptions>): Promise<WorkerTemplate> {
  const img = await loadImage(logo.dataUrl);
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas nicht verfügbar");
  ctx.drawImage(img, 0, 0);
  const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const o = options[logo.id] ?? {};
  return {
    id: logo.id,
    width: canvas.width,
    height: canvas.height,
    data: toGrayBytes(data, canvas.width * canvas.height),
    origWidth: logo.width,
    origHeight: logo.height,
    threshold: o.threshold ?? defaults.threshold,
    maxHits: o.maxHits ?? DEFAULT_LOGO_MAX_HITS,
    zone: o.zone ?? "all",
  };
}

interface PageGray {
  width: number;
  height: number;
  data: Uint8Array;
  wPt: number;
  hPt: number;
}

/** Renders one page (resolution follows the paper size, see searchSizes) and converts it to gray. (Never page.cleanup(): the page view renders with the same page object.) */
async function renderGray(doc: PDFDocumentProxy, pageNumber: number): Promise<PageGray> {
  const page = await doc.getPage(pageNumber);
  const vp1 = page.getViewport({ scale: 1 });
  const rendered = await browserRenderer.render(page, searchSizes(Math.max(vp1.width, vp1.height)).render / Math.max(vp1.width, vp1.height));
  try {
    const { width, height } = rendered;
    const data = new Uint8Array(width * height);
    const BAND = 256;
    for (let y0 = 0; y0 < height; y0 += BAND) {
      const y1 = Math.min(height, y0 + BAND);
      data.set(toGrayBytes(rendered.readRows(y0, y1), (y1 - y0) * width), y0 * width);
    }
    return { width, height, data, wPt: vp1.width, hPt: vp1.height };
  } finally {
    rendered.dispose();
  }
}

/** A worker with a request/response helper; terminated when `signal` aborts. */
function startWorker(signal?: AbortSignal) {
  const worker = new Worker(new URL("./logoWorker.ts", import.meta.url), { type: "module" });
  let requestId = 0;
  const ask = (req: Omit<WorkerRequest, "requestId">, transfer: Transferable[]) =>
    new Promise<WorkerResponse>((resolve, reject) => {
      const id = ++requestId;
      const onMessage = (e: MessageEvent<WorkerResponse>) => {
        if (e.data.requestId !== id) return;
        worker.removeEventListener("message", onMessage);
        resolve(e.data);
      };
      worker.addEventListener("message", onMessage);
      worker.addEventListener("error", () => reject(new Error("Worker-Fehler")), { once: true });
      worker.postMessage({ ...req, requestId: id } satisfies WorkerRequest, transfer);
    });
  const onAbort = () => worker.terminate();
  signal?.addEventListener("abort", onAbort);
  return {
    ask,
    stop: () => {
      signal?.removeEventListener("abort", onAbort);
      worker.terminate();
    },
  };
}

async function prepareAll(
  logos: readonly LogoTemplate[],
  defaults: { threshold: number },
  options: Record<string, LogoOptions>,
  problems: string[],
): Promise<WorkerTemplate[]> {
  const templates: WorkerTemplate[] = [];
  for (const logo of logos) {
    try {
      templates.push(await prepareTemplate(logo, defaults, options));
    } catch {
      problems.push(`Logo „${logo.name}“ konnte nicht gelesen werden.`);
    }
  }
  return templates;
}

export interface LogoDetectionResult {
  rects: AutoRect[];
  /** Logos that could not be used (unreadable image, worker failure). */
  problems: string[];
}

/**
 * Searches every page for the enabled logos in a Web Worker. Pages are
 * rendered one by one (pdf.js), converted to gray and handed over; all
 * processing stays in this browser. Threshold, search zone and maximum number
 * of matches can be set per logo.
 */
export async function detectLogosOnDocument(
  doc: PDFDocumentProxy,
  logos: readonly LogoTemplate[],
  defaults: { threshold: number },
  options: Record<string, LogoOptions>,
  opts: { signal?: AbortSignal; onPage?: (page: number) => void } = {},
): Promise<LogoDetectionResult> {
  const active = logos.filter((l) => l.enabled);
  const result: LogoDetectionResult = { rects: [], problems: [] };
  if (active.length === 0) return result;

  const templates = await prepareAll(active, defaults, options, result.problems);
  if (templates.length === 0) return result;
  const names = new Map(active.map((l) => [l.id, l.name]));

  const worker = startWorker(opts.signal);
  try {
    for (let p = 1; p <= doc.numPages; p++) {
      if (opts.signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
      opts.onPage?.(p);
      const g = await renderGray(doc, p);

      let response: WorkerResponse;
      try {
        response = await worker.ask(
          { mode: "detect", page: { width: g.width, height: g.height, data: g.data }, pageWidthPt: g.wPt, pageHeightPt: g.hPt, templates },
          [g.data.buffer as ArrayBuffer],
        );
      } catch {
        if (opts.signal?.aborted) throw new DOMException("Abgebrochen", "AbortError");
        result.problems.push("Die Logo-Suche konnte nicht ausgeführt werden.");
        break;
      }
      if (response.error) {
        result.problems.push(response.error);
        break;
      }
      for (const h of response.hits) {
        const mx = Math.max(LOGO_MARGIN_MIN_PT, LOGO_MARGIN_FRACTION * (h.x1 - h.x0) * g.wPt) / g.wPt;
        const my = Math.max(LOGO_MARGIN_MIN_PT, LOGO_MARGIN_FRACTION * (h.y1 - h.y0) * g.hPt) / g.hPt;
        const how = h.variant === "gray" ? "" : h.variant === "invert" ? ", invertiert" : ", Kanten";
        result.rects.push({
          page: p,
          x0: Math.max(0, h.x0 - mx),
          y0: Math.max(0, h.y0 - my),
          x1: Math.min(1, h.x1 + mx),
          y1: Math.min(1, h.y1 + my),
          reason: `Logo „${names.get(h.templateId) ?? "?"}“ ${Math.round(h.score * 100)} %${how}`,
          kind: "logo",
        });
      }
    }
  } finally {
    worker.stop();
  }
  return result;
}

export interface LogoDiagnosis {
  logoName: string;
  /** Per comparison: the best score inside the area the user marked (and the size that gave it). */
  atRegion: DiagnoseResult["atRegion"];
  /** Strongest matches elsewhere on the page, for comparison. */
  elsewhere: LogoHit[];
}

/**
 * "Why is my logo not found?": the user marks the REAL logo on a page; for every logo the best score at that spot
 * and the strongest competing matches elsewhere are returned (numbers only).
 */
export async function diagnoseLogosOnPage(
  doc: PDFDocumentProxy,
  pageNumber: number,
  logos: readonly LogoTemplate[],
  region: { x0: number; y0: number; x1: number; y1: number },
  defaults: { threshold: number },
  options: Record<string, LogoOptions>,
  signal?: AbortSignal,
): Promise<{ diagnoses: LogoDiagnosis[]; problems: string[] }> {
  const problems: string[] = [];
  const templates = await prepareAll(logos, defaults, options, problems);
  if (templates.length === 0) return { diagnoses: [], problems };
  const names = new Map(logos.map((l) => [l.id, l.name]));

  const worker = startWorker(signal);
  try {
    const g = await renderGray(doc, pageNumber);
    const res = await worker.ask(
      { mode: "diagnose", page: { width: g.width, height: g.height, data: g.data }, pageWidthPt: g.wPt, pageHeightPt: g.hPt, templates, region },
      [g.data.buffer as ArrayBuffer],
    );
    if (res.error || !res.diagnose) {
      problems.push(res.error ?? "Die Diagnose ist fehlgeschlagen.");
      return { diagnoses: [], problems };
    }
    return {
      diagnoses: res.diagnose.map((d) => ({ logoName: names.get(d.templateId) ?? "?", atRegion: d.atRegion, elsewhere: d.elsewhere })),
      problems,
    };
  } finally {
    worker.stop();
  }
}
