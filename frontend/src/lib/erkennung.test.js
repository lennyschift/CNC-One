import { describe, it, expect } from 'vitest';
import { erkennen, werkstoffNummer, materialFinden, ausDateiname, elementBei, lernregel, kundeFinden, elementMitWert, regelnAus, regelnZusammenfuehren, rohmaterialName, dichteSchaetzen } from './erkennung.js';
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

// Schriftfeld eines Kunden mit eigenen Stichwörtern, die die allgemeine Erkennung nicht kennt
const kundenSeite = (nr = '4711-0815-A', name = 'Halter links') => ({ elemente: [
  { text: 'Ident-Nr. Kunde', x: 0.6, y: 0.9, b: 0.08, h: 0.01 }, { text: nr, x: 0.7, y: 0.9, b: 0.07, h: 0.012 },
  { text: 'Teil', x: 0.6, y: 0.92, b: 0.03, h: 0.01 }, { text: name, x: 0.7, y: 0.92, b: 0.09, h: 0.012 },
  { text: 'Sachnummer', x: 0.1, y: 0.9, b: 0.06, h: 0.01 }, { text: 'INT-99', x: 0.1, y: 0.912, b: 0.04, h: 0.012 },
] });

describe('Kundenvorlage und Anlernen', () => {
  it('ohne Vorlage greift nur die allgemeine Erkennung', () => {
    expect(werte(erkennen(kundenSeite()))).toEqual({ teilenummer: 'INT-99' });
  });

  it('angelernte Regeln gehen vor: Stichwort und Stelle auf der Seite', () => {
    const vorlage = { felder: {
      teilenummer: [{ stichwort: 'ident-nr. kunde' }],
      bezeichnung: [{ bereich: { x: 0.695, y: 0.916, b: 0.15, h: 0.02 } }],
    } };
    const r = erkennen(kundenSeite('4711-0999-B', 'Halter rechts lang'), '', vorlage);
    expect(werte(r)).toEqual({ teilenummer: '4711-0999-B', bezeichnung: 'Halter rechts lang' });
    expect(r.felder.teilenummer.quelle).toBe('Kundenvorlage');
  });

  it('passt keine Regel mehr, hilft die allgemeine Erkennung', () => {
    const r = erkennen(kundenSeite(), '', { felder: { teilenummer: [{ stichwort: 'gibt es nicht' }] } });
    expect(r.felder.teilenummer).toMatchObject({ wert: 'INT-99', quelle: 'Schriftfeld' });
  });

  it('aus dem Klick auf einen Wert entstehen Stichwort und Bereich', () => {
    const seite = kundenSeite();
    const el = elementBei(seite, 0.72, 0.905);
    expect(el.text).toBe('4711-0815-A');
    const regel = lernregel(seite, el);
    expect(regel).toMatchObject({ wert: '4711-0815-A', stichwort: 'ident-nr. kunde' });
    expect(regel.bereich.x).toBeCloseTo(0.695);
    // die gelernte Regel findet den Wert auf der nächsten Zeichnung wieder
    const naechste = erkennen(kundenSeite('4711-1234-C'), '', { felder: { teilenummer: [{ stichwort: regel.stichwort }, { bereich: regel.bereich }] } });
    expect(naechste.felder.teilenummer.wert).toBe('4711-1234-C');
    expect(elementBei(seite, 0.3, 0.3)).toBeNull();
  });

  it('Label im selben Textstück wird abgetrennt, Werte darunter haben das Label darüber', () => {
    const seite = { elemente: [{ text: 'Mat.-Kurzz.: S355J2', x: 0.1, y: 0.1, b: 0.2, h: 0.01 }, { text: 'Benenng.', x: 0.5, y: 0.5, b: 0.05, h: 0.01 }, { text: 'Deckel', x: 0.5, y: 0.512, b: 0.05, h: 0.012 }] };
    expect(lernregel(seite, seite.elemente[0])).toMatchObject({ wert: 'S355J2', stichwort: 'mat.-kurzz.' });
    expect(lernregel(seite, seite.elemente[2])).toMatchObject({ wert: 'Deckel', stichwort: 'benenng.' });
  });

  it('Kunde zum Namen auf der Zeichnung', () => {
    const kunden = [{ id: 'K-1', name: 'ZZ Testkunde GmbH' }, { id: 'K-2', name: 'Muster AG' }];
    expect(kundeFinden('ZZ Testkunde', kunden)?.id).toBe('K-1');
    expect(kundeFinden('MUSTER AG, Werk 2', kunden)?.id).toBe('K-2');
    expect(kundeFinden('Fremd', kunden)).toBeNull();
  });
});

describe('Anlernen an echten Testzeichnungen eines Kunden mit fremdem Schriftfeld', () => {
  const erste = zeichnungen['ZZ-3D-004_Halter.pdf'];
  const zweite = zeichnungen['ZZ-3D-005_Halter.pdf'];
  // Klick auf die Mitte eines Textstücks, wie in der Zeichnungsansicht
  const klick = (seite, text) => {
    const e = seite.elemente.find((x) => x.text === text);
    return elementBei(seite, e.x + e.b / 2, e.y + e.h / 2);
  };

  it('ohne Vorlage greift die allgemeine Erkennung daneben (interne Sachnummer)', () => {
    const r = erkennen(erste, 'ZZ-3D-004_Halter.pdf');
    expect(r.felder.teilenummer.wert).toBe('INT-4400');
    expect(r.werkstoffNr).toBe('1.0037');
  });

  it('auf der ersten Zeichnung angelernt, auf der zweiten von selbst erkannt', () => {
    const vorlage = { felder: {} };
    for (const [feld, text] of [['teilenummer', '4711-0815-A'], ['bezeichnung', 'Halter links'], ['revision', 'c']]) {
      const r = lernregel(erste, klick(erste, text));
      expect(r.wert).toBe(text);
      vorlage.felder[feld] = [{ stichwort: r.stichwort }, { bereich: r.bereich }];
    }
    expect(vorlage.felder.teilenummer[0].stichwort).toBe('ident-nr. kunde');
    const r = erkennen(zweite, 'ZZ-3D-005_Halter.pdf', vorlage);
    expect(werte(r)).toMatchObject({ teilenummer: '4711-0999-B', bezeichnung: 'Halter rechts lang', revision: 'a', werkstoff: 'X5CrNi18-10' });
    expect(r.felder.teilenummer.quelle).toBe('Kundenvorlage');
    // Die Stelle allein trifft bei festem Schriftfeld; hier wachsen die Tabellenspalten mit dem Text, deshalb geht das Stichwort vor
    const nurStelle = { felder: { teilenummer: [vorlage.felder.teilenummer[1]] } };
    expect(erkennen(erste, '', nurStelle).felder.teilenummer.wert).toBe('4711-0815-A');
  });
});

describe('Korrekturen von Hand lernen (wie in der Maske getippt)', () => {
  const erste = zeichnungen['ZZ-3D-004_Halter.pdf'];
  const zweite = zeichnungen['ZZ-3D-005_Halter.pdf'];
  const lernenAusWert = (seite, wert) => regelnAus(lernregel(seite, elementMitWert(seite, wert)));

  it('getippter Wert, der in der Zeichnung steht, ergibt Regeln mit Versatz; die nächste Zeichnung passt', () => {
    const regeln = lernenAusWert(erste, '4711-0815-A');
    expect(regeln[0]).toMatchObject({ stichwort: 'ident-nr. kunde', dx: expect.any(Number), dy: expect.any(Number) });
    const vorlage = { felder: { teilenummer: regeln } };
    expect(erkennen(erste, '', vorlage).felder.teilenummer.wert).toBe('4711-0815-A');
    expect(erkennen(zweite, '', vorlage).felder.teilenummer.wert).toBe('4711-0999-B');
  });

  it('der Versatz trifft den Wert, auch wenn ein anderer näher rechts daneben steht', () => {
    const seite = { elemente: [
      { text: 'Benennung', x: 0.8, y: 0.88, b: 0.04, h: 0.009 }, { text: 'Blatt 1/1', x: 0.86, y: 0.88, b: 0.04, h: 0.012 },
      { text: 'Dorn Ø8,5', x: 0.835, y: 0.892, b: 0.05, h: 0.013 },
    ] };
    // die allgemeine Erkennung nimmt den Text rechts daneben
    expect(erkennen(seite).felder.bezeichnung.wert).toBe('Blatt 1/1');
    const vorlage = { felder: { bezeichnung: lernenAusWert(seite, 'Dorn Ø8,5') } };
    expect(vorlage.felder.bezeichnung[0]).toMatchObject({ stichwort: 'benennung', dx: 0.035, dy: 0.012 });
    expect(erkennen(seite, '', vorlage).felder.bezeichnung).toMatchObject({ wert: 'Dorn Ø8,5', quelle: 'Kundenvorlage' });
  });

  it('kurze Werte nur bei genauem Treffer, Stichwörter nur mit Wortgrenze', () => {
    expect(elementMitWert(erste, 'c')?.text).toBe('c');
    expect(elementMitWert(erste, '4')).toBeNull();
    expect(elementMitWert(erste, 'Lernkunde')?.text).toBe('ZZ Lernkunde AG');
    const seite = { elemente: [{ text: 'Teilenummer', x: 0.1, y: 0.1, b: 0.05, h: 0.01 }, { text: 'X-1', x: 0.2, y: 0.1, b: 0.03, h: 0.01 }] };
    expect(erkennen(seite, '', { felder: { bezeichnung: [{ stichwort: 'teil' }] } }).felder.bezeichnung).toBeUndefined();
  });

  it('beim Zusammenführen fallen widerlegte Regeln weg, nicht greifende bleiben', () => {
    const falsch = { stichwort: 'sachnummer' }; // liefert INT-4400
    const fremd = { stichwort: 'gibt es hier nicht' };
    const neue = lernenAusWert(erste, '4711-0815-A');
    const r = regelnZusammenfuehren([falsch, fremd, neue[0]], neue, erste, 'teilenummer', '4711-0815-A');
    expect(r).toEqual([...neue, fremd]);
    expect(regelnZusammenfuehren(undefined, neue, erste, 'teilenummer', '4711-0815-A')).toEqual(neue);
  });
});

describe('Werkstoff und Rohmaterial', () => {
  it('Werkstoffnummern auch ohne Eintrag in der Liste', () => {
    expect(werkstoffNummer('Werkstoff 1.2343 vergütet')).toBe('1.2343');
    expect(werkstoffNummer('en aw 5019')).toBe('EN AW-5019');
    expect(werkstoffNummer('CW713R')).toBe('CW713R');
    expect(werkstoffNummer('16MnCr5 einsatzgehärtet')).toBe('1.7131');
    expect(werkstoffNummer('AlMg3 H111')).toBe('EN AW-5754');
    // im ganzen Zeichnungstext nur bekannte Werkstoffe, ein Maß wie 2.5000 oder ein Jahr ist kein Werkstoff
    expect(werkstoffNummer('2.5000', { allgemein: false })).toBe('');
    expect(erkennen({ elemente: [{ text: 'Datum 12.03.2017', x: 0.1, y: 0.1, b: 0.1, h: 0.01 }] }).felder.werkstoff).toBeUndefined();
  });

  it('gemerkte Schreibweisen gehen vor, dann die Werkstoffnummer', () => {
    const materialien = [{ name: '1.4301 Edelstahl', schreibweisen: ['V2A gebürstet'] }, { name: 'AlMg3 / EN AW-5754', schreibweisen: [] }, { name: 'Sonderlegierung Kunde', schreibweisen: ['SL-77'] }];
    expect(materialFinden('V2A gebürstet', materialien)?.name).toBe('1.4301 Edelstahl');
    expect(materialFinden('Werkstoff SL-77 nach Norm', materialien)?.name).toBe('Sonderlegierung Kunde');
    expect(materialFinden('EN AW-5754 H22', materialien)?.name).toBe('AlMg3 / EN AW-5754');
    expect(materialFinden('X5CrNi18-10', materialien)?.name).toBe('1.4301 Edelstahl');
  });

  it('Name für ein neues Rohmaterial', () => {
    expect(rohmaterialName('16MnCr5')).toBe('1.7131 16MnCr5');
    expect(rohmaterialName('1.2343  vergütet')).toBe('1.2343 vergütet');
    expect(rohmaterialName('Sonderlegierung')).toBe('Sonderlegierung');
  });
});

describe('Dichte schätzen', () => {
  it('aus Werkstoffnummer oder Bezeichnung', () => {
    expect(dichteSchaetzen('1.4404 Edelstahl')).toBe(7.9);
    expect(dichteSchaetzen('1.0037 Baustahl S235')).toBe(7.85);
    expect(dichteSchaetzen('EN AW-7075 Aluminium')).toBe(2.7);
    expect(dichteSchaetzen('CuZn39Pb3 Messing')).toBe(8.5);
    expect(dichteSchaetzen('POM-C Kunststoff')).toBe(1.41);
    expect(dichteSchaetzen('Ti6Al4V')).toBe(4.43);
    expect(dichteSchaetzen('Holz')).toBe(0);
  });
});
