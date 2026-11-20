import { describe, it, expect } from 'vitest';
import { cadKanten, kanteAmStrahl, fangpunkt, flaechenpunkt, messen } from './kanten.js';
import { flaecheAnalysieren } from './messen.js';
import modelle from './testdaten/modelle.json';

// Testmodelle siehe messen.test.js: Flansch (Scheibe ⌀80×12, Bund ⌀40×20, Bohrung ⌀25, 4 × ⌀6,6 auf LK 60, Fase 1 mm),
// Halteblock 120×60×30 mit Tasche, Bohrungen und Ecken R4
const flansch = modelle['ZZ-3D-001_Flansch.step'];
const block = modelle['ZZ-3D-002_Halteblock.stp'];
const rund = (v, s = 10) => Math.round(v * s) / s;

describe('CAD-Kanten', () => {
  it('Flansch: Kreise mit den Durchmessern der Bohrungen und Absätze', () => {
    const kreise = cadKanten(flansch).filter((k) => k.art === 'Kreis').map((k) => rund(2 * k.radius));
    for (const d of [80, 40, 25, 6.6]) expect(kreise).toContain(d);
    expect(kreise.filter((d) => d === 6.6).length).toBeGreaterThanOrEqual(8); // je Loch oben und unten
  });

  it('Halteblock: Geraden 120, 60 und 30 mm, Bögen R4 an den Ecken', () => {
    const k = cadKanten(block);
    const geraden = k.filter((x) => x.art === 'Gerade').map((x) => rund(x.laenge));
    expect(geraden).toEqual(expect.arrayContaining([30]));
    expect(geraden.some((l) => l >= 100)).toBe(true);
    const boegen = k.filter((x) => x.art === 'Bogen').map((x) => rund(x.radius));
    expect(boegen).toContain(4);
    const r4 = k.find((x) => x.art === 'Bogen' && rund(x.radius) === 4);
    expect(rund((r4.winkel * 180) / Math.PI, 1)).toBe(90);
  });

  it('Kante unter dem Mauszeiger finden und fangen', () => {
    const k = cadKanten(block).find((x) => x.art === 'Gerade' && x.laenge > 50);
    // Strahl von oben/außen genau auf einen Punkt bei 30 % der Kante
    const ziel = k.start.map((v, i) => v + (k.ende[i] - v) * 0.3);
    const o = [ziel[0] + 300, ziel[1] + 300, ziel[2] + 300];
    const d0 = ziel.map((v, i) => v - o[i]);
    const l = Math.hypot(...d0);
    const d = d0.map((v) => v / l);
    const t = kanteAmStrahl(cadKanten(block), o, d, { proPixel: 0.002, fangPx: 8 });
    expect(t).not.toBeNull();
    expect(rund(t.kante.laenge)).toBe(rund(k.laenge));
    const f = fangpunkt(t, 1);
    expect(f.art).toBe('Kante');
    const amEnde = fangpunkt({ kante: k, punkt: k.start.map((v) => v + 0.2) }, 1);
    expect(amEnde.art).toBe('Endpunkt');
    expect(fangpunkt({ kante: k, punkt: k.mitte }, 1).art).toBe('Kantenmitte');
  });

  it('Messen: parallele Flächen senkrecht, Achsabstand der Lochkreisbohrungen', () => {
    const n = flansch[0];
    const a = n.flaechen.map((_f, i) => flaecheAnalysieren(n, i));
    const ebenen = a.filter((x) => x.art === 'Ebene' && Math.abs(x.normale[2]) > 0.999);
    // Unterseite (z = 0) und Oberseite der Scheibe (z = 12): Abstand 12, egal wo angeklickt
    const unten = flaechenpunkt([30, 5, 0], ebenen[0]);
    const oben = flaechenpunkt([-25, -10, 12], { ...ebenen[0] });
    const m = messen(unten, oben);
    expect(m.art).toBe('Abstand der Flächen');
    expect(rund(m.gesamt)).toBe(12);
    const loecher = a.filter((x) => x.art === 'Zylinder' && rund(x.durchmesser) === 6.6);
    const p = loecher.map((x) => flaechenpunkt(x.mitte, x));
    const weit = Math.max(...p.flatMap((x) => p.map((y) => messen(x, y).gesamt)));
    expect(rund(weit)).toBe(60);
    expect(messen(p[0], p[1]).art).toBe('Achsabstand');
  });

  it('Rundungen werden als Radius erkannt, volle Bohrungen nicht', () => {
    const n = block[0];
    const z = n.flaechen.map((_f, i) => flaecheAnalysieren(n, i)).filter((x) => x.art === 'Zylinder');
    expect(z.some((x) => x.rundung && rund(x.radius) === 4)).toBe(true);
    expect(z.filter((x) => rund(x.durchmesser) === 8.5).every((x) => !x.rundung)).toBe(true);
  });
});
