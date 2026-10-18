import { describe, it, expect } from 'vitest';
import { ausPlan, planAus, leererArbeitsgang, produziert, fortschritt, ueberproduktion, nachzuholen, fremdGebucht, nochNichtGesendet, arbeitsgangStatus, normalisiere, autoStatus, restMinuten, lasten, tageBis } from './fertigung.js';

const ag = (extra = {}) => ({ id: 'a', name: 'Fertigen', typ: 'intern', maschine: 'CTX400', ruestMin: 30, stueckMin: 2, status: 'Offen', gebucht: 0, lieferant: '', fremdStatus: '', ...extra });
const fb = (extra = {}) => ({ id: 'f', menge: 10, status: 'Offen', termin: '', arbeitsgaenge: [ag()], ...extra });

describe('Arbeitsplan und Arbeitsgänge', () => {
  const plan = [
    { id: 'p1', name: 'Drehen', typ: 'intern', maschine: 'CTX400', satz: 88, ruestMin: 45, stueckMin: 2.5 },
    { id: 'p2', name: 'Oberflächenbehandlung', typ: 'fremd', lieferant: 'Eloxal GmbH', fremdProStk: 1.2 },
  ];
  it('Fertigungsbauteil übernimmt den Arbeitsplan mit leerem Buchungsstand', () => {
    const r = ausPlan(plan, () => 'x');
    expect(r).toHaveLength(2);
    expect(r[0]).toMatchObject({ planId: 'p1', name: 'Drehen', maschine: 'CTX400', satz: 88, gebucht: 0, status: 'Offen', sendungen: [] });
    expect(r[1]).toMatchObject({ typ: 'fremd', lieferant: 'Eloxal GmbH', fremdProStk: 1.2 });
  });
  it('ohne Plan entstehen keine Arbeitsgänge', () => {
    expect(ausPlan([], () => 'x')).toEqual([]);
    expect(ausPlan(undefined, () => 'x')).toEqual([]);
  });
  it('Plan wird ohne Buchungsstand zurückgespeichert', () => {
    const ags = ausPlan(plan, () => 'neu');
    ags[0].gebucht = 7;
    const p = planAus(ags, () => 'q');
    expect(p[0]).toEqual({ id: 'p1', name: 'Drehen', typ: 'intern', maschine: 'CTX400', satz: 88, ruestMin: 45, stueckMin: 2.5, lieferant: '', fremdProStk: 0, fremdEinmal: 0, anfrageId: '' });
    expect(p[0]).not.toHaveProperty('gebucht');
  });
  it('neuer Arbeitsgang ist leer und hat einen Typ', () => {
    expect(leererArbeitsgang('fremd', () => 'n')).toMatchObject({ id: 'n', typ: 'fremd', name: '' });
  });
});

describe('Fortschritt', () => {
  it('produziert ist das Minimum über alle Arbeitsgänge', () => {
    const f = fb({ arbeitsgaenge: [ag({ gebucht: 8 }), ag({ gebucht: 5 })] });
    expect(produziert(f)).toBe(5);
    expect(fortschritt(f)).toBe(0.5);
  });
  it('wird bei Überproduktion auf 100 % begrenzt', () => {
    expect(fortschritt(fb({ arbeitsgaenge: [ag({ gebucht: 22 })] }))).toBe(1);
  });
  it('ohne Arbeitsgänge ist nichts produziert', () => {
    expect(produziert(fb({ arbeitsgaenge: [] }))).toBe(0);
  });
});

describe('Überproduktion', () => {
  it('ist der Anteil über der Sollmenge', () => {
    expect(ueberproduktion(fb({ arbeitsgaenge: [ag({ gebucht: 12 })] }))).toBe(2);
  });
  it('zählt nur Teile, die alle Arbeitsgänge durchlaufen haben', () => {
    expect(ueberproduktion(fb({ arbeitsgaenge: [ag({ gebucht: 15 }), ag({ gebucht: 11 })] }))).toBe(1);
  });
  it('ist 0 unter oder genau auf der Sollmenge', () => {
    expect(ueberproduktion(fb({ arbeitsgaenge: [ag({ gebucht: 10 })] }))).toBe(0);
    expect(ueberproduktion(fb({ arbeitsgaenge: [ag({ gebucht: 4 })] }))).toBe(0);
  });
  it('bleibt Fertig, wenn zusätzlich gebucht wird', () => {
    expect(autoStatus(fb({ arbeitsgaenge: [ag({ gebucht: 13 })] }))).toBe('Fertig');
  });
});

describe('Rückwirkend abhaken', () => {
  const dreiAg = () => fb({ menge: 10, arbeitsgaenge: [ag({ id: 'a1', gebucht: 2 }), ag({ id: 'a2', gebucht: 0 }), ag({ id: 'a3', gebucht: 0 })] });
  it('Buchung im letzten Arbeitsgang holt alle vorherigen nach', () => {
    expect(nachzuholen(dreiAg(), 'a3', 10)).toEqual([{ agId: 'a1', delta: 8 }, { agId: 'a2', delta: 10 }]);
  });
  it('Buchung im ersten Arbeitsgang holt nichts nach', () => {
    expect(nachzuholen(dreiAg(), 'a1', 5)).toEqual([]);
  });
  it('bereits weitere Arbeitsgänge werden nicht überschrieben', () => {
    const f = fb({ arbeitsgaenge: [ag({ id: 'a1', gebucht: 10 }), ag({ id: 'a2', gebucht: 0 })] });
    expect(nachzuholen(f, 'a2', 4)).toEqual([]);
  });
});

describe('Fremdvergabe in Sendungen', () => {
  const f = fb({ menge: 50 });
  const fremd = ag({ typ: 'fremd', sendungen: [
    { id: 's1', menge: 10, datumWeg: '2026-10-01', datumZurueck: '2026-10-05' },
    { id: 's2', menge: 15, datumWeg: '2026-10-06', datumZurueck: '' },
  ] });
  it('gebucht ist nur, was zurück ist', () => expect(fremdGebucht(fremd)).toBe(10));
  it('noch nicht gesendet ist der Rest der Menge', () => expect(nochNichtGesendet(f, fremd)).toBe(25));
  it('Status Läuft, solange etwas beim Lieferanten ist', () => expect(arbeitsgangStatus({ ...fremd, gebucht: 0 }, 50)).toBe('Läuft'));
  it('Status Offen ohne Sendung', () => expect(arbeitsgangStatus(ag({ typ: 'fremd', sendungen: [] }), 50)).toBe('Offen'));
  it('Status Fertig, wenn alles zurück ist', () => expect(arbeitsgangStatus({ ...fremd, gebucht: 50 }, 50)).toBe('Fertig'));
});

describe('alte Daten', () => {
  it('Fremdvergabe "Ware zurück" wird zu einer Sendung mit voller Menge', () => {
    const alt = { menge: 20, arbeitsgaenge: [{ id: 'x', typ: 'fremd', gebucht: 20, fremdStatus: 'Ware zurück', datumWeg: '2026-10-01', datumZurueck: '2026-10-04' }] };
    const r = normalisiere(alt);
    expect(r.arbeitsgaenge[0].sendungen).toEqual([{ id: 'x-s', menge: 20, datumWeg: '2026-10-01', datumZurueck: '2026-10-04' }]);
    expect(r.arbeitsgaenge[0]).not.toHaveProperty('fremdStatus');
  });
  it('Fremdvergabe nur "Geplant" bekommt keine Sendung', () => {
    expect(normalisiere({ menge: 5, arbeitsgaenge: [{ id: 'y', typ: 'fremd', fremdStatus: 'Geplant' }] }).arbeitsgaenge[0].sendungen).toEqual([]);
  });
});

describe('autoStatus', () => {
  it('Offen ohne Buchung', () => expect(autoStatus(fb())).toBe('Offen'));
  it('In Fertigung nach erster Buchung', () => expect(autoStatus(fb({ arbeitsgaenge: [ag({ gebucht: 1 })] }))).toBe('In Fertigung'));
  it('Fertig, wenn alle Arbeitsgänge komplett sind', () => {
    expect(autoStatus(fb({ arbeitsgaenge: [ag({ gebucht: 10 }), ag({ gebucht: 12 })] }))).toBe('Fertig');
  });
  it('nicht Fertig, solange ein Arbeitsgang fehlt', () => {
    expect(autoStatus(fb({ arbeitsgaenge: [ag({ gebucht: 10 }), ag({ gebucht: 3 })] }))).toBe('In Fertigung');
  });
});

describe('Zeiten und Last', () => {
  it('Restminuten: Rüsten + Stückzeit × Rest', () => expect(restMinuten(ag(), 10)).toBe(30 + 20));
  it('nach Beginn zählt das Rüsten nicht mehr', () => expect(restMinuten(ag({ gebucht: 4 }), 10)).toBe(12));
  it('Fremdvergabe belastet keine Maschine', () => expect(restMinuten(ag({ typ: 'fremd' }), 10)).toBe(0));

  it('gruppiert nach Maschine, Fremdvergabe zuletzt, nach Termin sortiert', () => {
    const a = fb({ id: 'a', termin: '2026-11-10' });
    const b = fb({ id: 'b', termin: '2026-11-01' });
    const c = fb({ id: 'c', arbeitsgaenge: [ag({ typ: 'fremd', lieferant: 'Eloxal GmbH' })] });
    const g = lasten([a, b, c]);
    expect(g.map((x) => x.name)).toEqual(['CTX400', 'Eloxal GmbH']);
    expect(g[0].eintraege.map((e) => e.fb.id)).toEqual(['b', 'a']);
    expect(g[0].minuten).toBe(100);
  });
  it('fertige Bauteile belasten nichts', () => {
    expect(lasten([fb({ status: 'Fertig' })])).toEqual([]);
  });
});

describe('tageBis', () => {
  const heute = new Date(2026, 9, 17);
  it('zählt Tage', () => expect(tageBis('2026-10-20', heute)).toBe(3));
  it('überfällig ist negativ', () => expect(tageBis('2026-10-15', heute)).toBe(-2));
  it('ohne Termin null', () => expect(tageBis('', heute)).toBeNull());
});
