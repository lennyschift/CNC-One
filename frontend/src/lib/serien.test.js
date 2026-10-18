import { describe, it, expect } from 'vitest';
import { bereichText, erledigt, offen, bereich, formatNr, hoechste } from './serien.js';

describe('Seriennummern', () => {
  it('Nummern haben immer führende Nullen', () => {
    expect(formatNr(1)).toBe('0001');
    expect(formatNr('10')).toBe('0010');
    expect(formatNr('0010')).toBe('0010');
    expect(formatNr(123, 6)).toBe('000123');
    expect(formatNr('')).toBe('');
    expect(formatNr(null)).toBe('');
  });
  it('Buchstaben und Sonderzeichen fallen weg', () => expect(formatNr('1a2-')).toBe('0012'));
  it('größte Nummer je Stellenzahl', () => {
    expect(hoechste(4)).toBe(9999);
    expect(hoechste(6)).toBe(999999);
  });
  it('Bereich ab der Startnummer', () => {
    expect(bereich(1001, 10)).toEqual({ von: 1001, bis: 1010 });
    expect(bereich('0021', 10)).toEqual({ von: 21, bis: 30 });
    expect(bereich('', 10)).toBeNull();
    expect(bereich('12a', 10)).toBeNull();
    expect(bereich(5, 0)).toBeNull();
  });
  it('Text mit führenden Nullen', () => {
    expect(bereichText(1, 10)).toBe('0001–0010');
    expect(bereichText(7, 7)).toBe('0007');
    expect(bereichText(121, 130, 6)).toBe('000121–000130');
    expect(bereichText(null, null)).toBe('');
  });
  it('die ersten gebuchten Nummern sind erledigt, der Rest offen', () => {
    expect(erledigt(1001, 1010, 5)).toEqual({ von: 1001, bis: 1005 });
    expect(offen(1001, 1010, 5)).toEqual({ von: 1006, bis: 1010 });
    expect(erledigt(1001, 1010, 0)).toBeNull();
    expect(offen(1001, 1010, 0)).toEqual({ von: 1001, bis: 1010 });
    expect(offen(1001, 1010, 10)).toBeNull();
  });
  it('Überproduktion bekommt keine Nummer', () => expect(erledigt(1001, 1010, 12)).toEqual({ von: 1001, bis: 1010 }));
  it('ohne Bereich nichts', () => { expect(erledigt(null, null, 3)).toBeNull(); expect(offen(undefined, undefined, 3)).toBeNull(); });
});
