// Liest STEP-Modelle mit occt-import-js (wie der Web-Worker im Browser) und schreibt Netz-Fixtures für die Mess-Tests.
// Aufruf im Frontend-Ordner: node scripts/modell_fixtures.mjs src/lib/testdaten/modelle.json modell1.step …
// Nur eigene Testmodelle verwenden, keine Kundendaten (die Fixtures liegen im Repo).
import { readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';
import { createRequire } from 'node:module';

const occt = await createRequire(import.meta.url)('occt-import-js')();
const [ziel, ...dateien] = process.argv.slice(2);
const runden = (a, s) => Array.from(a, (v) => Math.round(v * s) / s);
const out = {};
for (const f of dateien) {
  const r = occt.ReadStepFile(new Uint8Array(readFileSync(f)), { linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.002, angularDeflection: 0.4 });
  out[basename(f)] = r.meshes.map((m) => ({
    position: runden(m.attributes.position.array, 1000),
    normal: runden(m.attributes.normal.array, 10000),
    index: Array.from(m.index.array),
    flaechen: (m.brep_faces ?? []).map((x) => [x.first, x.last]),
  }));
}
writeFileSync(ziel, JSON.stringify(out));
console.log(Object.entries(out).map(([k, v]) => `${k}: ${v.length} Netze, ${v.reduce((s, n) => s + n.index.length / 3, 0)} Dreiecke, ${v.reduce((s, n) => s + n.flaechen.length, 0)} Flächen`).join('\n'));
