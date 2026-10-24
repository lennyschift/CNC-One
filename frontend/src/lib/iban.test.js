import { describe, it, expect } from 'vitest';
import { ibanGueltig, ibanFormatiert, ibanBereinigt } from './iban.js';

describe('IBAN', () => {
  it('gültige IBANs, mit und ohne Leerzeichen', () => {
    expect(ibanGueltig('DE64 6225 0030 0005 4437 72')).toBe(true);
    expect(ibanGueltig('DE50622901100502144009')).toBe(true);
  });
  it('zu kurze und falsche Prüfziffer', () => {
    expect(ibanGueltig('DE64 0030 0005 4437 72')).toBe(false);
    expect(ibanGueltig('DE65 6225 0030 0005 4437 72')).toBe(false);
    expect(ibanGueltig('')).toBe(false);
  });
  it('Formatierung in Vierergruppen', () => {
    expect(ibanFormatiert('de64622500300005443772')).toBe('DE64 6225 0030 0005 4437 72');
    expect(ibanBereinigt(' de64 6225 ')).toBe('DE646225');
  });
});
