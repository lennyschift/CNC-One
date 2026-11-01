import { describe, it, expect } from 'vitest';
import { tabelleDeuten, rollenMitKopf, datumAus, mengenAus, zeileWerte, passtZu, vorlageAus } from './mailtabelle.js';

// wie die Anfrage-Tabelle aus der Mail (eigene Testwerte)
const anfrage = [
  ['Nr.', 'Partnumber', 'Description', '', 'MOD Date', 'Quantity', 'Delivery date'],
  ['1', 'ZZ-00011-00-X-003', 'PLATE', 'MOUNT_RAIL', '26.06.2026', '2', '20.11..2026 00:00:00'],
  ['2', 'ZZ-00011-90-1-001', 'PLATE', 'MOUNT_SUPPORT', '26.06.2026', '10/25', '04.12.2026'],
  ['', 'TEST', 'schraube', '', '', '', ''],
];

describe('Anfrage-Tabelle deuten', () => {
  it('Kopfzeile und Spalten über Stichwörter (MOD Date ist kein Liefertermin)', () => {
    const t = tabelleDeuten([[['Firma', 'Telefon'], ['ZZ', '0711']], anfrage]);
    expect(t.tabelle).toBe(1);
    expect(t.rollen).toEqual(['', 'teilenummer', '', '', '', 'menge', 'liefertermin']);
    expect(t.zeilen.length).toBe(3);
    expect(zeileWerte(t.zeilen[0], t.rollen)).toEqual({ teilenummer: 'ZZ-00011-00-X-003', menge: [2], liefertermin: '2026-11-20' });
    expect(zeileWerte(t.zeilen[1], t.rollen)).toEqual({ teilenummer: 'ZZ-00011-90-1-001', menge: [10, 25], liefertermin: '2026-12-04' });
  });

  it('angelernte Vorlage geht vor: eigene Überschriften des Kunden', () => {
    const kunde = [['Pos', 'Kunden-Ident', 'Bedarf', 'Wann'], ['1', '4711-22', '50', '19.01.2027']];
    expect(tabelleDeuten([kunde])).toBeNull();
    const t = tabelleDeuten([kunde], { teilenummer: 'kunden-ident', menge: 'bedarf', liefertermin: 'wann' });
    expect(t.rollen).toEqual(['', 'teilenummer', 'menge', 'liefertermin']);
    expect(vorlageAus(t.kopfzeile, t.rollen)).toEqual({ teilenummer: 'kunden-ident', menge: 'bedarf', liefertermin: 'wann' });
    expect(zeileWerte(t.zeilen[0], t.rollen)).toEqual({ teilenummer: '4711-22', menge: [50], liefertermin: '2027-01-19' });
  });

  it('ohne bekannte Überschriften: Spalten aus dem Inhalt (Dateinamen, Zahlen ohne laufende Nummer, spätere Daten)', () => {
    const t = [
      ['Pos', 'Ident', 'Bedarf', 'Datum A', 'Datum B'],
      ['1', 'ZZ-55-001', '10', '01.01.2026', '15.03.2027'],
      ['2', 'ZZ-55-002', '4', '01.01.2026', '20.03.2027'],
    ];
    const d = tabelleDeuten([t], {}, ['ZZ-55-001.pdf', 'ZZ-55-002_Welle.step']);
    expect(d.kopf).toBe(0);
    expect(d.rollen).toEqual(['', 'teilenummer', 'menge', '', 'liefertermin']);
    expect(d.quellen).toEqual(['', 'inhalt', 'inhalt', '', 'inhalt']);
  });

  it('verbundene Kopfzelle (Raster vom Server) und selbst gewählte Kopfzeile', () => {
    const t = [
      ['Bestellung 4711', '', '', '', '', '', ''],
      ['Nr.', 'Partnumber', 'Description', '', 'MOD Date', 'Quantity', 'Delivery date'],
      ['1', 'ZZ-00011-00-X-003', 'PLATE', 'MOUNT', '26.06.2026', '2', '20.11..2026 00:00:00'],
    ];
    const d = tabelleDeuten([t]);
    expect(d.kopf).toBe(1);
    expect(d.rollen).toEqual(['', 'teilenummer', '', '', '', 'menge', 'liefertermin']);
    expect(rollenMitKopf(t, 1).rollen).toEqual(d.rollen);
  });

  it('Datum in verschiedenen Schreibweisen, ungültige leer', () => {
    expect(datumAus('20.11.2026')).toBe('2026-11-20');
    expect(datumAus('1.2.27')).toBe('2027-02-01');
    expect(datumAus('2026-11-20T00:00:00')).toBe('2026-11-20');
    expect(datumAus('20/11/2026')).toBe('2026-11-20');
    expect(datumAus('31.02.2026')).toBe('');
    expect(datumAus('nach Absprache')).toBe('');
    expect(mengenAus('1.000 Stk')).toEqual([1000]);
  });

  it('Teilenummer passt zum Dateinamen', () => {
    expect(passtZu('ZZ-00011-00-X-003', 'ZZ-00011-00-X-003.pdf')).toBe(true);
    expect(passtZu('ZZ-00011-90-1-001', 'ZZ 00011-90-1-001_PLATE.step')).toBe(true);
    expect(passtZu('TEST', 'ZZ-00011-00-X-003.pdf')).toBe(false);
    expect(passtZu('', 'x.pdf')).toBe(false);
  });
});
