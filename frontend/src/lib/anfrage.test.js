import { describe, it, expect } from 'vitest';
import { mengenFuer, fremdPositionen, preisFuerMenge, gehoertZu, zusammenfassung, zusammenfassungText, mailText, istFrei, freieZeile, materialAbmessung } from './anfrage.js';

describe('mengenFuer', () => {
  it('Staffelangebot fragt alle Staffeln an', () => {
    expect(mengenFuer({ menge: 10, staffel: { aktiv: true, stufen: [{ menge: 100 }, { menge: 5 }, { menge: 25 }, { menge: 5 }] } })).toEqual([5, 25, 100]);
  });
  it('Einzelangebot fragt die Stückzahl an', () => {
    expect(mengenFuer({ menge: 40, staffel: { aktiv: false, stufen: [] } })).toEqual([40]);
  });
});

describe('fremdPositionen', () => {
  const teile = [
    { id: 't1', name: 'A', menge: 10, staffel: { aktiv: false, stufen: [] }, arbeitsgaenge: [{ id: 'a1', typ: 'intern' }, { id: 'a2', typ: 'fremd', name: 'Härten' }] },
    { id: 't2', name: 'B', menge: 5, staffel: { aktiv: true, stufen: [{ menge: 5 }, { menge: 20 }] }, arbeitsgaenge: [{ id: 'a3', typ: 'fremd', name: 'Eloxieren' }, { id: 'a4', typ: 'fremd', name: 'Schleifen' }] },
    { id: 't3', name: 'C', menge: 1, staffel: { aktiv: false, stufen: [] }, arbeitsgaenge: [] },
  ];
  it('findet alle Fremdvergaben über alle Bauteile', () => {
    const p = fremdPositionen(teile);
    expect(p.map((x) => x.key)).toEqual(['t1:a2', 't2:a3', 't2:a4']);
  });
  it('bringt die Mengen des Bauteils mit', () => {
    const p = fremdPositionen(teile);
    expect(p[0].mengen).toEqual([10]);
    expect(p[1].mengen).toEqual([5, 20]);
  });
  it('Bauteile ohne Fremdvergabe tauchen nicht auf', () => {
    expect(fremdPositionen(teile).some((x) => x.teilId === 't3')).toBe(false);
  });
});

describe('preisFuerMenge', () => {
  const antwort = { preise: [{ posKey: 'p1', menge: 100, proStk: 1.0, einmalig: 0 }, { posKey: 'p1', menge: 10, proStk: 2.5, einmalig: 30 }, { posKey: 'p1', menge: 50, proStk: 1.6, einmalig: 30 }, { posKey: 'p2', menge: 10, proStk: 9, einmalig: 0 }] };
  it('gleiche Menge', () => expect(preisFuerMenge(antwort, 50, 'p1').proStk).toBe(1.6));
  it('dazwischen gilt die nächstkleinere Staffel', () => expect(preisFuerMenge(antwort, 70, 'p1').menge).toBe(50));
  it('unter der kleinsten Staffel gilt die kleinste', () => expect(preisFuerMenge(antwort, 3, 'p1').menge).toBe(10));
  it('Preise anderer Positionen werden nicht verwechselt', () => expect(preisFuerMenge(antwort, 10, 'p2').proStk).toBe(9));
  it('ohne Positionsangabe zählen alle Preise', () => expect(preisFuerMenge({ preise: [{ menge: 10, proStk: 3 }] }, 10).proStk).toBe(3));
  it('ohne Preise null', () => expect(preisFuerMenge({ preise: [] }, 10, 'p1')).toBeNull());
  it('ohne Antwort null', () => expect(preisFuerMenge(null, 10)).toBeNull());
});


describe('Zuordnung zum Angebot', () => {
  it('gehört zum Angebot mit gleicher Nummer', () => expect(gehoertZu({ angebotId: 'ANG-2026-0002' }, { angebotId: 'ANG-2026-0002' })).toBe(true));
  it('andere Angebote passen nicht', () => expect(gehoertZu({ angebotId: 'ANG-2026-0001' }, { angebotId: 'ANG-2026-0002' })).toBe(false));
  it('ohne Angebotsnummer passt nichts', () => expect(gehoertZu({ angebotId: '' }, { angebotId: '' })).toBe(false));
  it('noch nicht gespeichertes Angebot (null) passt auf nichts', () => expect(gehoertZu({ angebotId: 'ANG-2026-0001' }, { angebotId: null })).toBe(false));
});

describe('Zusammenfassung', () => {
  const liste = [{ status: 'Gesendet' }, { status: 'Gesendet' }, { status: 'Angebot erhalten' }];
  it('zählt je Status', () => expect(zusammenfassung(liste)).toMatchObject({ gesamt: 3, Gesendet: 2, 'Angebot erhalten': 1, Abgesagt: 0 }));
  it('Text nennt nur vorhandene Status', () => expect(zusammenfassungText(zusammenfassung(liste))).toBe('2 gesendet, 1 Angebot erhalten'));
  it('leere Liste ergibt leeren Text', () => expect(zusammenfassungText(zusammenfassung([]))).toBe(''));
});

describe('mailText', () => {
  const teil = { name: 'Flansch DN50', teilenummer: 'F31.683.122', zeichnungsnr: 'Z-4711-B', material: '1.4404' };
  const einzel = { id: 'LA-2026-0003', notiz: 'Eilig', positionen: [{ key: 'k', agName: 'Oberflächenbehandlung', mengen: [10, 50], teil }] };
  const mehrere = {
    id: 'LA-2026-0004', notiz: '',
    positionen: [
      { key: 'k1', agName: 'Eloxieren', mengen: [10], teil },
      { key: 'k2', agName: 'Härten', mengen: [5, 25], teil: { name: 'Welle', teilenummer: 'W-1' } },
    ],
  };
  it('Anfragenummer steht im Betreff', () => expect(mailText(einzel).betreff).toContain('LA-2026-0003'));
  it('Anfragenummer steht auch im Text', () => expect(mailText(einzel).text).toContain('unsere Anfragenummer LA-2026-0003'));
  it('Einzelanfrage nennt Bauteil, Mengen und Hinweis', () => {
    const t = mailText(einzel).text;
    expect(t).toContain('Bauteil: Flansch DN50 (Teilenummer F31.683.122)');
    expect(t).toContain('Angefragte Stückzahlen: 10, 50');
    expect(t).toContain('Hinweis: Eilig');
  });
  it('Sammelanfrage listet alle Positionen nummeriert', () => {
    const m = mailText(mehrere);
    expect(m.text).toContain('1. Eloxieren');
    expect(m.text).toContain('2. Härten');
    expect(m.text).toContain('Bauteil: Welle (Teilenummer W-1)');
    expect(m.text).toContain('Angefragte Stückzahlen: 5, 25');
    expect(m.betreff).toBe('Anfrage LA-2026-0004: Fremdvergabe, 2 Positionen');
  });
  it('lässt leere Angaben weg', () => {
    const t = mailText(mehrere).text;
    expect(t).not.toContain('Hinweis');
    expect(t).not.toMatch(/Zeichnung: undefined/);
  });
});

describe('freie Anfrage (Material)', () => {
  const a = {
    id: 'LA-2026-0009', art: 'Material', angebotId: '', notiz: 'mit Zeugnis 3.1',
    positionen: [
      { key: 'frei:1', teil: { name: 'Rundstahl', material: '42CrMo4' }, abmessung: 'Ø 50 x 3000 mm', einheit: 'Stangen', mengen: [2, 5] },
      { key: 'frei:2', teil: { name: 'Flachstahl', material: '' }, abmessung: '', einheit: 'm', mengen: [12] },
    ],
  };
  it('erkennt die freie Anfrage', () => {
    expect(istFrei(a)).toBe(true);
    expect(istFrei({ angebotId: 'ANG-1', positionen: [{ key: 't1:a1' }] })).toBe(false);
  });
  it('nennt Werkstoff, Abmessung und Mengen mit Einheit', () => {
    const t = mailText(a).text;
    expect(t).toContain('Angebot für folgendes Material:');
    expect(t).toContain('1. Rundstahl');
    expect(t).toContain('   Werkstoff: 42CrMo4');
    expect(t).toContain('   Abmessung: Ø 50 x 3000 mm');
    expect(t).toContain('   Menge: 2 Stangen / 5 Stangen');
    expect(t).toContain('   Menge: 12 m');
    expect(t).toContain('Hinweis: mit Zeugnis 3.1');
    expect(t).toContain('unsere Anfragenummer LA-2026-0009');
    expect(t).not.toContain('Zeichnungen');
  });
  it('Betreff mit Nummer', () => {
    expect(mailText(a).betreff).toBe('Anfrage LA-2026-0009: Material, 2 Positionen');
    expect(mailText({ ...a, positionen: [a.positionen[0]] }).betreff).toBe('Anfrage LA-2026-0009: Rundstahl 42CrMo4');
  });
  it('Kurzzeile', () => expect(freieZeile(a.positionen[0])).toBe('Rundstahl · 42CrMo4 · Ø 50 x 3000 mm'));
});

describe('materialAbmessung', () => {
  const rund = { form: 'Rund', abmessung: 'Ø20', ausfuehrung: 'gezogen h9' };
  it('Stange mit Länge', () => expect(materialAbmessung(rund, 'Stangen', 3000)).toBe('Rund Ø20 · gezogen h9 · Stangenlänge 3000 mm'));
  it('Stange ohne Länge: Lagerlänge', () => expect(materialAbmessung(rund, 'Stangen', 0)).toBe('Rund Ø20 · gezogen h9 · Stangenlänge nach Ihrem Lager'));
  it('Zuschnitt ohne Ausführung', () => expect(materialAbmessung({ form: 'Rund', abmessung: 'Ø40', ausfuehrung: '' }, 'Zuschnitte', 120.4)).toBe('Rund Ø40 · Zuschnitt 120 mm'));
  it('Platte mit Länge × Breite', () => expect(materialAbmessung({ form: 'Platte', abmessung: '20 mm', ausfuehrung: 'gewalzt' }, 'Zuschnitte', 500, 300)).toBe('Platte 20 mm · gewalzt · Zuschnitt 500 × 300 mm'));
  it('ganze Platten', () => expect(materialAbmessung({ form: 'Platte', abmessung: '20 mm' }, 'Platten', 2000, 1000)).toBe('Platte 20 mm · Plattenmaß 2000 × 1000 mm'));
  it('ohne Rohmaterial leer', () => expect(materialAbmessung(null, 'Stangen', 1)).toBe(''));
});
