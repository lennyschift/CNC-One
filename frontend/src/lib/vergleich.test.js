import { describe, it, expect } from 'vitest';
import { vergleich, weiterePositionen, vorgaenge, imVorgang, vorlagePasst, passendeVorlagen } from './vergleich.js';

const pos = [
  { key: 'frei:1', teil: { name: 'Rundstange', material: 'EN AW-6082' }, abmessung: 'Ø 40', einheit: 'Stangen', mengen: [2, 6] },
  { key: 'frei:2', teil: { name: 'Platte', material: 'EN AW-5083' }, abmessung: '20 mm', einheit: 'Stk', mengen: [1] },
];
const anfrage = (id, preise, extra = {}) => ({ id, vorgang: 'LA-1', lieferantName: id, status: preise ? 'Angebot erhalten' : 'Gesendet', positionen: pos, antwort: preise ? { angebotsnr: `A-${id}`, gueltigBis: '', lieferzeit: '1 Woche', preise } : null, ...extra });

const a = anfrage('LA-1', [
  { posKey: 'frei:1', menge: 2, proStk: 50, einmalig: 10 },
  { posKey: 'frei:1', menge: 6, proStk: 45, einmalig: 10 },
  { posKey: 'frei:2', menge: 1, proStk: 80, einmalig: 0 },
]);
const b = anfrage('LA-2', [
  { posKey: 'frei:1', menge: 2, proStk: 48, einmalig: 0 },
  { posKey: 'frei:1', menge: 6, proStk: 47, einmalig: 0 },
]);
const c = anfrage('LA-3', null);

describe('vergleich', () => {
  const v = vergleich([a, b, c]);
  it('je Position und Menge eine Zeile', () => {
    expect(v.zeilen.map((z) => z.key)).toEqual(['frei:1|2', 'frei:1|6', 'frei:2|1']);
    expect(v.zeilen[0].ersteZeile).toBe(true);
    expect(v.zeilen[1].ersteZeile).toBe(false);
  });
  it('Gesamt = Menge × Preis + einmalig, günstigster markiert', () => {
    expect(v.zeilen[0].zellen['LA-1'].gesamt).toBe(110);
    expect(v.zeilen[0].zellen['LA-2'].gesamt).toBe(96);
    expect(v.zeilen[0].bester).toBe('LA-2');
    expect(v.zeilen[1].bester).toBe('LA-1'); // 280 gegen 282
    expect(v.zeilen[0].zellen['LA-3']).toBeNull();
  });
  it('Summen je Stufe, der Beste nur unter den vollständigen', () => {
    expect(v.summen[0].je['LA-1']).toEqual({ betrag: 190, vollstaendig: true, mitAlternative: false });
    expect(v.summen[0].je['LA-2']).toEqual({ betrag: 96, vollstaendig: false, mitAlternative: false });
    expect(v.summen[0].bester).toBe('LA-1');
    expect(v.summen[1].je['LA-1'].betrag).toBe(360); // 6 Stangen + die eine Platte
  });
  it('Lieferanten mit Angaben', () => {
    expect(v.lieferanten.map((l) => [l.id, l.hatPreise, l.lieferzeit])).toEqual([['LA-1', true, '1 Woche'], ['LA-2', true, '1 Woche'], ['LA-3', false, '']]);
  });
  it('Vorgänge gruppieren, ohne Vorgang zählt die eigene Nummer', () => {
    const liste = [a, b, { ...c, id: 'LA-9', vorgang: '' }];
    expect(vorgaenge(liste).map((x) => [x.vorgang, x.anfragen.length])).toEqual([['LA-1', 2], ['LA-9', 1]]);
    expect(imVorgang(liste, 'LA-1').map((x) => x.id)).toEqual(['LA-1', 'LA-2']);
  });
});

describe('Vorlagen', () => {
  const alu = { name: 'Alu', stichwoerter: 'alu, en aw', isoGruppe: '', art: 'Material', lieferanten: ['A'], aktiv: true };
  const nicht = { name: 'NE', stichwoerter: '', isoGruppe: 'N', art: '', lieferanten: ['B'], aktiv: true };
  it('Stichwort im Werkstoff', () => expect(vorlagePasst(alu, { art: 'Material', texte: ['EN AW-6082'] })).toBe(true));
  it('falsche Art passt nicht', () => expect(vorlagePasst(alu, { art: 'Fremdvergabe', texte: ['Alu'] })).toBe(false));
  it('ISO-Gruppe aus dem Werkstoff', () => expect(vorlagePasst(nicht, { texte: ['AlMgSi1'] })).toBe(true));
  it('inaktive nie', () => expect(vorlagePasst({ ...alu, aktiv: false }, { texte: ['alu'] })).toBe(false));
  it('Liste filtern', () => expect(passendeVorlagen([alu, nicht], { art: 'Material', texte: ['1.4301'] })).toEqual([]));
});

describe('Nebenkosten und abweichende Mengen aus dem eingelesenen PDF', () => {
  const mitNeben = anfrage('LA-4', [{ posKey: 'frei:2', menge: 1, proStk: 70, einmalig: 0 }]);
  mitNeben.antwort = { ...mitNeben.antwort, nebenkosten: 25, daten: { je: { 'frei:2': { abweichung: true, angeboten: 2 } } } };
  const ohne = anfrage('LA-5', [{ posKey: 'frei:2', menge: 1, proStk: 80, einmalig: 0 }]);
  const einzeln = (x) => ({ ...x, positionen: [pos[1]] });
  const v = vergleich([einzeln(mitNeben), einzeln(ohne)]);
  it('zählt die Nebenkosten einmal in der Summe, auch bei nur einer Position', () => {
    expect(v.summen[0].je['LA-4'].betrag).toBe(95);
    expect(v.summen[0].je['LA-5'].betrag).toBe(80);
    expect(v.summen[0].bester).toBe('LA-5');
    expect(v.lieferanten[0].nebenkosten).toBe(25);
  });
  it('markiert eine andere angebotene Menge', () => {
    expect(v.zeilen[0].zellen['LA-4'].abweichung).toBe(2);
    expect(v.zeilen[0].zellen['LA-5'].abweichung).toBeNull();
  });
});

describe('Alternativen und weitere Positionen aus dem Angebot', () => {
  const einzeln = (x) => ({ ...x, positionen: [pos[1]] });
  const mitAlt = anfrage('LA-6', [{ posKey: 'frei:2', menge: 1, proStk: 435.04, einmalig: 0 }]);
  mitAlt.antwort = { ...mitAlt.antwort, nebenkosten: 10, daten: { netto: 1390.04, positionen: [
    { pos: '1', werkstoff: 'EN AW-6082', form: 'Platte', masse: [15, 20, 3020], betrag: 435.04, zuordnung: 'frei:2' },
    { pos: '2', option: true, werkstoff: 'EN AW-6082', form: 'Platte', masse: [15, 20, 150], betrag: 400, zuordnung: '' },
    { pos: '3', werkstoff: '1.4301', form: 'Rund', masse: [40], betrag: 50, zuordnung: '' },
    { pos: '4', werkstoff: '1.4301', form: 'Rund', masse: [30], betrag: 0, zuordnung: '' },
  ] } };
  const andere = anfrage('LA-7', [{ posKey: 'frei:2', menge: 1, proStk: 420, einmalig: 0 }]);
  const liste = [einzeln(mitAlt), einzeln(andere)];
  it('zeigt nicht zugeordnete Positionen mit Betrag, Optionen mit Bezug zur ersetzten Position', () => {
    const w = weiterePositionen(liste);
    expect(w.map((x) => [x.key, x.option, x.bezug])).toEqual([['LA-6|1', true, 'frei:2'], ['LA-6|2', false, '']]);
    expect(vergleich(liste).lieferanten[0].netto).toBe(1390.04);
  });
  it('rechnet gewählte Alternativen statt der Position bzw. zusätzlich in die Summe', () => {
    expect(vergleich(liste).summen[0].bester).toBe('LA-7');
    const v = vergleich(liste, { alternativen: ['LA-6|1'] });
    expect(v.summen[0].je['LA-6']).toEqual({ betrag: 410, vollstaendig: true, mitAlternative: true });
    expect(v.summen[0].bester).toBe('LA-6');
    expect(vergleich(liste, { alternativen: ['LA-6|1', 'LA-6|2'] }).summen[0].je['LA-6'].betrag).toBe(460);
  });
});

describe('Zuschlag je Position', () => {
  const x = anfrage('LA-1', [{ posKey: 'frei:1', menge: 2, proStk: 50, einmalig: 0 }, { posKey: 'frei:2', menge: 1, proStk: 80, einmalig: 0 }], { zuschlag: true, zuschlagPositionen: ['frei:1'], zuschlagAlternativen: [1] });
  x.antwort = { ...x.antwort, daten: { positionen: [{ werkstoff: 'EN AW-6082', form: 'Rund', masse: [40], betrag: 100, zuordnung: 'frei:1' }, { option: true, werkstoff: 'EN AW-6082', form: 'Rund', masse: [40, 500], betrag: 90, zuordnung: '' }] } };
  const y = anfrage('LA-2', [{ posKey: 'frei:2', menge: 1, proStk: 70, einmalig: 0 }], { zuschlag: true, zuschlagPositionen: ['frei:2'] });
  const v = vergleich([x, y]);
  it('kennzeichnet, an wen eine Position geht, auch per Alternative', () => {
    expect(v.zeilen.map((z) => [z.key, z.vergeben])).toEqual([
      ['frei:1|2', { id: 'LA-1', perAlternative: true }], ['frei:1|6', { id: 'LA-1', perAlternative: true }], ['frei:2|1', { id: 'LA-2', perAlternative: false }],
    ]);
    expect(v.weitere.map((w) => [w.key, w.index, w.bezug, w.zuschlag])).toEqual([['LA-1|1', 1, 'frei:1', true]]);
  });
});

describe('Liefertermine je Position', () => {
  const mitTerminen = (id, d1, d2) => anfrage(id, [
    { posKey: 'frei:1', menge: 2, proStk: 50, einmalig: 0 },
    { posKey: 'frei:2', menge: 1, proStk: 80, einmalig: 0 },
  ], {});
  const x = mitTerminen('LA-7');
  x.antwort.daten = { positionen: [
    { pos: '1', zuordnung: 'frei:1', betrag: 100, liefertermin: '10.12.2026', lieferdatum: '2026-12-10' },
    { pos: '2', zuordnung: 'frei:2', betrag: 80, liefertermin: 'KW 52', lieferdatum: '2026-12-24' },
    { pos: '3', zuordnung: '', betrag: 30, werkstoff: 'EN AW-5083', liefertermin: '2027-01-15', lieferdatum: '2027-01-15' },
  ] };
  const y = mitTerminen('LA-8');
  y.antwort.daten = { positionen: [{ pos: '1', zuordnung: 'frei:1', betrag: 90, liefertermin: 'ab Lager', lieferdatum: '' }, { pos: '2', zuordnung: 'frei:2', betrag: 70, liefertermin: '2026-12-01', lieferdatum: '2026-12-01' }] };
  it('zeigt den Termin in der Zelle und den spätesten als Gesamttermin', () => {
    const v = vergleich([x, y]);
    expect(v.zeilen[0].zellen['LA-7']).toMatchObject({ termin: '10.12.2026', datum: '2026-12-10' });
    const l7 = v.lieferanten.find((l) => l.id === 'LA-7');
    const l8 = v.lieferanten.find((l) => l.id === 'LA-8');
    expect(l7).toMatchObject({ spaetester: '2026-12-24', verschieden: true });
    expect(l8).toMatchObject({ spaetester: '2026-12-01', ohneDatum: ['ab Lager'], schnellster: true });
  });
  it('rechnet gewählte Alternativen in den Gesamttermin ein', () => {
    const v = vergleich([x, y], { alternativen: ['LA-7|2'] });
    expect(v.lieferanten.find((l) => l.id === 'LA-7').spaetester).toBe('2027-01-15');
  });
});
