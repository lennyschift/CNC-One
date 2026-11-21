// Anhänge einer Mail je Bauteil gruppieren: Zeichnung (PDF) und 3D-Modell (STEP) mit demselben Namen gehören zusammen,
// damit man sofort sieht, ob beides da ist. Erkannt am Dateinamen ohne Endung und ohne Zusätze wie „Zeichnung“, „3D“,
// „drw“, „Modell“; aus einer ZIP mit Dateien wie „Zeichnung.pdf“ + „Modell.stp“ zählt der Ordner (oft die Teilenummer).

const ZUSATZ = /(^|[\s_\-.])(zeichnung|zeichn|drawing|drw|zng|modell|model|3d|cad|step|stp|pdf)(?=$|[\s_\-.])/gi;
const ART = (name) => {
  const n = (name || '').toLowerCase();
  if (n.endsWith('.pdf')) return 'pdf';
  if (/\.(stp|step|igs|iges)$/.test(n)) return 'step';
  return '';
};

export function bauteilSchluessel(a) {
  const stamm = (a.name || '').replace(/\.[^.]+$/, '');
  const ohne = stamm.replace(ZUSATZ, ' ').replace(/[\s_\-.]+/g, ' ').trim().toLowerCase();
  if (ohne) return ohne;
  return (a.ordner || stamm).toLowerCase().trim();
}

// [{ schluessel, name, pdf, step }] für Zeichnungen und Modelle (in der Reihenfolge des ersten Auftretens),
// dazu `sonstige` (Tabellen, ZIPs, Bilder …). Mehrere PDFs zum selben Bauteil bekommen je eine eigene Zeile.
export function bauteilGruppen(anhaenge) {
  const gruppen = [];
  const sonstige = [];
  for (const a of anhaenge || []) {
    const art = ART(a.name);
    if (!art) { sonstige.push(a); continue; }
    const schluessel = bauteilSchluessel(a);
    let g = gruppen.find((x) => x.schluessel === schluessel && !x[art]);
    if (!g) {
      g = { schluessel, name: '', pdf: null, step: null };
      gruppen.push(g);
    }
    g[art] = a;
    if (!g.name) g.name = (a.name || '').replace(/\.[^.]+$/, '');
  }
  return { gruppen, sonstige };
}
