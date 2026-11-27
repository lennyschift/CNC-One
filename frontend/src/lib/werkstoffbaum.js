// Rohmaterial-Baum: ISO-Gruppe → Werkstoff → Zustand → Form → Ausführung → Abmessung, dazu Anforderungen (Werkszeugnis,
// Prüfungen) und Chargen im Rohmaterial-Lager. Reine Funktionen; die Daten kommen aus den Stammdaten (bootstrap.werkstoffbaum,
// bootstrap.materialien). Formen sind feste Geometrien, Abmessungen eine Reihe je Form (m1, m2 in mm).

export const FORMEN = [
  { id: 'Rund', label: 'Rund', m1: 'Ø' },
  { id: 'Vierkant', label: 'Vierkant', m1: 'Kante' },
  { id: 'Flach', label: 'Flach', m1: 'Breite', m2: 'Höhe' },
  { id: 'Sechskant', label: 'Sechskant', m1: 'SW' },
  { id: 'Rohr', label: 'Rohr', m1: 'Ø außen', m2: 'Wand' },
  { id: 'Platte', label: 'Platte', m1: 'Dicke' },
];
export const FORM_IDS = FORMEN.map((f) => f.id);

// Werkszeugnis nach EN 10204, aufsteigend: 3.2 erfüllt auch 3.1 usw.
export const ZEUGNISSE = ['', '2.2', '3.1', '3.2'];
export const zeugnisMax = (a, b) => (ZEUGNISSE.indexOf(a || '') >= ZEUGNISSE.indexOf(b || '') ? a || '' : b || '');
// Standard für neues Rohmaterial: Abnahmeprüfzeugnis 3.1, im Haus „WAZ“ genannt. „keins“ bleibt wählbar und gespeichert.
export const STANDARD_ZEUGNIS = '3.1';
// Beschriftung der Knöpfe
export const zeugnisKurz = (z) => (!z ? 'keins' : z === '3.1' ? '3.1 WAZ' : z);
// Bezeichnung für den Lieferanten (Anfrage-Mail): die Begriffe der EN 10204
export const zeugnisText = (z) => (!z ? '' : `${z === '2.2' ? 'Werkszeugnis' : 'Abnahmeprüfzeugnis'} ${z} (EN 10204)`);
// Anforderungen eines Rohteils; ohne eigene Angabe (neu angelegt) gilt der Standard, ein gespeichertes „keins“ bleibt
export const anforderungenVon = (roh) => roh?.anforderungen ?? { zeugnis: roh?.zeugnis ?? STANDARD_ZEUGNIS, pruefungen: [] };
// „Abnahmeprüfzeugnis 3.1 (EN 10204), RoHS/REACH“
export const anforderungenText = (a) => [zeugnisText(a?.zeugnis), ...(a?.pruefungen ?? [])].filter(Boolean).join(', ');

const n = (v) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : 0);
const z = (v) => String(Math.round(n(v) * 100) / 100).replace('.', ',');

// Formen eines Werkstoffs (leere Liste = alle)
export const formenVon = (w) => (w?.formen?.length ? FORM_IDS.filter((f) => w.formen.includes(f)) : FORM_IDS);
export const ausfuehrungenFuer = (baum, form, iso) => (baum?.ausfuehrungen ?? []).filter((a) => a.form === form && (!a.iso?.length || !iso || a.iso.includes(iso)));
export const abmessungenFuer = (baum, form) => (baum?.abmessungen ?? []).filter((a) => a.form === form);

export function masText(form, m1, m2 = 0) {
  switch (form) {
    case 'Rund': return `Ø${z(m1)}`;
    case 'Vierkant': return `□${z(m1)}`;
    case 'Flach': return `${z(m1)} × ${z(m2)}`;
    case 'Sechskant': return `SW${z(m1)}`;
    case 'Rohr': return `Ø${z(m1)} × ${z(m2)}`;
    case 'Platte': return `${z(m1)} mm`;
    default: return z(m1);
  }
}

// Querschnitt in mm² (Platte: 0, wird über die Fläche gerechnet)
export function querschnitt(form, m1, m2 = 0) {
  switch (form) {
    case 'Rund': return (Math.PI / 4) * n(m1) ** 2;
    case 'Vierkant': return n(m1) ** 2;
    case 'Flach': return n(m1) * n(m2);
    case 'Sechskant': return (Math.sqrt(3) / 2) * n(m1) ** 2;
    case 'Rohr': { const di = Math.max(n(m1) - 2 * n(m2), 0); return (Math.PI / 4) * (n(m1) ** 2 - di ** 2); }
    default: return 0;
  }
}
// Stangen: kg je Meter; Platte: kg je m² (Dicke in mm × Dichte)
export const kgJeMeter = (form, m1, m2, dichte) => (querschnitt(form, m1, m2) * n(dichte)) / 1000;
export const kgJeQm = (dicke, dichte) => n(dicke) * n(dichte);

// Rohteil-Felder (wie lib/rohmaterial.js sie rechnet) aus einer Abmessung; Länge/Breite des Zuschnitts bleiben
export function rohAusAbmessung(roh, abm) {
  const r = { ...roh, form: abm.form, abmessungId: abm.id, abmessung: abm.text, durchmesser: 0, innen: 0, schluesselweite: 0 };
  switch (abm.form) {
    case 'Rund': r.durchmesser = abm.m1; break;
    case 'Vierkant': r.breite = abm.m1; r.hoehe = abm.m1; break;
    case 'Flach': r.breite = abm.m1; r.hoehe = abm.m2; break;
    case 'Sechskant': r.schluesselweite = abm.m1; break;
    case 'Rohr': r.durchmesser = abm.m1; r.innen = Math.max(abm.m1 - 2 * abm.m2, 0); break;
    case 'Platte': r.hoehe = abm.m1; break;
    default: break;
  }
  if (abm.form !== 'Platte' && abm.form !== 'Flach' && abm.form !== 'Vierkant') r.breite = 0;
  if (!['Flach', 'Vierkant', 'Platte'].includes(abm.form)) r.hoehe = 0;
  return r;
}

// Passt die Abmessung auf den Bedarf? Bedarf: { form:'Rund', d, l } oder Quader { x, y, z } (Aufmaß schon enthalten)
const EPS = 1e-6;
function passt(abm, bed) {
  if (bed.form === 'Rund') {
    if (abm.form === 'Rund') return abm.m1 + EPS >= bed.d;
    return false;
  }
  const [a, b] = [bed.q1, bed.q2]; // Querschnitt (größer, kleiner), Länge = längste Seite
  if (abm.form === 'Vierkant') return abm.m1 + EPS >= a;
  if (abm.form === 'Flach') return abm.m1 + EPS >= a && abm.m2 + EPS >= b;
  if (abm.form === 'Rund') return abm.m1 + EPS >= Math.hypot(a, b);
  if (abm.form === 'Platte') return abm.m1 + EPS >= b;
  return false;
}
// Verschnitt je mm Länge (bzw. je mm Plattenlänge bei Platte: Dicke × Breite des Zuschnitts)
function flaeche(abm, bed) {
  if (abm.form === 'Platte') return abm.m1 * (bed.q1 ?? 0);
  return querschnitt(abm.form, abm.m1, abm.m2);
}

// Kleinste passende Abmessung für ein Rohteil aus dem 3D-Modell, nur in den Formen des Werkstoffs.
// r: { form:'Rund', durchmesser, laenge } oder { x, y, z }. Ergebnis: { abm, laenge, breite } oder null.
export function abmessungVorschlag(baum, w, r) {
  if (!r) return null;
  const formen = formenVon(w);
  let bed;
  if (r.form === 'Rund') bed = { form: 'Rund', d: n(r.durchmesser), l: n(r.laenge) };
  else {
    const [l, q1, q2] = [r.x, r.y, r.z].map(n).sort((a, b) => b - a);
    bed = { form: 'Quader', l, q1, q2 };
  }
  const kandidaten = (baum?.abmessungen ?? []).filter((a) => formen.includes(a.form) && passt(a, bed));
  if (!kandidaten.length) return null;
  const abm = kandidaten.reduce((best, a) => (flaeche(a, bed) < flaeche(best, bed) ? a : best));
  const auf = (v) => (n(v) ? Math.ceil(n(v) - EPS) : 0);
  return { abm, laenge: auf(bed.l), breite: abm.form === 'Platte' ? auf(bed.q1) : 0 };
}

// Artikeltext wie er bestellt und im Lager geführt wird, z. B. „EN AW-7075 T7351 · Rund Ø40 · gezogen h11“
export function artikelText(werkstoff, roh) {
  if (!werkstoff) return '';
  return [`${werkstoff} ${roh?.zustand || ''}`.trim(), roh?.abmessung ? `${roh.form} ${roh.abmessung}` : '', roh?.ausfuehrung].filter(Boolean).join(' · ');
}

// Anforderungen des Bauteils: eigene, mindestens die Vorgabe des Kunden
export function anforderungenMit(eigene, vorgabe) {
  const e = eigene ?? {};
  const v = vorgabe ?? {};
  return { zeugnis: zeugnisMax(e.zeugnis, v.zeugnis), pruefungen: [...new Set([...(v.pruefungen ?? []), ...(e.pruefungen ?? [])])] };
}

// Erfüllt eine Charge die Anforderungen? → { ok, fehlt: [...] }
export function chargePruefen(charge, anf) {
  const fehlt = [];
  if (anf?.zeugnis && ZEUGNISSE.indexOf(charge.zeugnis || '') < ZEUGNISSE.indexOf(anf.zeugnis)) fehlt.push(`Zeugnis ${anf.zeugnis}`);
  for (const p of anf?.pruefungen ?? []) if (!(charge.pruefungen ?? []).includes(p)) fehlt.push(p);
  return { ok: !fehlt.length, fehlt };
}

// Wie viele Zuschnitte gibt der Bestand einer Charge her? z = { laenge, breite, saege }
export function reichtFuer(charge, z) {
  const s = n(z?.saege);
  if (charge.form === 'Platte') {
    const b = n(z?.breite) + s;
    const l = n(z?.laenge) + s;
    if (!b || !l) return 0;
    return Math.max(Math.floor(n(charge.breite) / b) * Math.floor(n(charge.laenge) / l), Math.floor(n(charge.breite) / l) * Math.floor(n(charge.laenge) / b)) * Math.max(1, n(charge.stueck));
  }
  const l = n(z?.laenge) + s;
  return l ? Math.floor(n(charge.laenge) / l) * Math.max(1, n(charge.stueck)) : 0;
}

// Vorschlag aus dem 3D-Modell (lib/rohmaterial.js ausModell: Rund {durchmesser, laenge} oder Flach {laenge, breite, hoehe}, mit exakt)
// in die nächste passende Abmessung der Reihe umsetzen → { abm, laenge, breite } oder null
export function vorschlagAbmessung(baum, w, v) {
  if (!v) return null;
  const e = v.exakt ?? v;
  const r = v.form === 'Rund' ? { form: 'Rund', durchmesser: e.durchmesser, laenge: e.laenge } : { x: e.laenge, y: e.breite, z: e.hoehe };
  return abmessungVorschlag(baum, w, r);
}

// Bisheriges Rohteil ohne gewählte Abmessung (alte Bauteile): passende Abmessung aus seinen Maßen
export function abmessungAusAltemRoh(baum, w, roh) {
  if (!roh || roh.abmessungId) return null;
  if (roh.form === 'Rund' && roh.durchmesser) return abmessungVorschlag(baum, w, { form: 'Rund', durchmesser: roh.durchmesser, laenge: roh.laenge });
  if (roh.form === 'Flach' && roh.breite && roh.hoehe) return abmessungVorschlag(baum, w, { x: roh.laenge, y: roh.breite, z: roh.hoehe });
  return null;
}

// ---- Materialbedarf eines Angebots (alle Positionen), zusammengefasst je Artikel, mit Abgleich gegen das Rohmaterial-Lager.
// teile: Workbench-Teile; chargen: vorrätige Chargen. Bedarf in mm Stangenlänge (Platte: mm² Fläche) und kg, einmal für die
// Grundmenge (Stückzahl bzw. kleinste Staffel) und für die größte Staffel.
const mengenVon = (t) => {
  const st = t.staffel?.aktiv ? (t.staffel.stufen ?? []).map((s) => Math.max(1, Math.floor(n(s.menge)) || 1)) : [];
  return st.length ? [Math.min(...st), Math.max(...st)] : [Math.max(1, Math.floor(n(t.menge)) || 1), Math.max(1, Math.floor(n(t.menge)) || 1)];
};
export function materialBedarf(teile, chargen = []) {
  const gruppen = new Map();
  const unvollstaendig = [];
  for (const t of teile ?? []) {
    const r = t.roh ?? {};
    if (!t.material || !r.abmessungId || !n(r.laenge)) { unvollstaendig.push(t); continue; }
    const key = [t.material, r.zustand || '', r.abmessungId, r.ausfuehrung || ''].join('|');
    if (!gruppen.has(key)) {
      gruppen.set(key, { key, werkstoff: t.material, zustand: r.zustand || '', form: r.form, abmessungId: r.abmessungId, abmessung: r.abmessung || '', ausfuehrung: r.ausfuehrung || '', anforderungen: { zeugnis: '', pruefungen: [] }, teile: [], bedarf: 0, bedarfMax: 0, kg: 0, kgMax: 0 });
    }
    const g = gruppen.get(key);
    const [m0, m1] = mengenVon(t);
    const s = n(r.saege);
    const je = r.form === 'Platte' ? (n(r.laenge) + s) * (n(r.breite) + s) : n(r.laenge) + s;
    g.bedarf += je * m0;
    g.bedarfMax += je * m1;
    g.kg += n(t.gewichtKg) * m0;
    g.kgMax += n(t.gewichtKg) * m1;
    g.anforderungen = anforderungenMit(g.anforderungen, anforderungenVon(r));
    g.teile.push({ id: t.id, name: t.name, teilenummer: t.teilenummer, menge: m0, mengeMax: m1, zuschnitt: r.form === 'Platte' ? `${z(r.breite)} × ${z(r.laenge)}` : z(r.laenge) });
  }
  const liste = [...gruppen.values()].map((g) => {
    const passend = (chargen ?? []).filter((c) => c.werkstoff === g.werkstoff && c.abmessung === g.abmessungId && (!g.zustand || c.zustand === g.zustand) && (c.status ?? 'Vorrätig') === 'Vorrätig');
    const gute = passend.filter((c) => chargePruefen(c, g.anforderungen).ok);
    const vorrat = gute.reduce((sum, c) => sum + (c.form === 'Platte' ? n(c.breite) * n(c.laenge) : n(c.laenge) * Math.max(1, n(c.stueck))), 0);
    const status = vorrat >= g.bedarf - EPS ? 'lager' : vorrat > 0 ? 'teilweise' : 'bestellen';
    return { ...g, chargen: gute, ohneNachweis: passend.length - gute.length, vorrat, fehlt: Math.max(0, g.bedarf - vorrat), status };
  });
  return { liste, unvollstaendig };
}

// ---- Rohmaterial-Lager: interne Chargennummer, Filter und Gruppen je Material
// Muster wie auf dem Server (api/werkstoff.py interne_nr): {kuerzel} {JJJJ} {JJ} {MM} {TT}; {nr} wird hier als 1 gezeigt
export function interneChargennr(muster, kuerzel, eingang) {
  const d = eingang ? new Date(`${eingang}T00:00:00`) : new Date();
  const p2 = (x) => String(x).padStart(2, '0');
  return (muster || '{kuerzel}{MM}{JJ}').replaceAll('{kuerzel}', kuerzel || '').replaceAll('{JJJJ}', String(d.getFullYear()))
    .replaceAll('{JJ}', p2(d.getFullYear() % 100)).replaceAll('{MM}', p2(d.getMonth() + 1)).replaceAll('{TT}', p2(d.getDate())).replaceAll('{nr}', '1');
}
// Filter: { suche, werkstoff, form, abmessung, zustand, pruefung }
export function lagerFiltern(liste, f = {}) {
  const q = (f.suche ?? '').trim().toLowerCase();
  return (liste ?? []).filter((c) => (!f.werkstoff || c.werkstoff === f.werkstoff) && (!f.form || c.form === f.form)
    && (!f.abmessung || c.abmessung === f.abmessung) && (!f.zustand || c.zustand === f.zustand)
    && (!f.pruefung || (f.pruefung === 'zeugnis31' ? ['3.1', '3.2'].includes(c.zeugnis) : (c.pruefungen ?? []).includes(f.pruefung)))
    && (!q || [c.id, c.interneNr, c.chargennr, c.werkstoff, c.zustand, c.abmessungText, c.ausfuehrung, c.lieferant, c.lagerplatz, c.bemerkung, ...(c.pruefungen ?? [])].some((x) => (x || '').toLowerCase().includes(q))));
}
// Gruppen je Material (Werkstoff, Zustand, Form, Abmessung, Ausführung) mit Summe: Stangen/Platten und Meter bzw. m²
export function lagerGruppen(liste) {
  const g = new Map();
  for (const c of liste ?? []) {
    const key = [c.werkstoff, c.zustand, c.form, c.abmessung, c.ausfuehrung].join('|');
    if (!g.has(key)) g.set(key, { key, werkstoff: c.werkstoff, zustand: c.zustand, form: c.form, abmessungText: c.abmessungText, ausfuehrung: c.ausfuehrung, chargen: [], stueck: 0, meter: 0, qm: 0 });
    const x = g.get(key);
    x.chargen.push(c);
    if (c.status !== 'Vorrätig') continue;
    x.stueck += n(c.stueck) || 0;
    if (c.form === 'Platte') x.qm += (n(c.laenge) * n(c.breite) * Math.max(1, n(c.stueck))) / 1e6;
    else x.meter += (n(c.laenge) * Math.max(1, n(c.stueck))) / 1000;
  }
  return [...g.values()].map((x) => ({ ...x, chargen: x.chargen.sort((a, b) => (b.laenge * (b.stueck || 1)) - (a.laenge * (a.stueck || 1))) }))
    .sort((a, b) => a.werkstoff.localeCompare(b.werkstoff) || a.form.localeCompare(b.form) || (a.abmessungText || '').localeCompare(b.abmessungText || '', 'de', { numeric: true }));
}

// Posten des Lagers je Charge bündeln: eine Charge (interne Nummer, sonst Lieferanten-Charge) kann aus mehreren Posten
// bestehen, z. B. volle Stangen und Reststücke aus früheren Entnahmen. Reihenfolge der Chargen wie in der Liste,
// Posten je Charge nach Länge (volle zuerst). Summe: Stück und Meter bzw. m².
export function chargenBuendeln(liste) {
  const g = new Map();
  for (const c of liste ?? []) {
    const key = c.interneNr || c.chargennr || c.id;
    if (!g.has(key)) {
      g.set(key, {
        key, nr: c.interneNr || c.chargennr || c.id, chargennr: c.interneNr ? c.chargennr || '' : '', lieferant: c.lieferant || '', lieferantKurz: c.lieferantKurz || '',
        zeugnis: c.zeugnis || '', zeugnisDatei: c.zeugnisDatei || '', pruefungen: [], eingang: c.eingang || '', ok: true, fehlt: [], posten: [], stueck: 0, meter: 0, qm: 0, reicht: 0,
      });
    }
    const x = g.get(key);
    x.posten.push(c);
    for (const p of c.pruefungen ?? []) if (!x.pruefungen.includes(p)) x.pruefungen.push(p);
    if (c.ok === false) { x.ok = false; for (const f of c.fehlt ?? []) if (!x.fehlt.includes(f)) x.fehlt.push(f); }
    x.stueck += n(c.stueck);
    if (c.form === 'Platte') x.qm += (n(c.laenge) * n(c.breite) * Math.max(1, n(c.stueck))) / 1e6;
    else x.meter += (n(c.laenge) * Math.max(1, n(c.stueck))) / 1000;
    x.reicht += n(c.reicht);
  }
  return [...g.values()].map((x) => ({ ...x, posten: x.posten.sort((a, b) => (!!a.rest - !!b.rest) || n(b.laenge) * n(b.breite || 1) - n(a.laenge) * n(a.breite || 1)) }));
}
