import { describe, it, expect } from 'vitest';
import { gruppieren, mengenAusText } from './mailanfrage.js';

describe('Bauteile aus den Anhängen einer Mail', () => {
  it('Zeichnung und Modell mit gleichem Namen ergeben ein Bauteil', () => {
    const g = gruppieren([
      { name: 'ZZ-3D-001_Flansch.pdf' }, { name: 'ZZ-3D-002_Halteblock.pdf' }, { name: 'zz-3d-001 flansch.step' }, { name: 'ZZ-3D-002_Halteblock.stp' },
    ]);
    expect(g.map((x) => [x.basis, x.dateien.length])).toEqual([['ZZ-3D-001_Flansch', 2], ['ZZ-3D-002_Halteblock', 2]]);
  });
});

describe('Mengen aus dem Mailtext', () => {
  const text = 'Guten Tag,\n\nbitte bieten Sie an:\n- ZZ-3D-001 Flansch, 10 Stück\n- ZZ-3D-002 Halteblock: je 25/50/100 Stk.\n- Hülse Menge: 300\n\nGruß, Telefon 0711 123456';

  it('je Bauteil die Zeile mit seiner Nummer', () => {
    expect(mengenAusText(text, 'ZZ-3D-001_Flansch')).toEqual([10]);
    expect(mengenAusText(text, 'ZZ-3D-002_Halteblock')).toEqual([25, 50, 100]);
    expect(mengenAusText(text, 'ZZ-3D-003_Huelse')).toEqual([]);
  });

  it('Menge: oder englische Angaben, Tausenderpunkt', () => {
    expect(mengenAusText('Hülse Menge: 300', 'Hülse')).toEqual([300]);
    expect(mengenAusText('part 4711-22 qty 1.000 pcs', '4711-22_shaft')).toEqual([1000]);
  });

  it('nur ein Bauteil: der ganze Text zählt, Telefonnummern nicht', () => {
    expect(mengenAusText('Hallo,\nwas kostet die Hülse in 100 Stück?\nTel. 0711 4711', 'ZZ-3D-003_Huelse', { einziges: true })).toEqual([100]);
    expect(mengenAusText('Bitte um Preis.\nTel. 0711 4711', 'X', { einziges: true })).toEqual([]);
  });
});
