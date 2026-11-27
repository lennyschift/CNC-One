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

export function leererArbeitsgang(typ, uid, name = '') {
  return {
    id: uid(), name, typ, maschine: '', satz: 0, ruestMin: 0, stueckMin: 0,
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
// Rohmaterial: Stand aus dem Lager (vom Server: ohne | entnommen | reserviert | lager | teilweise | fehlt) für Karte,
// Liste und Kalender. Fertig melden geht erst, wenn feststeht, welches Material verwendet wurde.
export const MATERIAL = {
  reserviert: { kurz: 'Material reserviert', klasse: 'bg-ok/10 text-ok' },
  lager: { kurz: 'Material im Lager', klasse: 'bg-ok/10 text-ok' },
  teilweise: { kurz: 'Material teilweise', klasse: 'bg-warn/10 text-warn' },
  fehlt: { kurz: 'Material fehlt', klasse: 'bg-accent-soft text-accent' },
  entnommen: { kurz: 'Material entnommen', klasse: 'bg-surface2 text-mute' },
  ohne: { kurz: 'Rohmaterial offen', klasse: 'bg-surface2 text-mute' },
};
const rohVollstaendig = (s) => !!(s?.werkstoff && s?.abmessungId && Number(s?.laenge) > 0);
export const materialFehlt = (fb) => !!fb && rohVollstaendig(fb.roh?.spez) && !(fb.roh?.entnahmen ?? []).length && !fb.roh?.ohneLager;
// Wird das Bauteil mit dieser Buchung fertig? (der letzte Arbeitsgang erreicht die Sollmenge)
export function wirdFertig(fb, agId, menge) {
  const ags = fb?.arbeitsgaenge ?? [];
  const letzter = ags.at(-1);
  return !!letzter && letzter.id === agId && letzter.gebucht + Number(menge || 0) >= fb.menge;
}
// Verbrauch einer Entnahme wie auf dem Server (logic/rohlager.py): Stangen/Platten raus, Reststück zurück
export function entnahmeRechnen(charge, stueck, restLaenge = 0, restBreite = 0, menge = 0) {
  const st = Math.floor(Number(stueck) || 0);
  const platte = charge?.form === 'Platte';
  const rl = Number(restLaenge) || 0, rb = Number(restBreite) || 0;
  const verbraucht = platte ? st * num(charge?.laenge) * num(charge?.breite) - rl * rb : st * num(charge?.laenge) - rl;
  return { verbraucht: Math.max(0, verbraucht), einheit: platte ? 'mm²' : 'mm', jeStueck: menge > 0 ? Math.max(0, verbraucht) / menge : 0 };
}
// Vorschlag: so viele Stangen/Platten, wie für die Menge nötig sind, und das Reststück, das übrig bleibt (nur Stangen)
export function entnahmeVorschlag(charge, spez, menge) {
  const je = Number(charge?.jeEinheit) || 0;
  const stueck = je ? Math.min(Math.max(1, Math.ceil(menge / je)), charge.stueck || 1) : 1;
  if (charge?.form === 'Platte' || !je) return { stueck, restLaenge: 0 };
  const zuschnitt = num(spez?.laenge) + num(spez?.saege);
  const rest = stueck * num(charge.laenge) - Math.min(menge, stueck * je) * zuschnitt;
  // ein Rest unter einem Zuschnitt lohnt nicht zurück ins Lager
  return { stueck, restLaenge: rest >= zuschnitt ? Math.floor(rest) : 0 };
}

// Checkliste vor dem Start: Pflichtpunkte, die noch nicht abgehakt sind, und der Stand (erledigt / alle)
export const checkOffen = (fb) => (fb?.checkliste ?? []).filter((p) => p.pflicht && !p.erledigt);
export const checkStand = (fb) => ({ erledigt: (fb?.checkliste ?? []).filter((p) => p.erledigt).length, alle: (fb?.checkliste ?? []).length });
// Vor dem Start (Offen → In Fertigung, auch durch die erste Buchung) muss die Checkliste stimmen
export const startPruefen = (fb, neuerStatus = 'In Fertigung') => !!fb && fb.status === 'Offen' && neuerStatus !== 'Offen' && checkOffen(fb).length > 0;

export function felderVon(fb) {
  return {
    prioritaet: fb.prioritaet,
    termin: fb.termin || '',
    rohmaterial: { ...fb.rohmaterial },
    notizen: { ...fb.notizen },
    arbeitsgaenge: fb.arbeitsgaenge.map((a) => ({
      id: a.id, name: a.name, typ: a.typ, geplantAm: a.geplantAm || '', maschine: a.maschine ?? '', ruestMin: num(a.ruestMin), stueckMin: num(a.stueckMin),
      lieferant: a.lieferant ?? '', bestellung: a.bestellung ?? '',
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

// ---- Arbeitsgänge, Maschinen und Ist-Zeiten

// Maschinen, die eine Arbeitsgangart können (ohne Angabe an der Maschine: alle)
export const maschinenFuer = (maschinen, art) => (maschinen ?? []).filter((m) => !m.arbeitsgaenge?.length || !art || m.arbeitsgaenge.includes(art));

// Hat ein interner Arbeitsgang beim Fertigwerden schon Zeiten gemeldet?
export const zeitGemeldet = (ag) => !!ag.istAm;

// Interne Arbeitsgänge, die durch eine Buchung bzw. „Fertig“ abgeschlossen werden und noch keine Zeiten haben
// (beim Abschließen sind Zeiten Pflicht). Frühere Arbeitsgänge werden beim Buchen mit abgehakt.
export function zeitenNoetigBeiBuchung(fb, agId, menge) {
  const i = fb.arbeitsgaenge.findIndex((a) => a.id === agId);
  if (i < 0) return [];
  const neu = num(fb.arbeitsgaenge[i].gebucht) + num(menge);
  return fb.arbeitsgaenge.filter((a, k) => k <= i && a.typ === 'intern' && !zeitGemeldet(a) && num(a.gebucht) < fb.menge && Math.max(num(a.gebucht), neu) >= fb.menge);
}
export const zeitenNoetigBeiFertig = (fb) => fb.arbeitsgaenge.filter((a) => a.typ === 'intern' && !zeitGemeldet(a) && num(a.gebucht) < fb.menge);

// Fertige interne Arbeitsgänge ohne Zeiten (z. B. aus der Zeit vor der Zeitmeldung oder mit abgehakt durch eine Fremdvergabe)
export const zeitenFehlen = (fb) => fb.arbeitsgaenge.filter((a) => a.typ === 'intern' && num(a.gebucht) >= fb.menge && !zeitGemeldet(a));

// Soll-Minuten eines Arbeitsgangs für die ganze Menge
export const sollMinuten = (ag, menge) => (ag.typ === 'fremd' ? 0 : num(ag.ruestMin) + num(ag.stueckMin) * num(menge));
export const istMinuten = (ag) => num(ag.istRuestMin) + num(ag.istBearbMin);

// Alle Arbeitsgänge als flache Liste { fb, ag, index }
export function alleArbeitsgaenge(fertigungsbauteile) {
  const out = [];
  for (const fb of fertigungsbauteile) fb.arbeitsgaenge.forEach((ag, index) => out.push({ fb, ag, index }));
  return out;
}

// Datum als JJJJ-MM-TT (lokal)
export const tagIso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export function wocheVon(datum) {
  const d = new Date(datum.getFullYear(), datum.getMonth(), datum.getDate());
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d;
}
export function tageAb(start, anzahl) {
  return Array.from({ length: anzahl }, (_x, i) => { const d = new Date(start); d.setDate(d.getDate() + i); return d; });
}
// Kalenderwoche nach ISO 8601
export function kw(datum) {
  const d = new Date(Date.UTC(datum.getFullYear(), datum.getMonth(), datum.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const jahr = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - jahr) / 86400000 + 1) / 7);
}

// Auslastung je Maschine und Tag: noch offene Soll-Minuten der eingeplanten Arbeitsgänge gegen die verfügbaren Stunden.
// { [maschine]: { [tag]: minuten } }; nicht eingeplante offene Arbeitsgänge stehen unter `ungeplant`.
export function auslastung(fertigungsbauteile) {
  const plan = {};
  const ungeplant = {};
  for (const { fb, ag } of alleArbeitsgaenge(fertigungsbauteile)) {
    if (ag.typ === 'fremd' || num(ag.gebucht) >= fb.menge || fb.status === 'Fertig') continue;
    const m = ag.maschine || '';
    const min = restMinuten(ag, fb.menge);
    if (ag.geplantAm) {
      plan[m] ??= {};
      plan[m][ag.geplantAm] = (plan[m][ag.geplantAm] ?? 0) + min;
    } else {
      ungeplant[m] = (ungeplant[m] ?? 0) + min;
    }
  }
  return { plan, ungeplant };
}

// Soll/Ist der abgeschlossenen internen Arbeitsgänge mit gemeldeten Zeiten, gruppiert nach `nach` ('maschine' | 'art' | 'bauteil').
// Je Gruppe: anzahl, soll/ist in Minuten (Rüsten und Bearbeiten getrennt), abweichung in Prozent (ist/soll − 1).
export function sollIst(fertigungsbauteile, nach = 'maschine') {
  const g = new Map();
  for (const { fb, ag } of alleArbeitsgaenge(fertigungsbauteile)) {
    if (ag.typ === 'fremd' || !zeitGemeldet(ag)) continue;
    const key = nach === 'art' ? ag.name || 'ohne Name' : nach === 'bauteil' ? [fb.teil.teilenummer, fb.teil.name].filter(Boolean).join(' · ') || fb.id : ag.maschine || 'ohne Maschine';
    if (!g.has(key)) g.set(key, { name: key, anzahl: 0, sollRuest: 0, sollBearb: 0, istRuest: 0, istBearb: 0, eintraege: [] });
    const x = g.get(key);
    const menge = Math.max(num(ag.gebucht), num(fb.menge));
    x.anzahl += 1;
    x.sollRuest += num(ag.ruestMin);
    x.sollBearb += num(ag.stueckMin) * menge;
    x.istRuest += num(ag.istRuestMin);
    x.istBearb += num(ag.istBearbMin);
    x.eintraege.push({ fb, ag, menge });
  }
  return [...g.values()].map((x) => {
    const soll = x.sollRuest + x.sollBearb;
    const ist = x.istRuest + x.istBearb;
    return { ...x, soll, ist, abweichung: soll > 0 ? ist / soll - 1 : null };
  }).sort((a, b) => a.name.localeCompare(b.name));
}
