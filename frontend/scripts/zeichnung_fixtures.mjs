// Liest Text mit Positionen aus PDFs (wie im Browser mit pdf.js) und schreibt Fixtures für die Erkennungs-Tests.
// Aufruf im Frontend-Ordner: node scripts/zeichnung_fixtures.mjs src/lib/testdaten/zeichnungen.json datei1.pdf …
// Nur eigene Testzeichnungen verwenden, keine Kundendaten (die Fixtures liegen im Repo).
import { readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs';
import { textAusSeite } from '../src/lib/zeichnungText.js';

const [ziel, ...dateien] = process.argv.slice(2);
const out = {};
for (const f of dateien) {
  const doc = await pdfjs.getDocument({ data: new Uint8Array(readFileSync(f)), useSystemFonts: false }).promise;
  const seite = await doc.getPage(1);
  out[basename(f)] = await textAusSeite(seite);
}
writeFileSync(ziel, JSON.stringify(out, null, 1));
console.log(Object.entries(out).map(([k, v]) => `${k}: ${v.elemente.length} Textstücke`).join('\n'));
