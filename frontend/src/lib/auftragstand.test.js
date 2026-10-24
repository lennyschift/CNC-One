import { describe, it, expect } from 'vitest';
import { auftragStand } from './auftragstand.js';

const fb = (status) => ({ status });
const geliefert = { status: 'Geliefert' };
const berechnet = { status: 'Berechnet' };

describe('Stand des Auftrags im Ablauf', () => {
  it('ohne Fertigung steht der Auftrag am Anfang, auch wenn schon geliefert wurde', () => {
    expect(auftragStand({ lieferung: geliefert })).toBe(1);
  });
  it('Fertigung läuft: ein Lieferschein vorab hakt die Fertigung nicht ab', () => {
    expect(auftragStand({ fertigungsbauteile: [fb('In Fertigung')], lieferung: { status: 'Teilweise geliefert' } })).toBe(2);
    expect(auftragStand({ fertigungsbauteile: [fb('Fertig'), fb('Offen')], lieferung: geliefert })).toBe(2);
  });
  it('fertig gefertigt, aber noch nicht alles geliefert: Lieferung ist dran', () => {
    expect(auftragStand({ fertigungsbauteile: [fb('Fertig')], lieferung: { status: 'Teilweise geliefert' } })).toBe(3);
  });
  it('alles geliefert: Rechnung ist dran, auch mit Entwurf oder Teilberechnung', () => {
    const f = [fb('Fertig')];
    expect(auftragStand({ fertigungsbauteile: f, lieferung: geliefert, abrechnung: { status: 'Nicht berechnet' } })).toBe(4);
    expect(auftragStand({ fertigungsbauteile: f, lieferung: geliefert, abrechnung: { status: 'Teilweise berechnet' }, rechnungen: [{ art: 'Teilrechnung', status: 'Offen' }] })).toBe(4);
    expect(auftragStand({ fertigungsbauteile: f, lieferung: geliefert, abrechnung: berechnet, rechnungen: [{ art: 'Gesamtrechnung', status: 'Entwurf' }] })).toBe(4);
  });
  it('alles berechnet und festgeschrieben: Zahlung ist dran', () => {
    expect(auftragStand({ fertigungsbauteile: [fb('Fertig')], lieferung: geliefert, abrechnung: berechnet, rechnungen: [{ art: 'Gesamtrechnung', status: 'Offen' }] })).toBe(5);
    expect(auftragStand({ fertigungsbauteile: [fb('Fertig')], lieferung: geliefert, abrechnung: berechnet, rechnungen: [{ art: 'Gesamtrechnung', status: 'Teilbezahlt' }] })).toBe(5);
  });
  it('alles bezahlt: alles erledigt, stornierte Rechnungen zählen nicht', () => {
    const rechnungen = [
      { art: 'Gesamtrechnung', status: 'Storniert' }, { art: 'Storno', status: 'Gutschrift' }, { art: 'Gesamtrechnung', status: 'Bezahlt' },
    ];
    expect(auftragStand({ fertigungsbauteile: [fb('Fertig')], lieferung: geliefert, abrechnung: berechnet, rechnungen })).toBe(6);
  });
});
