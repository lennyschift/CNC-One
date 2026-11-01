// Aus einer Mail-Anfrage Bauteile bilden: Zeichnung und Modell mit gleichem Dateinamen gehören zu einem Bauteil,
// die Menge steht oft im Mailtext ("ZZ-3D-001 Flansch, 10 Stück" oder "je 10/25/50 Stk").

const basis = (name) => (/^(.*?)(\.[^.]+)?$/.exec(name)?.[1] ?? name).trim();
const schluessel = (s) => s.toLowerCase().replace(/[\s_\-./]+/g, '');

// [{ basis, dateien }] je Bauteil, in der Reihenfolge der Mail
export function gruppieren(dateien) {
  const gruppen = new Map();
  for (const d of dateien) {
    const b = basis(d.name);
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

// Spalten einer Anfrage-Tabelle an der Überschrift erkennen (deutsch und englisch)
const SPALTE_TEIL = /part\s*-?\s*(no|nr|number|num)|partnumber|teile\s*-?\s*(nr|nummer)|sach\s*-?\s*(nr|nummer)|artikel|article|item\s*no|zeichnungs\s*-?\s*(nr|nummer)|drawing/i;
const SPALTE_MENGE = /^(menge|anzahl|stückzahl|stueckzahl|stk\.?|qty|quantity|pcs|pieces|amount\s*\(pcs\))/i;

// Mengen zu einem Bauteil aus Tabellen der Mail (Zeilen mit Zellentexten, vom Server gelesen): Zeile, deren Teilenummer
// zum Bauteil passt, Wert der Mengenspalte. Mehrere Werte (z. B. "10/25/50") = Staffel. [] wenn keine Tabelle passt.
export function mengenAusTabellen(tabellen, name) {
  const m = merkmale(name);
  for (const t of tabellen ?? []) {
    const kopf = t.findIndex((z) => z.some((c) => SPALTE_MENGE.test(c.trim())) && z.some((c) => SPALTE_TEIL.test(c)));
    if (kopf < 0) continue;
    const iMenge = t[kopf].findIndex((c) => SPALTE_MENGE.test(c.trim()));
    const iTeil = t[kopf].findIndex((c) => SPALTE_TEIL.test(c));
    for (const z of t.slice(kopf + 1)) {
      const nr = schluessel(z[iTeil] ?? '');
      if (nr.length >= 4 && m.some((k) => k.includes(nr) || nr.includes(k))) {
        const werte = zahlen(z[iMenge] ?? '');
        if (werte.length) return [...new Set(werte)].sort((a, b) => a - b);
      }
    }
  }
  return [];
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
