// Rohmaterial eines Bauteils: Form und Maße des Rohteils, daraus Volumen und Gewicht. Reine Funktionen ohne UI.
// teil.roh = { form, durchmesser, innen, schluesselweite, breite, hoehe, laenge, gewichtAuto, zeugnis, ausLager, lagerHinweis }
// Maße in mm, Gewicht in kg, Dichte in kg/dm³ (= g/cm³). Das Aufmaß steckt schon in den Maßen (so wird bestellt).

export const FORMEN = [
  { id: 'Rund', label: 'Rund', felder: ['durchmesser', 'laenge'] },
  { id: 'Flach', label: 'Flach / Block', felder: ['breite', 'hoehe', 'laenge'] },
  { id: 'Rohr', label: 'Rohr', felder: ['durchmesser', 'innen', 'laenge'] },
  { id: 'Sechskant', label: 'Sechskant', felder: ['schluesselweite', 'laenge'] },
];

export const FELD_LABEL = { durchmesser: 'Ø außen', innen: 'Ø innen', schluesselweite: 'SW', breite: 'Breite', hoehe: 'Höhe', laenge: 'Länge' };
export const ZEUGNISSE = ['', '2.2', '3.1', '3.2'];

const n = (v) => {
  const x = Number(v);
  return Number.isFinite(x) && x > 0 ? x : 0;
};

export function leeresRoh() {
  return { form: 'Rund', durchmesser: 0, innen: 0, schluesselweite: 0, breite: 0, hoehe: 0, laenge: 0, gewichtAuto: true, zeugnis: '', ausLager: false, lagerHinweis: '' };
}

// Volumen in mm³ (0, wenn Maße fehlen)
export function rohVolumen(roh) {
  if (!roh) return 0;
  const l = n(roh.laenge);
  switch (roh.form) {
    case 'Rund': return (Math.PI / 4) * n(roh.durchmesser) ** 2 * l;
    case 'Rohr': {
      const da = n(roh.durchmesser);
      const di = Math.min(n(roh.innen), da);
      return (Math.PI / 4) * (da ** 2 - di ** 2) * l;
    }
    case 'Sechskant': return (Math.sqrt(3) / 2) * n(roh.schluesselweite) ** 2 * l;
    case 'Flach': return n(roh.breite) * n(roh.hoehe) * l;
    default: return 0;
  }
}

// Gewicht in kg auf Gramm gerundet
export const rohGewicht = (roh, dichte) => Math.round((rohVolumen(roh) / 1e6) * n(dichte) * 1000) / 1000;

// Sind alle Maße der Form eingetragen?
export const vollstaendig = (roh) => !!roh && (FORMEN.find((f) => f.id === roh.form)?.felder ?? []).filter((f) => f !== 'innen').every((f) => n(roh[f]) > 0);

const zahl = (v) => String(Math.round(n(v) * 10) / 10).replace('.', ',');

// Kurzer Text, z. B. „Rund Ø45 × 82“, „Flach 60 × 20 × 120“
export function rohText(roh) {
  if (!roh || !vollstaendig(roh)) return '';
  switch (roh.form) {
    case 'Rund': return `Rund Ø${zahl(roh.durchmesser)} × ${zahl(roh.laenge)}`;
    case 'Rohr': return `Rohr Ø${zahl(roh.durchmesser)}${n(roh.innen) ? ` × Ø${zahl(roh.innen)}` : ''} × ${zahl(roh.laenge)}`;
    case 'Sechskant': return `Sechskant SW${zahl(roh.schluesselweite)} × ${zahl(roh.laenge)}`;
    case 'Flach': return `Flach ${zahl(roh.breite)} × ${zahl(roh.hoehe)} × ${zahl(roh.laenge)}`;
    default: return '';
  }
}

// Auf volle Millimeter aufrunden (Rohmaß zum Bestellen); kleine Rechenreste (z. B. 45,0000001) zählen nicht
export const aufrunden = (v) => (n(v) ? Math.ceil(n(v) - 1e-6) : 0);

// Vorschlag aus dem 3D-Modell (Rohteil aus dem Viewer, Aufmaß schon enthalten) als Rohmaterial, auf volle mm aufgerundet.
// Quader: längste Seite wird die Länge, dann Breite ≥ Höhe.
export function ausModell(r) {
  if (!r) return null;
  if (r.form === 'Rund') return { form: 'Rund', durchmesser: aufrunden(r.durchmesser), laenge: aufrunden(r.laenge), drehteil: !!r.drehteil, exakt: { durchmesser: r.durchmesser, laenge: r.laenge } };
  const [l, b, h] = [r.x, r.y, r.z].map(n).sort((a, c) => c - a);
  return { form: 'Flach', laenge: aufrunden(l), breite: aufrunden(b), hoehe: aufrunden(h), exakt: { laenge: l, breite: b, hoehe: h } };
}

// Vorschlag ins Rohmaterial übernehmen: Form und Maße setzen, Übriges (Zeugnis, Lager) bleibt
export function vorschlagAnwenden(roh, v) {
  const basis = { ...leeresRoh(), ...(roh ?? {}) };
  for (const f of ['durchmesser', 'innen', 'schluesselweite', 'breite', 'hoehe', 'laenge']) basis[f] = 0;
  return { ...basis, form: v.form, ...Object.fromEntries(Object.entries(v).filter(([k]) => FELD_LABEL[k])) };
}
