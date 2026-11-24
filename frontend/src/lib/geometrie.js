// Geometrie-Fingerabdruck eines Bauteils aus den Dreiecksnetzen des STEP-Modells, für „ähnliche Bauteile“. Unabhängig
// davon, wie das Teil im CAD liegt (Hauptachsen statt X/Y/Z) und wie fein es vernetzt ist (Punkte nach Fläche gewichtet).
//   masse:   Ausdehnung entlang der drei Hauptachsen, größte zuerst (mm)
//   volumen, flaeche: mm³, mm²
//   fuell:   Volumen / Hüllquader der Hauptachsen (Vollmaterial nahe 1, Rahmen und Rohre klein)
//   d2:      Verteilung der Abstände zwischen zufälligen Punkten der Oberfläche, bezogen auf den größten Abstand
//            (Formverteilung „D2“: gleiche Form in anderer Größe ergibt dieselbe Verteilung)
// Verglichen wird auf dem Server (logic/aehnlichkeit.py). Der Zufall ist fest geseedet: gleiches Modell, gleicher Abdruck.
import { volumenUndFlaeche, quader, quaderBasis } from './messen.js';

export const GEO_VERSION = 1;
const FAECHER = 24;

function zufall(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Eigenvektoren einer symmetrischen 3×3-Matrix (Jacobi-Verfahren): Spalten von v
function eigen(m) {
  const a = m.map((r) => [...r]);
  const v = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  for (let it = 0; it < 50; it++) {
    let p = 0; let q = 1;
    for (const [i, j] of [[0, 1], [0, 2], [1, 2]]) if (Math.abs(a[i][j]) > Math.abs(a[p][q])) { p = i; q = j; }
    if (Math.abs(a[p][q]) < 1e-12) break;
    const th = 0.5 * Math.atan2(2 * a[p][q], a[q][q] - a[p][p]);
    const c = Math.cos(th); const s = Math.sin(th);
    for (let k = 0; k < 3; k++) {
      const akp = a[k][p]; const akq = a[k][q];
      a[k][p] = c * akp - s * akq; a[k][q] = s * akp + c * akq;
    }
    for (let k = 0; k < 3; k++) {
      const apk = a[p][k]; const aqk = a[q][k];
      a[p][k] = c * apk - s * aqk; a[q][k] = s * apk + c * aqk;
    }
    for (let k = 0; k < 3; k++) {
      const vkp = v[k][p]; const vkq = v[k][q];
      v[k][p] = c * vkp - s * vkq; v[k][q] = s * vkp + c * vkq;
    }
  }
  return [0, 1, 2].map((j) => [v[0][j], v[1][j], v[2][j]]);
}

// Punkte gleichmäßig auf der Oberfläche (je Fläche gewichtet)
function punkteAufOberflaeche(netze, anzahl, rnd) {
  const dreiecke = [];
  const summen = [];
  let gesamt = 0;
  for (const n of netze) {
    const p = n.position;
    for (let t = 0; t < n.index.length; t += 3) {
      const [i, j, k] = [n.index[t] * 3, n.index[t + 1] * 3, n.index[t + 2] * 3];
      const a = [p[i], p[i + 1], p[i + 2]]; const b = [p[j], p[j + 1], p[j + 2]]; const c = [p[k], p[k + 1], p[k + 2]];
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]; const w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const fl = Math.hypot(u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]) / 2;
      if (fl <= 0) continue;
      gesamt += fl;
      dreiecke.push([a, u, w]);
      summen.push(gesamt);
    }
  }
  if (!dreiecke.length) return [];
  const out = [];
  for (let s = 0; s < anzahl; s++) {
    const z = rnd() * gesamt;
    let lo = 0; let hi = summen.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (summen[mid] < z) lo = mid + 1; else hi = mid; }
    const [a, u, w] = dreiecke[lo];
    let r1 = rnd(); let r2 = rnd();
    if (r1 + r2 > 1) { r1 = 1 - r1; r2 = 1 - r2; }
    out.push([a[0] + r1 * u[0] + r2 * w[0], a[1] + r1 * u[1] + r2 * w[1], a[2] + r1 * u[2] + r2 * w[2]]);
  }
  return out;
}

export function fingerabdruck(netze, { punkte = 1500, paare = 6000 } = {}) {
  const rnd = zufall(20261124);
  const p = punkteAufOberflaeche(netze, punkte, rnd);
  if (p.length < 10) return null;
  // Hauptachsen aus der Kovarianz der Oberflächenpunkte
  const mitte = [0, 1, 2].map((k) => p.reduce((s, x) => s + x[k], 0) / p.length);
  const kov = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for (const x of p) for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) kov[i][j] += (x[i] - mitte[i]) * (x[j] - mitte[j]);
  // Kleinster Hüllquader: als Z-Richtung die CAD-Achsen und die Hauptachsen probieren, quer dazu das kleinste Rechteck
  // über die konvexe Hülle (exakt, auch wenn das Teil im CAD gedreht liegt)
  let besterQuader = quader(netze);
  for (const z of [[1, 0, 0], [0, 1, 0], [0, 0, 1], ...eigen(kov)]) {
    const basis = quaderBasis(netze, z);
    if (!basis) continue;
    const q = quader(netze, 0, basis);
    if (q.volumen < besterQuader.volumen - 1e-9) besterQuader = q;
  }
  const masse = [besterQuader.x, besterQuader.y, besterQuader.z].sort((a, b) => b - a);
  const { volumen, flaeche } = volumenUndFlaeche(netze);
  // D2: Abstände zufälliger Punktpaare, auf den größten bezogen
  const abst = [];
  for (let s = 0; s < paare; s++) {
    const a = p[Math.floor(rnd() * p.length)]; const b = p[Math.floor(rnd() * p.length)];
    abst.push(Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
  }
  const groesster = Math.max(...abst) || 1;
  const d2 = new Array(FAECHER).fill(0);
  for (const d of abst) d2[Math.min(FAECHER - 1, Math.floor((d / groesster) * FAECHER))] += 1;
  const r = (x, n) => Math.round(x * 10 ** n) / 10 ** n;
  const box = masse[0] * masse[1] * masse[2];
  return {
    v: GEO_VERSION,
    masse: masse.map((x) => r(x, 2)),
    volumen: r(volumen, 1),
    flaeche: r(flaeche, 1),
    fuell: box > 0 ? r(Math.min(1, volumen / box), 4) : 0,
    d2: d2.map((x) => r(x / abst.length, 5)),
  };
}
