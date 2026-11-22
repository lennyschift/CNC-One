import { describe, it, expect } from 'vitest';
import {
  querschnitt, kgJeMeter, kgJeQm, masText, artikelText, chargePruefen, reichtFuer, ausfuehrungenFuer, formenVon, rohAusAbmessung,
  abmessungVorschlag, anforderungenMit, zeugnisMax, materialBedarf,
} from './werkstoffbaum.js';
import { rohVolumen, rohText } from './rohmaterial.js';

const abm = (form, m1, m2 = 0) => ({ id: `${form}${m1}x${m2}`, form, m1, m2, text: masText(form, m1, m2) });
const BAUM = {
  ausfuehrungen: [{ id: 'a1', form: 'Rund', name: 'gezogen h9', iso: [] }, { id: 'a2', form: 'Rund', name: 'gepresst', iso: ['N'] }],
  abmessungen: [abm('Rund', 40), abm('Rund', 45), abm('Rund', 50), abm('Vierkant', 50), abm('Flach', 50, 20), abm('Flach', 60, 30), abm('Platte', 20), abm('Platte', 25)],
};

describe('Rohmaterial-Baum', () => {
  it('rechnet Querschnitt und Gewicht', () => {
    expect(querschnitt('Vierkant', 20)).toBe(400);
    expect(querschnitt('Flach', 50, 20)).toBe(1000);
    expect(kgJeMeter('Rund', 40, 0, 2.81)).toBeCloseTo(3.531, 3);
    expect(querschnitt('Rohr', 40, 4)).toBeCloseTo((Math.PI / 4) * (1600 - 1024), 6);
    expect(kgJeQm(20, 2.7)).toBeCloseTo(54, 6);
  });

  it('schreibt Maße und Artikel', () => {
    expect(masText('Rohr', 40, 4.5)).toBe('Ø40 × 4,5');
    expect(masText('Platte', 20)).toBe('20 mm');
    expect(artikelText('EN AW-7075', { zustand: 'T7351', form: 'Rund', abmessung: 'Ø40', ausfuehrung: 'gezogen h11' })).toBe('EN AW-7075 T7351 · Rund Ø40 · gezogen h11');
    expect(artikelText('C45', {})).toBe('C45');
  });

  it('filtert Formen und Ausführungen', () => {
    expect(formenVon({ formen: [] })).toHaveLength(6);
    expect(formenVon({ formen: ['Platte', 'Rund'] })).toEqual(['Rund', 'Platte']);
    expect(ausfuehrungenFuer(BAUM, 'Rund', 'P').map((a) => a.name)).toEqual(['gezogen h9']);
    expect(ausfuehrungenFuer(BAUM, 'Rund', 'N').map((a) => a.name)).toEqual(['gezogen h9', 'gepresst']);
  });

  it('übernimmt die Abmessung ins Rohteil und rechnet das Volumen mit Sägezugabe', () => {
    const r = rohAusAbmessung({ laenge: 97, saege: 3 }, abm('Vierkant', 20));
    expect([r.breite, r.hoehe, r.form, r.abmessung]).toEqual([20, 20, 'Vierkant', '□20']);
    expect(rohVolumen(r)).toBe(400 * 100);
    const p = rohAusAbmessung({ laenge: 200, breite: 100, saege: 0 }, abm('Platte', 10));
    expect(rohVolumen(p)).toBe(10 * 100 * 200);
    expect(rohText(p)).toBe('Platte 10 × 100 × 200');
    const rohr = rohAusAbmessung({ laenge: 50 }, abm('Rohr', 40, 4));
    expect(rohr.innen).toBe(32);
  });

  it('schlägt die kleinste passende Abmessung aus dem 3D-Rohteil vor', () => {
    expect(abmessungVorschlag(BAUM, { formen: [] }, { form: 'Rund', durchmesser: 42.3, laenge: 81.2 })).toMatchObject({ abm: { form: 'Rund', m1: 45 }, laenge: 82 });
    // Quader 120 × 48 × 18 aus Stangen: Flach 50×20 ist kleiner als Vierkant 50; mit Platte erlaubt: Platte 20 (20 × 48 Querschnitt)
    expect(abmessungVorschlag(BAUM, { formen: ['Rund', 'Vierkant', 'Flach'] }, { x: 120, y: 48, z: 18 }).abm.text).toBe('50 × 20');
    expect(abmessungVorschlag(BAUM, { formen: [] }, { x: 120, y: 48, z: 18 }).abm.text).toBe('20 mm');
    // nur Platte erlaubt: Dicke 20, Zuschnitt 120 × 48
    expect(abmessungVorschlag(BAUM, { formen: ['Platte'] }, { x: 120, y: 48, z: 18 })).toMatchObject({ abm: { m1: 20 }, laenge: 120, breite: 48 });
    expect(abmessungVorschlag(BAUM, { formen: ['Rund'] }, { form: 'Rund', durchmesser: 80, laenge: 10 })).toBeNull();
  });

  it('prüft Chargen und Anforderungen (3.2 erfüllt 3.1, Kunde setzt Mindestmaß)', () => {
    expect(zeugnisMax('3.1', '2.2')).toBe('3.1');
    expect(anforderungenMit({ zeugnis: '2.2', pruefungen: ['A'] }, { zeugnis: '3.1', pruefungen: ['B'] })).toEqual({ zeugnis: '3.1', pruefungen: ['B', 'A'] });
    expect(chargePruefen({ zeugnis: '3.2', pruefungen: [] }, { zeugnis: '3.1', pruefungen: [] }).ok).toBe(true);
    expect(chargePruefen({ zeugnis: '2.2', pruefungen: ['RoHS/REACH'] }, { zeugnis: '3.1', pruefungen: ['RoHS/REACH', 'Ultraschallgeprüft'] }).fehlt).toEqual(['Zeugnis 3.1', 'Ultraschallgeprüft']);
    expect(reichtFuer({ form: 'Rund', laenge: 3000, stueck: 2 }, { laenge: 97, saege: 3 })).toBe(60);
    expect(reichtFuer({ form: 'Platte', breite: 1000, laenge: 1400 }, { breite: 100, laenge: 200, saege: 0 })).toBe(70);
  });
});

describe('Materialbedarf eines Angebots', () => {
  const roh = (laenge, extra = {}) => ({ form: 'Rund', abmessungId: 'r40', abmessung: 'Ø40', zustand: 'T6', ausfuehrung: 'gezogen h9', laenge, saege: 3, ...extra });
  const teile = [
    { id: 't1', name: 'Welle', material: 'EN AW-6082', menge: 10, gewichtKg: 0.3, roh: roh(97, { anforderungen: { zeugnis: '3.1', pruefungen: [] } }), staffel: { aktiv: false } },
    { id: 't2', name: 'Bolzen', material: 'EN AW-6082', menge: 5, gewichtKg: 0.2, roh: roh(47, { anforderungen: { zeugnis: '2.2', pruefungen: ['RoHS/REACH'] } }), staffel: { aktiv: true, stufen: [{ menge: 5 }, { menge: 50 }] } },
    { id: 't3', name: 'Ohne Abmessung', material: 'C45', menge: 1, roh: { form: 'Rund', laenge: 10 } },
  ];
  it('fasst gleiche Artikel zusammen und rechnet Bedarf und Anforderungen', () => {
    const { liste, unvollstaendig } = materialBedarf(teile, []);
    expect(unvollstaendig.map((t) => t.id)).toEqual(['t3']);
    expect(liste).toHaveLength(1);
    const g = liste[0];
    expect(g.bedarf).toBe(100 * 10 + 50 * 5);
    expect(g.bedarfMax).toBe(100 * 10 + 50 * 50);
    expect(g.anforderungen).toEqual({ zeugnis: '3.1', pruefungen: ['RoHS/REACH'] });
    expect(g.status).toBe('bestellen');
  });
  it('gleicht mit dem Lager ab (nur Chargen, die die Anforderungen erfüllen)', () => {
    const c = (id, laenge, zeugnis, pruefungen) => ({ id, werkstoff: 'EN AW-6082', zustand: 'T6', abmessung: 'r40', form: 'Rund', laenge, stueck: 1, zeugnis, pruefungen });
    expect(materialBedarf(teile, [c('a', 3000, '3.1', ['RoHS/REACH'])]).liste[0]).toMatchObject({ status: 'lager', vorrat: 3000, fehlt: 0 });
    expect(materialBedarf(teile, [c('a', 1000, '3.1', ['RoHS/REACH'])]).liste[0]).toMatchObject({ status: 'teilweise', fehlt: 250 });
    expect(materialBedarf(teile, [c('a', 3000, '2.2', [])]).liste[0]).toMatchObject({ status: 'bestellen', ohneNachweis: 1 });
  });
});
