import { describe, it, expect } from 'vitest';
import { kalkulationUebernehmen, festpreisUebernehmen, preisText } from './historie.js';
// Bauteil der Workbench, verkürzt
const neuesTeil = (name = 'Neu') => ({ name, teilenummer: '', menge: 10, ruestMin: 0, stueckMin: 0, messkosten: 0, preisart: 'kalkuliert', festpreis: 0, staffel: { aktiv: false, stufen: [] }, arbeitsgaenge: [], dateien: [] });

const eur = (x) => `${x.toFixed(2)} €`;

describe('Preise aus der Historie', () => {
  it('Kalkulation übernehmen, Angaben des Bauteils bleiben', () => {
    const t = { ...neuesTeil('Flansch'), teilenummer: 'ZZ-1', menge: 40, dateien: [{ name: 'a.pdf' }] };
    const alt = { ...neuesTeil('Alt'), teilenummer: 'X', menge: 10, ruestMin: 90, stueckMin: 7, messkosten: 45, arbeitsgaenge: [{ id: 'a', name: 'Drehen', anfrageId: 'ANF-1' }] };
    let n = 0;
    kalkulationUebernehmen(t, alt, () => `neu${++n}`);
    expect(t).toMatchObject({ name: 'Flansch', teilenummer: 'ZZ-1', menge: 40, ruestMin: 90, stueckMin: 7, messkosten: 45 });
    expect(t.dateien.length).toBe(1);
    expect(t.arbeitsgaenge).toEqual([{ id: 'neu1', name: 'Drehen', anfrageId: '' }]);
    alt.arbeitsgaenge[0].name = 'geändert';
    expect(t.arbeitsgaenge[0].name).toBe('Drehen'); // Kopie, kein Verweis
  });

  it('Stückpreise als festen Preis, mit Staffeln', () => {
    const t = neuesTeil();
    festpreisUebernehmen(t, { preise: [{ menge: 25, einzel: 28.4 }, { menge: 100, einzel: 24.1 }] });
    expect(t.preisart).toBe('fest');
    expect(t.staffel.aktiv).toBe(true);
    expect(t.staffel.stufen).toEqual([{ menge: 25, extra: 0, preis: 28.4 }, { menge: 100, extra: 0, preis: 24.1 }]);
    const u = neuesTeil();
    festpreisUebernehmen(u, { einzelpreis: 20, jeStueck: 26, menge: 10 }, { umgelegt: true });
    expect(u.festpreis).toBe(26);
    expect(u.staffel.aktiv).toBe(false);
  });

  it('Preistext', () => {
    expect(preisText({ preise: [{ menge: 25, einzel: 28.4 }] }, eur)).toBe('25 Stk 28.40 €');
    expect(preisText({ einzelpreis: 5, menge: 3 }, eur)).toBe('3 Stk 5.00 €');
  });
});
