// Anfrage-Tabellen in Mails deuten: welche Spalte ist Teilenummer, Menge, Liefertermin. Zuerst gilt die angelernte
// Vorlage (Kunde/Kontakt, Spaltenüberschriften), sonst Stichwörter. Werte je Zeile: Menge(n) und Liefertermin.

export const ROLLEN = [
  { id: 'teilenummer', label: 'Teilenummer' },
  { id: 'menge', label: 'Menge' },
  { id: 'liefertermin', label: 'Liefertermin' },
];

const STICHWORT = {
  teilenummer: /part\s*-?\s*(no|nr|number|num)\b|partnumber|teile?\s*-?\s*(nr|nummer)|sach\s*-?\s*(nr|nummer)|artikel\s*-?\s*(nr|nummer)?|article|item\s*no|material\s*-?\s*(nr|nummer)|zeichnungs\s*-?\s*(nr|nummer)|drawing\s*(no|number)/i,
  menge: /^(menge|anzahl|stückzahl|stueckzahl|stk\.?|qty\.?|quantity|pcs\.?|pieces|bestellmenge|anfragemenge)\b/i,
  liefertermin: /liefer\s*-?\s*(termin|datum|date)|wunsch\s*-?\s*termin|delivery|due\s*date|^termin$|^lt$/i,
};

export const kopfText = (s) => (s ?? '').toLowerCase().split(/\s+/).filter(Boolean).join(' ');
const schluessel = (s) => (s ?? '').toLowerCase().replace(/[\s_\-./]+/g, '');

const GEWICHT = { vorlage: 100, stichwort: 10, inhalt: 1 };
const IST_MENGE = /^\d{1,3}([.,]?\d{3})*\s*(stk\.?|st\.?|pcs\.?|stück)?(\s*[/;,]\s*\d{1,3}([.,]?\d{3})*\s*(stk\.?|st\.?|pcs\.?|stück)?)*$/i;

// Ist der Text ein Wert dieser Rolle (und damit keine Überschrift)?
function istWert(rolle, text, dateien) {
  if (rolle === 'menge') return IST_MENGE.test(text.trim());
  if (rolle === 'liefertermin') return !!datumAus(text);
  return dateien.some((d) => passtZu(text, d));
}

// Werte einer Spalte (ohne leere Zellen)
const spalte = (zeilen, i) => zeilen.map((z) => (z[i] ?? '').trim()).filter(Boolean);
const anteil = (werte, test) => (werte.length ? werte.filter(test).length / werte.length : 0);

// Spaltenrollen aus Kopfzeile (Vorlage, dann Stichwörter) und, wo das nicht reicht, aus dem Inhalt der Datenzeilen:
// Teilenummer = Spalte, deren Werte zu den Dateien der Mail passen; Menge = Zahlenspalte, die keine laufende Nummer
// ist; Liefertermin = Datumsspalte, bei mehreren die mit den späteren Daten. Liefert { rollen, quellen }.
function rollenFuer(kopf, zeilen, vorlage = {}, dateien = []) {
  const breite = Math.max(kopf.length, ...zeilen.map((z) => z.length));
  const rollen = Array(breite).fill('');
  const quellen = Array(breite).fill('');
  const setzen = (i, r, q) => { rollen[i] = r; quellen[i] = q; };
  for (const r of ROLLEN) {
    const v = vorlage[r.id];
    const i = v ? kopf.findIndex((c, j) => !rollen[j] && kopfText(c) === v) : -1;
    if (i >= 0) setzen(i, r.id, 'vorlage');
  }
  for (const r of ROLLEN) {
    if (rollen.includes(r.id)) continue;
    const i = kopf.findIndex((c, j) => !rollen[j] && STICHWORT[r.id].test((c ?? '').trim()));
    if (i >= 0) setzen(i, r.id, 'stichwort');
  }
  const frei = () => [...Array(breite).keys()].filter((i) => !rollen[i]);
  if (!rollen.includes('teilenummer') && dateien.length) {
    const treffer = frei().map((i) => [i, spalte(zeilen, i).filter((w) => dateien.some((d) => passtZu(w, d))).length]).sort((a, b) => b[1] - a[1])[0];
    if (treffer?.[1]) setzen(treffer[0], 'teilenummer', 'inhalt');
  }
  if (!rollen.includes('menge')) {
    const kandidat = frei().map((i) => {
      const w = spalte(zeilen, i);
      const laufend = w.length > 1 && w.every((x, n) => x === String(n + 1));
      return [i, laufend ? 0 : anteil(w, (x) => IST_MENGE.test(x)), w.length];
    }).filter(([, a, n]) => a >= 0.6 && n).sort((a, b) => b[1] - a[1] || b[2] - a[2])[0];
    if (kandidat) setzen(kandidat[0], 'menge', 'inhalt');
  }
  if (!rollen.includes('liefertermin')) {
    const kandidat = frei().map((i) => {
      const daten = spalte(zeilen, i).map(datumAus);
      return [i, anteil(daten, Boolean), daten.filter(Boolean).sort().at(-1) ?? ''];
    }).filter(([, a]) => a >= 0.6).sort((a, b) => (b[2] > a[2] ? 1 : b[2] < a[2] ? -1 : 0))[0];
    if (kandidat) setzen(kandidat[0], 'liefertermin', 'inhalt');
  }
  return { rollen, quellen };
}

// Die passende Tabelle der Mail mit Kopfzeile und Spaltenrollen, oder null. Gebraucht werden die Teilenummer und Menge
// oder Liefertermin. Als Kopfzeile kommen die ersten drei Zeilen in Frage oder keine (dann zählt nur der Inhalt).
// `dateien`: Namen der Zeichnungen/Modelle in der Mail (für die Teilenummer-Spalte nach Inhalt).
export function tabelleDeuten(tabellen, vorlage = {}, dateien = []) {
  let beste = null;
  (tabellen ?? []).forEach((t, ti) => {
    for (let k = -1; k < Math.min(3, t.length - 1); k++) {
      const kopf = k >= 0 ? t[k] : [];
      const zeilen = t.slice(k + 1);
      const { rollen, quellen } = rollenFuer(kopf, zeilen, vorlage, dateien);
      if (!rollen.includes('teilenummer') || !(rollen.includes('menge') || rollen.includes('liefertermin'))) continue;
      // Eine Kopfzeile, deren Zellen in den erkannten Spalten selbst keine Werte sind, ist wahrscheinlich die Überschrift
      const wieKopf = k >= 0 && rollen.every((r, i) => !r || !istWert(r, kopf[i] ?? '', dateien));
      const wert = quellen.reduce((s, q) => s + (GEWICHT[q] ?? 0), 0) + (wieKopf ? 0.5 : 0);
      if (!beste || wert > beste.wert) beste = { tabelle: ti, kopf: k, rollen, quellen, wert, zeilen };
    }
  });
  if (!beste) return null;
  const { wert, ...rest } = beste;
  return { ...rest, kopfzeile: beste.kopf >= 0 ? tabellen[beste.tabelle][beste.kopf] : [] };
}

// Spaltenrollen für eine selbst gewählte Kopfzeile (k = -1: keine Kopfzeile)
export function rollenMitKopf(tabelle, k, vorlage = {}, dateien = []) {
  return rollenFuer(k >= 0 ? tabelle[k] : [], tabelle.slice(k + 1), vorlage, dateien);
}

// Menge(n) aus einer Zelle: "2", "1.000 Stk", "10/25/50" (= Staffel)
export function mengenAus(text) {
  const werte = (text ?? '').split(/[^\d.]+/).map((x) => Number(x.replace(/\./g, ''))).filter((n) => Number.isInteger(n) && n > 0 && n < 1e7);
  return [...new Set(werte)].sort((a, b) => a - b);
}

// Datum (ISO yyyy-mm-dd) aus einer Zelle: 20.11.2026, 20.11..2026 00:00:00, 20.11.26, 2026-11-20, 20/11/2026
export function datumAus(text) {
  const t = (text ?? '').trim();
  let j, m, d;
  const iso = /(\d{4})-(\d{1,2})-(\d{1,2})/.exec(t);
  const de = /(\d{1,2})\s*[./]+\s*(\d{1,2})\s*[./]+\s*(\d{2,4})/.exec(t);
  if (iso) [, j, m, d] = iso.map(Number);
  else if (de) { [, d, m, j] = de.map(Number); if (j < 100) j += 2000; } else return '';
  const datum = new Date(Date.UTC(j, m - 1, d));
  if (datum.getUTCFullYear() !== j || datum.getUTCMonth() !== m - 1 || datum.getUTCDate() !== d) return '';
  return `${j}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

// Werte einer Datenzeile nach den Spaltenrollen
export function zeileWerte(zeile, rollen) {
  const zelle = (rolle) => { const i = rollen.indexOf(rolle); return i >= 0 ? (zeile[i] ?? '') : ''; };
  return { teilenummer: zelle('teilenummer').trim(), menge: mengenAus(zelle('menge')), liefertermin: datumAus(zelle('liefertermin')) };
}

// Passt eine Teilenummer aus der Tabelle zu einem Dateinamen (Bauteil aus der Mail)?
export function passtZu(teilenummer, dateiname) {
  const nr = schluessel(teilenummer);
  if (nr.length < 4) return false;
  const basis = (/^(.*?)(\.[^.]+)?$/.exec(dateiname)?.[1] ?? dateiname);
  const merkmale = [schluessel(basis), schluessel(basis.split(/[\s_]+/)[0] ?? '')].filter((k) => k.length >= 4);
  return merkmale.some((k) => k.includes(nr) || nr.includes(k));
}

// Überschriften der Spalten je Rolle, zum Anlernen: { teilenummer: 'partnumber', menge: 'quantity', ... }
export function vorlageAus(kopfzeile, rollen) {
  return Object.fromEntries(rollen.map((r, i) => [r, kopfText(kopfzeile[i])]).filter(([r, k]) => r && k));
}
