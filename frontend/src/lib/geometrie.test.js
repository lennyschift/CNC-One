import { describe, it, expect } from 'vitest';
import { fingerabdruck, GEO_VERSION } from './geometrie.js';

// Quader als Dreiecksnetz, optional gedreht (um Z) und verschoben
function quader(a, b, c, { winkel = 0, versatz = [0, 0, 0] } = {}) {
  const ecken = [[0, 0, 0], [a, 0, 0], [a, b, 0], [0, b, 0], [0, 0, c], [a, 0, c], [a, b, c], [0, b, c]].map(([x, y, z]) => {
    const co = Math.cos(winkel); const si = Math.sin(winkel);
    return [x * co - y * si + versatz[0], x * si + y * co + versatz[1], z + versatz[2]];
  });
  const f = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]];
  return [{ position: Float32Array.from(ecken.flat()), index: Uint32Array.from(f.flat()) }];
}
const l1 = (x, y) => x.reduce((s, v, i) => s + Math.abs(v - y[i]), 0);

describe('fingerabdruck', () => {
  it('Maße, Volumen, Füllgrad eines Quaders', () => {
    const f = fingerabdruck(quader(100, 40, 20));
    expect(f.v).toBe(GEO_VERSION);
    expect(f.masse[0]).toBeCloseTo(100, 0);
    expect(f.masse[1]).toBeCloseTo(40, 0);
    expect(f.masse[2]).toBeCloseTo(20, 0);
    expect(f.volumen).toBeCloseTo(80000, -1);
    expect(f.fuell).toBeCloseTo(1, 2);
    expect(f.d2.reduce((s, x) => s + x, 0)).toBeCloseTo(1, 3);
  });
  it('unabhängig von Lage und Drehung', () => {
    const a = fingerabdruck(quader(100, 40, 20));
    const b = fingerabdruck(quader(100, 40, 20, { winkel: 0.7, versatz: [500, -30, 12] }));
    expect(b.masse[0]).toBeCloseTo(a.masse[0], 0);
    expect(b.masse[1]).toBeCloseTo(a.masse[1], 0);
    expect(l1(a.d2, b.d2)).toBeLessThan(0.15);
  });
  it('gleiche Form in anderer Größe: gleiche Verteilung, andere Form deutlich anders', () => {
    const a = fingerabdruck(quader(100, 40, 20));
    const gross = fingerabdruck(quader(200, 80, 40));
    const wuerfel = fingerabdruck(quader(50, 50, 50));
    expect(l1(a.d2, gross.d2)).toBeLessThan(0.15);
    expect(l1(a.d2, wuerfel.d2)).toBeGreaterThan(l1(a.d2, gross.d2));
  });
  it('immer gleich für dasselbe Modell', () => {
    expect(fingerabdruck(quader(30, 20, 10))).toEqual(fingerabdruck(quader(30, 20, 10)));
  });
  it('ohne Geometrie: null', () => expect(fingerabdruck([{ position: new Float32Array(0), index: new Uint32Array(0) }])).toBeNull());
});
