import { describe, it, expect } from 'vitest';
import { planAus, felderVon, leererArbeitsgang, produziert, fortschritt, ueberproduktion, nachzuholen, fremdGebucht, nochNichtGesendet, arbeitsgangStatus, autoStatus, restMinuten, lasten, tageBis } from './fertigung.js';

const ag = (extra = {}) => ({ id: 'a', name: 'Fertigen', typ: 'intern', maschine: 'CTX400', ruestMin: 30, stueckMin: 2, status: 'Offen', gebucht: 0, lieferant: '', fremdStatus: '', ...extra });
const fb = (extra = {}) => ({ id: 'f', menge: 10, status: 'Offen', termin: '', arbeitsgaenge: [ag()], ...extra });

describe('Arbeitsplan und Arbeitsgänge', () => {
  const plan = [
    { id: 'p1', name: 'Drehen', typ: 'intern', maschine: 'CTX400', satz: 88, ruestMin: 45, stueckMin: 2.5 },
    { id: 'p2', name: 'Oberflächenbehandlung', typ: 'fremd', lieferant: 'Eloxal GmbH', fremdProStk: 1.2 },
  ];
  it('Plan wird ohne Buchungsstand zurückgespeichert', () => {
    const ags = plan.map((p) => ({ ...p, id: 'neu', planId: p.id, gebucht: 7 }));
    const p = planAus(ags, () => 'q');
    expect(p[0]).toEqual({ id: 'p1', name: 'Drehen', typ: 'intern', maschine: 'CTX400', satz: 88, ruestMin: 45, stueckMin: 2.5, lieferant: '', fremdProStk: 0, fremdEinmal: 0, anfrageId: '', serie: false });
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

describe('bearbeitbare Felder', () => {
  it('enthalten keinen Buchungsstand', () => {
    const f = felderVon(fb({ prioritaet: 'Hoch', termin: '2026-12-01', rohmaterial: { charge: 'A' }, notizen: { pruefmasse: 'ok' }, arbeitsgaenge: [ag({ gebucht: 7, status: 'Läuft' })] }));
    expect(f).toMatchObject({ prioritaet: 'Hoch', termin: '2026-12-01', rohmaterial: { charge: 'A' }, notizen: { pruefmasse: 'ok' } });
    expect(f.arbeitsgaenge[0]).toEqual({ id: 'a', name: 'Fertigen', maschine: 'CTX400', satz: 0, ruestMin: 30, stueckMin: 2, lieferant: '', fremdProStk: 0, fremdEinmal: 0, bestellung: '' });
  });
  it('sind gleich, solange nichts geändert wird', () => {
    const x = fb({ rohmaterial: {}, notizen: {} });
    expect(JSON.stringify(felderVon(x))).toBe(JSON.stringify(felderVon(x)));
  });
});
