// Schwärzen in CNC One: verbindet den geprüften Kern (pipeline.ts, detect.ts …, übernommen aus dem Schwärz-Werkzeug)
// mit CNC One. Alles läuft im Browser — die Zeichnung verlässt den Rechner nur als fertige, geprüfte Bild-PDF zum
// eigenen Server (api/schwaerzen.py), der sie noch einmal unabhängig prüft.
import { pdfjs } from '../pdf.js';
import { runDetection } from './detect';
import { runRedaction } from './pipeline';
import { browserRenderer } from './browserRenderer';
import { sha256Hex } from './hash';
import { normalizeForMatch } from './sensitive';
import { regelnBereinigen } from './rules';
import { DEFAULT_EXPORT_SETTINGS } from './types';

let zaehler = 0;
export const neueId = () => `b${Date.now().toString(36)}${(zaehler++).toString(36)}`;

// Original holen (als Bytes, für die Prüfsumme) und mit pdf.js öffnen
export async function pdfLaden(url) {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`Die Zeichnung ließ sich nicht laden (${r.status}).`);
  const bytes = new Uint8Array(await r.arrayBuffer());
  const doc = await pdfjs.getDocument({ data: bytes.slice() }).promise;
  return { bytes, doc, sha: await sha256Hex(bytes) };
}

export const pdfOeffnen = (bytes) => pdfjs.getDocument({ data: new Uint8Array(bytes) }).promise;

// Regeln für die Erkennung: Regelsatz (Standard + Kunde) und die Begriffe aus den Stammdaten des Kunden als Stichwörter
export function regelnMitKunde(antwort) {
  const r = regelnBereinigen(antwort?.regeln ?? {});
  const begriffe = antwort?.kundenBegriffe ?? [];
  return { ...r, directKeywords: [...new Set([...r.directKeywords, ...begriffe])] };
}

// Prüfbegriffe für die Nachprüfung der fertigen Datei: Stichwörter, Begriffe des Kunden, Texte aus Stempeln/Feldern
export function pruefBegriffe(regeln, annotationTexts = []) {
  const alle = [...regeln.directKeywords, ...annotationTexts].map((t) => normalizeForMatch(String(t))).filter((t) => t.length >= 2);
  return [...new Set(alle)].slice(0, 300);
}

// Automatische Erkennung: Vorschläge als Bereiche (Lage 0…1 je Seite)
export async function erkennen(doc, regeln, signal) {
  const s = await runDetection({ doc, rules: regeln, signal });
  return {
    bereiche: s.rects.map((r) => ({ ...r, id: neueId(), source: 'auto' })),
    hinweise: s.notes,
    annotationTexts: s.annotationTexts ?? [],
  };
}

// Schwärzen und prüfen: neue PDF nur aus Bildern + Prüfprotokoll (ohne Inhalte)
export async function schwaerzen({ doc, bereiche, begriffe, signal, onProgress }) {
  const r = await runRedaction({
    doc,
    rects: bereiche,
    settings: { ...DEFAULT_EXPORT_SETTINGS },
    manualTerms: begriffe,
    renderer: browserRenderer,
    openResult: pdfOeffnen,
    fontBytes: null,
    onProgress,
    signal,
  });
  return { bytes: r.bytes, protokoll: r.report };
}

// Bytes → Base64 in Stücken (große Dateien sprengen sonst String.fromCharCode)
export function base64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

// Für die Anzeige der Prüfung: Status je Prüfpunkt
export const PRUEF_FARBE = { ok: 'text-ok', warn: 'text-warn', fail: 'text-accent' };
