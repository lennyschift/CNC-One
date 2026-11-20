import { describe, it, expect } from 'vitest';
import { werte, lesbar, felderAus, neuerFilter, passt, anwenden, aktiv, beschreibung, sortieren } from './filter.js';

const liste = [
  { id: 'AUF-1', status: 'Offen', kundeName: 'Alpha GmbH', netto: 1200, datum: '2026-11-02T10:00:00', eilig: true, kunde: { name: 'Alpha GmbH', adresse: ['Weg 1'] }, positionen: [{ key: 'a', teil: { name: 'Flansch', material: '1.4301', vorschaubild: '/files/x.png' } }] },
  { id: 'AUF-2', status: 'Fertig', kundeName: 'Beta AG', netto: 300, datum: '2026-10-15', eilig: false, kunde: { name: 'Beta AG', adresse: [] }, positionen: [{ key: 'b', teil: { name: 'Welle', material: 'EN AW-6082' } }, { key: 'c', teil: { name: 'Bolzen', material: '' } }] },
];

describe('werte und Beschriftung', () => {
  it('fächert Listen auf', () => expect(werte(liste[1], 'positionen.teil.name')).toEqual(['Welle', 'Bolzen']));
  it('lässt leere Werte weg', () => expect(werte(liste[1], 'positionen.teil.material')).toEqual(['EN AW-6082']));
  it('macht Namen lesbar', () => expect(lesbar('kunde.kundeName')).toBe('Kunde › Kunde Name'));
});

describe('felderAus', () => {
  const f = felderAus(liste, { beschriftungen: { status: 'Status' } });
  const typ = (p) => f.find((x) => x.pfad === p)?.typ;
  it('erkennt die Arten', () => {
    expect(typ('status')).toBe('auswahl');
    expect(typ('netto')).toBe('zahl');
    expect(typ('datum')).toBe('datum');
    expect(typ('eilig')).toBe('janein');
    expect(typ('positionen.teil.name')).toBe('auswahl');
  });
  it('lässt Technisches weg', () => {
    expect(f.some((x) => x.pfad === 'id' || x.pfad.endsWith('vorschaubild') || x.pfad.endsWith('.key'))).toBe(false);
  });
  it('beschriftete zuerst', () => expect(f[0]).toMatchObject({ pfad: 'status', label: 'Status' }));
  it('Optionen der Auswahl', () => expect(f.find((x) => x.pfad === 'status').optionen).toEqual(['Fertig', 'Offen']));
});

describe('passt', () => {
  it('Auswahl', () => expect(anwenden(liste, [{ pfad: 'status', typ: 'auswahl', wert: ['Offen'] }]).map((x) => x.id)).toEqual(['AUF-1']));
  it('Auswahl in Positionen', () => expect(anwenden(liste, [{ pfad: 'positionen.teil.name', typ: 'auswahl', wert: ['Bolzen'] }]).map((x) => x.id)).toEqual(['AUF-2']));
  it('Zahl', () => expect(anwenden(liste, [{ pfad: 'netto', typ: 'zahl', op: '>=', wert: 1000 }]).map((x) => x.id)).toEqual(['AUF-1']));
  it('Datum', () => expect(anwenden(liste, [{ pfad: 'datum', typ: 'datum', von: '2026-11-01', bis: '' }]).map((x) => x.id)).toEqual(['AUF-1']));
  it('Ja/Nein', () => expect(anwenden(liste, [{ pfad: 'eilig', typ: 'janein', wert: false }]).map((x) => x.id)).toEqual(['AUF-2']));
  it('Text enthält / ohne / leer', () => {
    expect(anwenden(liste, [{ pfad: 'kundeName', typ: 'text', op: 'enthaelt', wert: 'beta' }]).map((x) => x.id)).toEqual(['AUF-2']);
    expect(anwenden(liste, [{ pfad: 'kundeName', typ: 'text', op: 'nicht', wert: 'beta' }]).map((x) => x.id)).toEqual(['AUF-1']);
    expect(anwenden(liste, [{ pfad: 'kunde.adresse', typ: 'text', op: 'leer', wert: '' }]).map((x) => x.id)).toEqual(['AUF-2']);
  });
  it('leere Filter wirken nicht', () => {
    const f = neuerFilter({ pfad: 'status', typ: 'auswahl' });
    expect(aktiv(f)).toBe(false);
    expect(passt(liste[0], f)).toBe(true);
  });
  it('mehrere Filter zusammen', () => expect(anwenden(liste, [{ pfad: 'status', typ: 'auswahl', wert: ['Offen', 'Fertig'] }, { pfad: 'netto', typ: 'zahl', op: '<=', wert: 500 }]).map((x) => x.id)).toEqual(['AUF-2']));
  it('Beschreibung', () => {
    expect(beschreibung({ pfad: 'status', typ: 'auswahl', wert: ['A', 'B', 'C'] }, { label: 'Status' })).toBe('Status: A, B +1');
    expect(beschreibung({ pfad: 'netto', typ: 'zahl', op: '>=', wert: 5 }, { label: 'Netto' })).toBe('Netto ≥ 5');
  });
});

describe('sortieren', () => {
  const liste = [
    { id: 1, termin: '2026-12-10', prioritaet: 'Normal', ags: [{ m: 'B' }] },
    { id: 2, termin: '', prioritaet: 'Eilig', ags: [{ m: 'C' }, { m: 'A' }] },
    { id: 3, termin: '2026-11-30', prioritaet: 'Hoch', ags: [] },
  ];
  const ids = (l) => l.map((x) => x.id);
  it('Datum aufsteigend, leere ans Ende', () => {
    expect(ids(sortieren(liste, { pfad: 'termin', richtung: 'auf' }))).toEqual([3, 1, 2]);
    expect(ids(sortieren(liste, { pfad: 'termin', richtung: 'ab' }))).toEqual([1, 3, 2]);
  });
  it('fachliche Reihenfolge über rang', () => {
    expect(ids(sortieren(liste, { pfad: 'prioritaet', richtung: 'auf' }, { prioritaet: ['Eilig', 'Hoch', 'Normal'] }))).toEqual([2, 3, 1]);
  });
  it('Listen: kleinster Wert zählt', () => {
    expect(ids(sortieren(liste, { pfad: 'ags.m', richtung: 'auf' }))).toEqual([2, 1, 3]);
  });
  it('ohne Sortierung unverändert', () => {
    expect(ids(sortieren(liste, null))).toEqual([1, 2, 3]);
  });
});
