import { describe, it, expect } from 'vitest';
import { berechne, stueckpreisBei } from './calc.js';

const teil = (extra = {}) => ({
  name: 'Testteil',
  menge: 10,
  ruestMin: 60,
  satzRuest: 100,
  stueckMin: 6,
  satzStueck: 100,
  gewichtKg: 0.5,
  materialPreisKg: 8,
  pauschalMaterial: 0,
  messkosten: 20,
  sonderkosten: 0,
  expresskosten: 0,
  inStueckpreis: {},
  staffel: { aktiv: false, stufen: [] },
  ...extra,
});

describe('Einzelpreis', () => {
  it('Rüst + (Stück + Material) × Menge + Messkosten', () => {
    const r = berechne(teil());
    expect(r.gesamt).toBe(260);
    expect(r.stueckpreis).toBe(26);
  });

  it('Rüstkosten im Stückpreis ändern nur die Darstellung, nicht die Summe', () => {
    const r = berechne(teil({ inStueckpreis: { ruest: true } }));
    expect(r.gesamt).toBe(260);
    expect(r.zeilen[0].einzel).toBe(24);
    expect(r.zeilen.find((z) => z.label === 'Rüstkosten')).toBeUndefined();
  });

  it('Menge unter 1 wird auf 1 gesetzt', () => {
    expect(berechne(teil({ menge: 0 })).menge).toBe(1);
  });

  it('ungültige Zahlen zählen als 0', () => {
    const r = berechne(teil({ messkosten: 'abc', gewichtKg: null }));
    expect(r.gesamt).toBe(100 + 10 * 10);
  });
});

describe('Staffelpreise', () => {
  const staffel = { aktiv: true, stufen: [{ menge: 25, extra: 0 }, { menge: 5, extra: 0 }] };

  it('sortiert Stufen und rechnet Rüstkosten auf die Menge um', () => {
    const r = berechne(teil({ staffel }));
    expect(r.stufen.map((s) => s.menge)).toEqual([5, 25]);
    expect(r.stufen[0].stueckpreis).toBe(34);
    expect(r.stufen[0].gesamt).toBe(190);
    expect(r.stufen[1].stueckpreis).toBe(18);
    expect(r.stufen[1].gesamt).toBe(470);
  });

  it('die kleinste Staffel zählt für die Angebotssumme', () => {
    const r = berechne(teil({ staffel }));
    expect(r.gesamt).toBe(190);
  });

  it('eingerechnete Messkosten verschieben nur Stückpreis und Zeilen', () => {
    const r = berechne(teil({ staffel, inStueckpreis: { mess: true } }));
    expect(r.stufen[0].stueckpreis).toBe(38);
    expect(r.stufen[0].gesamt).toBe(190);
    expect(r.zeilen).toHaveLength(0);
  });

  it('Extra-Spalte wird auf den Stückpreis addiert', () => {
    const r = berechne(teil({ staffel: { aktiv: true, stufen: [{ menge: 5, extra: 2 }] } }));
    expect(r.stufen[0].stueckpreis).toBe(36);
    expect(r.stufen[0].gesamt).toBe(200);
  });

  it('ohne gültige Stufen ist die Summe 0', () => {
    expect(berechne(teil({ staffel: { aktiv: true, stufen: [] } })).gesamt).toBe(0);
  });
});

describe('Arbeitsplan', () => {
  const plan = [
    { id: 'a', name: 'Drehen', typ: 'intern', maschine: 'CTX400', satz: 90, ruestMin: 30, stueckMin: 4 },
    { id: 'b', name: 'Fräsen', typ: 'intern', maschine: 'Hermle C42', satz: 120, ruestMin: 60, stueckMin: 3 },
  ];

  it('Rüst- und Stückkosten kommen aus den Arbeitsgängen (Zeit × Satz je Maschine)', () => {
    const r = berechne(teil({ arbeitsgaenge: plan, messkosten: 0 }));
    // Rüsten: 30/60*90 + 60/60*120 = 45 + 120 = 165; Stück: 4/60*90 + 3/60*120 = 6 + 6 = 12; Material 4
    expect(r.setup).toBe(165);
    expect(r.unit).toBe(12);
    expect(r.gesamt).toBe(165 + (12 + 4) * 10);
  });

  it('ohne interne Arbeitsgänge gelten die einfachen Felder', () => {
    expect(berechne(teil({ arbeitsgaenge: [] })).gesamt).toBe(260);
  });

  it('Fremdvergabe je Stück erhöht die Stückkosten', () => {
    const fremd = { id: 'f', name: 'Oberflächenbehandlung', typ: 'fremd', fremdProStk: 1.5, fremdEinmal: 0 };
    const r = berechne(teil({ arbeitsgaenge: [fremd], messkosten: 0 }));
    expect(r.unit).toBe(10 + 1.5);
    expect(r.gesamt).toBe(100 + (11.5 + 4) * 10);
  });

  it('einmalige Fremdkosten erscheinen als eigene Zeile mit dem Namen des Arbeitsgangs', () => {
    const fremd = { id: 'f', name: 'Härten', typ: 'fremd', fremdProStk: 0, fremdEinmal: 80 };
    const r = berechne(teil({ arbeitsgaenge: [fremd], messkosten: 0 }));
    expect(r.zeilen.find((z) => z.label === 'Fremdvergabe Härten').betrag).toBe(80);
    expect(r.gesamt).toBe(100 + 14 * 10 + 80);
  });

  it('einmalige Fremdkosten zählen in jeder Staffel einmal', () => {
    const fremd = { id: 'f', name: 'Härten', typ: 'fremd', fremdProStk: 0, fremdEinmal: 80 };
    const r = berechne(teil({ arbeitsgaenge: [fremd], messkosten: 0, staffel: { aktiv: true, stufen: [{ menge: 5, extra: 0 }] } }));
    expect(r.stufen[0].gesamt).toBe(170 + 80);
  });
});

describe('Preiskurve', () => {
  it('sinkt mit steigender Menge', () => {
    const p = teil();
    expect(stueckpreisBei(p, 1)).toBeGreaterThan(stueckpreisBei(p, 100));
  });
});
