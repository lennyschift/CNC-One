import { describe, it, expect } from 'vitest';
import { berechne } from './calc.js';
import { optionen, auftragsPosition, angebotStatus } from './beleg.js';

const teil = (extra = {}) => ({
  name: 'Testteil', menge: 10, ruestMin: 60, satzRuest: 100, stueckMin: 6, satzStueck: 100,
  gewichtKg: 0.5, materialPreisKg: 8, pauschalMaterial: 0, messkosten: 20, sonderkosten: 0, expresskosten: 0,
  inStueckpreis: {}, staffel: { aktiv: false, stufen: [] }, ...extra,
});
const staffel = { aktiv: true, stufen: [{ menge: 5, extra: 0 }, { menge: 25, extra: 0 }] };

describe('optionen', () => {
  it('Staffelangebot liefert jede Staffel', () => {
    const t = teil({ staffel });
    expect(optionen(t, berechne(t)).map((o) => o.menge)).toEqual([5, 25]);
  });
  it('Einzelangebot liefert genau eine Option', () => {
    const t = teil();
    const o = optionen(t, berechne(t));
    expect(o).toHaveLength(1);
    expect(o[0].einzel).toBe(14);
  });
});

describe('auftragsPosition', () => {
  it('Staffel: Stückpreis kommt aus der gewählten Staffel, Menge ist frei', () => {
    const t = teil({ staffel });
    const e = berechne(t);
    const opt = optionen(t, e).find((o) => o.menge === 25);
    const p = auftragsPosition(t, e, opt, 30);
    expect(p.einzelpreis).toBe(18);
    expect(p.menge).toBe(30);
    expect(p.staffelMenge).toBe(25);
    expect(p.kosten).toEqual([{ label: 'Messkosten', betrag: 20 }]);
    expect(p.summe).toBe(18 * 30 + 20);
    expect(p.unterStaffel).toBe(false);
  });
  it('Menge unter der Staffel wird markiert', () => {
    const t = teil({ staffel });
    const e = berechne(t);
    const opt = optionen(t, e).find((o) => o.menge === 25);
    expect(auftragsPosition(t, e, opt, 20).unterStaffel).toBe(true);
  });
  it('Einzelangebot: anderer Mengenwert rechnet neu', () => {
    const t = teil();
    const e = berechne(t);
    const p = auftragsPosition(t, e, optionen(t, e)[0], 100);
    expect(p.menge).toBe(100);
    expect(p.summe).toBe(berechne({ ...t, menge: 100 }).gesamt);
  });
});

describe('angebotStatus', () => {
  const a = { status: 'Gesendet', positionen: [{ key: 'a' }, { key: 'b' }] };
  it('unbestellt bleibt Gesendet', () => expect(angebotStatus(a, {})).toBe('Gesendet'));
  it('eine von zwei Positionen ist teilweise bestellt', () => expect(angebotStatus(a, { a: 5 })).toBe('Teilweise bestellt'));
  it('alle Positionen sind bestellt', () => expect(angebotStatus(a, { a: 5, b: 1 })).toBe('Bestellt'));
  it('Entwurf bleibt Entwurf', () => expect(angebotStatus({ ...a, status: 'Entwurf' }, { a: 5 })).toBe('Entwurf'));
});
