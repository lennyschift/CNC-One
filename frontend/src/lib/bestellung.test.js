import { describe, it, expect } from 'vitest';
import { zahlAus, preiseinheitAus, zeilenAus, positionenAus, kopfAus, bestellungLesen, vorlageAus } from './bestellung.js';

// Seite aus Zeilen bauen: [y, [[x, text, breite], …]] (Lage 0 bis 1 wie zeichnungText.js)
const seite = (zeilen) => ({ elemente: zeilen.flatMap(([y, zellen]) => zellen.map(([x, text, b]) => ({ text, x, y, b: b ?? text.length * 0.007, h: 0.012 }))) });

// Bestellung im Stil eines SAP-Ausdrucks (eigene Testwerte)
const sap = seite([
  [0.05, [[0.06, 'ZZ Bestellkunde GmbH'], [0.6, 'Bestellnummer'], [0.75, '4500012345']]],
  [0.07, [[0.06, 'Einkauf'], [0.6, 'Datum'], [0.75, '18.11.2026']]],
  [0.09, [[0.06, 'Ansprechpartner: einkauf@zz-kunde.de']]],
  [0.2, [[0.06, 'Pos.'], [0.12, 'Material'], [0.3, 'Bezeichnung'], [0.55, 'Menge'], [0.63, 'ME'], [0.7, 'Preis'], [0.78, 'PE'], [0.86, 'Gesamtwert']]],
  [0.23, [[0.06, '00010'], [0.12, 'ZZ-4711-01'], [0.3, 'Flansch DN50'], [0.56, '25'], [0.63, 'ST'], [0.7, '28,40'], [0.79, '1'], [0.86, '710,00']]],
  [0.25, [[0.12, 'Liefertermin: 15.01.2027'], [0.3, 'Zeichnung Z-4711 Rev. B']]],
  [0.28, [[0.06, '00020'], [0.12, 'ZZ-0815'], [0.3, 'Distanzhülse'], [0.55, '500'], [0.63, 'ST'], [0.7, '1.250,00'], [0.78, '100'], [0.86, '6.250,00']]],
  [0.30, [[0.12, 'Liefertermin: 22.01.2027']]],
  [0.35, [[0.06, 'Gesamtnettowert'], [0.86, '6.960,00']]],
]);

describe('Zahlen und Preiseinheit', () => {
  it('deutsche und englische Schreibweise', () => {
    expect(zahlAus('1.234,56')).toBe(1234.56);
    expect(zahlAus('1,234.56')).toBe(1234.56);
    expect(zahlAus('28,40 EUR')).toBe(28.4);
    expect(zahlAus('1.000')).toBe(1000);
    expect(zahlAus('12.5')).toBe(12.5);
    expect(zahlAus('25 ST')).toBe(25);
    expect(zahlAus('abc')).toBeNull();
  });
  it('Preiseinheit im Text', () => {
    expect(preiseinheitAus('12,50 / 100 ST')).toBe(100);
    expect(preiseinheitAus('pro 1.000 Stk')).toBe(1000);
    expect(preiseinheitAus('12,50 EUR')).toBe(1);
  });
});

describe('Bestellung lesen', () => {
  it('Positionen mit Folgezeilen, Preiseinheit und Ende bei der Summe', () => {
    const { positionen, spalten } = positionenAus(zeilenAus([sap]));
    expect(spalten.map((s) => s.rolle)).toEqual(['bestellposition', 'teilenummer', 'bezeichnung', 'menge', '', 'preis', 'preiseinheit', 'betrag']);
    expect(positionen.length).toBe(2);
    expect(positionen[0]).toMatchObject({ bestellposition: '00010', teilenummer: 'ZZ-4711-01', bezeichnung: 'Flansch DN50', menge: 25, preis: 28.4, preiseinheit: 1, betrag: 710, termin: '2027-01-15' });
    expect(positionen[0].text).toContain('Z-4711 Rev. B');
    expect(positionen[1]).toMatchObject({ bestellposition: '00020', menge: 500, preis: 12.5, preiseinheit: 100, betrag: 6250, termin: '2027-01-22' });
  });

  it('Preiseinheit aus dem Betrag, wenn keine Spalte sie nennt', () => {
    const s = seite([
      [0.2, [[0.06, 'Pos'], [0.12, 'Artikel-Nr.'], [0.55, 'Menge'], [0.7, 'Einzelpreis'], [0.86, 'Betrag']]],
      [0.23, [[0.06, '1'], [0.12, 'ZZ-77'], [0.56, '200'], [0.7, '850,00'], [0.86, '1.700,00']]],
    ]);
    const p = positionenAus(zeilenAus([s])).positionen[0];
    expect(p.preiseinheit).toBe(100);
    expect(p.preis).toBe(8.5);
  });

  it('Kopf: Bestellnummer, Datum und Mail', () => {
    expect(kopfAus(zeilenAus([sap]))).toEqual({ bestellnr: '4500012345', datum: '2026-11-18', email: 'einkauf@zz-kunde.de' });
  });

  it('angelernte Überschriften des Kunden', () => {
    const s = seite([
      [0.1, [[0.06, 'Unser Zeichen'], [0.3, 'ZZ-PO-77123']]],
      [0.2, [[0.06, 'Lfd'], [0.12, 'Ihre Ident'], [0.55, 'Bedarf'], [0.7, 'Kosten/Stk']]],
      [0.23, [[0.06, '1'], [0.12, 'ZZ-99'], [0.56, '40'], [0.7, '3,10']]],
    ]);
    const vorlage = { spalten: { lfd: 'bestellposition', 'ihre ident': 'teilenummer', bedarf: 'menge', 'kosten/stk': 'preis' }, kopf: { bestellnr: 'Unser Zeichen' } };
    const r = bestellungLesen([s], vorlage);
    expect(r.positionen[0]).toMatchObject({ bestellposition: '1', teilenummer: 'ZZ-99', menge: 40, preis: 3.1 });
    expect(r.kopf.bestellnr).toBe('ZZ-PO-77123');
    expect(vorlageAus(r.spalten)).toEqual(vorlage.spalten);
  });

  it('ohne erkennbare Tabelle keine Positionen', () => {
    expect(positionenAus(zeilenAus([seite([[0.1, [[0.1, 'Nur ein Brief']]]])])).positionen).toEqual([]);
  });
});
