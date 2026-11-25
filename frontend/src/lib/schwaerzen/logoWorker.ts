/// <reference lib="webworker" />
import { findLogoHits, scoreLogoAtRegion, type GrayImage, type LogoHit, type LogoZone, type RegionScore } from "./logoMatch";

/** Web Worker: runs the (CPU-heavy) logo search off the UI thread. No network, no DOM. */

export interface WorkerTemplate {
  id: string;
  width: number;
  height: number;
  /** Gray pixels of the (possibly down-scaled) template, 0..255. */
  data: Uint8Array;
  /** Original size (px at 300 DPI) the scale range refers to. */
  origWidth: number;
  origHeight: number;
  threshold: number;
  maxHits: number;
  zone: LogoZone;
}

export interface WorkerRequest {
  requestId: number;
  mode: "detect" | "diagnose";
  page: { width: number; height: number; data: Uint8Array };
  pageWidthPt: number;
  pageHeightPt: number;
  templates: WorkerTemplate[];
  /** diagnose only: the area (page fractions) the user marked as "this is the real logo". */
  region?: { x0: number; y0: number; x1: number; y1: number };
}

export interface DiagnoseResult {
  templateId: string;
  /** Best score of each comparison inside the marked area. */
  atRegion: RegionScore[];
  /** Strongest matches elsewhere on the page (low threshold), to compare with. */
  elsewhere: LogoHit[];
}

export interface WorkerResponse {
  requestId: number;
  hits: (LogoHit & { templateId: string })[];
  diagnose?: DiagnoseResult[];
  error?: string;
}

const toGray = (w: number, h: number, data: Uint8Array): GrayImage => ({ width: w, height: h, data: Float32Array.from(data) });

const overlaps = (a: LogoHit, r: { x0: number; y0: number; x1: number; y1: number }) =>
  Math.min(a.x1, r.x1) - Math.max(a.x0, r.x0) > 0 && Math.min(a.y1, r.y1) - Math.max(a.y0, r.y0) > 0;

self.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const req = event.data;
  try {
    const page = toGray(req.page.width, req.page.height, req.page.data);
    const hits: WorkerResponse["hits"] = [];
    const diagnose: DiagnoseResult[] = [];
    for (const t of req.templates) {
      const template = toGray(t.width, t.height, t.data);
      const common = {
        pageWidthPt: req.pageWidthPt,
        pageHeightPt: req.pageHeightPt,
        templateWidth: t.origWidth,
        templateHeight: t.origHeight,
      };
      if (req.mode === "diagnose" && req.region) {
        const region = req.region;
        const elsewhere = findLogoHits(page, template, { ...common, threshold: 0.3, maxHits: 6 })
          .filter((h) => !overlaps(h, region))
          .slice(0, 3);
        diagnose.push({ templateId: t.id, atRegion: scoreLogoAtRegion(page, template, region, common), elsewhere });
        continue;
      }
      for (const h of findLogoHits(page, template, { ...common, threshold: t.threshold, maxHits: t.maxHits, zone: t.zone })) {
        hits.push({ ...h, templateId: t.id });
      }
    }
    self.postMessage({ requestId: req.requestId, hits, diagnose: req.mode === "diagnose" ? diagnose : undefined } satisfies WorkerResponse);
  } catch {
    self.postMessage({ requestId: req.requestId, hits: [], error: "Logo-Suche fehlgeschlagen." } satisfies WorkerResponse);
  }
};
