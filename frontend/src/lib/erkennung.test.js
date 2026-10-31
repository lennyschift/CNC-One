import { describe, it, expect } from 'vitest';
import { erkennen, werkstoffNummer, materialFinden, ausDateiname } from './erkennung.js';
import zeichnungen from './testdaten/zeichnungen.json';

// Werte je Feld (ohne Lage), für übersichtliche Vergleiche
const werte = (r) => Object.fromEntries(Object.entries(r.felder).map(([k, v]) => [k, v.wert]));

describe('Erkennung aus Testzeichnungen (eigene Zeichnungen mit echtem PDF-Text)', () => {
  it('deutsches Schriftfeld, Wert unter dem Stichwort', () => {
    const r = erkennen(zeichnungen['ZZ-3D-001_Flansch.pdf'], 'ZZ-3D-001_Flansch.pdf');
    expect(werte(r)).toEqual({
      kunde: 'ZZ Testkunde GmbH', bezeichnung: 'Flansch DN25', toleranz: 'ISO 2768-mK', teilenummer: 'ZZ-3D-001',
      zeichnungsnr: 'Z-ZZ-3D-001', revision: 'B', werkstoff: '1.4404 (X2CrNiMo17-12-2)', oberflaeche: 'gebeizt und passiviert',
    });
    expect(r.werkstoffNr).toBe('1.4404');
    expect(r.felder.teilenummer.sicherheit).toBe('hoch');
    expect(r.felder.teilenummer.lage).toMatchObject({ x: expect.any(Number), y: expect.any(Number) });
  });

  it('englisches Schriftfeld in einer Zeile', () => {
    const r = erkennen(zeichnungen['ZZ-3D-002_Halteblock.pdf']);
    expect(werte(r)).toEqual({
      bezeichnung: 'Holding block', teilenummer: 'ZZ-3D-002', zeichnungsnr: 'D-77-0042', revision: '03',
      werkstoff: 'EN AW-6082 T651', oberflaeche: 'Anodized black', toleranz: 'ISO 2768-f', kunde: 'ZZ Example Ltd.',
    });
    expect(r.werkstoffNr).toBe('EN AW-6082');
  });

  it('Wert rechts neben dem Stichwort, Angaben mit Doppelpunkt im Text', () => {
    const r = erkennen(zeichnungen['ZZ-3D-003_Huelse.pdf']);
    expect(werte(r)).toEqual({
      kunde: 'ZZ Prüfkunde AG', teilenummer: 'ZZ-3D-003', bezeichnung: 'Distanzhülse lang', zeichnungsnr: 'ZN 3003-01',
      revision: 'A2', werkstoff: 'X5CrNi18-10', oberflaeche: 'Ra 0,8', toleranz: 'ISO 2768-mK',
    });
    expect(r.felder.toleranz.quelle).toBe('Muster');
    expect(r.werkstoffNr).toBe('1.4301');
  });
});

describe('Rückfälle und Hilfen', () => {
  it('ohne Schriftfeld hilft der Dateiname, mit niedriger Sicherheit', () => {
    const r = erkennen({ elemente: [{ text: '⌀40 h7', x: 0.3, y: 0.3, b: 0.05, h: 0.02 }] }, 'P27.135.322_Distanzhuelse_Rev3.pdf');
    expect(r.felder.teilenummer).toMatchObject({ wert: 'P27.135.322', sicherheit: 'niedrig', quelle: 'Dateiname' });
    expect(r.felder.bezeichnung.wert).toBe('Distanzhuelse');
    expect(ausDateiname('zeichnung_4711.pdf')).toEqual({ teilenummer: '4711', bezeichnung: '' });
  });

  it('Werkstoff im Fließtext wird über Muster gefunden', () => {
    const r = erkennen({ elemente: [{ text: 'Mat. AlZnMgCu1,5 T6', x: 0.1, y: 0.1, b: 0.2, h: 0.01 }] });
    expect(r.felder.werkstoff).toMatchObject({ wert: 'Mat. AlZnMgCu1,5 T6', sicherheit: 'mittel' });
    expect(r.werkstoffNr).toBe('EN AW-7075');
  });

  it('ein Datum ist keine Teilenummer, ein Stichwort mitten im Satz kein Label', () => {
    const r = erkennen({ elemente: [
      { text: 'Teilenummer', x: 0.1, y: 0.1, b: 0.1, h: 0.01 }, { text: '12.10.2026', x: 0.1, y: 0.112, b: 0.08, h: 0.01 },
      { text: 'Material laut Anfrage beistellen', x: 0.1, y: 0.5, b: 0.3, h: 0.01 },
    ] });
    expect(r.felder.teilenummer).toBeUndefined();
    expect(r.felder.werkstoff).toBeUndefined();
  });

  it('Werkstoffnummern und Abgleich mit den Rohmaterial-Stammdaten', () => {
    expect(werkstoffNummer('V2A gebürstet')).toBe('1.4301');
    expect(werkstoffNummer('42CrMo4 vergütet')).toBe('1.7225');
    expect(werkstoffNummer('Holz')).toBe('');
    const materialien = [{ name: '1.4404 Edelstahl' }, { name: 'EN AW-7075 Aluminium' }, { name: 'Alu 6082' }];
    expect(materialFinden('X2CrNiMo17-12-2', materialien)?.name).toBe('1.4404 Edelstahl');
    expect(materialFinden('AlZnMgCu1,5', materialien)?.name).toBe('EN AW-7075 Aluminium');
    expect(materialFinden('EN AW-6082 T651', materialien)?.name).toBe('Alu 6082');
    expect(materialFinden('1.4301', materialien)).toBeNull();
  });
});
