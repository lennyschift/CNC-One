import { describe, it, expect } from 'vitest';
import { bauteilGruppen, bauteilSchluessel } from './anhaenge.js';

const a = (name, ordner = '') => ({ name, url: `/f/${name}`, ordner });

describe('Anhänge je Bauteil', () => {
  it('PDF und STEP mit gleichem Namen gehören zusammen, Zusätze zählen nicht', () => {
    const { gruppen, sonstige } = bauteilGruppen([
      a('F31.683.122_Zeichnung.pdf'), a('Liste.xlsx'), a('F31.683.122_3D.stp'), a('4711-B.pdf'), a('Welle 88.step'),
    ]);
    expect(gruppen.map((g) => [g.schluessel, !!g.pdf, !!g.step])).toEqual([
      ['f31 683 122', true, true],
      ['4711 b', true, false],
      ['welle 88', false, true],
    ]);
    expect(sonstige.map((x) => x.name)).toEqual(['Liste.xlsx']);
  });

  it('aus einer ZIP mit Zeichnung.pdf und Modell.stp zählt der Ordner', () => {
    expect(bauteilSchluessel(a('Zeichnung.pdf', 'BT-100'))).toBe('bt-100');
    const { gruppen } = bauteilGruppen([a('Zeichnung.pdf', 'BT-100'), a('Modell.stp', 'BT-100'), a('Zeichnung.pdf', 'BT-200')]);
    expect(gruppen.map((g) => [g.schluessel, !!g.pdf, !!g.step])).toEqual([['bt-100', true, true], ['bt-200', true, false]]);
  });

  it('zwei PDFs zum selben Bauteil bekommen zwei Zeilen', () => {
    const { gruppen } = bauteilGruppen([a('Teil-7.pdf'), a('Teil-7 drw.pdf'), a('Teil-7.stp')]);
    expect(gruppen.map((g) => [!!g.pdf, !!g.step])).toEqual([[true, true], [true, false]]);
  });
});
