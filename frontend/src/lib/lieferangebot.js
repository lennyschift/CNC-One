// Angebot eines Lieferanten (PDF) lesen: Kopf (Angebotsnummer, Datum, Gültigkeit), Positionen (Werkstoff, Zustand, Form,
// Maße, Stück, kg, Meter, Preis mit Preiseinheit, Betrag, Liefertermin, Option) und Nebenkosten (Verpackung, Fracht …).
//
// Allgemein: Die Spalten kommen aus der Kopfzeile der Tabelle (Stichwörter, angelernte Spalten des Lieferanten gehen vor).
// Eine Position beginnt mit einer Zeile, die einen Betrag hat; die Zeilen darunter (Werkstoff, Maße, Liefertermin …)
// gehören dazu. Zeilen mit Betrag und Wörtern wie Verpackung oder Fracht sind Nebenkosten, Summenzeilen beenden die
// Tabelle. Kopf- und Fußzeilen, die auf jeder Seite stehen, zählen nicht.
// Je Lieferant anlernbar (Vorlage): Rolle je Spaltenüberschrift und die Preiseinheit (je kg, je Stück, je Meter).
// Ob der Preis je kg oder je Stück gilt, wird außerdem am Betrag geprüft: Preis × Menge muss den Betrag ergeben.
import { zeilenAus, zahlAus, kopfText } from './bestellung.js';
import { datumAus } from './mailtabelle.js';

export const ROLLEN = [
  { id: 'pos', label: 'Position' },
  { id: 'artikel', label: 'Artikel / Text' },
  { id: 'beschreibung', label: 'Beschreibung' },
  { id: 'menge', label: 'Menge' },
  { id: 'einheit', label: 'Einheit' },
  { id: 'gewicht', label: 'Gewicht (kg)' },
  { id: 'preis', label: 'Preis' },
  { id: 'preiseinheit', label: 'Preiseinheit' },
  { id: 'rabatt', label: 'Rabatt %' },
  { id: 'betrag', label: 'Betrag' },
];
export const PREIS_JE = [
  { id: '', label: 'automatisch' },
  { id: 'kg', label: 'je kg' },
  { id: 'Stk', label: 'je Stück' },
  { id: 'm', label: 'je Meter' },
];

// Reihenfolge zählt: „Preis Rabatt %“ ist der Preis, „Gew. (kg)“ das Gewicht, „Menge Einheit“ die Menge
const STICHWORT = [
  ['pos', /^(pos\.?|position|pos\.?\s*-?\s*nr\.?|item|lfd\.?\s*nr\.?)(\s|$)/i],
  ['betrag', /betrag|total|gesamt|amount|summe|^wert/i],
  ['preiseinheit', /^pe$|^p\.?e\.?$|preiseinheit|price\s*unit|^per$/i],
  ['gewicht', /^gew|gewicht|weight/i],
  ['preis', /preis|price/i],
  ['rabatt', /rabatt|discount/i],
  ['menge', /menge|quantity|^qty|anzahl/i],
  ['einheit', /^me$|^einheit$|^unit$|^eh$/i],
  ['beschreibung', /beschreibung|bezeichnung|description|benennung|^text$/i],
  ['artikel', /^artikel|^art\.?\s*-?\s*nr|^material$/i],
];

const zeilenText = (z) => z.zellen.map((c) => c.text).join(' ');
const norm = (t) => (t ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
const r2 = (x) => Math.round(x * 100) / 100;
const r4 = (x) => Math.round(x * 10000) / 10000;

function rolleFuer(text, vorlage) {
  const k = kopfText(text);
  if (vorlage?.spalten?.[k] !== undefined) return { rolle: vorlage.spalten[k], quelle: 'vorlage' };
  const t = (text ?? '').trim();
  if (t.length > 30) return null;
  const s = STICHWORT.find(([, re]) => re.test(t));
  return s ? { rolle: s[0], quelle: 'stichwort' } : null;
}

// Kopfzeile der Positionstabelle: die Zeile mit den meisten erkannten Spalten (Menge und Preis oder Betrag)
export function kopfzeileFinden(zeilen, vorlage = {}) {
  let beste = null;
  zeilen.forEach((z, i) => {
    const spalten = z.zellen.map((c) => ({ ...c, ...(rolleFuer(c.text, vorlage) ?? { rolle: '', quelle: '' }) }));
    const rollen = new Set(spalten.map((s) => s.rolle).filter(Boolean));
    if (!rollen.has('menge') || !(rollen.has('preis') || rollen.has('betrag')) || rollen.size < 3) return;
    const wert = spalten.reduce((n, s) => n + (s.quelle === 'vorlage' ? 10 : s.quelle ? 1 : 0), 0);
    if (!beste || wert > beste.wert) beste = { index: i, wert, spalten };
  });
  return beste;
}

// Spalte einer Zelle: die Kopfzelle mit der größten Überdeckung, sonst die nächste
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

// ------------------------------------------------------------------ Einheiten, Werkstoff, Form, Maße
const EINHEIT = /(\d[\d.,]*)\s*(kg|stück|stueck|stck\.?|stk\.?|st\.?|pcs\.?|pc|pieces|lfm|mtr\.?|m)(?![a-zäöüß])/gi;
export function einheitNorm(e) {
  const t = (e ?? '').toLowerCase().replace(/\.$/, '');
  if (t === 'kg') return 'kg';
  if (['m', 'lfm', 'mtr'].includes(t)) return 'm';
  if (/^(stück|stueck|stck|stk|st|pcs|pc|pieces|platten?|stangen?|zuschnitte?)$/.test(t)) return 'Stk';
  return '';
}
function mengenAus(text) {
  const out = [];
  for (const m of String(text ?? '').matchAll(EINHEIT)) {
    const wert = zahlAus(m[1]);
    if (wert != null) out.push({ wert, einheit: einheitNorm(m[2]) });
  }
  return out;
}

// Werkstoff in einer Schreibweise: „EN AW-6082“, „1.4301“, „C45“ …
export function werkstoffAus(text) {
  const t = String(text ?? '');
  let m = /EN\s*AW[\s-]*(\d{4}[A-Z]?)/i.exec(t) || /\bAW[\s-]?(\d{4}[A-Z]?)\b/i.exec(t) || /(?:alplan|fortal|certal|alca|weldural|hokotol|alumec)\s*®?\s*(\d{4})/i.exec(t);
  if (m) return `EN AW-${m[1].toUpperCase()}`;
  m = /\b1\.\d{4}\b/.exec(t);
  if (m) return m[0];
  m = /\b(S235\w*|S355\w*|C45E?|C60E?|42CrMo4|16MnCr5|11SMnPb30|11SMn30|CuZn39Pb3|CuZn40Pb2|X\d+Cr[\w]*|POM-?C|PA6|PEEK)\b/i.exec(t);
  return m ? m[1] : '';
}
// Kurzer Schlüssel zum Vergleichen: „6082“, „1.4301“, „C45“
export const werkstoffSchluessel = (text) => {
  const w = werkstoffAus(text);
  return (/EN AW-(\d{4})/.exec(w)?.[1] ?? w).toUpperCase();
};

export function zustandAus(text) {
  const m = /(?:^|[\s,;/(-])(T\d{1,5}|H\d{2,3})(?![\d\w])/.exec(String(text ?? ''));
  return m ? m[1] : '';
}

const FORMEN = [
  ['Platte', /platte|plate|zuschnitt|walzplatte|blech|sheet/i],
  ['Rund', /\brund|round|rundstange|\bbar\b/i],
  ['Flach', /\bflach|flat/i],
  ['Vierkant', /vierkant|square/i],
  ['Sechskant', /sechskant|hex/i],
  ['Rohr', /\brohr|tube|pipe/i],
];
export const formAus = (text) => FORMEN.find(([, re]) => re.test(text ?? ''))?.[0] ?? '';

// Maße in mm (aufsteigend, ohne Doppel) und der erste Maßausdruck als Text. Toleranzen zählen nicht.
const zahlMm = String.raw`(\d+(?:[.,]\d+)?)`;
export function masseAus(text) {
  const zeilen = String(text ?? '').split('\n').filter((z) => !/toleranz|tolerance/i.test(z));
  const t = zeilen.join('\n');
  const werte = [];
  let anzeige = '';
  const dazu = (...xs) => { for (const x of xs) { const n = zahlAus(x); if (n != null && n > 0 && n < 100000) werte.push(n); } };
  const kette = new RegExp(String.raw`${zahlMm}\s*[x×*]\s*${zahlMm}(?:\s*[x×*]\s*${zahlMm})?\s*mm`, 'gi');
  for (const m of t.matchAll(kette)) { dazu(m[1], m[2], m[3]); anzeige ||= m[0]; }
  for (const m of t.matchAll(new RegExp(String.raw`(?:[ØøΦ⌀]|rund|dia\.?|durchmesser)\s*${zahlMm}\s*mm`, 'gi'))) { dazu(m[1]); anzeige ||= m[0]; }
  for (const m of t.matchAll(new RegExp(String.raw`a['’´]?\s*${zahlMm}\s*mm`, 'gi'))) dazu(m[1]);
  for (const m of t.matchAll(new RegExp(String.raw`(?<![x×*]\s*)(?<![\d.,])${zahlMm}\s*mm\b(?!\s*[x×*])`, 'gi'))) { dazu(m[1]); anzeige ||= m[0]; }
  return { masse: [...new Set(werte.map(r4))].sort((a, b) => a - b), anzeige: anzeige.replace(/\s+/g, ' ').trim() };
}

// ------------------------------------------------------------------ Zeilenarten
const SUMME = /^(gesamt|summe|zwischensumme|total|netto|nettobetrag|mehrwertsteuer|mwst|\d+\s*%\s*mwst|endbetrag|sub\s*total)/i;
const ENDE = /^(gesamtwert|gesamtbetrag|nettobetrag|netto\s*gesamt|gesamt\s*netto|total\s*eur|endbetrag|summe\s*netto|net\s*total|total\s*net)/i;
const NEBEN = /verpackung|transport|fracht|maut|treibstoff|versand|porto|carrier|freight|packing|shipping|zuschlag|mindermenge|zeugnis|surcharge|anlieferung|delivery\s*charge|sägekosten|schnittkosten/i;
const BOILER = /\biban\b|\bbic\b|hrb|ust[.-]?id|steuernummer|handelsregister|amtsgericht|geschäftsführ|vorstand|aufsichtsrat|registergericht|telefax/i;

// Texte, die auf mehreren Seiten an derselben Stelle stehen (Kopf- und Fußzeilen). Gleiche Texte an anderer Stelle
// (z. B. derselbe Liefertermin in zwei Positionen) zählen nicht.
const SEITENZAHL = /\d+\s*(\/|of|von)\s*\d+|seite\s*\d+|page\s*\d+/g;
const boilerSchluessel = (z) => `${Math.round(z.y * 100)}|${norm(zeilenText(z)).replace(SEITENZAHL, '')}`;
function wiederholt(zeilen) {
  const seiten = new Map();
  for (const z of zeilen) {
    const k = boilerSchluessel(z);
    if (!seiten.has(k)) seiten.set(k, new Set());
    seiten.get(k).add(z.seite);
  }
  return new Set([...seiten.entries()].filter(([, s]) => s.size > 1).map(([k]) => k));
}

// ------------------------------------------------------------------ Kopf
function wertBei(zeilen, label, istWert) {
  for (let i = 0; i < zeilen.length; i++) {
    const z = zeilen[i];
    for (let j = 0; j < z.zellen.length; j++) {
      const c = z.zellen[j];
      const m = label.exec(c.text);
      if (!m) continue;
      const rest = c.text.slice(m.index + m[0].length).replace(/^[\s:#.]+/, '').trim();
      // rechts daneben, sonst direkt darunter (Kopf als kleine Tabelle)
      const darunter = (zeilen[i + 1]?.seite === z.seite ? zeilen[i + 1].zellen : []).filter((x) => Math.min(x.x2, c.x2) - Math.max(x.x, c.x) > 0).map((x) => x.text);
      const w = [rest, ...z.zellen.slice(j + 1, j + 2).map((x) => x.text), ...darunter].find((k) => k && istWert(k));
      if (w) return w.trim();
    }
  }
  return '';
}
const istBelegnr = (t) => /^[A-Z0-9][\w\-/.]{3,}$/i.test(t.trim().split(/\s+/)[0] ?? '') && /\d{4,}/.test(t) && !datumAus(t);
const NR_LABELS = [
  /^(angebots?\s*-?\s*(?:nr\.?|nummer)|belegnummer|beleg\s*-?\s*nr\.?|quotation\s*(?:no\.?|number|nr\.?)|quote\s*(?:no\.?|number)|order\s*number)/i,
  /^(angebot|quotation|offer)\b(?!s?\s*-?\s*g[üu]ltig)/i,
];
const DATUM_LABEL = /^(beleg\s*-?\s*datum|angebots\s*-?\s*datum|datum|date)\b/i;
const GUELTIG = /(g[üu]ltig\s*bis|angebotsg[üu]ltigkeit|g[üu]ltigkeit|bindefrist|valid\s*(?:until|to|till))\s*[:.]?\s*/i;

function addTage(iso, n) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function kopfAus(zeilen, vorlage = {}) {
  const oben = zeilen.filter((z) => z.seite === 0);
  const eigenes = vorlage?.kopf?.angebotsnr ? new RegExp(`^${vorlage.kopf.angebotsnr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i') : null;
  const nrText = [eigenes, ...NR_LABELS].filter(Boolean).map((l) => wertBei(oben, l, istBelegnr)).find(Boolean) ?? '';
  const datum = datumAus(wertBei(oben, DATUM_LABEL, (t) => !!datumAus(t)));
  const alle = zeilen.map(zeilenText).join('\n');
  let gueltigBis = '';
  // erste Angabe mit Datum oder Tagen („Angebotsbindefrist sich ändern kann“ hat keine)
  for (const g of alle.matchAll(new RegExp(GUELTIG.source, 'gi'))) {
    const rest = alle.slice(g.index + g[0].length, g.index + g[0].length + 60);
    const tage = /^(\d{1,3})\s*(?:arbeits)?tage?/i.exec(rest);
    gueltigBis = datumAus(rest.split('\n')[0]) || (tage && datum ? addTage(datum, Number(tage[1])) : '');
    if (gueltigBis) break;
  }
  return {
    angebotsnr: nrText.split(/\s+/)[0] ?? '',
    datum,
    gueltigBis,
    anfrage: /\bLA-\d{4}-\d{3,}\b/i.exec(alle)?.[0]?.toUpperCase() ?? '',
  };
}

// ------------------------------------------------------------------ Positionen
function positionAus(b, vorlage, vorige) {
  const volltext = b.zeilen.join('\n');
  const text = [...b.vorspann, ...b.texte].filter(Boolean).join('\n');
  const posText = (b.werte.pos ?? '').trim();
  const option = /^\(\s*\d+\s*\)$/.test(posText) || /\b(option|alternativ)/i.test(b.zeilen[0] ?? '') || /^\(.*\)$/.test((b.werte.betrag ?? '').trim());
  const pos = posText.replace(/[()\s]/g, '');

  // Mengen: Mengenspalte (alle Zeilen der Position), Einheitenspalte, Gewicht, „Anzahl: 18“
  const mengen = mengenAus(`${b.mengeTexte.join(' ')}`);
  // Zahl ohne Einheit in der Mengenspalte: Einheit aus der Einheitenspalte
  if (!mengen.length) {
    const einheitSpalte = einheitNorm(b.werte.einheit?.trim().split(/\s+/)[0]);
    for (const n of b.mengeTexte.map((t) => t.trim()).filter((t) => /^\d[\d.,]*$/.test(t))) mengen.push({ wert: zahlAus(n), einheit: einheitSpalte });
  }
  const gewicht = zahlAus(b.werte.gewicht);
  if (gewicht != null) mengen.push({ wert: gewicht, einheit: 'kg' });
  const anzahl = /(?:anzahl|stückzahl)\s*:?\s*(\d+)(?!\s*[.,]\d)/i.exec(volltext);
  if (anzahl) mengen.push({ wert: Number(anzahl[1]), einheit: 'Stk' });
  const erste = (e) => mengen.find((m) => m.einheit === e)?.wert ?? null;
  let stueck = erste('Stk');
  const kg = erste('kg');
  const { masse, anzeige } = masseAus(volltext);
  let werkstoff = werkstoffAus(volltext);
  let zustand = zustandAus(volltext);
  let form = formAus(volltext);
  // „Wie vorhergehende Position, jedoch …“: Werkstoff, Zustand und Form von der Position davor
  if (vorige && /wie\s+vorher|wie\s+oben|wie\s+pos|as\s+above/i.test(volltext)) {
    werkstoff ||= vorige.werkstoff;
    zustand ||= vorige.zustand;
    form ||= vorige.form;
  }
  let meter = erste('m');
  const laenge = /a['’´]?\s*(\d+(?:[.,]\d+)?)\s*mm/i.exec(volltext);
  if (meter == null && stueck && laenge && ['Rund', 'Flach', 'Vierkant', 'Sechskant', 'Rohr'].includes(form)) meter = r4((stueck * zahlAus(laenge[1])) / 1000);

  // Preis, Rabatt und Preiseinheit
  const betrag = zahlAus(b.werte.betrag);
  let preis = zahlAus(String(b.werte.preis ?? '').split(/\s+/).find((t) => /\d/.test(t)));
  const rabatt = zahlAus(b.werte.rabatt);
  if (preis != null && rabatt) preis = r4(preis * (1 - rabatt / 100));
  const peText = (b.werte.preiseinheit ?? '').trim();
  let pe = 1;
  let preisJe = vorlage?.preisJe || '';
  const hinweis = `${b.werte.preis ?? ''} ${b.preisTexte.join(' ')}`;
  if (!preisJe) {
    const je = /(?:\/|per|je|pro)\s*(kg|stk\.?|stück|st\.?|pc|pcs|m|lfm|mtr)\b/i.exec(hinweis);
    if (je) preisJe = einheitNorm(je[1]);
    else if (einheitNorm(peText)) preisJe = einheitNorm(peText);
  }
  if (/^\d[\d.,]*$/.test(peText) && (zahlAus(peText) ?? 1) > 1) pe = zahlAus(peText);
  if (preis != null && pe > 1) preis = r4(preis / pe);
  const menge = { kg, Stk: stueck, m: meter };
  const passt = (e) => preis != null && betrag != null && menge[e] != null && Math.abs(preis * menge[e] - betrag) <= Math.max(0.05, betrag * 0.01);
  // nicht genannt oder passt nicht zum Betrag: die Einheit, mit der Preis × Menge den Betrag ergibt
  if (!vorlage?.preisJe && (!preisJe || !passt(preisJe))) {
    const p = ['kg', 'Stk', 'm'].find(passt);
    if (p) preisJe = p;
  }
  if (!preisJe) preisJe = mengen[0]?.einheit || 'Stk';
  if (preis == null && betrag != null && menge[preisJe]) preis = r4(betrag / menge[preisJe]);
  if (stueck == null && preisJe === 'Stk' && mengen[0]?.einheit === 'Stk') stueck = mengen[0].wert;

  const lt = /liefer(?:termin|zeit|datum)\s*:?\s*([^\n]+)/i.exec(volltext);
  const artikelnr = (/(?:artikel\s*-?\s*nr\.?|art\.?\s*-?\s*nr\.?|unsere\s*nr\.?)\s*:?\s*([\w\-/.]+)/i.exec(volltext)?.[1])
    || (/^\d{4,}$/.test((b.werte.artikel ?? '').trim()) ? b.werte.artikel.trim() : '');
  return {
    pos, option, text, werkstoff, zustand, form, masse, abmessung: anzeige,
    stueck, kg, meter, preis, preisJe, betrag: betrag ?? (preis != null && menge[preisJe] ? r2(preis * menge[preisJe]) : null),
    liefertermin: lt ? lt[1].trim() : '', lieferdatum: lt ? datumAus(lt[1]) : '', artikelnr,
  };
}

// Liest das ganze Angebot. `seiten` wie aus zeichnungText.textAusSeite. Liefert { kopf, positionen, nebenkosten, netto,
// summePositionen, summeNebenkosten, stimmt, spalten (Kopfzeile mit Rollen, zum Anlernen), text }.
export function angebotLesen(seiten, vorlage = {}) {
  const zeilen = zeilenAus(seiten);
  const text = zeilen.map(zeilenText).join('\n');
  const kopf = kopfAus(zeilen, vorlage);
  const k = kopfzeileFinden(zeilen, vorlage);
  const leer = { kopf, positionen: [], nebenkosten: [], netto: null, summePositionen: 0, summeNebenkosten: 0, stimmt: false, spalten: [], text };
  if (!k) return leer;
  const spalten = k.spalten;
  const kopfTexte = new Set(spalten.map((s) => kopfText(s.text)).filter(Boolean));
  const boiler = wiederholt(zeilen);
  const bloecke = [], nebenkosten = [];
  let aktuell = null, vorspann = [], netto = null, ende = false, nachKopf = true;
  const rest = [];
  for (const z of zeilen.slice(k.index + 1)) {
    const t = zeilenText(z).trim();
    if (ende) { rest.push(t); continue; }
    // wiederholte Tabellenkopfzeile auf Folgeseiten, Kopf- und Fußzeilen, Bankverbindung
    if (z.zellen.filter((c) => kopfTexte.has(kopfText(c.text))).length >= 2) { nachKopf = true; continue; }
    if (boiler.has(boilerSchluessel(z)) || BOILER.test(t)) continue;
    // Fortsetzung der Kopfzeile („Ref.-Nr.“ unter „Kunden-“): kurzer Text ohne Zahl, nicht in der Textspalte
    const rollenDerZeile = z.zellen.map((c) => spalten[spalteVon(c, spalten)]?.rolle ?? '');
    if (nachKopf && !/\d/.test(t) && t.length < 25 && rollenDerZeile.every((r) => !['beschreibung', 'artikel', ''].includes(r))) { nachKopf = false; continue; }
    nachKopf = false;
    const werte = {};
    const roh = {};
    for (const c of z.zellen) {
      const r = spalten[spalteVon(c, spalten)]?.rolle;
      if (!r) continue;
      werte[r] = werte[r] ? `${werte[r]} ${c.text}` : c.text;
      (roh[r] ??= []).push(c.text);
    }
    const betrag = zahlAus(String(werte.betrag ?? '').replace(/[()]/g, ''));
    if (SUMME.test(t)) {
      if (ENDE.test(t) && !/inkl|incl|brutto|mwst/i.test(t)) {
        const n = zahlAus(String(werte.betrag ?? t.split(/\s+/).at(-1)));
        if (n != null) netto = n;
        ende = true;
      }
      aktuell = null;
      continue;
    }
    if (betrag != null && NEBEN.test(t) && !/^\d+$/.test((werte.pos ?? '').trim())) {
      nebenkosten.push({ text: t.replace(/\s+[\d.,]+\s*€?\s*(pa\.?|\/\s*\w+\.?)?\s*[\d.,]*\s*$/i, '').replace(/\s+\d+\s*st(ü|ue)ck.*$/i, '').trim() || t, betrag });
      aktuell = null;
      continue;
    }
    const textZellen = z.zellen.filter((c) => ['beschreibung', 'artikel', ''].includes(spalten[spalteVon(c, spalten)]?.rolle ?? '')).map((c) => c.text);
    if (betrag != null) {
      aktuell = { werte, zeilen: [t], texte: [], vorspann, mengeTexte: [...(roh.menge ?? []), ...(roh.einheit ?? [])], preisTexte: [] };
      // Artikelnummer allein in der Artikelspalte ist kein Text
      let beschr = textZellen.filter((x) => !(werte.artikel && x === werte.artikel && /^\d{4,}$/.test(x)));
      // ohne eigene Positionsspalte: eine kleine Zahl ganz links ist die Position
      if (!werte.pos && /^\(?\d{1,4}\)?$/.test(beschr[0] ?? '') && z.zellen[0]?.text === beschr[0]) { werte.pos = beschr[0]; beschr = beschr.slice(1); }
      aktuell.texte.push(beschr.join(' '));
      vorspann = [];
      bloecke.push(aktuell);
      continue;
    }
    if (!aktuell) { if (bloecke.length === 0 || textZellen.length) vorspann.push(t); continue; }
    aktuell.zeilen.push(t);
    if (textZellen.length) aktuell.texte.push(textZellen.join(' '));
    aktuell.mengeTexte.push(...(roh.menge ?? []), ...(roh.einheit ?? []));
    if (roh.preis) aktuell.preisTexte.push(...roh.preis);
    for (const [r, w] of Object.entries(werte)) if (!aktuell.werte[r] && ['artikel', 'preiseinheit'].includes(r)) aktuell.werte[r] = w;
  }
  // Nebenkosten im Fließtext unter der Tabelle („zzgl. Transportkostenanteil 89,90 € / Anlieferung“)
  for (const t of rest) {
    const m = /(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})\s*(?:€|eur)/i.exec(t);
    if (m && NEBEN.test(t) && !/mindest|unter\s+\d/i.test(t)) {
      const b = zahlAus(m[1]);
      if (!nebenkosten.some((n) => n.betrag === b)) nebenkosten.push({ text: t.slice(0, m.index).replace(/[:\s]+$/, '').trim(), betrag: b, zusaetzlich: true });
    }
  }
  const positionen = [];
  for (const b of bloecke) positionen.push(positionAus(b, vorlage, positionen.at(-1)));
  const summePositionen = r2(positionen.filter((p) => !p.option).reduce((s, p) => s + (p.betrag ?? 0), 0));
  const summeNebenkosten = r2(nebenkosten.filter((n) => !n.zusaetzlich).reduce((s, n) => s + n.betrag, 0));
  const stimmt = netto == null ? null : Math.abs(summePositionen + summeNebenkosten - netto) <= 0.05;
  return {
    kopf, positionen, nebenkosten, netto, summePositionen, summeNebenkosten, stimmt, text,
    spalten: spalten.map(({ text: st, rolle }) => ({ text: st, rolle })),
  };
}

// Zum Anlernen: Überschriften der Spalten mit der gewählten Rolle (leer = Spalte nicht benutzen)
export const spaltenVorlage = (spalten) => Object.fromEntries((spalten ?? []).filter((s) => kopfText(s.text)).map((s) => [kopfText(s.text), s.rolle ?? '']));

// ------------------------------------------------------------------ Zuordnung zu unserer Anfrage und Preise
const zahlenIn = (text) => [...String(text ?? '').matchAll(/\d+(?:[.,]\d+)?/g)].map((m) => zahlAus(m[0])).filter((n) => n != null && n > 0);

// Wie gut passt eine Angebotsposition zu einer Position unserer Anfrage? Werkstoff zählt am meisten, dann gleiche Maße
// und die Stückzahl.
export function passung(o, p) {
  const angefragt = `${p.teil?.name ?? ''} ${p.teil?.material ?? ''} ${p.abmessung ?? ''}`;
  let w = 0;
  const ws = werkstoffSchluessel(angefragt);
  if (ws && o.werkstoff) w += werkstoffSchluessel(o.werkstoff) === ws ? 3 : -3;
  const zahlen = new Set(zahlenIn(angefragt));
  w += (o.masse ?? []).filter((m) => zahlen.has(m)).length;
  const f = formAus(angefragt);
  if (f && o.form) w += f === o.form ? 1 : -1;
  return w;
}

// Vorschlag: je Angebotsposition die passendste Anfrageposition (Optionen bleiben ohne Zuordnung)
export function zuordnen(positionen, anfrage) {
  const ps = anfrage?.positionen ?? [];
  return positionen.map((o) => {
    if (o.option || !ps.length) return '';
    if (ps.length === 1) return ps[0].key;
    let beste = '', wert = 0;
    for (const p of ps) { const w = passung(o, p); if (w > wert) { wert = w; beste = p.key; } }
    return beste;
  });
}

// Menge einer Angebotsposition in unserer Einheit (Stk, Platten, Zuschnitte, Stangen = Stück; kg; m)
export function mengeIn(o, einheit) {
  if (einheit === 'kg') return o.kg ?? null;
  if (einheit === 'm') return o.meter ?? (o.stueck && o.masse?.length && ['Rund', 'Flach', 'Vierkant', 'Sechskant', 'Rohr'].includes(o.form) ? r4((o.stueck * Math.max(...o.masse)) / 1000) : null);
  return o.stueck ?? null;
}

// Preise für unsere Anfrage: je Position der Preis je angefragter Einheit (Betrag ÷ angebotene Menge), gültig für jede
// angefragte Menge; dazu, ob die angebotene Menge von der angefragten abweicht.
// zuordnung: [anfrageKey|'' je Angebotsposition]. Liefert { preise: [{ posKey, menge, proStk, einmalig }], je: { [key]: {...} } }
export function preiseFuer(anfrage, positionen, zuordnung) {
  const preise = [];
  const je = {};
  for (const p of anfrage?.positionen ?? []) {
    const os = positionen.filter((o, i) => zuordnung[i] === p.key);
    if (!os.length) continue;
    const betrag = r2(os.reduce((s, o) => s + (o.betrag ?? 0), 0));
    const mengen = os.map((o) => mengeIn(o, p.einheit || 'Stk'));
    const angeboten = mengen.every((m) => m != null) ? r4(mengen.reduce((s, m) => s + m, 0)) : null;
    const ersteMenge = p.mengen?.[0] ?? 0;
    const einzel = angeboten ? r4(betrag / angeboten) : ersteMenge ? r4(betrag / ersteMenge) : 0;
    je[p.key] = { betrag, angeboten, einzel, abweichung: angeboten != null && !(p.mengen ?? []).some((m) => Math.abs(m - angeboten) < 1e-6), geschaetzt: angeboten == null };
    for (const m of p.mengen ?? []) preise.push({ posKey: p.key, menge: m, proStk: einzel, einmalig: 0 });
  }
  return { preise, je };
}

// Abgleich einer Angebotsposition mit der angefragten: [{ feld, angefragt, angeboten, ok }]
export function abgleich(o, p) {
  const angefragt = `${p.teil?.name ?? ''} ${p.teil?.material ?? ''} ${p.abmessung ?? ''}`;
  const out = [];
  const ws = werkstoffAus(angefragt);
  if (ws || o.werkstoff) out.push({ feld: 'Werkstoff', angefragt: ws || '–', angeboten: o.werkstoff || '–', ok: !ws || !o.werkstoff ? null : werkstoffSchluessel(ws) === werkstoffSchluessel(o.werkstoff) });
  const zs = zustandAus(angefragt);
  if (zs) out.push({ feld: 'Zustand', angefragt: zs, angeboten: o.zustand || '–', ok: o.zustand ? o.zustand.startsWith(zs) || zs.startsWith(o.zustand) : null });
  const f = formAus(angefragt);
  if (f || o.form) out.push({ feld: 'Form', angefragt: f || '–', angeboten: o.form || '–', ok: !f || !o.form ? null : f === o.form });
  const zahlen = new Set(zahlenIn(p.abmessung ?? ''));
  if (o.masse?.length) {
    const treffer = o.masse.filter((m) => zahlen.has(m)).length;
    out.push({ feld: 'Maße', angefragt: (p.abmessung ?? '').split(' · ')[0] || '–', angeboten: o.abmessung || o.masse.join(' × '), ok: zahlen.size ? treffer > 0 : null });
  }
  const anf = (p.anforderungen ?? '').trim();
  if (anf) {
    const zeugnis = /3\.1|3\.2|2\.2|zeugnis/i.test(anf);
    const erwaehnt = /3\.1|3\.2|2\.2|zeugnis|10204|certificate|cert\b/i.test(o.text ?? '');
    out.push({ feld: 'Anforderungen', angefragt: anf, angeboten: erwaehnt ? 'im Angebot erwähnt' : 'nicht erwähnt', ok: zeugnis ? (erwaehnt ? true : null) : null });
  }
  return out;
}

// ------------------------------------------------------------------ Mehrere Angebote ohne eigene Anfrage vergleichen
// (Anfrage lief außerhalb von CNC One, z. B. per Telefon oder vor der Einführung): Lieferant erkennen und aus den
// Angebotspositionen gemeinsame Positionen bilden, die dann eine Anfrage je Lieferant ergeben.

const RECHTSFORM = /^(gmbh|ag|kg|se|ltd|co|mbh|e\.?k\.?|s\.?p\.?a\.?|srl|bv|inc|und|&|metall|metal|stahl|handel|high|performance)$/i;
const namensWoerter = (name) => String(name ?? '').split(/[\s,.\-/&]+/).filter((w) => w.length >= 4 && !RECHTSFORM.test(w));

// Lieferant aus den Stammdaten, dessen Name (ohne Rechtsform) oder Mail-Domain im Text steht: id oder ''
export function lieferantErkennen(text, lieferanten) {
  const t = String(text ?? '').toLowerCase();
  let beste = '', wert = 0;
  for (const l of lieferanten ?? []) {
    let w = 0;
    const domains = [l.email, ...String(l.weitereEmails ?? '').split(/\s+/)].map((m) => String(m ?? '').split('@')[1]).filter(Boolean);
    if (domains.some((d) => t.includes(d.toLowerCase()))) w += 3;
    const woerter = namensWoerter(l.name);
    // Namenswörter enthalten nur Buchstaben und Ziffern (Trennzeichen sind oben weggefallen): als Wortanfang suchen
    if (woerter.length && woerter.every((x) => new RegExp(`(^|[^a-zäöüß0-9])${x.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')}`, 'u').test(t))) w += 2;
    if (w > wert) { wert = w; beste = l.id; }
  }
  return beste;
}

// Name für einen neuen Lieferanten: erste Firma mit Rechtsform im Text (nicht die eigene), sonst die erste Zeile
export function lieferantVorschlag(text, ausser = []) {
  const eigen = ausser.map((x) => String(x).toLowerCase()).filter(Boolean);
  for (const zeile of String(text ?? '').split('\n')) {
    const m = /([A-ZÄÖÜ][\wÄÖÜäöüß&.\- ]{1,40}?\s(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|AG|KG|SE|Ltd\.?|S\.p\.A\.?|e\.K\.))(?![\wäöü])/.exec(zeile);
    if (m && !eigen.some((e) => m[1].toLowerCase().includes(e))) return m[1].trim();
  }
  return String(text ?? '').split('\n').map((z) => z.trim()).find((z) => z.length > 2 && !eigen.some((e) => z.toLowerCase().includes(e))) ?? '';
}

const gruppenSchluessel = (o) => `${werkstoffSchluessel(o.werkstoff)}|${o.form}|${(o.masse ?? []).join('x')}`;

// Gemeinsame Positionen aus mehreren Angeboten: gleicher Werkstoff, gleiche Form und gleiche Maße = eine Position.
// angebote: [{ positionen }]. Liefert { gruppen: [{ werkstoff, zustand, form, masse, abmessung, einheit, menge, name,
// material, abmessungText }], zuordnung: [[gruppenIndex|-1 je Position] je Angebot] }. Optionen bleiben außen vor.
export function positionsGruppen(angebote) {
  const gruppen = [];
  const index = new Map();
  const zuordnung = (angebote ?? []).map((a) => (a.positionen ?? []).map((o) => {
    if (o.option || o.betrag == null) return -1;
    const k = gruppenSchluessel(o);
    if (!index.has(k)) { index.set(k, gruppen.length); gruppen.push({ ...o, offers: [] }); }
    const i = index.get(k);
    gruppen[i].offers.push(o);
    gruppen[i].zustand ||= o.zustand;
    return i;
  }));
  return {
    zuordnung,
    gruppen: gruppen.map((g) => {
      const einheit = g.offers.every((o) => o.stueck != null) ? 'Stk' : g.offers.every((o) => o.kg != null) ? 'kg' : 'Stk';
      const menge = Math.max(1, Math.ceil(Math.max(...g.offers.map((o) => mengeIn(o, einheit) ?? 0))));
      // aus allen erkannten Maßen (der erste Maßausdruck im Text lässt z. B. die Dicke weg); Rundmaterial mit Ø
      const zahlen = (g.masse ?? []).map((x) => String(x).replace('.', ','));
      const mass = !zahlen.length ? '' : g.form === 'Rund' ? `Ø${zahlen[0]}${zahlen.length > 1 ? ` × ${zahlen.slice(1).join(' × ')}` : ''} mm` : `${zahlen.join(' × ')} mm`;
      const material = [g.werkstoff, g.zustand].filter(Boolean).join(' ');
      return {
        werkstoff: g.werkstoff, zustand: g.zustand, form: g.form, masse: g.masse, einheit, menge,
        name: [material || 'Material', [g.form, mass].filter(Boolean).join(' ')].filter(Boolean).join(' · '),
        material, abmessungText: [g.form, mass].filter(Boolean).join(' '),
      };
    }),
  };
}
