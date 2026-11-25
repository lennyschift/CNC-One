import { LIMITS } from "./types";

/**
 * Sensitive-term handling. A "term" is a normalized string that must never
 * appear in the saved file's text layer / bytes. Terms come from two sources:
 *  - typed in by the user ("Sensible Begriffe"),
 *  - derived from the text that lies under the redaction rectangles.
 * Everything here works on plain strings, never touches drawing bytes.
 */

const INVISIBLE_RE = /[​-‍﻿­]/g;

export function normalizeForMatch(s: string): string {
  return s.normalize("NFKC").replace(INVISIBLE_RE, "").toLowerCase().replace(/\s+/g, " ").trim();
}

const WORD_CHAR_RE = /[\p{L}\p{N}]/u;

function isWordChar(ch: string | undefined): boolean {
  return ch !== undefined && ch !== "" && WORD_CHAR_RE.test(ch);
}

/** Terms shorter than this only match on word boundaries ("VW" must not hit "VWX"). */
const BOUNDARY_ONLY_BELOW = 4;

/** `haystack` and `term` must already be normalized. */
export function containsTerm(haystack: string, term: string): boolean {
  if (term.length === 0) return false;
  const needBoundary = term.length < BOUNDARY_ONLY_BELOW;
  let from = 0;
  for (;;) {
    const i = haystack.indexOf(term, from);
    if (i < 0) return false;
    if (!needBoundary) return true;
    if (!isWordChar(haystack[i - 1]) && !isWordChar(haystack[i + term.length])) return true;
    from = i + 1;
  }
}

/** Parses the free-text "Sensible Begriffe" box: one term per line / comma / semicolon. */
export function parseManualTerms(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of text.split(/[\n\r,;]+/)) {
    const term = normalizeForMatch(part.slice(0, LIMITS.maxTermLength));
    if (term.length < 2 || seen.has(term)) continue;
    seen.add(term);
    out.push(term);
    if (out.length >= LIMITS.maxTerms) break;
  }
  return out;
}

const HAS_LETTER_RE = /\p{L}/u;

/**
 * Derives terms from the text items that lie under redaction rectangles: the
 * whole (trimmed) item string, plus every word of ≥ 4 characters containing a
 * letter. Pure numbers/short tokens are skipped to keep false positives
 * (dimensions like "50") low. Deliberately conservative: an over-broad term
 * only costs searchability, never safety.
 */
export function deriveTerms(itemStrings: readonly string[]): string[] {
  const seen = new Set<string>();
  const add = (raw: string) => {
    const term = normalizeForMatch(raw.slice(0, LIMITS.maxTermLength));
    if (term.length < 3 || seen.has(term)) return;
    const digitsOnly = /^[\d\s.,+\-/()]+$/.test(term);
    if (digitsOnly ? term.replace(/\D/g, "").length < 5 : !HAS_LETTER_RE.test(term)) return;
    seen.add(term);
  };
  for (const s of itemStrings) {
    add(s);
    for (const word of s.split(/\s+/)) {
      if (word.length >= 4 && HAS_LETTER_RE.test(word)) add(word.replace(/^[^\p{L}\p{N}@]+|[^\p{L}\p{N}@]+$/gu, ""));
    }
    if (seen.size >= LIMITS.maxTerms * 5) break;
  }
  return [...seen];
}

export function looksLikeEmail(text: string): boolean {
  return text.includes("@");
}

/**
 * Phone-like: a run of digits/separators with ≥ 7 digits that either starts
 * with "+"/"00" (international) or contains a group of ≥ 5 consecutive digits
 * ("089 123456"). Dimension chains such as "12.5 30 40" are deliberately NOT
 * matched — they would wipe legitimate text from the search layer.
 */
export function looksLikePhone(text: string): boolean {
  const runs = text.match(/(?:\+|00)?\d[\d ()/.\-–]{5,}\d/g) ?? [];
  return runs.some((run) => {
    if ((run.match(/\d/g)?.length ?? 0) < 7) return false;
    return /^(?:\+|00)/.test(run) || /\d{5,}/.test(run);
  });
}

export type SensitiveHit = "term" | "email" | "phone";

/** Which kind of sensitive content (if any) `text` contains. */
export function findSensitive(text: string, normalizedTerms: readonly string[]): SensitiveHit | null {
  const norm = normalizeForMatch(text);
  for (const term of normalizedTerms) {
    if (containsTerm(norm, term)) return "term";
  }
  if (looksLikeEmail(text)) return "email";
  if (looksLikePhone(text)) return "phone";
  return null;
}
