// Filter für alle Listen. Welche Eigenschaften man filtern kann, wird aus den Daten selbst abgeleitet (nicht fest im Code):
// jede einfache Angabe eines Eintrags, auch in Unterobjekten und Listen (z. B. Positionen → Bauteil → Name).
// Die Seite kann Beschriftungen mitgeben; ohne Beschriftung wird der Name lesbar gemacht. Reine Funktionen (filter.test.js).

const MAX_TIEFE = 3;
const DATUM = /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}.*)?$/;
// Technische Angaben, nach denen niemand filtert (Adressen von Dateien, Bilder, HTML, interne Schlüssel)
const TECHNISCH = /(^|\.)(id|key|url|html|bild|vorschaubild|zeichnung|stepDatei|dateien|datei|agId|posKey|teilId|angebotKey|position_key|zitat)$/i;

// Werte an einem Pfad; Listen unterwegs werden aufgefächert ("positionen.teil.name" → alle Namen)
export function werte(x, pfad) {
  let aktuell = [x];
  for (const teil of pfad.split('.')) {
    const naechste = [];
    for (const w of aktuell) {
      if (w == null) continue;
      const v = w[teil];
      if (Array.isArray(v)) naechste.push(...v);
      else naechste.push(v);
    }
    aktuell = naechste;
  }
  return aktuell.filter((v) => v !== undefined && v !== null && v !== '' && typeof v !== 'object');
}

// "kundeName" → "Kunde Name", "kopf.anfrageNr" → "Kopf › Anfrage Nr"
export function lesbar(pfad) {
  return pfad.split('.').map((t) => t.replace(/([a-zäöü])([A-ZÄÖÜ])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())).join(' › ');
}

function pfadeSammeln(obj, praefix, tiefe, pfade) {
  if (!obj || typeof obj !== 'object' || tiefe > MAX_TIEFE) return;
  for (const [k, v] of Object.entries(obj)) {
    const pfad = praefix ? `${praefix}.${k}` : k;
    if (TECHNISCH.test(pfad)) continue;
    if (Array.isArray(v)) {
      for (const e of v.slice(0, 20)) {
        if (e && typeof e === 'object') pfadeSammeln(e, pfad, tiefe + 1, pfade);
        else if (e !== null && e !== undefined) pfade.add(pfad);
      }
    } else if (v && typeof v === 'object') pfadeSammeln(v, pfad, tiefe + 1, pfade);
    else pfade.add(pfad);
  }
}

// Filterbare Felder einer Liste: [{ pfad, label, typ: 'auswahl' | 'text' | 'zahl' | 'datum' | 'janein', optionen }]
// Auswahl, wenn es wenige verschiedene Werte gibt (z. B. Status, Kunde); sonst Text bzw. Zahl/Datum.
export function felderAus(liste, { beschriftungen = {}, ausblenden = [] } = {}) {
  const stichprobe = (liste ?? []).slice(0, 300);
  const pfade = new Set();
  for (const x of stichprobe) pfadeSammeln(x, '', 0, pfade);
  const felder = [];
  for (const pfad of pfade) {
    if (ausblenden.includes(pfad)) continue;
    const alle = stichprobe.flatMap((x) => werte(x, pfad));
    if (!alle.length) continue;
    const verschieden = [...new Set(alle.map((v) => (typeof v === 'string' ? v.trim() : v)))];
    let typ;
    if (alle.every((v) => typeof v === 'boolean')) typ = 'janein';
    else if (alle.every((v) => typeof v === 'number')) typ = verschieden.length <= 8 && stichprobe.length > 8 ? 'auswahl' : 'zahl';
    else if (alle.every((v) => typeof v === 'string' && DATUM.test(v))) typ = 'datum';
    else if (alle.some((v) => typeof v === 'string' && (v.startsWith('/') || v.startsWith('http') || v.length > 120))) continue;
    else typ = verschieden.length <= 40 ? 'auswahl' : 'text';
    felder.push({
      pfad, typ, label: beschriftungen[pfad] ?? lesbar(pfad),
      optionen: typ === 'auswahl' ? verschieden.sort((a, b) => String(a).localeCompare(String(b), 'de', { numeric: true })) : [],
      bekannt: pfad in beschriftungen,
    });
  }
  // Beschriftete (von der Seite empfohlene) zuerst, dann alphabetisch
  return felder.sort((a, b) => (b.bekannt - a.bekannt) || a.label.localeCompare(b.label, 'de'));
}

// Leerer Filter für ein Feld
export function neuerFilter(feld) {
  const basis = { pfad: feld.pfad, typ: feld.typ };
  if (feld.typ === 'auswahl') return { ...basis, wert: [] };
  if (feld.typ === 'zahl') return { ...basis, op: '>=', wert: null };
  if (feld.typ === 'datum') return { ...basis, von: '', bis: '' };
  if (feld.typ === 'janein') return { ...basis, wert: true };
  return { ...basis, op: 'enthaelt', wert: '' };
}

// Ist der Filter ausgefüllt (sonst wirkt er nicht)?
export function aktiv(f) {
  if (f.typ === 'auswahl') return f.wert?.length > 0;
  if (f.typ === 'zahl') return f.wert !== null && f.wert !== '' && !Number.isNaN(Number(f.wert));
  if (f.typ === 'datum') return !!(f.von || f.bis);
  if (f.typ === 'janein') return typeof f.wert === 'boolean';
  return f.op === 'leer' || f.op === 'nichtleer' || !!String(f.wert ?? '').trim();
}

export function passt(x, f) {
  if (!aktiv(f)) return true;
  const w = werte(x, f.pfad);
  switch (f.typ) {
    case 'auswahl': return w.some((v) => f.wert.includes(typeof v === 'string' ? v.trim() : v));
    case 'janein': return f.wert ? w.includes(true) : !w.includes(true);
    case 'zahl': {
      const z = Number(f.wert);
      return w.some((v) => (f.op === '<=' ? v <= z : f.op === '=' ? v === z : v >= z));
    }
    case 'datum': return w.some((v) => { const d = String(v).slice(0, 10); return (!f.von || d >= f.von) && (!f.bis || d <= f.bis); });
    default: {
      if (f.op === 'leer') return !w.length;
      if (f.op === 'nichtleer') return w.length > 0;
      const q = String(f.wert).trim().toLowerCase();
      const treffer = w.some((v) => String(v).toLowerCase().includes(q));
      return f.op === 'nicht' ? !treffer : treffer;
    }
  }
}

export const anwenden = (liste, filter) => (liste ?? []).filter((x) => (filter ?? []).every((f) => passt(x, f)));

// Kurztext für den Filter-Knopf: "Status: Offen, Gesendet" / "Netto ≥ 1000"
export function beschreibung(f, feld) {
  const name = feld?.label ?? lesbar(f.pfad);
  if (!aktiv(f)) return name;
  if (f.typ === 'auswahl') return `${name}: ${f.wert.length > 2 ? `${f.wert.slice(0, 2).join(', ')} +${f.wert.length - 2}` : f.wert.join(', ')}`;
  if (f.typ === 'janein') return `${name}: ${f.wert ? 'ja' : 'nein'}`;
  if (f.typ === 'zahl') return `${name} ${f.op === '<=' ? '≤' : f.op === '=' ? '=' : '≥'} ${f.wert}`;
  if (f.typ === 'datum') { const de = (d) => d.split('-').reverse().join('.'); return `${name}: ${f.von ? `ab ${de(f.von)}` : ''}${f.von && f.bis ? ' ' : ''}${f.bis ? `bis ${de(f.bis)}` : ''}`; }
  if (f.op === 'leer') return `${name}: leer`;
  if (f.op === 'nichtleer') return `${name}: nicht leer`;
  return `${name} ${f.op === 'nicht' ? 'ohne' : 'enthält'} „${f.wert}“`;
}

// Sortieren nach einer beliebigen Eigenschaft: s = { pfad, richtung: 'auf' | 'ab' }. Bei Listen im Eintrag zählt der
// kleinste (aufsteigend) bzw. größte Wert; Einträge ohne Wert kommen ans Ende. `rang` legt für einzelne Felder eine
// fachliche Reihenfolge fest, z. B. { prioritaet: ['Eilig', 'Hoch', 'Normal'] } (eiligste zuerst).
export function vergleich(a, b) {
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b);
  return String(a).localeCompare(String(b), 'de', { numeric: true });
}
export function sortieren(liste, s, rang = {}) {
  if (!s?.pfad) return [...(liste ?? [])];
  const r = s.richtung === 'ab' ? -1 : 1;
  const reihe = rang[s.pfad];
  const wert = (v) => (reihe ? (reihe.indexOf(v) < 0 ? reihe.length : reihe.indexOf(v)) : v);
  const schluessel = (x) => {
    const w = werte(x, s.pfad).map(wert);
    if (!w.length) return null;
    return w.reduce((a, b) => (r * vergleich(a, b) <= 0 ? a : b));
  };
  return (liste ?? [])
    .map((x, i) => [schluessel(x), i, x])
    .sort(([a, i], [b, j]) => (a === null ? (b === null ? i - j : 1) : b === null ? -1 : r * vergleich(a, b) || i - j))
    .map(([, , x]) => x);
}
