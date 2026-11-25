// Deliberately independent of the production scanner (byteSearch.ts / verify.ts):
// the tests must not trust the code they are testing to find its own leaks.
import zlib from "node:zlib";

/**
 * Raw file + every inflate-able `stream … endstream` segment. Image payloads (our own pixel data) are left out: they hold
 * no text, and random pixel bytes would "contain" 3-letter terms like "AFR" by chance.
 */
function haystacks(bytes: Uint8Array): Buffer[] {
  const buf = Buffer.from(bytes);
  const raw = Buffer.from(bytes); // copy in which image payloads get zeroed
  const out: Buffer[] = [raw];
  let pos = 0;
  for (;;) {
    const s = buf.indexOf("stream", pos, "latin1");
    if (s < 0) break;
    let start = s + "stream".length;
    if (buf[start] === 0x0d) start++;
    if (buf[start] === 0x0a) start++;
    const end = buf.indexOf("endstream", start, "latin1");
    if (end < 0) break;
    const dict = buf.subarray(Math.max(0, s - 400), s).toString("latin1");
    const objStart = dict.lastIndexOf("obj"); // the dictionary of THIS stream starts after its "n 0 obj"
    const isImage = /\/Subtype\s*\/Image/.test(objStart >= 0 ? dict.slice(objStart) : dict);
    if (isImage) {
      raw.fill(0, start, end);
    } else {
      try {
        out.push(zlib.inflateSync(buf.subarray(start, end)));
      } catch {
        /* not deflate */
      }
    }
    pos = end + "endstream".length;
  }
  return out;
}

/** Decoded contents of every <hex string> (independent regex implementation). */
function hexStrings(hay: Buffer): Buffer[] {
  const out: Buffer[] = [];
  const text = hay.toString("latin1");
  for (const m of text.matchAll(/<([0-9a-fA-F\s]{8,})>/g)) {
    out.push(Buffer.from(m[1]!.replace(/\s+/g, ""), "hex"));
  }
  return out;
}

function lower(b: Buffer): Buffer {
  return Buffer.from(b.toString("latin1").toLowerCase(), "latin1");
}

function utf16(s: string, be: boolean): Buffer {
  const b = Buffer.alloc(s.length * 2);
  for (let i = 0; i < s.length; i++) {
    if (be) b.writeUInt16BE(s.charCodeAt(i), i * 2);
    else b.writeUInt16LE(s.charCodeAt(i), i * 2);
  }
  return b;
}

/** Returns the needles that occur anywhere (ASCII / UTF-16BE / UTF-16LE, also inside decoded <hex> strings, case-insensitive). */
export function findLeaks(bytes: Uint8Array, needles: readonly string[]): string[] {
  const base = haystacks(bytes);
  const hay = [...base, ...base.flatMap(hexStrings)].map(lower);
  return needles.filter((needle) => {
    const n = needle.toLowerCase();
    const patterns = [Buffer.from(n, "latin1"), utf16(n, true), utf16(n, false)];
    return hay.some((h) => patterns.some((p) => h.includes(p)));
  });
}
