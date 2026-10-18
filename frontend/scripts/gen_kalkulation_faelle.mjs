// Erzeugt shared/kalkulation_faelle.json: Eingaben für die Kalkulation und das Ergebnis von calc.js.
// Sowohl die Tests der Oberfläche (calc.js) als auch die Server-Tests (kalkulation.py) prüfen gegen diese Datei.
// Aufruf nach jeder Änderung der Rechenregeln:  node scripts/gen_kalkulation_faelle.mjs
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { berechne } from '../src/lib/calc.js';

const basis = (extra = {}) => ({
  name: 'Testteil', menge: 10, ruestMin: 60, satzRuest: 100, stueckMin: 6, satzStueck: 100,
  gewichtKg: 0.5, materialPreisKg: 8, pauschalMaterial: 0, pauschalAlsZeile: false,
  messkosten: 20, sonderkosten: 0, expresskosten: 0,
  inStueckpreis: { ruest: false, mess: false, sonder: false, express: false },
  staffel: { aktiv: false, stufen: [] }, arbeitsgaenge: [],
  ...extra,
});
const staffel = (stufen) => ({ aktiv: true, stufen });
const intern = (id, name, satz, ruestMin, stueckMin) => ({ id, name, typ: 'intern', maschine: 'M', satz, ruestMin, stueckMin });
const fremd = (id, name, fremdProStk, fremdEinmal) => ({ id, name, typ: 'fremd', lieferant: 'L', fremdProStk, fremdEinmal });

const faelle = {
  'einzelpreis einfach': basis(),
  'ruestkosten im stueckpreis': basis({ inStueckpreis: { ruest: true } }),
  'pauschal material in den stueckpreis': basis({ pauschalMaterial: 90 }),
  'pauschal material als eigene zeile': basis({ pauschalMaterial: 90, pauschalAlsZeile: true }),
  'alle zusatzkosten einzeln': basis({ messkosten: 20, sonderkosten: 35.5, expresskosten: 150 }),
  'zusatzkosten im stueckpreis': basis({ messkosten: 20, sonderkosten: 35.5, expresskosten: 150, inStueckpreis: { mess: true, sonder: true, express: true } }),
  'staffel einfach': basis({ staffel: staffel([{ menge: 25, extra: 0 }, { menge: 5, extra: 0 }, { menge: 100, extra: 0 }]) }),
  'staffel mit aufschlag': basis({ staffel: staffel([{ menge: 5, extra: 2.5 }, { menge: 50, extra: 0.75 }]) }),
  'staffel mit eingerechneten kosten': basis({ sonderkosten: 77, inStueckpreis: { mess: true, sonder: false }, staffel: staffel([{ menge: 5, extra: 0 }, { menge: 20, extra: 0 }]) }),
  'staffel ohne gueltige stufen': basis({ staffel: staffel([{ menge: 0, extra: 1 }]) }),
  'arbeitsplan mit zwei maschinen': basis({ messkosten: 0, arbeitsgaenge: [intern('a', 'Drehen', 88, 45, 2.5), intern('b', 'Fräsen', 105, 60, 4)] }),
  'arbeitsplan mit fremdvergabe je stueck': basis({ messkosten: 0, arbeitsgaenge: [intern('a', 'Drehen', 88, 45, 2.5), fremd('c', 'Oberflächenbehandlung', 1.8, 0)] }),
  'arbeitsplan mit einmaliger fremdvergabe': basis({ arbeitsgaenge: [intern('a', 'Drehen', 88, 45, 2.5), fremd('c', 'Härten', 0.6, 80)] }),
  'nur fremdvergabe ohne interne arbeitsgaenge': basis({ arbeitsgaenge: [fremd('c', 'Eloxieren', 1.2, 45)] }),
  'staffel mit fremdvergabe': basis({ arbeitsgaenge: [intern('a', 'Drehen', 88, 45, 2.5), fremd('c', 'Härten', 0.6, 80)], staffel: staffel([{ menge: 5, extra: 0 }, { menge: 25, extra: 0 }]) }),
  'ungueltige werte': basis({ messkosten: 'abc', gewichtKg: null, ruestMin: undefined, menge: 'x' }),
  'menge null und negativ': basis({ menge: 0, staffel: staffel([{ menge: -5, extra: 0 }]) }),
  'zahlen als text': basis({ menge: '12', gewichtKg: '0.75', materialPreisKg: '6.4', stueckMin: '3.5' }),
  'rundung grenzfall': basis({ menge: 3, ruestMin: 7, satzRuest: 33.33, stueckMin: 1.1, satzStueck: 17.77, gewichtKg: 0.333, materialPreisKg: 6.99 }),
  'viele nachkommastellen': basis({ menge: 7, ruestMin: 13, satzRuest: 94.37, stueckMin: 2.27, satzStueck: 111.11, messkosten: 12.345 }),
};

const ausgabe = Object.entries(faelle).map(([name, eingabe]) => ({
  name,
  eingabe: JSON.parse(JSON.stringify(eingabe)),
  erwartet: JSON.parse(JSON.stringify(berechne(eingabe))),
}));

const ziel = resolve(dirname(fileURLToPath(import.meta.url)), '../../shared/kalkulation_faelle.json');
mkdirSync(dirname(ziel), { recursive: true });
writeFileSync(ziel, JSON.stringify(ausgabe, null, 1) + '\n');
console.log(`${ausgabe.length} Fälle nach ${ziel}`);
