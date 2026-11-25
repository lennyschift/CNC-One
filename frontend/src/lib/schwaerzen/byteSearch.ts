/**
 * Boyer–Moore–Horspool search on raw bytes (no giant string conversion, so it
 * also works on tens of MB). Returns the first index of `needle` in
 * `haystack` at or after `from`, or -1.
 */
export function indexOfBytes(haystack: Uint8Array, needle: Uint8Array, from = 0): number {
  const n = needle.length;
  if (n === 0 || haystack.length < n) return -1;
  const skip = new Int32Array(256).fill(n);
  for (let i = 0; i < n - 1; i++) skip[needle[i]!] = n - 1 - i;

  let pos = Math.max(0, from);
  const last = n - 1;
  while (pos <= haystack.length - n) {
    let j = last;
    while (j >= 0 && haystack[pos + j] === needle[j]) j--;
    if (j < 0) return pos;
    pos += skip[haystack[pos + last]!]!;
  }
  return -1;
}

/** ASCII-only case fold (A-Z -> a-z), returns a copy. Non-ASCII bytes are untouched. */
export function foldAsciiCase(bytes: Uint8Array): Uint8Array {
  const out = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    const b = bytes[i]!;
    out[i] = b >= 0x41 && b <= 0x5a ? b + 32 : b;
  }
  return out;
}

/**
 * All byte encodings a text string could take inside a PDF: Latin-1/ASCII,
 * UTF-8, UTF-16BE (Info dictionary / XMP) and UTF-16LE.
 * `term` should already be lower-cased; the haystack is folded the same way.
 */
export function termByteVariants(term: string): Uint8Array[] {
  const variants: Uint8Array[] = [];
  const enc = new TextEncoder();
  variants.push(enc.encode(term));

  if ([...term].every((ch) => ch.charCodeAt(0) < 256)) {
    variants.push(Uint8Array.from([...term], (ch) => ch.charCodeAt(0)));
  }

  const be = new Uint8Array(term.length * 2);
  const le = new Uint8Array(term.length * 2);
  for (let i = 0; i < term.length; i++) {
    const c = term.charCodeAt(i);
    be[i * 2] = c >> 8;
    be[i * 2 + 1] = c & 255;
    le[i * 2] = c & 255;
    le[i * 2 + 1] = c >> 8;
  }
  variants.push(be, le);

  return variants;
}

const isHexDigit = (b: number) => (b >= 0x30 && b <= 0x39) || (b >= 0x41 && b <= 0x46) || (b >= 0x61 && b <= 0x66);
const isPdfSpace = (b: number) => b === 0x20 || b === 0x0a || b === 0x0d || b === 0x09 || b === 0x0c || b === 0x00;
const hexVal = (b: number) => (b <= 0x39 ? b - 0x30 : (b | 0x20) - 0x61 + 10);

/**
 * PDF strings can be written in hex form (`<FEFF0067…>`: Info entries, form
 * values, annotation text …). Hex spelling is NOT case-neutral ('G' = 47,
 * 'g' = 67), so a pattern search on the hex digits would miss mixed-case
 * text; instead every `<hex…>` run (≥ 4 decoded bytes) is DECODED here and
 * the decoded bytes are searched like any other data. All runs are returned
 * joined by 0xFF separators (a term cannot span two strings by accident).
 */
export function decodeHexStrings(bytes: Uint8Array): Uint8Array {
  const chunks: number[][] = [];
  for (let i = 0; i < bytes.length; i++) {
    if (bytes[i] !== 0x3c || bytes[i + 1] === 0x3c) continue; // '<' but not '<<'
    const digits: number[] = [];
    let j = i + 1;
    for (; j < bytes.length; j++) {
      const b = bytes[j]!;
      if (isHexDigit(b)) digits.push(hexVal(b));
      else if (!isPdfSpace(b)) break;
    }
    if (bytes[j] === 0x3e && digits.length >= 8) {
      const decoded: number[] = [];
      for (let k = 0; k + 1 < digits.length; k += 2) decoded.push(digits[k]! * 16 + digits[k + 1]!);
      if (digits.length % 2 === 1) decoded.push(digits[digits.length - 1]! * 16);
      chunks.push(decoded);
      i = j;
    }
  }
  const total = chunks.reduce((n, c) => n + c.length + 2, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
    out[o++] = 0xff;
    out[o++] = 0xff;
  }
  return out;
}

/**
 * CNC One: blanks the PDF SYNTAX of the (stream-less) structure — name tokens such as `/Width` or `/MediaBox` and the
 * keywords obj/endobj/stream/endstream/xref/trailer/startxref — so that a word from the drawing that happens to equal a
 * PDF key ("Width", "Size", "Type" in a bilingual title block) is not reported as found. Text inside literal strings
 * `( … )` and hex strings is left untouched and still searched.
 */
const KEYWORDS = ["obj", "endobj", "stream", "endstream", "xref", "trailer", "startxref"].map((k) => new TextEncoder().encode(k));
const DELIM = new Set([...Array.from({ length: 33 }, (_, i) => i), ...[..."()<>[]{}/%"].map((c) => c.charCodeAt(0))]);
export function blankPdfSyntax(bytes: Uint8Array): Uint8Array {
  const out = bytes.slice();
  let depth = 0;
  for (let i = 0; i < out.length; i++) {
    const b = out[i]!;
    if (depth > 0) {
      if (b === 0x5c) i++; // escaped character inside a literal string
      else if (b === 0x28) depth++;
      else if (b === 0x29) depth--;
      continue;
    }
    if (b === 0x28) { depth = 1; continue; }
    if (b === 0x2f) {
      let j = i + 1;
      while (j < out.length && !DELIM.has(out[j]!)) j++;
      out.fill(0x20, i, j);
      i = j - 1;
      continue;
    }
    if (DELIM.has(b) || (i > 0 && !DELIM.has(out[i - 1]!))) continue;
    for (const kw of KEYWORDS) {
      if (i + kw.length <= out.length && kw.every((c, k) => out[i + k] === c) && (i + kw.length === out.length || DELIM.has(out[i + kw.length]!))) {
        out.fill(0x20, i, i + kw.length);
        break;
      }
    }
  }
  return out;
}

const STREAM_KW = new TextEncoder().encode("stream");
const ENDSTREAM_KW = new TextEncoder().encode("endstream");

/**
 * Returns a copy of `bytes` in which the payload of EVERY stream (pixel data, compressed content, font programs …) is
 * zeroed, leaving the object structure, dictionaries, strings, trailer and anything outside streams. The raw-file scan
 * uses this: compressed or binary payloads are effectively random bytes and "contain" short terms like "VW" or "AFR"
 * purely by chance (false alarm). The payloads are not skipped — the decoded streams are scanned separately.
 */
export function blankStreamPayloads(bytes: Uint8Array): Uint8Array {
  const out = bytes.slice();
  let from = 0;
  for (;;) {
    let s = indexOfBytes(out, STREAM_KW, from);
    // skip the "stream" inside "endstream"
    while (s >= 3 && out[s - 3] === 0x65 && out[s - 2] === 0x6e && out[s - 1] === 0x64) {
      s = indexOfBytes(out, STREAM_KW, s + 1);
    }
    if (s < 0) break;
    const e = indexOfBytes(out, ENDSTREAM_KW, s + STREAM_KW.length);
    if (e < 0) break;
    out.fill(0, s + STREAM_KW.length, e);
    from = e + ENDSTREAM_KW.length;
  }
  return out;
}
