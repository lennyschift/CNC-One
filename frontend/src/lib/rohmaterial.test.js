import { describe, it, expect } from 'vitest';
import { rohVolumen, rohGewicht, rohText, vollstaendig, ausModell, vorschlagAnwenden, leeresRoh, aufrunden } from './rohmaterial.js';

describe('Rohmaterial', () => {
  it('Volumen je Form', () => {
    expect(rohVolumen({ form: 'Rund', durchmesser: 10, laenge: 100 })).toBeCloseTo(Math.PI * 25 * 100);
    expect(rohVolumen({ form: 'Flach', breite: 60, hoehe: 20, laenge: 100 })).toBe(120000);
    expect(rohVolumen({ form: 'Rohr', durchmesser: 40, innen: 30, laenge: 10 })).toBeCloseTo((Math.PI / 4) * (1600 - 900) * 10);
    expect(rohVolumen({ form: 'Sechskant', schluesselweite: 20, laenge: 10 })).toBeCloseTo((Math.sqrt(3) / 2) * 400 * 10);
    expect(rohVolumen({ form: 'Rund', durchmesser: 10 })).toBe(0);
  });

  it('Gewicht: Rund Ø45 × 82 aus C45 (7,85) wiegt rund 1,02 kg', () => {
    expect(rohGewicht({ form: 'Rund', durchmesser: 45, laenge: 82 }, 7.85)).toBeCloseTo(1.024, 3);
    expect(rohGewicht({ form: 'Rund', durchmesser: 45, laenge: 82 }, 0)).toBe(0);
  });

  it('Text und Vollständigkeit', () => {
    expect(rohText({ form: 'Rund', durchmesser: 45, laenge: 82.5 })).toBe('Rund Ø45 × 82,5');
    expect(rohText({ form: 'Rohr', durchmesser: 40, innen: 0, laenge: 10 })).toBe('Rohr Ø40 × 10');
    expect(vollstaendig({ form: 'Flach', breite: 10, hoehe: 0, laenge: 5 })).toBe(false);
    expect(rohText({ form: 'Flach', breite: 10, hoehe: 0, laenge: 5 })).toBe('');
  });

  it('Vorschlag aus dem Modell: auf volle mm aufgerundet, beim Quader längste Seite als Länge', () => {
    expect(ausModell({ form: 'Rund', durchmesser: 44.6, laenge: 80.1, drehteil: true })).toMatchObject({ form: 'Rund', durchmesser: 45, laenge: 81, drehteil: true });
    expect(ausModell({ form: 'Flach', x: 20.2, y: 120, z: 60.4 })).toMatchObject({ form: 'Flach', laenge: 120, breite: 61, hoehe: 21 });
    expect(aufrunden(45.0000001)).toBe(45);
  });

  it('Vorschlag übernehmen: Maße neu, Zeugnis und Lager bleiben', () => {
    const alt = { ...leeresRoh(), form: 'Flach', breite: 10, hoehe: 10, laenge: 10, zeugnis: '3.1', ausLager: true };
    const neu = vorschlagAnwenden(alt, ausModell({ form: 'Rund', durchmesser: 30, laenge: 50 }));
    expect(neu).toMatchObject({ form: 'Rund', durchmesser: 30, laenge: 50, breite: 0, hoehe: 0, zeugnis: '3.1', ausLager: true });
    expect(neu.exakt).toBeUndefined();
  });
});
