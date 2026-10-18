// Regeln der Fertigung. Reine Funktionen, getestet in fertigung.test.js.
import { num } from './calc.js';

export const STATUS = ['Offen', 'In Fertigung', 'Fertig'];

// Arbeitsgang im Fertigungsbauteil aus einem Eintrag des Arbeitsplans (am Bauteil gespeichert).
export function ausPlan(plan, uid) {
  return (plan ?? []).map((p) => ({
    id: uid(),
    planId: p.id ?? '',
    name: p.name ?? '',
    typ: p.typ === 'fremd' ? 'fremd' : 'intern',
    maschine: p.maschine ?? '',
    satz: num(p.satz),
    ruestMin: num(p.ruestMin),
    stueckMin: num(p.stueckMin),
    lieferant: p.lieferant ?? '',
    fremdProStk: num(p.fremdProStk),
    fremdEinmal: num(p.fremdEinmal),
    anfrageId: p.anfrageId ?? '',
    bestellung: '',
    status: 'Offen',
    gebucht: 0,
    sendungen: [],
  }));
}

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
  }));
}

export function leererArbeitsgang(typ, uid) {
  return {
    id: uid(), name: '', typ, maschine: '', satz: 0, ruestMin: 0, stueckMin: 0,
    lieferant: '', fremdProStk: 0, fremdEinmal: 0, anfrageId: '',
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

// Alte, im Browser gespeicherte Fertigungsbauteile auf die aktuelle Form bringen.
export function normalisiere(fb) {
  for (const ag of fb.arbeitsgaenge ?? []) {
    ag.sendungen ??= [];
    ag.satz ??= 0;
    ag.fremdProStk ??= 0;
    ag.fremdEinmal ??= 0;
    ag.anfrageId ??= '';
    ag.bestellung ??= '';
    if (ag.typ === 'fremd' && !ag.sendungen.length && ag.fremdStatus && ag.fremdStatus !== 'Geplant') {
      ag.sendungen.push({ id: ag.id + '-s', menge: fb.menge, datumWeg: ag.datumWeg || '', datumZurueck: ag.fremdStatus === 'Ware zurück' ? (ag.datumZurueck || ag.datumWeg || '') : '' });
    }
    delete ag.fremdStatus;
    delete ag.datumWeg;
    delete ag.datumZurueck;
  }
  return fb;
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
