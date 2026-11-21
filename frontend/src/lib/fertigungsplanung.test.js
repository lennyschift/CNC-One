import { describe, it, expect } from 'vitest';
import { maschinenFuer, zeitenNoetigBeiBuchung, zeitenNoetigBeiFertig, zeitenFehlen, auslastung, sollIst, kw, wocheVon, tagIso } from './fertigung.js';

const ag = (id, extra = {}) => ({ id, name: 'Fräsen', typ: 'intern', maschine: 'C42', ruestMin: 60, stueckMin: 6, gebucht: 0, istAm: '', ...extra });
const fb = (ags, extra = {}) => ({ id: 'f', menge: 10, status: 'Offen', teil: { name: 'Welle', teilenummer: 'W-1' }, arbeitsgaenge: ags, ...extra });

describe('Maschinen je Arbeitsgang', () => {
  it('ohne Angabe kann eine Maschine alles', () => {
    const m = [{ name: 'C42', arbeitsgaenge: ['Fräsen'] }, { name: 'CTX', arbeitsgaenge: ['Drehen'] }, { name: 'Säge', arbeitsgaenge: [] }];
    expect(maschinenFuer(m, 'Fräsen').map((x) => x.name)).toEqual(['C42', 'Säge']);
  });
});

describe('Zeiten beim Abschließen', () => {
  it('Teilbuchung braucht keine, die letzte schon, auch für mit abgehakte frühere Arbeitsgänge', () => {
    const x = fb([ag('a'), ag('b', { name: 'Härten', typ: 'fremd' }), ag('c', { name: 'Entgraten' })]);
    expect(zeitenNoetigBeiBuchung(x, 'c', 4)).toEqual([]);
    expect(zeitenNoetigBeiBuchung(x, 'c', 10).map((a) => a.id)).toEqual(['a', 'c']);
    x.arbeitsgaenge[0].istAm = '2026-11-20T10:00:00';
    expect(zeitenNoetigBeiBuchung(x, 'c', 10).map((a) => a.id)).toEqual(['c']);
  });
  it('Fertig braucht alle offenen internen ohne Zeiten; fehlende werden erkannt', () => {
    const x = fb([ag('a', { gebucht: 10 }), ag('b'), ag('c', { typ: 'fremd' })]);
    expect(zeitenNoetigBeiFertig(x).map((a) => a.id)).toEqual(['b']);
    expect(zeitenFehlen(x).map((a) => a.id)).toEqual(['a']);
  });
});

describe('Auslastung und Soll/Ist', () => {
  it('summiert die offenen Minuten je Maschine und Tag', () => {
    const l = auslastung([fb([ag('a', { geplantAm: '2026-11-23' }), ag('b', { geplantAm: '2026-11-23', gebucht: 5 }), ag('c')])]);
    expect(l.plan.C42['2026-11-23']).toBe(60 + 60 + 30); // Rüsten + 10×6, dann nur noch 5×6 (schon begonnen)
    expect(l.ungeplant.C42).toBe(120);
  });
  it('vergleicht Soll und Ist der gemeldeten Arbeitsgänge', () => {
    const x = fb([ag('a', { gebucht: 10, istAm: 'x', istRuestMin: 90, istBearbMin: 72 }), ag('b', { maschine: 'CTX' })]);
    const [g] = sollIst([x]);
    expect([g.name, g.anzahl, g.soll, g.ist]).toEqual(['C42', 1, 120, 162]);
    expect(g.abweichung).toBeCloseTo(0.35, 5);
    expect(sollIst([x], 'bauteil')[0].name).toBe('W-1 · Welle');
  });
});

describe('Kalender', () => {
  it('Wochenanfang Montag und Kalenderwoche', () => {
    expect(tagIso(wocheVon(new Date(2026, 10, 21)))).toBe('2026-11-16');
    expect(kw(new Date(2026, 10, 21))).toBe(47);
    expect(kw(new Date(2027, 0, 1))).toBe(53);
  });
});
