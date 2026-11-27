// Bestellung des Kunden aus dem PDF lesen: Kopf (Bestellnummer, Datum) und Positionen (Position, Teilenummer,
// Bezeichnung, Menge, Stückpreis, Preiseinheit, Betrag, Liefertermin). Grundlage ist der Text der Seiten mit Lage
// (zeichnungText.js). Die Spalten kommen aus der Kopfzeile der Tabelle: zuerst die angelernte Vorlage des Kunden, sonst
// Stichwörter. Eine Position beginnt mit einer Zeile, die eine Menge hat; weitere Zeilen (Text, Liefertermin,
// Zeichnung …) gehören dazu, bis die nächste Position beginnt. Den Text der ganzen Position bekommt der Server, er sucht
// darin auch die Teilenummern der Bauteile des Kunden.
// Zweizeilige Spalten: eine Überschrift wie „Details / Materialnummer“ oder „Lief.dat. / MOD Dat.“ hat zwei Rollen, die
// erste gilt für die Zeile der Position, die zweite für die Zeile darunter. Jede Spalte des PDFs landet außerdem in
// `angaben` der Position (Überschrift und Wert), damit nichts aus der Bestellung verloren geht.
import { datumAus } from './mailtabelle.js';

export const ROLLEN = [
  { id: 'bestellposition', label: 'Position' },
  { id: 'teilenummer', label: 'Teilenummer' },
  { id: 'bezeichnung', label: 'Bezeichnung' },
  { id: 'menge', label: 'Menge' },
  { id: 'preis', label: 'Stückpreis' },
  { id: 'preiseinheit', label: 'Preiseinheit' },
  { id: 'betrag', label: 'Betrag' },
  { id: 'liefertermin', label: 'Liefertermin' },
  { id: 'einheit', label: 'Einheit' },
  { id: 'zeichnungsdatum', label: 'Zeichnungsdatum / -stand' },
];

// Reihenfolge zählt: Betrag und Preiseinheit vor Preis ("Gesamtpreis", "Preiseinheit")
const STICHWORT = [
  ['bestellposition', /^(pos\.?|position|pos\.?\s*-?\s*nr\.?|item|lfd\.?\s*nr\.?|nr\.?)$/i],
  ['betrag', /gesamt|netto\s*-?\s*wert|^wert|betrag|amount|total|summe/i],
  ['preiseinheit', /preiseinheit|^pe$|^p\.?e\.?$|price\s*unit|^per$/i],
  ['preis', /preis|price|^e-?p$/i],
  ['menge', /^(bestell)?menge|anzahl|^qty|quantity|stückzahl|^stk\.?$|^anz\.?$/i],
  // Zeichnungsdatum vor Liefertermin und Bezeichnung („Zeichnungsdatum“, „MOD Dat.“, „Änderungsstand“)
  ['zeichnungsdatum', /zeichnungs?\s*-?\s*(datum|stand)|^mod\.?\s*-?\s*dat|änderungs\s*-?\s*(datum|stand)|ausgabe\s*-?\s*(datum|stand)|revision\s*-?\s*date|drawing\s*date/i],
  ['liefertermin', /lief(er)?\.?\s*-?\s*(termin|datum|dat\.?|date)|delivery|^termin|^lt$|wunschtermin|due/i],
  ['einheit', /^(me|einh\.?|einheit|mengeneinheit|unit|uom|bme)$/i],
  // Bezeichnung vor Teilenummer: "Bezeichnung" enthält "zeichnung"
  ['bezeichnung', /bezeichnung|beschreibung|kurztext|^text$|description|benennung|^details?$/i],
  ['teilenummer', /(material|artikel|teile|teil|sach|ident|part|kunden)\s*-?\s*(nr|nummer|no|number)?\.?$|^zeichnung|zeichnungs\s*-?\s*(nr|nummer)|drawing/i],
];

export const kopfText = (s) => (s ?? '').toLowerCase().split(/\s+/).filter(Boolean).join(' ');

// Zahl aus "1.234,56", "1,234.56", "12,5", "1.000", "26,00 EUR", "10 ST"
export function zahlAus(text) {
  let t = String(text ?? '').replace(/[^\d.,-]/g, '');
  if (!/\d/.test(t)) return null;
  const komma = t.lastIndexOf(','), punkt = t.lastIndexOf('.');
  if (komma >= 0 && punkt >= 0) t = komma > punkt ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '');
  // nur Komma: Dezimalkomma, außer bei mehreren Tausendergruppen ("1,000,000")
  else if (komma >= 0) t = /^-?\d{1,3}(,\d{3}){2,}$/.test(t) ? t.replace(/,/g, '') : t.replace(',', '.');
  else if (punkt >= 0 && /^-?\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

// Preiseinheit aus Text: "pro 100", "/ 100 ST", "per 1000", "je 100 Stk"
export function preiseinheitAus(text) {
  const m = /(?:pro|per|je|\/)\s*(\d{1,3}(?:[.,]?\d{3})*)\s*(?:st|stk|stück|pc|pcs|ea)?\b/i.exec(text ?? '');
  const n = m ? zahlAus(m[1]) : null;
  return n && n > 1 ? n : 1;
}

// Zeilen aus den Textstücken aller Seiten: gleiche Höhe = eine Zeile, nahe Stücke = eine Zelle
export function zeilenAus(seiten) {
  const zeilen = [];
  (seiten ?? []).forEach((s, si) => {
    const el = [...(s.elemente ?? [])].sort((a, b) => a.y - b.y || a.x - b.x);
    const gruppen = [];
    for (const e of el) {
      const g = gruppen.at(-1);
      if (g && Math.abs(g.y - e.y) <= Math.max(0.004, Math.min(g.h, e.h) * 0.5)) g.el.push(e);
      else gruppen.push({ y: e.y, h: e.h, el: [e] });
    }
    for (const g of gruppen) {
      const sortiert = g.el.sort((a, b) => a.x - b.x);
      const zellen = [];
      for (const e of sortiert) {
        const z = zellen.at(-1);
        const luecke = z ? e.x - z.x2 : 1;
        if (z && luecke < Math.max(0.006, e.h * 0.45)) { z.text += (luecke > e.h * 0.12 ? ' ' : '') + e.text; z.x2 = Math.max(z.x2, e.x + e.b); }
        else zellen.push({ text: e.text, x: e.x, x2: e.x + e.b });
      }
      zeilen.push({ seite: si, y: g.y, zellen });
    }
  });
  return zeilen;
}

const zeilenText = (z) => z.zellen.map((c) => c.text).join(' ');

const stichwort = (t) => STICHWORT.find(([, re]) => re.test(t))?.[0] ?? '';
// Rolle(n) einer Überschrift; „A / B“ ergibt zwei Rollen (oben und darunter). In der Vorlage steht dann „a|b“.
function rolleFuer(text, vorlage) {
  const k = kopfText(text);
  if (vorlage?.spalten?.[k]) {
    const [rolle, rolle2 = ''] = String(vorlage.spalten[k]).split('|');
    return { rolle, rolle2, quelle: 'vorlage' };
  }
  const t = (text ?? '').trim();
  if (t.length > 40) return null;
  const teile = t.split(/\s+\/\s+|\s*\/\s*(?=[A-ZÄÖÜa-zäöü]{2})/).map((x) => x.trim()).filter(Boolean);
  if (teile.length === 2) {
    const [a, b] = teile.map(stichwort);
    if (a || b) return { rolle: a || b, rolle2: a && b && a !== b ? b : '', quelle: 'stichwort' };
  }
  const s = stichwort(t);
  return s ? { rolle: s, rolle2: '', quelle: 'stichwort' } : null;
}

// Kopfzeile der Positionstabelle: die Zeile mit den meisten erkannten Spalten (mindestens Menge und eine weitere)
// Umgebrochene Überschrift („Preis pro“ / „Einheit in EUR“, auch vertikal zentriert über drei Zeilen): die Zeilen
// i … i+anzahl-1 ohne Ziffern, dicht untereinander, werden nach ihrer Lage zu Spalten zusammengefasst
function kopfMitUmbruch(zeilen, i, anzahl) {
  const teil = zeilen.slice(i, i + anzahl);
  if (teil.length < anzahl || teil.some((z, k) => z.seite !== teil[0].seite || (k && z.y - teil[k - 1].y > 0.025) || z.zellen.some((c) => /\d/.test(c.text)))) return null;
  const zellen = [];
  for (const u of teil.flatMap((z) => z.zellen)) {
    const k = zellen.find((c) => Math.min(c.x2, u.x2) - Math.max(c.x, u.x) > 0);
    if (k) { k.text = `${k.text} ${u.text}`; k.x = Math.min(k.x, u.x); k.x2 = Math.max(k.x2, u.x2); } else zellen.push({ ...u });
  }
  return zellen.sort((a, b) => a.x - b.x);
}

export function kopfzeileFinden(zeilen, vorlage = {}) {
  let beste = null;
  const pruefen = (zellen, i) => {
    const spalten = zellen.map((c) => ({ ...c, ...(rolleFuer(c.text, vorlage) ?? { rolle: '', rolle2: '', quelle: '' }) }));
    const rollen = new Set(spalten.flatMap((s) => [s.rolle, s.rolle2]).filter(Boolean));
    if (!rollen.has('menge') || rollen.size < 2) return;
    const wert = spalten.reduce((n, s) => n + (s.quelle === 'vorlage' ? 10 : s.quelle ? 1 : 0), 0);
    if (!beste || wert > beste.wert) beste = { index: i, wert, spalten };
  };
  zeilen.forEach((z, i) => {
    pruefen(z.zellen, i);
    for (const anzahl of [2, 3]) {
      const mit = kopfMitUmbruch(zeilen, i, anzahl);
      if (!mit) break;
      const vorher = beste;
      pruefen(mit, i + anzahl - 1);
      // die Einzelteile der umgebrochenen Überschrift erkennen die wiederholte Kopfzeile auf Folgeseiten
      if (beste !== vorher) beste.teile = zeilen.slice(i, i + anzahl).flatMap((x) => x.zellen).map((c) => c.text);
    }
  });
  return beste;
}

// Spalte einer Zelle: die Kopfzelle mit der größten Überdeckung, sonst die nächste (Zahlen stehen oft rechtsbündig)
function spalteVon(zelle, spalten) {
  let beste = -1, wert = -Infinity;
  spalten.forEach((s, i) => {
    const ueber = Math.min(zelle.x2, s.x2) - Math.max(zelle.x, s.x);
    const abstand = Math.min(Math.abs((zelle.x + zelle.x2) / 2 - (s.x + s.x2) / 2), Math.abs(zelle.x2 - s.x2), Math.abs(zelle.x - s.x));
    const w = ueber > 0 ? 1 + ueber : -abstand;
    if (w > wert) { wert = w; beste = i; }
  });
  return beste;
}

// Summenzeilen beenden die Tabelle („Ust-IdNr.“ in der Fußzeile nicht)
const ENDE = /^(gesamt|summe|zwischensumme|total|nettowert|netto\s*gesamt|gesamtnetto|endbetrag|mwst\b|ust\b(?!\s*-?\s*id))/i;

// Liefertermin als Kalenderwoche („KW50“, „KW 3/2027“): Freitag dieser Woche (ISO-Woche). Ohne Jahr das Jahr der
// Bestellung, liegt die Woche davor, das nächste.
export function kwDatum(text, bezug = '') {
  const m = /\bKW\s*(\d{1,2})(?:\s*[/.\-]\s*(\d{2,4}))?/i.exec(text ?? '');
  if (!m) return '';
  const woche = Number(m[1]);
  if (woche < 1 || woche > 53) return '';
  const start = bezug ? new Date(`${bezug}T00:00:00Z`) : new Date();
  let jahr = m[2] ? (Number(m[2]) < 100 ? 2000 + Number(m[2]) : Number(m[2])) : start.getUTCFullYear();
  const freitag = (j) => {
    const jan4 = new Date(Date.UTC(j, 0, 4));
    const montag1 = new Date(jan4);
    montag1.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7));
    const f = new Date(montag1);
    f.setUTCDate(montag1.getUTCDate() + (woche - 1) * 7 + 4);
    return f;
  };
  let d = freitag(jahr);
  if (!m[2] && d < start) d = freitag(++jahr);
  return d.toISOString().slice(0, 10);
}
const terminAus = (t, bezug) => datumAus(t ?? '') || kwDatum(t, bezug);

// Zeichnungsnummer mit Index/Revision im Positionstext („10241355 IDX: A“, „Zeichnung 4711 Rev. B“)
export function zeichnungAus(text) {
  const m = /([A-Z0-9][\w\-./]{3,})\s*(?:IDX|Index|Rev(?:ision)?\.?|Ind\.)\s*[:.]?\s*([A-Z0-9]{1,3}\b|-)/i.exec(text ?? '');
  return m ? { zeichnungsnr: m[1], index: m[2] === '-' ? '' : m[2].toUpperCase() } : { zeichnungsnr: '', index: '' };
}

// Seriennummern, die der Kunde je Position vorgibt: Zeilen wie „8F8115283G/0081“ (Teilenummer/Nummer) oder Angaben wie
// „Seriennummer 0081 - 0090“, „SN: 81 bis 90“. → { nummern, von, bis, stellen, praefix, luecken } oder null
const SN_TOKEN = /([A-Z0-9][\w.\-]{2,})\/(\d{2,8})\b/gi;
const SN_BEREICH = /\b(?:serien?\s*-?\s*(?:nummern?|nr\.?)|s\/?n\.?|serial\s*(?:no\.?|numbers?)?)\s*[:.]?\s*(\d{1,8})\s*(?:-|–|bis|to)\s*(\d{1,8})/i;
export const istSerienZeile = (text) => {
  const t = (text ?? '').trim();
  return !!t && [...t.matchAll(SN_TOKEN)].length > 0 && t.replace(SN_TOKEN, '').replace(/[\s,;]+/g, '') === '';
};
export function seriennummernAus(texte, teilenummer = '') {
  const norm = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const tn = norm(teilenummer);
  const nummern = [];
  let praefix = '', stellen = 0;
  for (const t of texte ?? []) {
    for (const m of String(t).matchAll(SN_TOKEN)) {
      // nur Nummern zur eigenen Teilenummer, wenn sie bekannt ist (Zeichnungsnummer/Index o. Ä. bleibt außen vor)
      if (tn && norm(m[1]) !== tn && !norm(m[1]).startsWith(tn) && !tn.startsWith(norm(m[1]))) continue;
      nummern.push(Number(m[2]));
      praefix ||= m[1];
      stellen = Math.max(stellen, m[2].length);
    }
    const b = SN_BEREICH.exec(String(t));
    if (b && !nummern.length) {
      const von = Number(b[1]), bis = Number(b[2]);
      if (bis >= von && bis - von < 100000) for (let n = von; n <= bis; n++) nummern.push(n);
      stellen = Math.max(b[1].length, b[2].length);
    }
  }
  if (!nummern.length) return null;
  const sortiert = [...new Set(nummern)].sort((a, b) => a - b);
  const von = sortiert[0], bis = sortiert.at(-1);
  return { nummern: sortiert, von, bis, anzahl: sortiert.length, stellen: Math.max(stellen, 1), praefix, luecken: bis - von + 1 !== sortiert.length };
}

// Gleicher Text auf mehreren Seiten (Fußzeile mit Bank, Anschrift): gehört zu keiner Position
function wiederholte(zeilen) {
  const seiten = new Map();
  for (const z of zeilen) {
    const t = zeilenText(z).trim();
    if (!seiten.has(t)) seiten.set(t, new Set());
    seiten.get(t).add(z.seite);
  }
  return new Set([...seiten].filter(([, x]) => x.size > 1).map(([t]) => t));
}

// Positionen der Bestellung. Liefert { kopf, positionen: [{ bestellposition, teilenummer, bezeichnung, menge, preis,
// preiseinheit, betrag, termin, text }], spalten (Kopfzeile mit Rollen, zum Anlernen) } oder positionen: [] ohne Tabelle.
export function positionenAus(zeilen, vorlage = {}) {
  const kopf = kopfzeileFinden(zeilen, vorlage);
  if (!kopf) return { spalten: [], positionen: [] };
  const spalten = kopf.spalten;
  const kopfTexte = new Set([...spalten.map((s) => s.text), ...(kopf.teile ?? [])].map(kopfText));
  const istKopf = (z) => z.zellen.filter((c) => kopfTexte.has(kopfText(c.text))).length >= 2;
  const rand = wiederholte(zeilen);
  // Folgeseiten: was über der wiederholten Kopfzeile steht (Bestellnummer, „Seite 2 von 2“), gehört nicht dazu
  const kopfAufSeite = new Map();
  zeilen.forEach((z, i) => { if (i > kopf.index && istKopf(z) && !kopfAufSeite.has(z.seite)) kopfAufSeite.set(z.seite, i); });
  const bloecke = [];
  for (const [i, z] of zeilen.entries()) {
    if (i <= kopf.index) continue;
    const text = zeilenText(z);
    if (rand.has(text.trim())) continue;
    if (z.seite !== zeilen[kopf.index].seite && kopfAufSeite.has(z.seite) && i < kopfAufSeite.get(z.seite)) continue;
    if (ENDE.test(text.trim())) { if (bloecke.length) break; else continue; }
    // wiederholte Kopfzeile auf Folgeseiten überspringen
    if (istKopf(z)) continue;
    const werte = {};
    const roh = {}; // Spalte → Text dieser Zeile
    for (const c of z.zellen) {
      const i = spalteVon(c, spalten);
      roh[i] = roh[i] ? `${roh[i]} ${c.text}` : c.text;
      const r = spalten[i]?.rolle;
      if (r) werte[r] = werte[r] ? `${werte[r]} ${c.text}` : c.text;
    }
    const menge = zahlAus(werte.menge);
    const start = menge != null && menge > 0 && /\d/.test(werte.menge ?? '') && (zahlAus(werte.preis) != null || zahlAus(werte.betrag) != null || /^\d+$/.test((werte.bestellposition ?? '').trim()));
    if (start) bloecke.push({ werte, texte: [text], roh: Object.fromEntries(Object.entries(roh).map(([k, v]) => [k, [v]])) });
    else if (bloecke.length) {
      const b = bloecke.at(-1);
      b.texte.push(text);
      // Zeilen nur mit Seriennummern („8F8115283G/0081“) gehören zur Position, aber in keine Spalte
      if (istSerienZeile(text)) continue;
      for (const [k, v] of Object.entries(roh)) {
        (b.roh[k] ??= []).push(v);
        // zweite Rolle der Spalte: die Zeile darunter („Details / Materialnummer“ → Materialnummer)
        const r2 = spalten[k]?.rolle2;
        if (r2 && !b.werte[r2]) b.werte[r2] = v;
      }
      for (const [r, w] of Object.entries(werte)) if (['teilenummer', 'bezeichnung', 'liefertermin', 'zeichnungsdatum', 'einheit'].includes(r) && !b.werte[r] && !spalten.some((s) => s.rolle === r && s.rolle2)) b.werte[r] = w;
    }
  }
  const alle = spalten.map((s) => ({ text: s.text, rolle: s.rolle, rolle2: s.rolle2 ?? '' }));
  return { spalten: alle, positionen: bloecke.map((b) => positionAus(b, alle)) };
}

function positionAus({ werte, texte, roh }, spalten = []) {
  const text = texte.join('\n');
  const menge = Math.round(zahlAus(werte.menge) ?? 0);
  let pe = werte.preiseinheit ? (zahlAus(werte.preiseinheit) || 1) : preiseinheitAus(werte.preis ?? '');
  let preis = zahlAus(werte.preis);
  const betrag = zahlAus(werte.betrag);
  // Preiseinheit nicht genannt, aber der Betrag passt nur mit 100 oder 1000 Stück je Preis
  if (pe === 1 && preis && betrag && menge && Math.abs(preis * menge - betrag) > Math.max(0.05, betrag * 0.01)) {
    const passt = [10, 100, 1000].find((e) => Math.abs((preis / e) * menge - betrag) <= Math.max(0.05, betrag * 0.01));
    if (passt) pe = passt;
  }
  if (preis != null) preis = Math.round((preis / (pe || 1)) * 10000) / 10000;
  else if (betrag && menge) preis = Math.round((betrag / menge) * 10000) / 10000;
  const termin = datumAus(werte.liefertermin ?? '') || texte.map((t) => datumAus(t)).find(Boolean) || '';
  // alle Spalten wie im PDF (mehrzeilig mit „ / “), auch die ohne Rolle
  const angaben = spalten.map((s, i) => ({ spalte: s.text, wert: (roh?.[i] ?? []).join(' / ').trim() })).filter((x) => x.wert);
  return {
    bestellposition: (werte.bestellposition ?? '').trim(),
    teilenummer: (werte.teilenummer ?? '').trim().split(/\s+/)[0] ?? '',
    bezeichnung: (werte.bezeichnung ?? '').trim(),
    menge, preis, preiseinheit: pe, betrag, termin, text,
    einheit: (werte.einheit ?? '').trim(),
    zeichnungsdatum: datumAus(werte.zeichnungsdatum ?? '') || '',
    angaben,
    serien: seriennummernAus(texte, (werte.teilenummer ?? '').trim().split(/\s+/)[0] ?? ''),
    ...zeichnungAus(text),
  };
}

// Kopfangaben: Bestellnummer und Bestelldatum. Ein angelerntes Stichwort des Kunden geht vor.
const BESTELLNR = /(bestell(?:ung)?(?:s)?\s*-?\s*(?:nr\.?|nummer)|bestellung|auftrags?\s*-?\s*(?:nr\.?|nummer)|order\s*(?:no\.?|number|nr\.?)|purchase\s*order(?:\s*no\.?)?|\bp\.?o\.?\s*(?:no\.?|nr\.?|number|#|:))\s*[:#.]?\s*/i;
const DATUM = /(bestell\s*-?\s*datum|datum|date|vom)\s*[:.]?\s*/i;

// Wert hinter dem Stichwort in derselben Zeile, sonst darunter (Kästchen: „Bestell-Nr.“ oben, die Nummer darunter)
function wertNach(zeilen, label, istWert) {
  for (const [zi, z] of zeilen.entries()) {
    for (let i = 0; i < z.zellen.length; i++) {
      const c = z.zellen[i].text;
      const m = label.exec(c);
      if (!m) continue;
      const rest = c.slice(m.index + m[0].length).trim();
      const kandidaten = [rest, ...z.zellen.slice(i + 1).map((x) => x.text)];
      const w = kandidaten.find((k) => k && istWert(k));
      if (w) return w;
      const zelle = z.zellen[i];
      const unten = zeilen.slice(zi + 1, zi + 3).filter((u) => u.seite === z.seite && u.y - z.y < 0.04)
        .flatMap((u) => u.zellen).filter((u) => u.x < zelle.x2 + 0.01 && u.x2 > zelle.x - 0.02).map((u) => u.text).find((k) => istWert(k));
      if (unten) return unten;
    }
  }
  return '';
}

const istNummer = (t) => /^[A-Z0-9][A-Z0-9\-/._]{3,}$/i.test(t.trim().split(/\s+/)[0] ?? '') && /\d{3,}/.test(t);

export function kopfAus(zeilen, vorlage = {}) {
  const oben = zeilen.filter((z) => z.seite === 0);
  const eigenes = (s) => (s ? new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*[:#.]?\\s*', 'i') : null);
  const nrLabel = eigenes(vorlage?.kopf?.bestellnr);
  const bestellnr = ((nrLabel && wertNach(oben, nrLabel, istNummer)) || wertNach(oben, BESTELLNR, istNummer)).trim().split(/\s+/)[0] ?? '';
  const datumLabel = eigenes(vorlage?.kopf?.datum);
  const datumText = (datumLabel && wertNach(oben, datumLabel, (t) => !!datumAus(t))) || wertNach(oben, DATUM, (t) => !!datumAus(t));
  const ersteDaten = oben.slice(0, Math.ceil(oben.length * 0.4)).map((z) => datumAus(zeilenText(z))).find(Boolean) ?? '';
  const email = /[\w.+-]+@[\w-]+\.[\w.-]+/.exec(oben.map(zeilenText).join(' '))?.[0] ?? '';
  return { bestellnr, datum: datumAus(datumText) || ersteDaten, email };
}

// Alles in einem Schritt: aus den Seiten (zeichnungText.textAusSeite) Kopf, Positionen und den ganzen Text
export function bestellungLesen(seiten, vorlage = {}) {
  const zeilen = zeilenAus(seiten);
  const kopf = kopfAus(zeilen, vorlage);
  const r = positionenAus(zeilen, vorlage);
  // Kalenderwoche in der Position, sonst ein Liefertermin für die ganze Bestellung (z. B. „Liefertermin KW50“ unter der Tabelle)
  const gesamt = zeilen.map((z) => /liefer(?:termin|datum|woche)\s*[:.]?\s*(.+)/i.exec(zeilenText(z))?.[1]).filter(Boolean).map((t) => terminAus(t, kopf.datum)).find(Boolean) ?? '';
  const positionen = r.positionen.map((p) => ({ ...p, termin: p.termin || kwDatum(p.text, kopf.datum) || gesamt }));
  return { kopf: { ...kopf, liefertermin: gesamt }, ...r, positionen, text: zeilen.map(zeilenText).join('\n') };
}

// Zum Anlernen: Überschriften der Spalten mit der gewählten Rolle
export const vorlageAus = (spalten) => Object.fromEntries((spalten ?? []).filter((s) => s.rolle && kopfText(s.text)).map((s) => [kopfText(s.text), s.rolle2 ? `${s.rolle}|${s.rolle2}` : s.rolle]));
