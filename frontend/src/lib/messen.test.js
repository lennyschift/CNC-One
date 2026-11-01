import { describe, it, expect } from 'vitest';
import { volumenUndFlaeche, gewichtKg, rundmaterial, quader, rohteile, umkreis, flaecheAnalysieren, flaecheZuDreieck, messpunkt, abstand, ACHSEN } from './messen.js';
import modelle from './testdaten/modelle.json';

// Eigene Testmodelle (CadQuery): Flansch Scheibe ⌀80×12 + Bund ⌀40×20, Bohrung ⌀25, 4 Löcher ⌀6,6 auf LK ⌀60, Fase 1 mm oben;
// Halteblock 120×60×30 mit Tasche 70×30×12, 4 Bohrungen ⌀8,5, Querbohrung ⌀10,2×40, Ecken R4
const flansch = modelle['ZZ-3D-001_Flansch.step'];
const block = modelle['ZZ-3D-002_Halteblock.stp'];
const analysen = (netze) => netze.flatMap((n) => n.flaechen.map((_f, i) => flaecheAnalysieren(n, i)));
const zylinder = (netze) => analysen(netze).filter((a) => a.art === 'Zylinder').map((a) => Math.round(a.durchmesser * 10) / 10).sort((a, b) => a - b);

describe('Volumen und Gewicht', () => {
  it('Flansch: Volumen wie gerechnet (Netz etwas kleiner als die echte Rundung)', () => {
    const soll = Math.PI * (40 ** 2 * 12 + 20 ** 2 * 20 - 12.5 ** 2 * 32 - 4 * 3.3 ** 2 * 12);
    const { volumen } = volumenUndFlaeche(flansch);
    expect(volumen / soll).toBeGreaterThan(0.985);
    expect(volumen / soll).toBeLessThan(1.002);
  });

  it('Halteblock: Quader minus Tasche, Bohrungen und Eckenrundung (Überschlag, Querbohrung schneidet die Tasche)', () => {
    const soll = 120 * 60 * 30 - 70 * 30 * 12 - 4 * Math.PI * 4.25 ** 2 * 30 - Math.PI * 5.1 ** 2 * 40 - 4 * 30 * (16 - 4 * Math.PI);
    const v = volumenUndFlaeche(block).volumen / soll;
    expect(v).toBeGreaterThan(0.99);
    expect(v).toBeLessThan(1.02);
  });

  it('Gewicht aus Volumen und Dichte', () => {
    expect(gewichtKg(1e6, 7.85)).toBeCloseTo(7.85);
    expect(gewichtKg(1e6, 0)).toBe(0);
  });
});

describe('Rohteil', () => {
  it('Flansch: Rundmaterial um Z ⌀80 × 32, mit Aufmaß 2 ⌀84 × 36, als Vorschlag', () => {
    const r = rundmaterial(flansch, ACHSEN.Z);
    expect(r.durchmesser).toBeCloseTo(80, 0);
    expect(r.laenge).toBeCloseTo(32, 3);
    const mitAufmass = rohteile(flansch, 2);
    expect(mitAufmass.vorschlag).toMatchObject({ art: 'Rund', achsName: 'Z' });
    expect(mitAufmass.vorschlag.durchmesser).toBeCloseTo(84, 0);
    expect(mitAufmass.vorschlag.laenge).toBeCloseTo(36, 3);
  });

  it('Halteblock: Quader 120 × 60 × 30 ist der Vorschlag', () => {
    const q = quader(block);
    expect([q.x, q.y, q.z].map((v) => Math.round(v * 100) / 100)).toEqual([120, 60, 30]);
    expect(rohteile(block).vorschlag.art).toBe('Quader');
  });

  it('kleinster umschließender Kreis', () => {
    const k = umkreis([[0, 0], [2, 0], [1, 1], [1, -1], [1, 0.2]]);
    expect([k.x, k.y, k.r].map((v) => Math.round(v * 1000) / 1000)).toEqual([1, 0, 1]);
  });
});

describe('Flächen anklicken', () => {
  it('Flansch: Zylinder mit ihren Durchmessern, Bohrungen erkannt', () => {
    expect(zylinder(flansch)).toEqual([6.6, 6.6, 6.6, 6.6, 25, 40, 80]);
    const bohrung = analysen(flansch).find((a) => a.art === 'Zylinder' && Math.abs(a.durchmesser - 25) < 0.1);
    expect(bohrung.bohrung).toBe(true);
    expect(Math.abs(bohrung.achse[2])).toBeCloseTo(1, 3);
    expect(bohrung.laenge).toBeCloseTo(31, 1); // 32 mm hoch, oben 1 mm Fase
    expect(analysen(flansch).find((a) => a.art === 'Zylinder' && Math.abs(a.durchmesser - 80) < 0.1).bohrung).toBe(false);
  });

  it('Halteblock: Bohrungen ⌀8,5 und ⌀10,2, ebene Flächen', () => {
    const d = zylinder(block);
    expect(d.filter((x) => x === 8.5)).toHaveLength(4);
    expect(d).toContain(10.2);
    expect(analysen(block).filter((a) => a.art === 'Ebene').length).toBeGreaterThan(6);
  });

  it('Lochkreis: Abstand zweier gegenüberliegender Bohrungsmitten ist ⌀60', () => {
    const n = flansch[0];
    const loecher = n.flaechen.map((_f, i) => flaecheAnalysieren(n, i)).filter((a) => a.art === 'Zylinder' && Math.abs(a.durchmesser - 6.6) < 0.1);
    const mitten = loecher.map((a) => messpunkt(a.mitte, a).punkt);
    const weiteste = Math.max(...mitten.flatMap((p) => mitten.map((q) => abstand(p, q).gesamt)));
    expect(weiteste).toBeCloseTo(60, 1);
    expect(messpunkt([0, 0, 5], { art: 'Ebene' })).toEqual({ punkt: [0, 0, 5], art: 'Fläche' });
    expect(flaecheZuDreieck(n, n.flaechen[3][0])).toBe(3);
  });
});
