import { describe, it, expect } from 'vitest';
import { aufmassNorm, quaderZugaben, rundZugaben, aufmassUmschalten, aufmassSpeicherform, aufmassText, pfeilFeld, pfeilWert, aufmassAendern } from './aufmass.js';
import { quader, rundmaterial, ACHSEN } from './messen.js';

// Würfel 10 × 20 × 30 mm von (0,0,0) bis (10,20,30) als ein Netz aus Eckpunkten
const ecken = [];
for (const x of [0, 10]) for (const y of [0, 20]) for (const z of [0, 30]) ecken.push(x, y, z);
const block = [{ position: new Float32Array(ecken), index: null }];

describe('Aufmaß des Rohteils', () => {
  it('eine Zahl gilt wie bisher rundum', () => {
    expect(aufmassNorm(2).art).toBe('gleich');
    expect(quaderZugaben(2)).toEqual({ minus: [2, 2, 2], plus: [2, 2, 2], fest: null });
    const q = quader(block, 2);
    expect([q.x, q.y, q.z]).toEqual([14, 24, 34]);
  });

  it('Seiten, oben und unten getrennt (wie Fusion)', () => {
    const a = { art: 'seiten', seite: 4, oben: 1, unten: 5 };
    expect(quaderZugaben(a)).toEqual({ minus: [4, 4, 5], plus: [4, 4, 1], fest: null });
    const q = quader(block, a);
    expect([q.x, q.y, q.z]).toEqual([18, 28, 36]);
    expect(q.min[2]).toBe(-5);
    expect(q.max[2]).toBe(31);
  });

  it('je Richtung einzeln', () => {
    const q = quader(block, { art: 'einzeln', xm: 1, xp: 2, ym: 0, yp: 3, zm: 0, zp: 0.5 });
    expect([q.x, q.y, q.z]).toEqual([13, 23, 30.5]);
    expect(q.min).toEqual([-1, 0, 0]);
  });

  it('feste Größe liegt mittig, zu klein wird gemeldet', () => {
    const q = quader(block, { art: 'fest', x: 20, y: 20, z: 40 });
    expect([q.x, q.y, q.z]).toEqual([20, 20, 40]);
    expect(q.min).toEqual([-5, 0, -5]);
    expect(q.kleiner).toBe(false);
    expect(quader(block, { art: 'fest', x: 8, y: 20, z: 40 }).kleiner).toBe(true);
  });

  it('Rund: Durchmesser und Stirnseiten getrennt, Mitte verschiebt sich', () => {
    const r0 = rundmaterial(block, ACHSEN.Z);
    const r = rundmaterial(block, ACHSEN.Z, { art: 'einzeln', radial: 1, l1: 2, l2: 6 });
    expect(r.durchmesser).toBeCloseTo(r0.durchmesser + 2, 6);
    expect(r.laenge).toBeCloseTo(38, 6);
    expect(r.mitte[2]).toBeCloseTo(17, 6); // von −2 bis 36
    expect(rundZugaben({ art: 'seiten', radial: 3, stirn: 2 })).toEqual({ radial: 3, l1: 2, l2: 2, fest: null });
    const f = rundmaterial(block, ACHSEN.Z, { art: 'fest', d: 40, l: 35 });
    expect([f.durchmesser, f.laenge, f.kleiner]).toEqual([40, 35, false]);
  });

  it('Umschalten belegt die neue Art aus dem bisherigen Aufmaß vor', () => {
    const s = aufmassUmschalten(3, 'seiten');
    expect([s.seite, s.oben, s.unten, s.radial, s.stirn]).toEqual([3, 3, 3, 3, 3]);
    const e = aufmassUmschalten({ art: 'seiten', seite: 4, oben: 1, unten: 5 }, 'einzeln');
    expect([e.xm, e.xp, e.zm, e.zp]).toEqual([4, 4, 5, 1]);
    const f = aufmassUmschalten(2, 'fest', { art: 'Quader', x: 14.2, y: 24, z: 34.0000001 });
    expect([f.x, f.y, f.z]).toEqual([15, 24, 34]);
    expect(aufmassSpeicherform(aufmassUmschalten(e, 'gleich'))).toBe(5);
  });

  it('Kurztext', () => {
    expect(aufmassText(2)).toBe('2 mm je Seite');
    expect(aufmassText({ art: 'seiten', seite: 4, oben: 1, unten: 5 })).toBe('Seiten 4, oben 1, unten 5 mm');
    expect(aufmassText({ art: 'einzeln', radial: 1.5, l1: 2, l2: 3 }, 'Rund')).toBe('⌀ +3, Stirnseiten 2 / 3 mm');
  });
});

describe('Ziehen an den Richtungspfeilen', () => {
  it('wählt das Feld je Aufmaß-Art und Pfeil', () => {
    expect(pfeilFeld(2, 'Quader', 'xp')).toEqual({ feld: 'wert', faktor: 1 });
    expect(pfeilFeld({ art: 'seiten' }, 'Quader', 'ym')).toEqual({ feld: 'seite', faktor: 1 });
    expect(pfeilFeld({ art: 'seiten' }, 'Quader', 'zp').feld).toBe('oben');
    expect(pfeilFeld({ art: 'seiten' }, 'Quader', 'zm').feld).toBe('unten');
    expect(pfeilFeld({ art: 'einzeln' }, 'Quader', 'yp').feld).toBe('yp');
    expect(pfeilFeld({ art: 'fest' }, 'Quader', 'zm')).toEqual({ feld: 'z', faktor: 2 });
    expect(pfeilFeld({ art: 'einzeln' }, 'Rund', 'a').feld).toBe('l1');
    expect(pfeilFeld({ art: 'einzeln' }, 'Rund', 'b').feld).toBe('l2');
    expect(pfeilFeld({ art: 'seiten' }, 'Rund', 'r').feld).toBe('radial');
    expect(pfeilFeld({ art: 'fest' }, 'Rund', 'r')).toEqual({ feld: 'd', faktor: 2 });
  });
  it('liest und setzt den Wert, feste Größe aus dem Rohteil vorbelegt', () => {
    expect(pfeilWert({ art: 'einzeln', xp: 3 }, 'Quader', 'xp')).toBe(3);
    const r = quader(block, 0);
    expect(pfeilWert({ art: 'fest' }, 'Quader', 'yp', r)).toBe(20);
    expect(aufmassAendern({ art: 'fest' }, 'x', 14, r)).toEqual({ art: 'fest', x: 14, y: 20, z: 30, d: 0, l: 0 });
    expect(aufmassAendern(1, 'wert', 2.345)).toBe(2.35);
    expect(aufmassAendern({ art: 'einzeln', xm: 1 }, 'xm', -4).xm).toBe(0);
  });
});
