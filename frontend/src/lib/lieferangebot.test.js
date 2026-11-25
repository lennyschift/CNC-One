import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import { angebotLesen, masseAus, werkstoffAus, zustandAus, zuordnen, preiseFuer, abgleich, spaltenVorlage, lieferantErkennen, lieferantVorschlag, positionsGruppen, betragAus, gleicheWare, abweichungen, merkmaleAus, toleranzenAus } from './lieferangebot.js';

// Text mit Lage aus echten Angeboten (Fußzeilen mit Bankverbindung entfernt)
const DATEN = JSON.parse(fs.readFileSync(new URL('./testdaten/lieferangebote.json', import.meta.url), 'utf8'));
const kurz = (p) => ({ pos: p.pos, option: p.option, werkstoff: p.werkstoff, zustand: p.zustand, form: p.form, masse: p.masse, stueck: p.stueck, kg: p.kg, preis: p.preis, preisJe: p.preisJe, betrag: p.betrag });

describe('Lieferantenangebote lesen', () => {
  it('Almet: Preis je kg, Option mit Preis je Stück, Nebenkosten unter der Summe', () => {
    const r = angebotLesen(DATEN.almet);
    expect(r.kopf).toMatchObject({ angebotsnr: '945914', datum: '2026-11-17', gueltigBis: '2026-11-17' });
    expect(r.positionen.map(kurz)).toEqual([
      { pos: '1', option: false, werkstoff: 'EN AW-6082', zustand: 'T651', form: 'Platte', masse: [15, 20, 3020], stueck: 18, kg: 44.85, preis: 9.7, preisJe: 'kg', betrag: 435.04 },
      { pos: '2', option: true, werkstoff: 'EN AW-6082', zustand: 'T651', form: 'Platte', masse: [15, 20, 150], stueck: 350, kg: null, preis: 2.7, preisJe: 'Stk', betrag: 945 },
    ]);
    expect(r.positionen[0]).toMatchObject({ artikelnr: '1014375', lieferdatum: '2026-11-20' });
    expect(r.nebenkosten.map((n) => [n.text, n.betrag])).toEqual([['Verpackung', 30], ['Transportkostenanteil incl. Maut', 79], ['Treibstoffzuschlag', 9.2]]);
    expect([r.netto, r.stimmt]).toEqual([553.24, true]);
  });

  it('Weinmann: mehrseitig, kg und Stück in der Mengenspalte, Preiseinheit KG, Verpackung zwischen den Positionen', () => {
    const r = angebotLesen(DATEN.weinmann);
    expect(r.kopf).toMatchObject({ angebotsnr: 'VAN26-281053', datum: '2026-11-11' });
    expect(r.positionen.map((p) => p.pos)).toEqual(['10', '20', '30', '40', '60', '70', '80', '90']);
    expect(kurz(r.positionen[0])).toEqual({ pos: '10', option: false, werkstoff: 'EN AW-7075', zustand: 'T651', form: 'Platte', masse: [20, 50, 1500], stueck: 16, kg: 68.5, preis: 8.3, preisJe: 'kg', betrag: 568.55 });
    expect(r.positionen[3]).toMatchObject({ werkstoff: 'EN AW-7075', masse: [20, 185, 360], preis: 12.05 });
    expect(r.positionen[2].liefertermin).toMatch(/24\.11\.26/); // steht oben auf Seite 2
    expect(r.positionen[5]).toMatchObject({ form: 'Rund', masse: [110, 601], stueck: 1, kg: 16.5, meter: 0.601, preisJe: 'kg', betrag: 114.68 });
    expect(r.positionen[6]).toMatchObject({ form: 'Flach', werkstoff: 'EN AW-6082', masse: [20, 90, 3000], meter: 3 });
    expect(r.nebenkosten.map((n) => [n.text, n.betrag, !!n.zusaetzlich])).toEqual([
      ['Verpackung Plattenzuschnitte', 20, false],
      ['Gesamtbetrag zzgl. Transportkostenanteil(e)', 89.9, true],
    ]);
    expect([r.netto, r.stimmt]).toEqual([2264.23, true]);
  });

  it('Mastel: Stückzahl im Text, Preis je kg aus dem Betrag erkannt, Gültigkeit in Tagen', () => {
    const r = angebotLesen(DATEN.mastel);
    expect(r.kopf).toMatchObject({ angebotsnr: '11212408', datum: '2026-11-17', gueltigBis: '2026-11-20' });
    expect(r.positionen.map(kurz)).toEqual([
      { pos: '1', option: false, werkstoff: 'EN AW-6082', zustand: 'T651', form: 'Platte', masse: [15, 20, 3020], stueck: 18, kg: 45.66, preis: 12.5, preisJe: 'kg', betrag: 570.78 },
    ]);
    expect(r.positionen[0]).toMatchObject({ artikelnr: '12-0150', liefertermin: '2 Arbeitstage u.V.' });
    expect(r.positionen[0].text).toMatch(/Aus der Platte gesägt/);
    expect([r.netto, r.stimmt]).toEqual([570.78, true]);
  });

  it('Smiths: englisch, Dezimalpunkt, Preis „per PC“, Fracht', () => {
    const r = angebotLesen(DATEN.smiths);
    expect(r.kopf).toMatchObject({ angebotsnr: '9960007019', datum: '2026-11-16' });
    expect(r.positionen.map(kurz)).toEqual([
      { pos: '', option: false, werkstoff: 'EN AW-6082', zustand: 'T651', form: 'Platte', masse: [20, 90, 1000], stueck: 3, kg: null, preis: 73, preisJe: 'Stk', betrag: 219 },
    ]);
    expect(r.nebenkosten).toEqual([{ text: 'Carrier charge', betrag: 35 }]);
  });

  it('angelernte Spalten und Preiseinheit des Lieferanten gehen vor', () => {
    const r = angebotLesen(DATEN.mastel);
    const vorlage = { spalten: spaltenVorlage(r.spalten.map((s) => (s.rolle === 'einheit' ? { ...s, rolle: '' } : s))), preisJe: 'Stk' };
    const p = angebotLesen(DATEN.mastel, vorlage).positionen[0];
    expect([p.preisJe, p.preis]).toEqual(['Stk', 12.5]);
  });
});

describe('Bausteine', () => {
  it('Maße, Werkstoff, Zustand', () => {
    expect(masseAus('Platte 20x50x1500 mm\nDickentoleranz: +/- 0,10 mm').masse).toEqual([20, 50, 1500]);
    expect(masseAus('Rund 110 mm a\' 601 mm RL').masse).toEqual([110, 601]);
    expect(masseAus('Ø40 mm').masse).toEqual([40]);
    expect(werkstoffAus('ALPLAN®7075 T651')).toBe('EN AW-7075');
    expect(werkstoffAus('Rundstahl 1.4301 blank')).toBe('1.4301');
    expect(zustandAus('AlMgSi1/EN AW-6082 T6/ T6511')).toBe('T6');
  });
});

describe('Zuordnung zur Anfrage und Preise', () => {
  const anfrage = {
    positionen: [
      { key: 'mat:1', teil: { name: 'EN AW-6082 T651 · Platte 15 mm', material: 'EN AW-6082 T651' }, abmessung: 'Platte 15 mm · für 18 × 20 × 3020 mm', einheit: 'Stk', mengen: [18], anforderungen: 'Zeugnis 3.1' },
      { key: 'mat:2', teil: { name: 'EN AW-7075 T651 · Platte 20 mm', material: 'EN AW-7075 T651' }, abmessung: 'Platte 20 mm', einheit: 'kg', mengen: [60, 100] },
    ],
  };
  it('ordnet nach Werkstoff und Maßen zu, Optionen bleiben offen', () => {
    const almet = angebotLesen(DATEN.almet).positionen;
    expect(zuordnen(almet, anfrage)).toEqual(['mat:1', '']);
    const wm = angebotLesen(DATEN.weinmann).positionen;
    expect(zuordnen(wm.slice(0, 1), anfrage)).toEqual(['mat:2']);
  });
  it('rechnet den Preis je angefragter Einheit und meldet abweichende Mengen', () => {
    const almet = angebotLesen(DATEN.almet).positionen;
    const r = preiseFuer(anfrage, almet, ['mat:1', '']);
    expect(r.preise).toEqual([{ posKey: 'mat:1', menge: 18, proStk: 24.1689, einmalig: 0 }]);
    expect(r.je['mat:1']).toMatchObject({ betrag: 435.04, angeboten: 18, abweichung: false });
    const wm = angebotLesen(DATEN.weinmann).positionen.slice(0, 1);
    const k = preiseFuer(anfrage, wm, ['mat:2']);
    expect(k.preise.map((p) => [p.menge, p.proStk])).toEqual([[60, 8.3], [100, 8.3]]);
    expect(k.je['mat:2']).toMatchObject({ angeboten: 68.5, abweichung: true });
  });
  it('gleicht Werkstoff, Form, Maße und Anforderungen ab', () => {
    const [o] = angebotLesen(DATEN.mastel).positionen;
    const a = Object.fromEntries(abgleich(o, anfrage.positionen[0]).map((x) => [x.feld, x.ok]));
    expect(a).toEqual({ Werkstoff: true, Zustand: true, Form: true, 'Maße': true, Anforderungen: null });
    const b = Object.fromEntries(abgleich(o, anfrage.positionen[1]).map((x) => [x.feld, x.ok]));
    expect(b.Werkstoff).toBe(false);
  });
});

describe('Angebote vom 25.11.2026 (dieselbe Anfrage an vier Lieferanten)', () => {
  const kurz2 = (p) => ({ pos: p.pos, werkstoff: p.werkstoff, form: p.form, masse: p.masse, stueck: p.stueck, kg: p.kg, preis: p.preis, preisJe: p.preisJe, betrag: p.betrag });
  it('Bikar: ohne Mengenspalte, Position über der Betragszeile, Nebenkosten neben- und untereinander, Endbetrag rechts', () => {
    const r = angebotLesen(DATEN.bikar);
    expect(r.kopf.angebotsnr).toBe('3133031');
    expect(r.positionen.map(kurz2)).toEqual([
      { pos: '1.1', werkstoff: 'EN AW-7075', form: 'Platte', masse: [20, 50, 3020], stueck: 8, kg: 67.65, preis: 8.45, preisJe: 'kg', betrag: 571.9 },
      { pos: '2.1', werkstoff: 'EN AW-7075', form: 'Platte', masse: [30, 75, 3020], stueck: 5, kg: 95.13, preis: 8.45, preisJe: 'kg', betrag: 804.02 },
      { pos: '3.1', werkstoff: 'EN AW-5083', form: 'Platte', masse: [8, 92, 225], stueck: 3, kg: 1.32, preis: 12.65, preisJe: 'Stk', betrag: 37.95 },
      { pos: '4.1', werkstoff: 'EN AW-6082', form: 'Flach', masse: [20, 90, 3000], stueck: 1, kg: 14.58, preis: 4.85, preisJe: 'kg', betrag: 70.71 },
      { pos: '5.1', werkstoff: 'EN AW-6082', form: 'Flach', masse: [15, 20, 3000], stueck: 18, kg: 43.74, preis: 4.85, preisJe: 'kg', betrag: 212.14 },
    ]);
    expect(r.nebenkosten.map((n) => [n.text, n.betrag])).toEqual([['Frachtkostenanteil', 49.5], ['Verpackungskostenanteil', 28.5], ['Maut', 20.41], ['Dieselfloater', 8], ['Handlingskosten', 15]]);
    expect([r.netto, r.stimmt]).toEqual([1818.13, true]);
  });
  it('AMCO: „Nr.“ unter „Angebot“, Maße ohne mm, Termin-Spalte, Nebenkosten als kleine Tabelle, Kopfnummer ist kein Betrag', () => {
    const r = angebotLesen(DATEN.amco);
    expect(r.kopf.angebotsnr).toBe('VAN00561434');
    expect(r.positionen.map((p) => [p.pos, p.masse.join('x'), p.stueck, p.preis, p.preisJe, p.betrag, p.lieferdatum])).toEqual([
      ['10', '20x50x3020', 8, 79.5, 'Stk', 636, '2026-12-07'], ['20', '30x75x3020', 5, 175, 'Stk', 875, '2026-12-07'],
      ['30', '8x92x225', 3, 18.5, 'Stk', 55.5, '2026-12-07'], ['40', '20x90x3020', 1, 107, 'Stk', 107, '2026-12-07'],
      ['50', '15x20x3020', 18, 18.5, 'Stk', 333, '2026-12-07'],
    ]);
    expect(r.nebenkosten.map((n) => [n.text, n.betrag])).toEqual([['Frachtkostenanteil', 56.99], ['Maut', 19.99], ['Verpackung', 23.99], ['Werkzeugnis', 25]]);
    expect([r.netto, r.stimmt]).toEqual([2132.47, true]);
  });
  it('Weinmann: „Seite 2/2“ ist kein Betrag, Verpackung zwischen den Positionen', () => {
    const r = angebotLesen(DATEN.weinmann2);
    expect(r.positionen.map((p) => p.pos)).toEqual(['10', '20', '30', '40', '50']);
    expect([r.netto, r.stimmt]).toEqual([1764.75, true]);
  });
  it('Mastel: unverändert sauber', () => {
    const r = angebotLesen(DATEN.mastel2);
    expect(r.positionen).toHaveLength(5);
    expect([r.netto, r.stimmt]).toEqual([2366.9, true]);
  });
  it('fasst die vier Angebote je Abmessung zusammen und zeigt, was abweicht (Werkstoff, Flach statt Platte, Länge)', () => {
    const a = ['weinmann2', 'bikar', 'amco', 'mastel2'].map((k) => angebotLesen(DATEN[k]));
    const { gruppen, zuordnung } = positionsGruppen(a);
    expect(zuordnung).toEqual([[0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4]]);
    expect(gruppen).toHaveLength(5);
    // Pos. 3: drei bieten Gussplatte EN AW-5083, Weinmann EN AW-7075
    expect(gruppen[2]).toMatchObject({ werkstoff: 'EN AW-5083', masse: [8, 92, 225] });
    expect(abweichungen(a[0].positionen[2], gruppen[2]).map((x) => x.feld)).toEqual(['Werkstoff']);
    expect(abweichungen(a[1].positionen[2], gruppen[2])).toEqual([]);
    // Pos. 4: Flachstange 3000 mm gegen Platte 3020 mm
    const flach = abweichungen(a[1].positionen[3], { ...gruppen[3], form: 'Platte', masse: [20, 90, 3020] });
    expect(flach.map((x) => x.feld)).toEqual(['Form', 'Maße']);
  });
  it('Herstellung, Oberfläche und Toleranzen je Position', () => {
    const [w, b, am, m] = ['weinmann2', 'bikar', 'amco', 'mastel2'].map((k) => angebotLesen(DATEN[k]).positionen);
    expect(w[2].merkmale).toEqual(['gewalzt', 'beidseitig plangefräst', 'foliert']);
    expect(w[2].toleranzen).toEqual(['Dickentoleranz: +/- 0,10 mm']);
    expect(w[3].merkmale).toEqual(['gepresst']);
    expect(b[0].merkmale).toEqual(['gewalzt']);
    expect(b[0].toleranzen).toEqual(['Tol./Dicke: +1,6 / -0,0 mm']);
    expect(b[2].merkmale).toEqual(['Gussplatte', 'plangefräst', 'foliert']);
    expect(am[2].merkmale).toEqual(['Gussplatte', 'plangefräst', 'foliert']);
    expect(am[0].merkmale).toEqual(['gewalzt']);
    expect(m[2].merkmale).toContain('Gussplatte');
    expect(merkmaleAus('Gussplatte beids.\nplangefräst 8x92x225')).toEqual(['Gussplatte', 'beidseitig plangefräst']);
    expect(toleranzenAus('Längentoleranz:\nDickentoleranz: +/- 0,10 mm')).toEqual(['Dickentoleranz: +/- 0,10 mm']);
  });
  it('Beträge und gleiche Ware', () => {
    expect([betragAus('ca. 571,90 €'), betragAus('1.234,56'), betragAus('(945,00)'), betragAus('1,234.50'), betragAus('Seite 2/2'), betragAus('Nr. VAN00561434')]).toEqual([571.9, 1234.56, 945, 1234.5, null, null]);
    expect(gleicheWare({ werkstoff: 'EN AW-6082', form: 'Flach', masse: [20, 90, 3000] }, { werkstoff: 'EN AW-6082 T651', form: 'Platte', masse: [20, 90, 3020] })).toBe(true);
    expect(gleicheWare({ werkstoff: 'EN AW-6082', form: 'Flach', masse: [20, 90, 3000] }, { werkstoff: 'EN AW-6082', form: 'Rund', masse: [20, 90, 3000] })).toBe(false);
    expect(gleicheWare({ werkstoff: 'EN AW-6082', form: 'Platte', masse: [20, 90, 1000] }, { werkstoff: 'EN AW-6082', form: 'Platte', masse: [20, 90, 3020] })).toBe(false);
  });
});

describe('Angebote ohne eigene Anfrage vergleichen', () => {
  const alle = ['almet', 'mastel', 'smiths', 'weinmann'].map((k) => angebotLesen(DATEN[k]));
  it('erkennt den Lieferanten aus den Stammdaten oder schlägt einen Namen vor', () => {
    const l = [{ id: 'Almet GmbH', name: 'Almet GmbH', email: '' }, { id: 'Mastel', name: 'Mastel Metall GmbH', email: 'info@mastel.de' }, { id: 'Hohenstein', name: 'Hohenstein GmbH' }];
    expect(lieferantErkennen(alle[0].text, l)).toBe('Almet GmbH');
    expect(lieferantErkennen(alle[1].text, l)).toBe('Mastel');
    expect(lieferantErkennen(alle[2].text, l.slice(0, 2))).toBe('');
    expect(alle.map((r) => lieferantVorschlag(r.text, ['Hohenstein']))).toEqual(['ALMET GmbH', 'Mastel Metall GmbH', 'SMITHS HIGH PERFORMANCE', 'Weinmann Aach AG']);
  });
  it('fasst gleiche Positionen verschiedener Lieferanten zusammen', () => {
    const { gruppen, zuordnung } = positionsGruppen(alle);
    expect(zuordnung[0]).toEqual([0, -1]); // Almet: Option bleibt außen vor
    expect(zuordnung[1]).toEqual([0]); // Mastel: dieselbe Platte wie Almet
    expect(zuordnung[2]).toEqual([1]);
    expect(zuordnung[3]).toHaveLength(8);
    expect(gruppen).toHaveLength(10);
    expect(gruppen[0]).toMatchObject({ werkstoff: 'EN AW-6082', zustand: 'T651', form: 'Platte', einheit: 'Stk', menge: 18, material: 'EN AW-6082 T651' });
    expect(gruppen[0].name).toBe('EN AW-6082 T651 · Platte 15 × 20 × 3020 mm');
    expect(gruppen[1].name).toBe('EN AW-6082 T651 · Platte 20 × 90 × 1000 mm');
    expect(gruppen.find((g) => g.form === 'Rund').abmessungText).toBe('Rund Ø110 × 601 mm');
  });
});
