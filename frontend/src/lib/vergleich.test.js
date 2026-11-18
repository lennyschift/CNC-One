import { describe, it, expect } from 'vitest';
import { vergleich, vorgaenge, imVorgang, vorlagePasst, passendeVorlagen } from './vergleich.js';

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
    expect(v.summen[0].je['LA-1']).toEqual({ betrag: 190, vollstaendig: true });
    expect(v.summen[0].je['LA-2']).toEqual({ betrag: 96, vollstaendig: false });
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
