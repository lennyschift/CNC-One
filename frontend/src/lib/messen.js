// Messen am 3D-Modell, ohne Three.js: rechnet direkt auf den Dreiecksnetzen aus dem STEP-Leser
// ({ position, normal, index, flaechen: [[erstesDreieck, letztesDreieck], …] }, Längen in mm, CAD-Achsen X/Y/Z).
// Volumen und Gewicht, Rohteil als Quader oder Rundmaterial (mit Aufmaß je Seite), Art und Maß einer angeklickten
// CAD-Fläche (Ebene, Zylinder: Bohrung oder Welle mit Durchmesser) und Abstände.

export const ACHSEN = { X: [1, 0, 0], Y: [0, 1, 0], Z: [0, 0, 1] };

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const laenge = (a) => Math.hypot(a[0], a[1], a[2]);
const einheit = (a) => { const l = laenge(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const punkt = (pos, i) => [pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]];

// Volumen (mm³) und Oberfläche (mm²) eines geschlossenen Netzes: Summe der Tetraeder vom Ursprung zu jedem Dreieck
export function volumenUndFlaeche(netze) {
  let volumen = 0;
  let flaeche = 0;
  for (const n of netze) {
    for (let t = 0; t < n.index.length; t += 3) {
      const a = punkt(n.position, n.index[t]);
      const b = punkt(n.position, n.index[t + 1]);
      const c = punkt(n.position, n.index[t + 2]);
      volumen += dot(a, cross(b, c)) / 6;
      flaeche += laenge(cross(sub(b, a), sub(c, a))) / 2;
    }
  }
  return { volumen: Math.abs(volumen), flaeche };
}

// Gewicht in kg aus Volumen (mm³) und Dichte (kg/dm³ = g/cm³)
export const gewichtKg = (volumenMm3, dichte) => (volumenMm3 / 1e6) * (dichte || 0);

function allePunkte(netze) {
  const p = [];
  for (const n of netze) for (let i = 0; i < n.position.length; i += 3) p.push([n.position[i], n.position[i + 1], n.position[i + 2]]);
  return p;
}

// Basis senkrecht zu einer Achse (für Projektionen in die Ebene quer zur Achse)
function quer(achse) {
  const a = einheit(achse);
  const hilf = Math.abs(a[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
  const u = einheit(cross(a, hilf));
  return [u, cross(a, u)];
}

// Kleinster umschließender Kreis von 2D-Punkten (Welzl, iterativ mit zufälliger Reihenfolge)
export function umkreis(punkte) {
  const p = punkte.slice();
  for (let i = p.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
  const drin = (k, q) => Math.hypot(q[0] - k.x, q[1] - k.y) <= k.r + 1e-7;
  const aus2 = (a, b) => ({ x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2, r: Math.hypot(a[0] - b[0], a[1] - b[1]) / 2 });
  const aus3 = (a, b, c) => {
    const d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]));
    if (Math.abs(d) < 1e-12) return null;
    const a2 = a[0] ** 2 + a[1] ** 2; const b2 = b[0] ** 2 + b[1] ** 2; const c2 = c[0] ** 2 + c[1] ** 2;
    const x = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d;
    const y = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d;
    return { x, y, r: Math.hypot(a[0] - x, a[1] - y) };
  };
  let k = { x: p[0]?.[0] ?? 0, y: p[0]?.[1] ?? 0, r: 0 };
  for (let i = 1; i < p.length; i++) {
    if (drin(k, p[i])) continue;
    k = { x: p[i][0], y: p[i][1], r: 0 };
    for (let j = 0; j < i; j++) {
      if (drin(k, p[j])) continue;
      k = aus2(p[i], p[j]);
      for (let m = 0; m < j; m++) if (!drin(k, p[m])) k = aus3(p[i], p[j], p[m]) ?? k;
    }
  }
  return k;
}

// Rundmaterial um eine Achse: Durchmesser (kleinster umschließender Kreis quer zur Achse) und Länge entlang der Achse
export function rundmaterial(netze, achse, aufmass = 0) {
  const a = einheit(achse);
  const [u, v] = quer(a);
  const p = allePunkte(netze);
  let min = Infinity; let max = -Infinity;
  const flach = p.map((q) => { const s = dot(q, a); if (s < min) min = s; if (s > max) max = s; return [dot(q, u), dot(q, v)]; });
  const k = umkreis(flach);
  const durchmesser = 2 * k.r + 2 * aufmass;
  const l = max - min + 2 * aufmass;
  const mitte = add(add(mul(u, k.x), mul(v, k.y)), mul(a, (min + max) / 2));
  return { art: 'Rund', achse: a, durchmesser, laenge: l, mitte, volumen: Math.PI * (durchmesser / 2) ** 2 * l };
}

// Quader entlang der CAD-Achsen
export function quader(netze, aufmass = 0) {
  const p = allePunkte(netze);
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const q of p) for (let i = 0; i < 3; i++) { if (q[i] < min[i]) min[i] = q[i]; if (q[i] > max[i]) max[i] = q[i]; }
  const masse = [0, 1, 2].map((i) => max[i] - min[i] + 2 * aufmass);
  return { art: 'Quader', x: masse[0], y: masse[1], z: masse[2], min: min.map((m) => m - aufmass), max: max.map((m) => m + aufmass), volumen: masse[0] * masse[1] * masse[2] };
}

// Mögliche Rohteile (Quader und Rundmaterial je Achse) mit dem kleinsten Volumen als Vorschlag
export function rohteile(netze, aufmass = 0) {
  const liste = [quader(netze, aufmass), ...Object.entries(ACHSEN).map(([name, a]) => ({ ...rundmaterial(netze, a, aufmass), achsName: name }))];
  const vorschlag = liste.reduce((best, r) => (r.volumen < best.volumen ? r : best));
  return { liste, vorschlag };
}

// ---- Fläche analysieren
// Kleinster Eigenvektor einer symmetrischen 3x3-Matrix: Potenzverfahren auf (Spur·E − M), dessen größter Eigenvektor
// der kleinste von M ist
function kleinsterEigenvektor(m) {
  const spur = m[0][0] + m[1][1] + m[2][2] + 1e-9;
  const b = m.map((z, r) => z.map((w, c) => (r === c ? spur : 0) - w));
  const spalten = [0, 1, 2].map((c) => [b[0][c], b[1][c], b[2][c]]);
  let v = einheit(spalten.reduce((x, y) => (laenge(y) > laenge(x) ? y : x)));
  for (let i = 0; i < 200; i++) v = einheit([dot(b[0], v), dot(b[1], v), dot(b[2], v)]);
  return v;
}

// Kreis durch 2D-Punkte (algebraische Ausgleichsrechnung nach Kåsa): Mittelpunkt und Radius
function kreisAusgleich(p) {
  let sx = 0; let sy = 0; let sxx = 0; let syy = 0; let sxy = 0; let sz = 0; let sxz = 0; let syz = 0;
  for (const [x, y] of p) { const z = x * x + y * y; sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; sz += z; sxz += x * z; syz += y * z; }
  const n = p.length;
  // löse [sxx sxy sx; sxy syy sy; sx sy n] * [A B C] = [sxz syz sz]
  const M = [[sxx, sxy, sx, sxz], [sxy, syy, sy, syz], [sx, sy, n, sz]];
  for (let i = 0; i < 3; i++) {
    const piv = [i, i + 1, i + 2].filter((r) => r < 3).reduce((b, r) => (Math.abs(M[r][i]) > Math.abs(M[b][i]) ? r : b), i);
    [M[i], M[piv]] = [M[piv], M[i]];
    if (Math.abs(M[i][i]) < 1e-12) return null;
    for (let r = 0; r < 3; r++) if (r !== i) { const f = M[r][i] / M[i][i]; for (let c = i; c < 4; c++) M[r][c] -= f * M[i][c]; }
  }
  const A = M[0][3] / M[0][0]; const B = M[1][3] / M[1][1]; const C = M[2][3] / M[2][2];
  const x = A / 2; const y = B / 2;
  return { x, y, r: Math.sqrt(C + x * x + y * y) };
}

// Zu welcher CAD-Fläche gehört ein Dreieck? Liefert den Index in netz.flaechen oder -1.
export function flaecheZuDreieck(netz, dreieck) {
  return (netz.flaechen ?? []).findIndex(([a, b]) => dreieck >= a && dreieck <= b);
}

// Art und Maß einer CAD-Fläche: Ebene (Normale, Fläche), Zylinder (Durchmesser, Achse, Länge, Bohrung oder Welle) oder Freiform
export function flaecheAnalysieren(netz, flaechenIndex) {
  const [erstes, letztes] = netz.flaechen[flaechenIndex];
  const ecken = new Set();
  let flaeche = 0;
  for (let t = erstes; t <= letztes; t++) {
    const i = [netz.index[3 * t], netz.index[3 * t + 1], netz.index[3 * t + 2]];
    i.forEach((x) => ecken.add(x));
    const [a, b, c] = i.map((x) => punkt(netz.position, x));
    flaeche += laenge(cross(sub(b, a), sub(c, a))) / 2;
  }
  const idx = [...ecken];
  const p = idx.map((i) => punkt(netz.position, i));
  const n = idx.map((i) => einheit(punkt(netz.normal, i)));
  const dreiecke = [];
  for (let t = erstes; t <= letztes; t++) dreiecke.push(t);

  const mittelN = einheit(n.reduce((s, x) => add(s, x), [0, 0, 0]));
  if (n.every((x) => dot(x, mittelN) > 0.9995)) return { art: 'Ebene', normale: mittelN, flaeche, dreiecke };

  // Zylinder: alle Normalen stehen senkrecht auf der Achse
  const cov = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for (const x of n) for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) cov[r][c] += x[r] * x[c];
  const achse = kleinsterEigenvektor(cov);
  if (n.every((x) => Math.abs(dot(x, achse)) < 0.03)) {
    const [u, v] = quer(achse);
    const k = kreisAusgleich(p.map((q) => [dot(q, u), dot(q, v)]));
    if (k) {
      let min = Infinity; let max = -Infinity;
      for (const q of p) { const s = dot(q, achse); if (s < min) min = s; if (s > max) max = s; }
      const mitte = add(add(mul(u, k.x), mul(v, k.y)), mul(achse, (min + max) / 2));
      // Bohrung: Normalen zeigen zur Achse hin
      const nachInnen = p.reduce((s, q, i) => s + dot(n[i], sub(q, mitte)) - dot(n[i], achse) * dot(sub(q, mitte), achse), 0) < 0;
      return { art: 'Zylinder', durchmesser: 2 * k.r, achse, mitte, laenge: max - min, bohrung: nachInnen, flaeche, dreiecke };
    }
  }
  return { art: 'Freiform', flaeche, dreiecke };
}

// Messpunkt zu einem Klick: auf einem Zylinder der nächste Punkt auf seiner Achse (Mitte von Bohrung oder Welle),
// sonst der angeklickte Punkt selbst
export function messpunkt(klick, analyse) {
  if (analyse?.art !== 'Zylinder') return { punkt: klick, art: 'Fläche' };
  const s = dot(sub(klick, analyse.mitte), analyse.achse);
  return { punkt: add(analyse.mitte, mul(analyse.achse, s)), art: analyse.bohrung ? 'Bohrungsmitte' : 'Wellenmitte' };
}

export function abstand(a, b) {
  const d = sub(b, a);
  return { gesamt: laenge(d), dx: Math.abs(d[0]), dy: Math.abs(d[1]), dz: Math.abs(d[2]) };
}
