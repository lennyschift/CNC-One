// Regeln der Fertigung. Reine Funktionen, getestet in fertigung.test.js.
import { num } from './calc.js';

export const STATUS = ['Offen', 'In Fertigung', 'Fertig'];

// Eintrag des Arbeitsplans (ohne Buchungsstand) zum Speichern am Bauteil.
export function planAus(arbeitsgaenge, uid) {
  return (arbeitsgaenge ?? []).map((a) => ({
    id: a.planId || a.id || uid(),
    name: a.name,
    typ: a.typ,
    maschine: a.maschine ?? '',
    satz: num(a.satz),
    ruestMin: num(a.ruestMin),
    stueckMin: num(a.stueckMin),
    lieferant: a.lieferant ?? '',
    fremdProStk: num(a.fremdProStk),
    fremdEinmal: num(a.fremdEinmal),
    anfrageId: a.anfrageId ?? '',
    serie: !!a.serie,
  }));
}

export function leererArbeitsgang(typ, uid) {
  return {
    id: uid(), name: '', typ, maschine: '', satz: 0, ruestMin: 0, stueckMin: 0,
    lieferant: '', fremdProStk: 0, fremdEinmal: 0, anfrageId: '', serie: false,
  };
}

// Fremdvergabe: gebucht ist, was vom Lieferanten zurück ist. Sendungen können Teilmengen sein.
export const fremdGebucht = (ag) => (ag.sendungen ?? []).filter((s) => s.datumZurueck).reduce((s, x) => s + num(x.menge), 0);
export const sendungenSumme = (ag) => (ag.sendungen ?? []).reduce((s, x) => s + num(x.menge), 0);
export const nochNichtGesendet = (fb, ag) => Math.max(0, fb.menge - sendungenSumme(ag));

// Stückzahl, die alle Arbeitsgänge durchlaufen hat.
export function produziert(fb) {
  if (!fb.arbeitsgaenge.length) return 0;
  return Math.min(...fb.arbeitsgaenge.map((a) => num(a.gebucht)));
}

// Mehr als bestellt produziert: die Überproduktion wird später ins Lager eingebucht.
export const ueberproduktion = (fb) => Math.max(0, produziert(fb) - fb.menge);

export const fortschritt = (fb) => (fb.menge > 0 ? Math.min(1, produziert(fb) / fb.menge) : 0);

// Wird in einem Arbeitsgang auf `neueGesamt` gebucht, gelten alle früheren Arbeitsgänge mindestens
// bis zu dieser Menge als erledigt. Liefert die dafür nötigen Nachbuchungen.
export function nachzuholen(fb, agId, neueGesamt) {
  const i = fb.arbeitsgaenge.findIndex((a) => a.id === agId);
  const korrekturen = [];
  for (let k = 0; k < i; k++) {
    const delta = neueGesamt - num(fb.arbeitsgaenge[k].gebucht);
    if (delta > 0) korrekturen.push({ agId: fb.arbeitsgaenge[k].id, delta });
  }
  return korrekturen;
}

// Status aus dem Stand der Arbeitsgänge. Ohne Arbeitsgänge bleibt das Bauteil offen.
export function autoStatus(fb) {
  const ags = fb.arbeitsgaenge;
  if (ags.length && ags.every((a) => num(a.gebucht) >= fb.menge)) return 'Fertig';
  if (ags.some((a) => num(a.gebucht) > 0 || a.status === 'Läuft')) return 'In Fertigung';
  return 'Offen';
}

export function arbeitsgangStatus(ag, menge) {
  if (num(ag.gebucht) >= menge) return 'Fertig';
  const unterwegs = (ag.sendungen ?? []).some((s) => s.datumWeg && !s.datumZurueck);
  if (num(ag.gebucht) > 0 || unterwegs) return 'Läuft';
  return 'Offen';
}

// Die frei bearbeitbaren Felder eines Fertigungsbauteils (ohne Buchungsstand, Status und Sendungen).
// Sie werden automatisch gespeichert; der Server übernimmt nur diese Felder.
export function felderVon(fb) {
  return {
    prioritaet: fb.prioritaet,
    termin: fb.termin || '',
    rohmaterial: { ...fb.rohmaterial },
    notizen: { ...fb.notizen },
    arbeitsgaenge: fb.arbeitsgaenge.map((a) => ({
      id: a.id, name: a.name, maschine: a.maschine ?? '', satz: num(a.satz), ruestMin: num(a.ruestMin), stueckMin: num(a.stueckMin),
      lieferant: a.lieferant ?? '', fremdProStk: num(a.fremdProStk), fremdEinmal: num(a.fremdEinmal), bestellung: a.bestellung ?? '',
    })),
  };
}

// Noch offene Minuten eines Arbeitsgangs (Rüsten nur, solange noch nichts gebucht ist).
export function restMinuten(ag, menge) {
  if (ag.typ === 'fremd') return 0;
  const rest = Math.max(0, menge - num(ag.gebucht));
  return (num(ag.gebucht) > 0 ? 0 : num(ag.ruestMin)) + num(ag.stueckMin) * rest;
}

// Auslastung je Maschine bzw. Lieferant aus allen offenen Arbeitsgängen.
export function lasten(fertigungsbauteile) {
  const m = new Map();
  for (const fb of fertigungsbauteile) {
    if (fb.status === 'Fertig') continue;
    for (const ag of fb.arbeitsgaenge) {
      if (num(ag.gebucht) >= fb.menge) continue;
      const key = ag.typ === 'fremd' ? (ag.lieferant || 'Fremdvergabe ohne Lieferant') : (ag.maschine || 'Ohne Maschine');
      if (!m.has(key)) m.set(key, { name: key, fremd: ag.typ === 'fremd', eintraege: [], minuten: 0 });
      const g = m.get(key);
      g.eintraege.push({ fb, ag });
      g.minuten += restMinuten(ag, fb.menge);
    }
  }
  const termin = (e) => e.fb.termin || '9999-12-31';
  for (const g of m.values()) g.eintraege.sort((a, b) => termin(a).localeCompare(termin(b)));
  return [...m.values()].sort((a, b) => Number(a.fremd) - Number(b.fremd) || a.name.localeCompare(b.name));
}

// Tage bis zum Termin (negativ = überfällig), null ohne Termin.
export function tageBis(termin, heute = new Date()) {
  if (!termin) return null;
  const a = new Date(termin + 'T00:00:00');
  const b = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate());
  return Math.round((a - b) / 86400000);
}
