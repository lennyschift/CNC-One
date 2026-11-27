import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import { zahlAus, preiseinheitAus, zeilenAus, positionenAus, kopfAus, bestellungLesen, vorlageAus, kwDatum, zeichnungAus, seriennummernAus, istSerienZeile } from './bestellung.js';

// Text mit Lage aus einer echten Bestellung (Bankverbindung entfernt)
const ECHT = JSON.parse(fs.readFileSync(new URL('./testdaten/bestellungen.json', import.meta.url), 'utf8'));

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
    expect(spalten.map((s) => s.rolle)).toEqual(['bestellposition', 'teilenummer', 'bezeichnung', 'menge', 'einheit', 'preis', 'preiseinheit', 'betrag']);
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

describe('Bestellung über zwei Seiten mit Kästchen im Kopf (echtes PDF)', () => {
  const r = bestellungLesen(ECHT.eiberger);
  it('liest alle Positionen beider Seiten, Fußzeilen stören nicht', () => {
    expect(r.positionen.map((p) => [p.bestellposition, p.teilenummer, p.menge, p.preis, p.betrag])).toEqual([
      ['1', '215975', 5, 373, 1865], ['2', '215810', 10, 38, 380], ['3', '216011', 10, 15, 150], ['4', '216067', 20, 56.2, 1124],
      ['5', '216085', 10, 75, 750], ['6', '216083', 10, 40, 400], ['7', '216084', 10, 40, 400], ['8', '216043', 20, 34, 680],
    ]);
    expect(r.positionen.reduce((s, p) => s + p.betrag, 0)).toBe(5749);
    expect(r.positionen[4].text).not.toMatch(/Seite 2|Ust-IdNr/);
  });
  it('Bestellnummer unter dem Stichwort, Liefertermin KW50 für alle, Zeichnung mit Index', () => {
    expect(r.kopf).toMatchObject({ bestellnr: '20260050', datum: '2026-11-05', liefertermin: '2026-12-11' });
    expect(r.positionen.every((p) => p.termin === '2026-12-11')).toBe(true);
    expect(r.positionen[0]).toMatchObject({ bezeichnung: 'Fahrzeugdeckel MPU5', zeichnungsnr: '10241355', index: 'A' });
    expect(r.positionen[5]).toMatchObject({ zeichnungsnr: '10242012', index: '' });
  });
  it('Kalenderwoche und Zeichnungsnummer', () => {
    expect(kwDatum('KW 3/2027')).toBe('2027-01-22');
    expect(kwDatum('KW2', '2026-11-05')).toBe('2027-01-15'); // Woche schon vorbei: nächstes Jahr
    expect(kwDatum('ohne')).toBe('');
    expect(zeichnungAus('Zeichnung Z-4711 Rev. B')).toEqual({ zeichnungsnr: 'Z-4711', index: 'B' });
  });
});

describe('Zweizeilige Spalten', () => {
  // Aufbau wie bei manchen Kunden: Bezeichnung und Materialnummer untereinander, unter dem Liefertermin das Zeichnungsdatum
  const zwei = seite([
    [0.2, [[0.05, 'Pos.'], [0.12, 'Details / Materialnummer', 0.14], [0.42, 'Lief.dat. / MOD Dat.', 0.1], [0.56, 'Menge'], [0.62, 'ME'], [0.7, 'Preis pro Einheit in EUR', 0.12], [0.88, 'Betrag in EUR', 0.08]]],
    [0.23, [[0.05, '00010'], [0.12, 'ZZ RING_1.5 MM', 0.1], [0.42, '09.12.2026', 0.06], [0.56, '300,00'], [0.62, 'ST'], [0.77, '13,13'], [0.9, '3.940,00']]],
    [0.25, [[0.12, 'ZZ31175378AB', 0.08], [0.42, '24.03.26', 0.05]]],
    [0.29, [[0.05, '00020'], [0.12, 'ZZ WASHER_5X11X1,5', 0.12], [0.42, '09.12.2026', 0.06], [0.56, '200,00'], [0.62, 'ST'], [0.78, '5,83'], [0.9, '1.165,00']]],
    [0.31, [[0.12, 'ZZ31608023', 0.07], [0.42, '11.03.24', 0.05]]],
  ]);
  it('obere Zeile Bezeichnung und Liefertermin, untere Teilenummer und Zeichnungsdatum', () => {
    const { spalten, positionen } = positionenAus(zeilenAus([zwei]));
    expect(spalten[1]).toMatchObject({ rolle: 'bezeichnung', rolle2: 'teilenummer' });
    expect(spalten[2]).toMatchObject({ rolle: 'liefertermin', rolle2: 'zeichnungsdatum' });
    expect(positionen.length).toBe(2);
    expect(positionen[0]).toMatchObject({ bestellposition: '00010', bezeichnung: 'ZZ RING_1.5 MM', teilenummer: 'ZZ31175378AB', termin: '2026-12-09', zeichnungsdatum: '2026-03-24', menge: 300, einheit: 'ST', preis: 13.13, betrag: 3940 });
    expect(positionen[1]).toMatchObject({ teilenummer: 'ZZ31608023', zeichnungsdatum: '2024-03-11', betrag: 1165 });
    // alles aus dem PDF bleibt sichtbar
    expect(positionen[0].angaben).toContainEqual({ spalte: 'Details / Materialnummer', wert: 'ZZ RING_1.5 MM / ZZ31175378AB' });
  });
  it('umgebrochene Überschrift über zwei Zeilen', () => {
    const s = seite([
      [0.2, [[0.05, 'Pos.'], [0.12, 'Details /', 0.06], [0.42, 'Lief.dat. / MOD', 0.09], [0.56, 'Menge'], [0.62, 'ME'], [0.74, 'Preis pro', 0.06], [0.88, 'Betrag in', 0.06]]],
      [0.212, [[0.12, 'Materialnummer', 0.09], [0.42, 'Dat.', 0.03], [0.74, 'Einheit in EUR', 0.08], [0.9, 'EUR', 0.03]]],
      [0.24, [[0.05, '00010'], [0.12, 'ZZ RING', 0.06], [0.42, '09.12.2026', 0.06], [0.56, '300,00'], [0.62, 'ST'], [0.77, '13,13'], [0.9, '3.940,00']]],
      [0.252, [[0.12, 'ZZ311753', 0.06], [0.42, '24.03.26', 0.05]]],
    ]);
    const { spalten, positionen } = positionenAus(zeilenAus([s]));
    expect(spalten.map((x) => x.rolle)).toEqual(['bestellposition', 'bezeichnung', 'liefertermin', 'menge', 'einheit', 'preis', 'betrag']);
    expect(positionen[0]).toMatchObject({ bezeichnung: 'ZZ RING', teilenummer: 'ZZ311753', zeichnungsdatum: '2026-03-24', preis: 13.13, betrag: 3940 });
  });
  it('angelernt: zwei Rollen in der Vorlage', () => {
    const v = vorlageAus([{ text: 'Details / Materialnummer', rolle: 'bezeichnung', rolle2: 'teilenummer' }]);
    expect(v).toEqual({ 'details / materialnummer': 'bezeichnung|teilenummer' });
    const { spalten } = positionenAus(zeilenAus([zwei]), { spalten: v });
    expect(spalten[1]).toMatchObject({ rolle: 'bezeichnung', rolle2: 'teilenummer' });
  });
});

describe('Seriennummern aus der Bestellung', () => {
  it('Zeilen „Teilenummer/Nummer“ unter der Position', () => {
    const s = seite([
      [0.2, [[0.05, 'Pos.'], [0.12, 'Details / Materialnummer', 0.14], [0.42, 'Lief.dat. / MOD Dat.', 0.1], [0.56, 'Menge'], [0.62, 'ME'], [0.7, 'Preis pro Einheit in EUR', 0.12], [0.88, 'Betrag in EUR', 0.08]]],
      [0.23, [[0.05, '00010'], [0.12, 'ZZ SLEEVE_D9,9 / L14,2', 0.12], [0.42, '17.11.2026', 0.06], [0.56, '10,00'], [0.62, 'ST'], [0.77, '4,50'], [0.9, '45,00']]],
      [0.25, [[0.12, 'ZZ8115283G', 0.07], [0.42, '09.12.24', 0.05]]],
      ...Array.from({ length: 10 }, (_, i) => [0.27 + i * 0.015, [[0.3, `ZZ8115283G/${String(81 + i).padStart(4, '0')}`, 0.1]]]),
      [0.45, [[0.05, '00020'], [0.12, 'ZZ RING', 0.06], [0.42, '17.11.2026', 0.06], [0.56, '5,00'], [0.62, 'ST'], [0.77, '1,00'], [0.9, '5,00']]],
      [0.47, [[0.12, 'ZZ999', 0.04], [0.42, '01.01.25', 0.05]]],
    ]);
    const { positionen } = positionenAus(zeilenAus([s]));
    expect(positionen.length).toBe(2);
    expect(positionen[0]).toMatchObject({ teilenummer: 'ZZ8115283G', bezeichnung: 'ZZ SLEEVE_D9,9 / L14,2', menge: 10 });
    expect(positionen[0].serien).toMatchObject({ von: 81, bis: 90, anzahl: 10, stellen: 4, praefix: 'ZZ8115283G', luecken: false });
    // die Seriennummern landen nicht in den Spalten
    expect(positionen[0].angaben.find((a) => a.spalte === 'Details / Materialnummer').wert).toBe('ZZ SLEEVE_D9,9 / L14,2 / ZZ8115283G');
    expect(positionen[1].serien).toBeNull();
  });
  it('Bereich im Text und Lücken', () => {
    expect(seriennummernAus(['Seriennummer 0081 - 0085'])).toMatchObject({ von: 81, bis: 85, anzahl: 5, stellen: 4 });
    expect(seriennummernAus(['SN: 7 bis 9'])).toMatchObject({ von: 7, bis: 9 });
    expect(seriennummernAus(['ZZ1/0001', 'ZZ1/0003'], 'ZZ1')).toMatchObject({ anzahl: 2, luecken: true });
    expect(seriennummernAus(['ANDERE/0001'], 'ZZ1')).toBeNull();
    expect(istSerienZeile('ZZ8115283G/0081')).toBe(true);
    expect(istSerienZeile('Zeichnung 4711/02 Rev A')).toBe(false);
  });
});
