import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { berechne } from './calc.js';
import { positionFuerAuftrag } from './beleg.js';

// Dieselben Fälle prüft der Server (cnc_one/tests/test_beleg.py). Erzeugt mit scripts/gen_auftrag_faelle.mjs.
const faelle = JSON.parse(readFileSync(resolve(__dirname, '../../../shared/auftrag_faelle.json'), 'utf-8'));

describe('gemeinsame Auftragsfälle', () => {
  it('es gibt Fälle', () => expect(faelle.length).toBeGreaterThan(8));
  for (const f of faelle) {
    it(f.name, () => {
      const r = positionFuerAuftrag(f.teil, berechne(f.teil), f.wahl, f.menge, f.kostenAus);
      expect(JSON.parse(JSON.stringify(r))).toEqual(f.erwartet);
    });
  }
});
