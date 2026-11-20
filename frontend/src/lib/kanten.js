// CAD-Kanten und Fangpunkte am 3D-Modell, ohne Three.js. Der STEP-Leser liefert nur Dreiecke je CAD-Fläche; die echten
// Kanten sind dort, wo zwei verschiedene CAD-Flächen zusammenstoßen. Daraus entstehen Geraden (Länge), Kreise und Bögen
// (Radius, Mittelpunkt) und Kurven. Beim Messen wird auf Endpunkte, Kantenmitten, Kreis- und Bogenmitten, Achsen von
// Bohrungen/Wellen und Ebenen gefangen, nicht auf beliebige Punkte.
import { quer, kleinsterEigenvektor, kreisAusgleich, messpunkt, abstand } from './messen.js';

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const laenge = (a) => Math.hypot(a[0], a[1], a[2]);
const einheit = (a) => { const l = laenge(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const punkt = (pos, i) => [pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]];

// Alle CAD-Kanten der Netze: [{ art: 'Gerade'|'Kreis'|'Bogen'|'Kurve', punkte, laenge, start, ende, mitte, zentrum,
// radius, normale, winkel (Bogenmaß), geschlossen, kugel: { m, r } }]
export function cadKanten(netze) {
  const kanten = [];
  for (const n of netze) {
    if (!(n.flaechen ?? []).length) continue;
    const anzahl = n.index.length / 3;
    const flaecheVon = new Int32Array(anzahl).fill(-1);
    n.flaechen.forEach(([a, b], fi) => { for (let t = a; t <= b; t++) flaecheVon[t] = fi; });
    // Punkte zusammenführen: jede CAD-Fläche hat eigene Eckpunkte
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < n.position.length; i += 3) for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], n.position[i + k]); max[k] = Math.max(max[k], n.position[i + k]); }
    const q = Math.max(laenge(sub(max, min)) * 2e-5, 5e-4);
    const ids = new Map();
    const pkt = [];
    const vid = new Int32Array(n.position.length / 3);
    for (let i = 0; i < vid.length; i++) {
      const s = `${Math.round(n.position[3 * i] / q)},${Math.round(n.position[3 * i + 1] / q)},${Math.round(n.position[3 * i + 2] / q)}`;
      let id = ids.get(s);
      if (id === undefined) { id = pkt.length; ids.set(s, id); pkt.push(punkt(n.position, i)); }
      vid[i] = id;
    }
    // Dreieckskanten mit den Flächen, an denen sie liegen
    const map = new Map();
    for (let t = 0; t < anzahl; t++) {
      for (let e = 0; e < 3; e++) {
        const a = vid[n.index[3 * t + e]];
        const b = vid[n.index[3 * t + ((e + 1) % 3)]];
        if (a === b) continue;
        const s = a < b ? a * 4294967296 + b : b * 4294967296 + a;
        const k = map.get(s);
        if (k) k.f.push(flaecheVon[t]);
        else map.set(s, { a: Math.min(a, b), b: Math.max(a, b), f: [flaecheVon[t]] });
      }
    }
    // Merkmalskanten (zwei verschiedene Flächen oder offener Rand) je Flächenpaar sammeln
    const gruppen = new Map();
    for (const k of map.values()) {
      const f = [...new Set(k.f)].sort((x, y) => x - y);
      if (f.length < 2 && k.f.length > 1) continue; // innen in einer Fläche, auch die Naht eines Zylinders
      const s = f.length === 1 ? `${f[0]}|rand` : f.join('|');
      if (!gruppen.has(s)) gruppen.set(s, []);
      gruppen.get(s).push([k.a, k.b]);
    }
    for (const stuecke of gruppen.values()) {
      for (const zug of verketten(stuecke)) {
        for (const teil of anEckenTeilen(zug, pkt)) kanten.push(kanteEinordnen(teil.map((i) => pkt[i]), teil.length > 3 && teil[0] === teil[teil.length - 1]));
      }
    }
  }
  return kanten;
}

// Stücke [a, b] zu Linienzügen (Punktnummern) verketten; geschlossene Züge enden mit ihrem Anfang
function verketten(stuecke) {
  const nachbarn = new Map();
  const dazu = (a, b) => { if (!nachbarn.has(a)) nachbarn.set(a, []); nachbarn.get(a).push(b); };
  for (const [a, b] of stuecke) { dazu(a, b); dazu(b, a); }
  const benutzt = new Set();
  const key = (a, b) => (a < b ? `${a},${b}` : `${b},${a}`);
  const laufen = (start) => {
    const zug = [start];
    let vor = start;
    for (;;) {
      const weiter = (nachbarn.get(vor) ?? []).find((x) => !benutzt.has(key(vor, x)));
      if (weiter === undefined) break;
      benutzt.add(key(vor, weiter));
      zug.push(weiter);
      vor = weiter;
      if (weiter === start || nachbarn.get(weiter).length !== 2) break;
    }
    return zug;
  };
  const zuege = [];
  // erst von Enden und Verzweigungen aus, danach die geschlossenen Ringe
  for (const [p, l] of nachbarn) if (l.length !== 2) while (l.some((x) => !benutzt.has(key(p, x)))) zuege.push(laufen(p));
  for (const [a, b] of stuecke) if (!benutzt.has(key(a, b))) zuege.push(laufen(a));
  return zuege.filter((z) => z.length > 1);
}

// An scharfen Ecken (> 40°) teilen: zwei Flächen können sich über mehrere Kanten berühren
function anEckenTeilen(zug, pkt) {
  const geschlossen = zug.length > 3 && zug[0] === zug[zug.length - 1];
  const ecke = (i, j, k) => dot(einheit(sub(pkt[j], pkt[i])), einheit(sub(pkt[k], pkt[j]))) < Math.cos((40 * Math.PI) / 180);
  const teile = [];
  let akt = [zug[0]];
  for (let i = 1; i < zug.length; i++) {
    akt.push(zug[i]);
    if (i < zug.length - 1 && ecke(zug[i - 1], zug[i], zug[i + 1])) { teile.push(akt); akt = [zug[i]]; }
  }
  teile.push(akt);
  if (geschlossen && teile.length > 1) {
    // Ring mit Ecken: hat auch der Anfang eine Ecke, bleibt er geteilt, sonst gehören letztes und erstes Stück zusammen
    if (!ecke(zug[zug.length - 2], zug[0], zug[1])) { const letztes = teile.pop(); teile[0] = [...letztes, ...teile[0].slice(1)]; }
  }
  return teile.filter((t) => t.length > 1);
}

function punktAufZug(p, s) {
  let rest = s;
  for (let i = 1; i < p.length; i++) {
    const d = laenge(sub(p[i], p[i - 1]));
    if (rest <= d) return add(p[i - 1], mul(sub(p[i], p[i - 1]), d ? rest / d : 0));
    rest -= d;
  }
  return p[p.length - 1];
}

function kanteEinordnen(p, geschlossen) {
  let lg = 0;
  for (let i = 1; i < p.length; i++) lg += laenge(sub(p[i], p[i - 1]));
  const m = mul(p.reduce((s, x) => add(s, x), [0, 0, 0]), 1 / p.length);
  const kugel = { m, r: Math.max(...p.map((x) => laenge(sub(x, m)))) };
  const start = p[0];
  const ende = p[p.length - 1];
  const basis = { punkte: p, laenge: lg, start, ende, geschlossen, kugel };
  // Gerade: alle Punkte auf der Verbindung von Anfang und Ende
  const rl = laenge(sub(ende, start));
  if (!geschlossen && rl > 1e-9) {
    const r = mul(sub(ende, start), 1 / rl);
    const abw = Math.max(...p.map((x) => { const d = sub(x, start); return laenge(sub(d, mul(r, dot(d, r)))); }));
    if (abw < Math.max(1e-3, rl * 1e-3)) return { ...basis, art: 'Gerade', laenge: rl, mitte: mul(add(start, ende), 0.5), richtung: r };
  }
  // Kreis oder Bogen: Punkte in einer Ebene und gleich weit von einem Mittelpunkt
  const ohne = geschlossen ? p.slice(0, -1) : p;
  if (ohne.length >= 3) {
    const mo = mul(ohne.reduce((s, x) => add(s, x), [0, 0, 0]), 1 / ohne.length);
    const cov = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (const x of ohne) { const d = sub(x, mo); for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) cov[r][c] += d[r] * d[c]; }
    const normale = kleinsterEigenvektor(cov);
    const eben = Math.max(...ohne.map((x) => Math.abs(dot(sub(x, mo), normale))));
    const [u, v] = quer(normale);
    const k = kreisAusgleich(ohne.map((x) => [dot(x, u), dot(x, v)]));
    if (k && k.r > 1e-6) {
      const zentrum = add(add(mul(u, k.x), mul(v, k.y)), mul(normale, dot(mo, normale)));
      const abw = Math.max(...ohne.map((x) => Math.abs(laenge(sub(x, zentrum)) - k.r)));
      const tol = Math.max(5e-3, k.r * 5e-3);
      if (eben < tol && abw < tol) {
        let winkel = 0;
        for (let i = 1; i < p.length; i++) { const a = sub(p[i - 1], zentrum); const b = sub(p[i], zentrum); winkel += Math.atan2(laenge(cross(a, b)), dot(a, b)); }
        if (geschlossen || winkel > 2 * Math.PI - 0.05) return { ...basis, art: 'Kreis', radius: k.r, zentrum, normale, winkel: 2 * Math.PI, laenge: 2 * Math.PI * k.r, mitte: zentrum };
        return { ...basis, art: 'Bogen', radius: k.r, zentrum, normale, winkel, laenge: k.r * winkel, mitte: punktAufZug(p, lg / 2) };
      }
    }
  }
  return { ...basis, art: 'Kurve', mitte: punktAufZug(p, lg / 2) };
}

// Kleinster Abstand zwischen einem Strahl (o, Einheitsrichtung d) und der Strecke a-b
function strahlStrecke(o, d, a, b) {
  const u = sub(b, a);
  const w = sub(a, o);
  const uu = dot(u, u); const ud = dot(u, d); const uw = dot(u, w); const dw = dot(d, w);
  const nenner = uu - ud * ud;
  const s = Math.min(1, Math.max(0, nenner > 1e-12 ? (ud * dw - uw) / nenner : 0));
  const q = add(a, mul(u, s));
  const t = dot(sub(q, o), d);
  return { abstand: laenge(sub(q, add(o, mul(d, t)))), t, punkt: q };
}

// Nächste Kante zum Mauszeiger. Strahl in CAD-Koordinaten; proPixel = Weltmaß je Pixel in Abstand 1 vor der Kamera
// (2·tan(fov/2) / Bildhöhe). Kanten deutlich hinter der getroffenen Fläche (bisT) sind verdeckt.
// Liefert { kante, punkt, t, px } oder null.
export function kanteAmStrahl(kanten, o, d, { proPixel, fangPx = 8, bisT = Infinity }) {
  let best = null;
  for (const k of kanten) {
    const w = sub(k.kugel.m, o);
    const tk = dot(w, d);
    if (tk + k.kugel.r < 0) continue;
    const seitlich = laenge(sub(w, mul(d, tk)));
    if (seitlich - k.kugel.r > fangPx * proPixel * Math.max(tk + k.kugel.r, 1e-6)) continue;
    for (let i = 1; i < k.punkte.length; i++) {
      const r = strahlStrecke(o, d, k.punkte[i - 1], k.punkte[i]);
      if (r.t <= 0) continue;
      const px = r.abstand / (proPixel * r.t);
      if (px > fangPx || r.t > bisT + 3 * fangPx * proPixel * r.t + 1e-6) continue;
      if (!best || px < best.px - 0.75 || (Math.abs(px - best.px) <= 0.75 && r.t < best.t)) best = { kante: k, punkt: r.punkt, t: r.t, px };
    }
  }
  return best;
}

// Fangpunkt auf einer Kante: Kreis → Kreismitte; nahe am Ende → Endpunkt; Bogen → Bogenmitte (Mittelpunkt des Radius);
// nahe der Mitte → Kantenmitte; sonst der Punkt auf der Kante. toleranz = Weltmaß für Endpunkt und Mitte.
export function fangpunkt(treffer, toleranz) {
  const k = treffer.kante;
  if (k.art === 'Kreis') return { punkt: k.zentrum, art: 'Kreismitte', kante: k, achse: k.normale };
  for (const e of [k.start, k.ende]) if (laenge(sub(e, treffer.punkt)) <= toleranz) return { punkt: e, art: 'Endpunkt', kante: k };
  if (k.art === 'Bogen') return { punkt: k.zentrum, art: 'Bogenmitte', kante: k, achse: k.normale };
  if (laenge(sub(k.mitte, treffer.punkt)) <= toleranz * 1.5) return { punkt: k.mitte, art: 'Kantenmitte', kante: k };
  return { punkt: treffer.punkt, art: 'Kante', kante: k };
}

// Fangpunkt auf einer Fläche: Zylinder = Achse (Mitte von Bohrung oder Welle), Ebene = Punkt mit Normale
export function flaechenpunkt(klick, analyse) {
  const p = messpunkt(klick, analyse);
  if (analyse?.art === 'Zylinder') return { ...p, art: analyse.rundung ? 'Radiusmitte' : p.art, achse: analyse.achse, analyse };
  if (analyse?.art === 'Ebene') return { ...p, normale: analyse.normale, analyse };
  return { ...p, analyse };
}

// Abstand zweier Fangpunkte: parallele Ebenen senkrecht, Punkt oder Achse zu einer Ebene senkrecht, parallele Achsen
// als Achsabstand, sonst Punkt zu Punkt. Liefert { gesamt, dx, dy, dz, von, bis, art }.
export function messen(a, b) {
  const paar = (von, bis, art) => ({ ...abstand(von, bis), von, bis, art });
  const parallel = (x, y) => Math.abs(dot(x, y)) > 0.9995;
  if (a.normale && b.normale) {
    if (!parallel(a.normale, b.normale)) return paar(a.punkt, b.punkt, 'Punkt zu Punkt');
    const s = dot(sub(b.punkt, a.punkt), a.normale);
    return paar(sub(b.punkt, mul(a.normale, s)), b.punkt, 'Abstand der Flächen');
  }
  const zurEbene = (eb, p) => {
    if (p.achse && Math.abs(dot(p.achse, eb.normale)) > 1e-3 && p.art !== 'Kreismitte' && p.art !== 'Bogenmitte') return null;
    const s = dot(sub(p.punkt, eb.punkt), eb.normale);
    return [sub(p.punkt, mul(eb.normale, s)), p.punkt];
  };
  if (a.normale) { const r = zurEbene(a, b); if (r) return paar(r[0], r[1], 'senkrecht zur Fläche'); }
  if (b.normale) { const r = zurEbene(b, a); if (r) return paar(r[1], r[0], 'senkrecht zur Fläche'); }
  if (a.achse && b.achse && parallel(a.achse, b.achse) && !a.kante && !b.kante) {
    const d = sub(b.punkt, a.punkt);
    return paar(add(a.punkt, mul(a.achse, dot(d, a.achse))), b.punkt, 'Achsabstand');
  }
  return paar(a.punkt, b.punkt, 'Punkt zu Punkt');
}
