import { describe, it, expect } from 'vitest';
import { gruppieren, anzeigename, bestandteile } from './zuordnung.js';

const paare = (g) => g.map((x) => [x.basis, x.dateien.map((d) => d.name).sort()]);

describe('Zeichnung und Modell zusammenfinden', () => {
  it('Stufe 1: gleicher Name trotz Vorsilbe „step_“, Typwörtern und Trennzeichen', () => {
    expect(bestandteile('step_F03_912_101_Q__END_COVER.stp')).toEqual(['f03', '912', '101', 'q', 'end', 'cover']);
    const g = gruppieren([
      { name: 'F03_912_101_Q__END_COVER.pdf', paket: 'a' }, { name: 'F03_912_101_P__END_COVER.pdf', paket: 'a' },
      { name: 'step_F03_912_101_Q__END_COVER.stp', paket: 'a' }, { name: 'step_F03_912_101_P__END_COVER.stp', paket: 'a' },
    ]);
    expect(paare(g)).toEqual([
      ['F03 912 101 Q END COVER', ['F03_912_101_Q__END_COVER.pdf', 'step_F03_912_101_Q__END_COVER.stp']],
      ['F03 912 101 P END COVER', ['F03_912_101_P__END_COVER.pdf', 'step_F03_912_101_P__END_COVER.stp']],
    ]);
  });

  it('Stufe 2: genau eine Zeichnung und ein Modell im selben ZIP gehören zusammen, egal wie sie heißen', () => {
    const g = gruppieren([
      { name: 'Ansicht_final.pdf', aus: 'a.zip', ordner: '' }, { name: 'export_v3.stp', aus: 'a.zip', ordner: '' },
      { name: 'Teil X.pdf', aus: 'b.zip', ordner: '' }, { name: 'Body.stp', aus: 'b.zip', ordner: '' },
    ]);
    expect(paare(g)).toEqual([['Ansicht final', ['Ansicht_final.pdf', 'export_v3.stp']], ['Teil X', ['Body.stp', 'Teil X.pdf']]]);
  });

  it('Stufe 3: ähnlichster Name (gleiche Projektnummer und Revision), Dokumentnummern verschieden', () => {
    const g = gruppieren([
      { name: '216067_10242028_ipt_B.step' }, { name: '216067_10242029_dra_B.pdf' },
      { name: '216083_10242011_ipt_0.step' }, { name: '216083_10242012_dra_0.pdf' },
      { name: '216084_10242013_ipt_0.step' }, { name: '216084_10242014_dra_0.pdf' },
    ]);
    expect(paare(g)).toEqual([
      ['216067 10242029 B', ['216067_10242028_ipt_B.step', '216067_10242029_dra_B.pdf']],
      ['216083 10242012 0', ['216083_10242011_ipt_0.step', '216083_10242012_dra_0.pdf']],
      ['216084 10242014 0', ['216084_10242013_ipt_0.step', '216084_10242014_dra_0.pdf']],
    ]);
  });

  it('nicht eindeutig: lieber getrennt lassen als falsch zusammenführen', () => {
    const g = gruppieren([
      { name: '216067_10242028_ipt_B.step' }, { name: '216067_10242029_dra_B.pdf' },
      { name: '216067_10242030_ipt_B.step' }, { name: '216067_10242031_dra_B.pdf' },
    ]);
    expect(g).toHaveLength(4);
  });

  it('beim Hineinziehen: das fehlende Modell kommt zum vorhandenen Bauteil', () => {
    const vorhandene = [
      { id: 't1', name: '216067 10242029 B', dateien: [{ name: '216067_10242029_dra_B.pdf', art: 'Zeichnung' }] },
      { id: 't2', name: 'Fertig', dateien: [{ name: 'fertig.pdf', art: 'Zeichnung' }, { name: 'fertig.stp', art: 'STEP' }] },
    ];
    const g = gruppieren([{ name: '216067_10242028_ipt_B.step', paket: 'ablage' }, { name: 'neu.pdf', paket: 'ablage' }], { vorhandene });
    expect(g.map((x) => [x.teilId, x.basis, x.dateien.map((d) => d.name)])).toEqual([
      ['t1', '216067 10242029 B', ['216067_10242028_ipt_B.step']],
      [null, 'neu', ['neu.pdf']],
    ]);
  });

  it('Bauteilname ohne Typwörter und Zeitstempel, Teilenummern bleiben ganz', () => {
    expect(anzeigename('step_F03.912.101.Q_K1_SAP_Released_20261109094445.stp')).toBe('F03.912.101.Q K1');
    expect(anzeigename('ZZ-3D-001_Flansch.pdf')).toBe('ZZ-3D-001 Flansch');
    expect(anzeigename('Zeichnung.pdf')).toBe('');
  });
});
