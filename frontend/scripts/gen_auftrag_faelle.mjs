// Erzeugt shared/auftrag_faelle.json: Auftragsposition aus einer Angebotsposition (calc.js + beleg.js).
// Der Server prüft dieselben Fälle (tests/test_beleg.py). Aufruf: node scripts/gen_auftrag_faelle.mjs
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { berechne } from '../src/lib/calc.js';
import { positionFuerAuftrag } from '../src/lib/beleg.js';

const basis = (extra = {}) => ({
  name: 'Testteil', menge: 10, ruestMin: 60, satzRuest: 100, stueckMin: 6, satzStueck: 100,
  gewichtKg: 0.5, materialPreisKg: 8, pauschalMaterial: 0, pauschalAlsZeile: false,
  messkosten: 20, sonderkosten: 0, expresskosten: 0,
  inStueckpreis: { ruest: false, mess: false, sonder: false, express: false },
  staffel: { aktiv: false, stufen: [] }, arbeitsgaenge: [], ...extra,
});
const staffel = (...mengen) => ({ aktiv: true, stufen: mengen.map((menge) => ({ menge, extra: 0 })) });
const fremd = (id, name, proStk, einmal) => ({ id, name, typ: 'fremd', lieferant: 'L', fremdProStk: proStk, fremdEinmal: einmal });

const faelle = [
  ['einzelangebot mit angebotsmenge', basis(), null, 10, []],
  ['einzelangebot mit anderer menge', basis(), null, 100, []],
  ['einzelangebot mit abgewaehlten kosten', basis(), null, 10, ['Rüstkosten']],
  ['staffel erste stufe', basis({ staffel: staffel(5, 25, 100) }), 5, 5, []],
  ['staffel mittlere stufe mit freier menge', basis({ staffel: staffel(5, 25, 100) }), 25, 30, []],
  ['staffel menge unter der stufe', basis({ staffel: staffel(5, 25, 100) }), 25, 20, []],
  ['staffel mit abgewaehlter messkosten', basis({ staffel: staffel(5, 25) }), 25, 25, ['Messkosten']],
  ['unbekannte staffel faellt auf die erste zurueck', basis({ staffel: staffel(5, 25) }), 77, 5, []],
  ['staffel mit fremdvergabe einmalig', basis({ arbeitsgaenge: [fremd('c', 'Härten', 0.6, 80)], staffel: staffel(5, 25) }), 25, 25, []],
  ['einzelangebot mit fremdvergabe', basis({ arbeitsgaenge: [fremd('c', 'Eloxieren', 1.2, 45)] }), null, 12, []],
  ['menge null wird eins', basis(), null, 0, []],
].map(([name, teil, wahl, menge, kostenAus]) => ({
  name,
  teil: JSON.parse(JSON.stringify(teil)),
  wahl,
  menge,
  kostenAus,
  erwartet: JSON.parse(JSON.stringify(positionFuerAuftrag(teil, berechne(teil), wahl, menge, kostenAus))),
}));

const ziel = resolve(dirname(fileURLToPath(import.meta.url)), '../../shared/auftrag_faelle.json');
writeFileSync(ziel, JSON.stringify(faelle, null, 1) + '\n');
console.log(`${faelle.length} Fälle nach ${ziel}`);
