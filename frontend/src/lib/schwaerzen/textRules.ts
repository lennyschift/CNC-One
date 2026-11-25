import type { Rect } from "./coordinates";
import { looksLikePhone } from "./sensitive";
import type { RuleSet } from "./rules";
import type { PageTextItem } from "./textItems";
import type { RuleKind } from "./types";

/*
 * Text-based detection: port of the rules of auto_redact_v11_robust.py as
 * DATA-driven functions over pdf.js text items (page space, pt, origin
 * top-left). Everything it returns is only a PROPOSAL (rectangle + reason);
 * the user accepts, moves or deletes it.
 *
 * Differences to the Python tool (deliberate):
 *  - all rules always run (Python skipped direct keywords/e-mail on pages without a header),
 *  - keywords may span several text items of one line ("AFR" + "GmbH"),
 *  - character positions inside an item use per-character width estimates, not equal widths,
 *    plus a margin; whole-item matches are exact,
 *  - no "whole cell" fallbacks (they painted large areas): if nothing stands below a header, nothing is proposed.
 */

/** Where a keyword sits INSIDE one longer text item — estimated; see snapRange.ts for how it is made exact. */
export interface SnapInfo {
  /** Bounds of the whole item (pt) and the vertical band (pt) in which the letters' ink is looked at. */
  itemX0: number;
  itemX1: number;
  bandTop: number;
  bandBottom: number;
  /** Estimated start/end of the keyword (pt) — only an estimate. */
  ks: number;
  ke: number;
  /** The characters of the whole item and the keyword's range [from, to) in it (to count letter groups exactly). */
  chars: string;
  from: number;
  to: number;
}

export interface Detection {
  /** Page space, pt. */
  rect: Rect;
  reason: string;
  kind: RuleKind;
  /** Only for a keyword in the middle of a longer item: lets the detection pull the rectangle onto the real letters. */
  snap?: SnapInfo;
}

/** Ascender/descender extent of a text box, like PyMuPDF's span bbox (≈ 1.12 × font size). */
const ASCENT = 0.9;
const DESCENT = 0.22;
const PAD_X = 2;
const PAD_Y = 1;

interface Geo {
  horizontal: boolean;
  /** Ink-like box (tight for horizontal text, the generous bbox otherwise). */
  tight: Rect;
  baseline: number;
  fs: number;
}

export function itemGeometry(item: PageTextItem): Geo {
  const [a, b, , d, e, f] = item.matrix;
  const fs = item.fontSize;
  const horizontal = a > 0 && Math.abs(b) < 0.1 * Math.abs(a) && d !== 0;
  if (!horizontal) return { horizontal: false, tight: item.bbox, baseline: f, fs };
  const up = d < 0 ? -1 : 1; // page space is y-down: normal text has d < 0
  const top = up < 0 ? f - ASCENT * fs : f - DESCENT * fs;
  const bottom = up < 0 ? f + DESCENT * fs : f + ASCENT * fs;
  return { horizontal: true, tight: { x0: e, y0: top, x1: e + item.widthPt, y1: bottom }, baseline: f, fs };
}

const NARROW = new Set("ijl.,:;'|!`´".split(""));
const SLIM = new Set("frtI()[]{}-–/\\ ".split(""));
const WIDE = new Set("mwMW@%".split(""));

/** Rough advance widths (em) for proportional estimation of positions INSIDE one text item. */
function charWidth(ch: string): number {
  if (NARROW.has(ch)) return 0.26;
  if (ch === " ") return 0.28;
  if (SLIM.has(ch)) return 0.34;
  if (WIDE.has(ch)) return ch === "m" ? 0.83 : ch === "w" ? 0.74 : 0.92;
  if (ch >= "0" && ch <= "9") return 0.56;
  if (ch >= "A" && ch <= "Z") return 0.68;
  return 0.54;
}

/** cum[i] = fraction of the item width before character i (cum[n] = 1). */
function cumulativeFractions(str: string): number[] {
  const chars = [...str];
  const cum = [0];
  let total = 0;
  for (const ch of chars) {
    total += charWidth(ch);
    cum.push(total);
  }
  return cum.map((v) => (total > 0 ? v / total : 0));
}

interface LineItem {
  item: PageTextItem;
  geo: Geo;
  /** [start, end) of this item's characters in the line text. */
  start: number;
  end: number;
  chars: string[];
}

interface Line {
  items: LineItem[];
  /** Lower-case text, whitespace collapsed to single spaces, same length as the sum of item chars + separators. */
  text: string;
}

/** Length-preserving lower-casing per code point. */
function lowerChar(ch: string): string {
  if (/\s/u.test(ch)) return " ";
  const l = ch.toLowerCase();
  return [...l].length === 1 ? l : ch;
}

/** Groups horizontal items sharing a baseline into lines (sorted left → right). */
export function assembleLines(items: readonly PageTextItem[]): Line[] {
  const geos = items.map((item) => ({ item, geo: itemGeometry(item) })).filter((g) => g.geo.horizontal);
  geos.sort((p, q) => p.geo.baseline - q.geo.baseline);
  const groups: typeof geos[] = [];
  for (const g of geos) {
    const last = groups[groups.length - 1];
    const ref = last?.[last.length - 1];
    if (last && ref && Math.abs(g.geo.baseline - ref.geo.baseline) <= 0.35 * Math.max(g.geo.fs, ref.geo.fs)) last.push(g);
    else groups.push([g]);
  }
  return groups.map((group) => {
    group.sort((p, q) => p.geo.tight.x0 - q.geo.tight.x0);
    const lineItems: LineItem[] = [];
    let text = "";
    let prev: Geo | null = null;
    for (const { item, geo } of group) {
      if (prev && geo.tight.x0 - prev.tight.x1 > 0.1 * Math.min(geo.fs, prev.fs)) text += " ";
      const chars = [...item.str].map(lowerChar);
      const start = text.length;
      text += chars.join("");
      lineItems.push({ item, geo, start, end: text.length, chars });
      prev = geo;
    }
    return { items: lineItems, text };
  });
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function normalizeKeyword(kw: string): string {
  return [...kw.trim()].map(lowerChar).join("").replace(/ +/g, " ");
}

/** Whole-word matcher: letters/digits on either side break the match (like \b, also for umlauts). */
function wordRegex(kw: string, optionalTrailingDot: boolean): RegExp {
  let body = escapeRe(kw);
  if (optionalTrailingDot && kw.endsWith(".")) body = escapeRe(kw.slice(0, -1)) + "\\.?";
  return new RegExp(`(?<![\\p{L}\\p{N}])${body}(?![\\p{L}\\p{N}])`, "gu");
}

const union = (rs: readonly Rect[]): Rect => ({
  x0: Math.min(...rs.map((r) => r.x0)),
  y0: Math.min(...rs.map((r) => r.y0)),
  x1: Math.max(...rs.map((r) => r.x1)),
  y1: Math.max(...rs.map((r) => r.y1)),
});

const pad = (r: Rect, px = PAD_X, py = PAD_Y): Rect => ({ x0: r.x0 - px, y0: r.y0 - py, x1: r.x1 + px, y1: r.y1 + py });

/** Box of the characters [s, e) of a line: exact for whole items, proportional + margin for partial ones. */
function rangeRect(line: Line, s: number, e: number): { rect: Rect; snap?: SnapInfo } {
  const parts: Rect[] = [];
  let snap: SnapInfo | undefined;
  for (const li of line.items) {
    const a = Math.max(s, li.start);
    const b = Math.min(e, li.end);
    if (b <= a) continue;
    const t = li.geo.tight;
    if (a === li.start && b === li.end) {
      parts.push(pad(t));
      continue;
    }
    const cum = cumulativeFractions(li.chars.join(""));
    const w = t.x1 - t.x0;
    // Positions inside the item are ESTIMATED (no per-glyph metrics): the margin grows with the item width.
    const margin = Math.max(PAD_X, 0.3 * li.geo.fs, 0.07 * w);
    const ks = t.x0 + cum[a - li.start]! * w;
    const ke = t.x0 + cum[b - li.start]! * w;
    parts.push({ x0: ks - margin, x1: ke + margin, y0: t.y0 - PAD_Y, y1: t.y1 + PAD_Y });
    snap = {
      itemX0: t.x0,
      itemX1: t.x1,
      bandTop: li.geo.baseline - 0.65 * li.geo.fs,
      bandBottom: li.geo.baseline - 0.05 * li.geo.fs,
      ks,
      ke,
      chars: li.chars.join(""),
      from: a - li.start,
      to: b - li.start,
    };
  }
  // only a match inside ONE item can be snapped (a match over several items already ends at item boundaries)
  return { rect: union(parts), snap: parts.length === 1 ? snap : undefined };
}

/** Whole boxes of all items touched by [s, e) — like the Python "span" header boxes. */
function touchedItemsBox(line: Line, s: number, e: number): Rect {
  return union(line.items.filter((li) => li.end > s && li.start < e).map((li) => li.geo.tight));
}

interface Header {
  keyword: string;
  box: Rect;
}

function findHeaders(lines: readonly Line[], keywords: readonly string[]): Header[] {
  const out: Header[] = [];
  const seen = new Set<string>();
  for (const kw of keywords) {
    const norm = normalizeKeyword(kw);
    if (!norm) continue;
    const re = wordRegex(norm, true);
    // variant without . / - (like find_keyword_variations)
    const clean = norm.replace(/[./-]/g, "");
    const re2 = clean && clean !== norm ? wordRegex(clean, false) : null;
    for (const line of lines) {
      for (const rx of re2 ? [re, re2] : [re]) {
        rx.lastIndex = 0;
        for (const m of line.text.matchAll(rx)) {
          const box = touchedItemsBox(line, m.index!, m.index! + m[0].length);
          const key = `${kw}|${Math.round(box.x0)}|${Math.round(box.y0)}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({ keyword: kw, box });
        }
      }
    }
  }
  return out;
}

/** find_text_under_keyword_precise: the text block(s) directly under a header. */
function textUnderHeader(items: readonly PageTextItem[], h: Rect): Rect | null {
  const hh = h.y1 - h.y0;
  const hw = h.x1 - h.x0;
  const hcx = (h.x0 + h.x1) / 2;
  const found: { box: Rect; dist: number }[] = [];
  let minDist = Infinity;
  for (const item of items) {
    const g = itemGeometry(item);
    if (!g.horizontal) continue;
    const b = g.tight;
    if (b.y0 < h.y1 + 2) continue;
    if (b.y0 > h.y1 + hh * 2) continue;
    const overlap = Math.min(h.x1, b.x1) - Math.max(h.x0, b.x0);
    const denom = Math.max(hw, b.x1 - b.x0);
    const ratio = denom > 0 ? overlap / denom : 0;
    const aligned = Math.abs((b.x0 + b.x1) / 2 - hcx) < hw * 0.8;
    // Added to the Python rules: a (long) value that STARTS under the label — typical for a narrow label such as
    // "Name" over a left-aligned "Erika Beispiel", where the 40 % overlap rule fails.
    const startsUnderLabel = b.x0 <= h.x1 && b.x1 >= h.x0 && b.x0 >= h.x0 - Math.max(6, 0.5 * hw);
    if (ratio >= 0.4 || aligned || startsUnderLabel) {
      const dist = b.y0 - h.y1;
      found.push({ box: b, dist });
      minDist = Math.min(minDist, dist);
    }
  }
  const near = found.filter((f) => f.dist <= minDist + hh);
  return near.length > 0 ? pad(union(near.map((f) => f.box))) : null;
}

/** find_all_text_in_column_under_header: all rows of a revision-table column. */
function columnRows(boxes: readonly Rect[], h: Rect, pageW: number, pageH: number): Rect[] {
  const hw = h.x1 - h.x0;
  const colHalf = Math.min(hw / 2 + 10, 35);
  const cx = (h.x0 + h.x1) / 2;
  const colLeft = Math.max(0, cx - colHalf);
  const colRight = Math.min(pageW, cx + colHalf);
  const maxBottom = Math.min(h.y1 + 0.65 * pageH, h.y1 + 180);

  const spans = boxes
    .filter((b) => b.y0 >= h.y1 + 3 && b.y0 <= maxBottom && (b.x0 + b.x1) / 2 >= colLeft && (b.x0 + b.x1) / 2 <= colRight)
    .sort((p, q) => p.y0 - q.y0);
  if (spans.length === 0) return [];

  const heights = spans.map((s) => s.y1 - s.y0).sort((p, q) => p - q);
  const mid = Math.floor(heights.length / 2);
  let typical = mid > 0 ? (heights[mid]! + heights[mid - 1]!) / 2 : heights[0]!;
  typical = Math.max(5, Math.min(typical, 80));

  let cut = spans.length;
  for (let i = 1; i < spans.length; i++) {
    if (Math.max(0, spans[i]!.y0 - spans[i - 1]!.y1) > 2.5 * typical) {
      cut = i;
      break;
    }
  }
  const kept = spans.slice(0, cut);
  const rowH = Math.max(typical, (h.y1 - h.y0) * 0.8);
  const merged: Rect[] = [];
  let current: Rect[] = [kept[0]!];
  for (const s of kept.slice(1)) {
    if (s.y0 <= current[current.length - 1]!.y1 + rowH * 1.2) current.push(s);
    else {
      merged.push(union(current));
      current = [s];
    }
  }
  merged.push(union(current));

  // only real table rows: something stands left or right of the column on the same row
  const all = boxes;
  const rows = merged.filter((r) => {
    const cy = (r.y0 + r.y1) / 2;
    const rh = Math.max(r.y1 - r.y0, typical);
    const lo = cy - rh * 0.8;
    const hi = cy + rh * 0.8;
    return all.some((s) => (s.x1 <= colLeft || s.x0 >= colRight) && s.y0 < hi && s.y1 > lo);
  });
  return (rows.length > 0 ? rows : merged).map((r) => pad(r));
}

/** Drops rectangles lying completely inside another one (e.g. "AFR" inside "AFR GmbH"). */
function dropContained(list: Detection[]): Detection[] {
  const area = (r: Rect) => (r.x1 - r.x0) * (r.y1 - r.y0);
  const inside = (a: Rect, b: Rect) => a.x0 >= b.x0 - 0.5 && a.y0 >= b.y0 - 0.5 && a.x1 <= b.x1 + 0.5 && a.y1 <= b.y1 + 0.5;
  return list.filter((d, i) =>
    !list.some((o, j) => {
      if (i === j || !inside(d.rect, o.rect)) return false;
      const ad = area(d.rect);
      const ao = area(o.rect);
      return ao > ad + 0.01 || (Math.abs(ao - ad) <= 0.01 && j < i);
    }),
  );
}

/** Tight boxes of all horizontal items. */
const horizontalBoxes = (items: readonly PageTextItem[]): Rect[] => items.map(itemGeometry).filter((g) => g.horizontal).map((g) => g.tight);

/** Mirrors a rectangle top ↔ bottom (so "column ABOVE a header" can reuse the "column BELOW a header" routine). */
const flipY = (r: Rect, pageH: number): Rect => ({ x0: r.x0, x1: r.x1, y0: pageH - r.y1, y1: pageH - r.y0 });

/** Label words → the field(s) to the RIGHT on the same line ("Gez. 17.10.2011 MUELLER"): at most this many following fields. */
const MAX_RIGHT_FIELDS = 3;
/** A gap wider than this many font sizes ends the row of fields (next table cell group). */
const RIGHT_GAP_FS = 5;

function valuesRightOfLabels(lines: readonly Line[], keywords: readonly string[]): Detection[] {
  const out: Detection[] = [];
  const seen = new Set<string>();
  for (const kw of keywords) {
    const norm = normalizeKeyword(kw);
    if (!norm) continue;
    const re = wordRegex(norm, true);
    for (const line of lines) {
      re.lastIndex = 0;
      for (const m of line.text.matchAll(re)) {
        const mStart = m.index!;
        const mEnd = mStart + m[0].length;
        const touched = line.items.filter((li) => li.end > mStart && li.start < mEnd);
        const last = touched[touched.length - 1];
        if (!last) continue;
        const add = (rect: Rect, snap?: SnapInfo) => {
          const key = `${Math.round(rect.x0)}|${Math.round(rect.y0)}`;
          if (seen.has(key)) return;
          seen.add(key);
          out.push({ rect, reason: `Wert neben ‚${kw}‘`, kind: "labelRight", snap });
        };
        // rest of the label's own item ("Gez. 17.10.2011" as ONE text item)
        let restStart = mEnd;
        while (restStart < last.end && line.text[restStart] === " ") restStart++;
        let prev = last.geo.tight;
        let count = 0;
        if (restStart < last.end) {
          const r = rangeRect(line, restStart, last.end);
          add(r.rect, r.snap);
          count++;
        }
        for (const li of line.items.filter((x) => x.geo.tight.x0 >= last.geo.tight.x1 - 0.5 && x !== last)) {
          if (count >= MAX_RIGHT_FIELDS) break;
          const t = li.geo.tight;
          if (t.x0 - prev.x1 > RIGHT_GAP_FS * Math.max(li.geo.fs, last.geo.fs)) break;
          if (!/\S/u.test(li.item.str)) continue;
          add(pad(t));
          prev = t;
          count++;
        }
      }
    }
  }
  return out;
}

export interface TextRuleInput {
  items: readonly PageTextItem[];
  pageWidthPt: number;
  pageHeightPt: number;
  rules: Pick<RuleSet, "directKeywords" | "headerKeywords" | "changeTableKeywords" | "detectEmail" | "detectPhone"> &
    Partial<Pick<RuleSet, "labelRightKeywords" | "columnAboveKeywords">>;
}

const TABLE_ZONE_TOP_FRAC = 0.35;

export function detectTextRules(input: TextRuleInput): Detection[] {
  const { items, pageWidthPt: W, pageHeightPt: H, rules } = input;
  const lines = assembleLines(items);
  const out: Detection[] = [];

  // 1) header words → text below / revision-table column
  const changeSet = new Set(rules.changeTableKeywords.map((k) => k.toLowerCase().trim()));
  const headers = findHeaders(lines, rules.headerKeywords);
  const topmost = new Map<string, Rect>();
  for (const h of headers) {
    const key = h.keyword.toLowerCase().trim();
    if (!changeSet.has(key) || h.box.y1 > TABLE_ZONE_TOP_FRAC * H) continue;
    const cur = topmost.get(key);
    if (!cur || h.box.y0 < cur.y0) topmost.set(key, h.box);
  }
  for (const h of headers) {
    const key = h.keyword.toLowerCase().trim();
    if (changeSet.has(key)) {
      const top = topmost.get(key);
      if (!top || Math.abs(h.box.x0 - top.x0) > 2 || Math.abs(h.box.y0 - top.y0) > 2) continue; // only the first one in the upper 35 %
      for (const r of columnRows(horizontalBoxes(items), h.box, W, H)) {
        out.push({ rect: r, reason: `Änderungstabelle ‚${h.keyword}‘`, kind: "changeTable" });
      }
      continue;
    }
    const under = textUnderHeader(items, h.box);
    if (under) out.push({ rect: under, reason: `Unter Kopfzeile ‚${h.keyword}‘`, kind: "header" });
  }

  // 1b) revision tables that grow UPWARD (header at the bottom, rows above it): the column ABOVE the header, lowest 35 % of the page
  const aboveKeywords = rules.columnAboveKeywords ?? [];
  if (aboveKeywords.length > 0) {
    const boxes = horizontalBoxes(items);
    const flipped = boxes.map((b) => flipY(b, H));
    const aboveHeaders = findHeaders(lines, aboveKeywords).filter((h) => flipY(h.box, H).y1 <= TABLE_ZONE_TOP_FRAC * H);
    const lowest = new Map<string, Rect>(); // the lowest header of each word = first one seen from the bottom edge
    for (const h of aboveHeaders) {
      const key = h.keyword.toLowerCase().trim();
      const cur = lowest.get(key);
      if (!cur || h.box.y1 > cur.y1) lowest.set(key, h.box);
    }
    for (const h of aboveHeaders) {
      const top = lowest.get(h.keyword.toLowerCase().trim());
      if (!top || Math.abs(h.box.x0 - top.x0) > 2 || Math.abs(h.box.y0 - top.y0) > 2) continue;
      for (const r of columnRows(flipped, flipY(h.box, H), W, H)) {
        out.push({ rect: flipY(r, H), reason: `Spalte über ‚${h.keyword}‘ (Änderungstabelle)`, kind: "changeTable" });
      }
    }
  }

  // 1c) label → field(s) to the right on the same line
  if ((rules.labelRightKeywords ?? []).length > 0) out.push(...valuesRightOfLabels(lines, rules.labelRightKeywords ?? []));

  // 2) direct keywords (blacked out themselves)
  for (const kw of rules.directKeywords) {
    const norm = normalizeKeyword(kw);
    if (!norm) continue;
    const re = wordRegex(norm, false);
    for (const line of lines) {
      re.lastIndex = 0;
      for (const m of line.text.matchAll(re)) {
        const r = rangeRect(line, m.index!, m.index! + m[0].length);
        out.push({ rect: r.rect, reason: `Stichwort ‚${kw}‘`, kind: "keyword", snap: r.snap });
      }
    }
  }

  // 3) e-mail: every item with "@" (whole item, like the Python tool) + addresses split over items
  if (rules.detectEmail) {
    for (const item of items) {
      if (!item.str.includes("@")) continue;
      const g = itemGeometry(item);
      out.push({ rect: g.horizontal ? pad(g.tight) : pad(item.bbox), reason: "E-Mail-Adresse (@)", kind: "email" });
    }
    for (const line of lines) {
      for (const m of line.text.matchAll(/\S*@\S*/g)) {
        if (line.items.some((li) => li.chars.join("").includes("@") && li.end > m.index! && li.start < m.index! + m[0].length && li.end - li.start === m[0].length && li.start === m.index)) continue;
        out.push({ rect: pad(touchedItemsBox(line, m.index!, m.index! + m[0].length)), reason: "E-Mail-Adresse (@)", kind: "email" });
      }
    }
  }

  // 4) phone-number pattern (optional)
  if (rules.detectPhone) {
    for (const item of items) {
      if (!looksLikePhone(item.str)) continue;
      const g = itemGeometry(item);
      out.push({ rect: g.horizontal ? pad(g.tight) : pad(item.bbox), reason: "Telefonnummer-Muster", kind: "phone" });
    }
  }

  // clamp to the page, drop degenerate and contained rectangles
  const clamped = out
    .map((d) => ({
      ...d,
      rect: { x0: Math.max(0, d.rect.x0), y0: Math.max(0, d.rect.y0), x1: Math.min(W, d.rect.x1), y1: Math.min(H, d.rect.y1) },
    }))
    .filter((d) => d.rect.x1 - d.rect.x0 > 1 && d.rect.y1 - d.rect.y0 > 1);
  return dropContained(clamped);
}
