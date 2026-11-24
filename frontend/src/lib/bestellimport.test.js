import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import { bestellungLesen } from './bestellung.js';
import { bestellungFinden, dateienZuordnen, nummernVon, bekanntheit } from './bestellimport.js';

const ECHT = JSON.parse(fs.readFileSync(new URL('./testdaten/bestellungen.json', import.meta.url), 'utf8'));

describe('Bestellung mit Zeichnungen und Modellen einlesen', () => {
  const r = bestellungLesen(ECHT.eiberger);
  it('findet die Bestellung unter den PDFs', () => {
    const zeichnung = { positionen: [], kopf: {} };
    expect(bestellungFinden([{ name: '10241355_A.pdf', r: zeichnung }, { name: 'Bestellung Nr. 20260050.pdf', r }, { name: 'kaputt.pdf', r: null }])).toBe(1);
    expect(bestellungFinden([{ name: 'a.pdf', r: zeichnung }])).toBe(-1);
  });
  it('ordnet Zeichnungen und Modelle über Artikel- oder Zeichnungsnummer im Namen zu', () => {
    const pos = r.positionen;
    const namen = ['10241355_A.pdf', '10241355_A.step', '215810 Schnittstellenabdeckung.stp', 'ZZ-Fremd.pdf', 'Spannplatte_10242038-A.STEP'];
    expect(dateienZuordnen(pos, namen)).toEqual([0, 0, 1, -1, 7]);
    // die Nummern eines bekannten Bauteils zählen mit
    expect(nummernVon({ teilenummer: '216011', zeichnungsnr: '', bauteil: { teilenummer: '216011', zeichnungsnr: 'Z-77/1' } })).toEqual(['216011', 'z771']);
  });
  it('sagt, was CNC One über die Position weiß', () => {
    expect(bekanntheit({ letzterAuftrag: { auftrag: 'AB-2026-0003', menge: 10, datum: '' }, quellen: [] }).art).toBe('auftrag');
    expect(bekanntheit({ quellen: [{ angebot: 'ANG-2026-0001' }], bauteil: { id: 'BT-1' } }).art).toBe('angebot');
    expect(bekanntheit({ quellen: [], bauteil: { id: 'BT-1', frueherGefertigt: true, frueherNotiz: '2022' } })).toEqual({ art: 'frueher', text: 'Schon gefertigt (vor CNC One): 2022' });
    expect(bekanntheit({ quellen: [], bauteil: null }).art).toBe('neu');
  });
});
