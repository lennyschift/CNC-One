// Aus einer Mail-Anfrage Bauteile bilden: Zeichnung und Modell mit gleichem Dateinamen gehören zu einem Bauteil,
// die Menge steht oft im Mailtext ("ZZ-3D-001 Flansch, 10 Stück" oder "je 10/25/50 Stk").

const basis = (name) => (/^(.*?)(\.[^.]+)?$/.exec(name)?.[1] ?? name).trim();
const schluessel = (s) => s.toLowerCase().replace(/[\s_\-./]+/g, '');

// Name einer Datei mit ihrem Ordner aus der ZIP ("4711-A/Zeichnung.pdf"), eindeutig auch bei gleichen Dateinamen
export const dateiPfad = (d) => (d.ordner ? `${d.ordner}/${d.name}` : d.name);

// Aus einer ZIP: Liegen Zeichnung und Modell in einem eigenen Ordner und heißen nicht wie das Bauteil
// ("4711-A/Zeichnung.pdf", "4711-A/Modell.stp"), ist der Ordner das Bauteil. Ein Sammelordner mit mehreren
// Zeichnungen oder Modellen ("Zeichnungen/") ist es nicht, dort zählt der Dateiname.
function ordnerIstBauteil(d, dateien) {
  if (!d.ordner) return false;
  const imOrdner = dateien.filter((x) => x.ordner === d.ordner);
  if (imOrdner.filter((x) => x.art === 'Zeichnung').length > 1 || imOrdner.filter((x) => x.art === 'STEP').length > 1) return false;
  const k = schluessel(basis(d.name));
  return new Set(imOrdner.map((x) => schluessel(basis(x.name)))).size > 1 || dateien.some((x) => x.ordner !== d.ordner && schluessel(basis(x.name)) === k);
}

// [{ basis, dateien }] je Bauteil, in der Reihenfolge der Mail
export function gruppieren(dateien) {
  const gruppen = new Map();
  for (const d of dateien) {
    const b = ordnerIstBauteil(d, dateien) ? d.ordner : basis(d.name);
    const k = schluessel(b);
    if (!gruppen.has(k)) gruppen.set(k, { basis: b, dateien: [] });
    gruppen.get(k).dateien.push(d);
  }
  return [...gruppen.values()];
}

const EINHEIT = String.raw`(?:stück|stueck|stk\.?|st\.|pcs\.?|pieces|pc\.?)`;
const ZAHLEN = new RegExp(String.raw`((?:\d[\d.]*\s*(?:,|/|;|\+|und|u\.|oder|bzw\.?)\s*)*\d[\d.]*)\s*${EINHEIT}(?![a-zäöü])`, 'gi');
const MENGE = /(?:menge|anzahl|stückzahl|qty|quantity)\s*[:=]?\s*((?:\d[\d.]*\s*(?:,|\/|;|und)\s*)*\d[\d.]*)/gi;

const zahlen = (s) => s.split(/[^\d.]+/).map((x) => Number(x.replace(/\./g, ''))).filter((n) => Number.isInteger(n) && n > 0 && n < 1e7);

// Erkennungsmerkmale eines Bauteils im Text: der ganze Dateiname und sein erster Teil (meist die Teilenummer)
function merkmale(name) {
  const teile = name.split(/[\s_]+/).filter(Boolean);
  return [...new Set([schluessel(name), schluessel(teile[0] ?? '')])].filter((k) => k.length >= 4);
}

// Mengen zu einem Bauteil aus dem Mailtext, aufsteigend (mehrere = Staffel). Gesucht wird in den Zeilen, die das
// Bauteil nennen; nennt keine Zeile ein Bauteil und gibt es nur eines, zählt der ganze Text.
export function mengenAusText(text, name, { einziges = false } = {}) {
  const zeilen = (text ?? '').split(/\n/);
  const m = merkmale(name);
  let treffer = zeilen.filter((z) => m.some((k) => schluessel(z).includes(k)));
  if (!treffer.length && einziges) treffer = zeilen;
  const gefunden = [];
  for (const z of treffer) {
    for (const r of z.matchAll(ZAHLEN)) gefunden.push(...zahlen(r[1]));
    for (const r of z.matchAll(MENGE)) gefunden.push(...zahlen(r[1]));
  }
  return [...new Set(gefunden)].sort((a, b) => a - b);
}
