import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { berechne } from './calc.js';

// Dieselben Fälle prüft auch der Server (cnc_one/tests/test_kalkulation.py). Erzeugt mit scripts/gen_kalkulation_faelle.mjs.
const faelle = JSON.parse(readFileSync(resolve(__dirname, '../../../shared/kalkulation_faelle.json'), 'utf-8'));

describe('gemeinsame Kalkulationsfälle', () => {
  it('es gibt Fälle', () => expect(faelle.length).toBeGreaterThan(10));
  for (const f of faelle) {
    it(f.name, () => {
      expect(JSON.parse(JSON.stringify(berechne(f.eingabe)))).toEqual(f.erwartet);
    });
  }
});
