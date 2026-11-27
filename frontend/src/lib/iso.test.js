import { describe, it, expect } from 'vitest';
import { isoAusName } from './iso.js';

describe('ISO-Materialgruppe aus dem Werkstoff', () => {
  it('Werkstoffnummern', () => {
    expect(isoAusName('1.0037')).toBe('P');
    expect(isoAusName('1.7225 42CrMo4')).toBe('P');
    expect(isoAusName('1.2379')).toBe('P');
    expect(isoAusName('1.4301')).toBe('M');
    expect(isoAusName('1.4404')).toBe('M');
    expect(isoAusName('0.6025')).toBe('K');
    expect(isoAusName('0.7040')).toBe('K');
    expect(isoAusName('3.3547')).toBe('N');
    expect(isoAusName('2.0401')).toBe('N');
    expect(isoAusName('2.4816')).toBe('S');
    expect(isoAusName('3.7165')).toBe('S');
  });
  it('Kurznamen', () => {
    expect(isoAusName('S235JR')).toBe('P');
    expect(isoAusName('C45')).toBe('P');
    expect(isoAusName('42CrMo4')).toBe('P');
    expect(isoAusName('X153CrMoV12')).toBe('P');
    expect(isoAusName('AISI 4140')).toBe('P');
    expect(isoAusName('X5CrNi18-10')).toBe('M');
    expect(isoAusName('V4A')).toBe('M');
    expect(isoAusName('AISI 316L')).toBe('M');
    expect(isoAusName('EN-GJL-250')).toBe('K');
    expect(isoAusName('EN AW-6082')).toBe('N');
    expect(isoAusName('AlMg4,5Mn')).toBe('N');
    expect(isoAusName('CW614N')).toBe('N');
    expect(isoAusName('POM-C')).toBe('O');
    expect(isoAusName('PEEK natur')).toBe('O');
    expect(isoAusName('PA 6')).toBe('O');
    expect(isoAusName('EN AW-7075')).toBe('N');
    expect(isoAusName('Inconel 718')).toBe('S');
    expect(isoAusName('Ti6Al4V')).toBe('S');
  });
  it('unbekannt bleibt leer', () => {
    expect(isoAusName('')).toBe('');
    expect(isoAusName('Sonderwerkstoff')).toBe('');
  });
});
