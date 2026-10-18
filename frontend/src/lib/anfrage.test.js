import { describe, it, expect } from 'vitest';
import { nummer, mengenFuer, fremdPositionen, preisFuerMenge, normalisiereAnfrage, gehoertZu, zusammenfassung, zusammenfassungText, mailText } from './anfrage.js';

describe('Nummernkreis', () => {
  it('LA-Jahr-laufende Nummer', () => expect(nummer(7, 2026)).toBe('LA-2026-0007'));
});

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

describe('alte Anfragen', () => {
  it('Anfrage mit einem Bauteil wird zur Anfrage mit einer Position', () => {
    const alt = { id: 'LA-2026-0001', teil: { name: 'X' }, agId: 'ag1', agName: 'Härten', mengen: [5, 10], antwort: { preise: [{ menge: 5, proStk: 2 }] } };
    const n = normalisiereAnfrage(alt);
    expect(n.positionen).toHaveLength(1);
    expect(n.positionen[0]).toMatchObject({ agId: 'ag1', agName: 'Härten', mengen: [5, 10], teil: { name: 'X' } });
    expect(n.antwort.preise[0].posKey).toBe(n.positionen[0].key);
    expect(n).not.toHaveProperty('teil');
  });
  it('neue Anfragen behalten ihre Positionen', () => {
    const neu = { id: 'x', positionen: [{ key: 'k' }] };
    expect(normalisiereAnfrage(neu).positionen).toEqual([{ key: 'k' }]);
  });
  it('fehlende Bezüge zum Angebot werden leer ergänzt, vorhandene bleiben', () => {
    expect(normalisiereAnfrage({ positionen: [] })).toMatchObject({ entwurfId: '', angebotId: '', kundeName: '' });
    expect(normalisiereAnfrage({ positionen: [], angebotId: 'ANG-1' }).angebotId).toBe('ANG-1');
  });
});

describe('Zuordnung zum Angebot', () => {
  const a = { entwurfId: 'e1', angebotId: '' };
  const b = { entwurfId: 'e1', angebotId: 'ANG-2026-0001' };
  const c = { entwurfId: 'e2', angebotId: 'ANG-2026-0002' };
  it('Entwurf wird über die entwurfId erkannt', () => expect(gehoertZu(a, { entwurfId: 'e1', angebotId: null })).toBe(true));
  it('gespeichertes Angebot wird über die Angebotsnummer erkannt', () => expect(gehoertZu(c, { entwurfId: '', angebotId: 'ANG-2026-0002' })).toBe(true));
  it('Anfrage vor und nach dem Speichern gehört zum selben Angebot', () => {
    const ziel = { entwurfId: 'e1', angebotId: 'ANG-2026-0001' };
    expect(gehoertZu(a, ziel)).toBe(true);
    expect(gehoertZu(b, ziel)).toBe(true);
    expect(gehoertZu(c, ziel)).toBe(false);
  });
  it('leere Ids passen auf nichts', () => expect(gehoertZu({ entwurfId: '', angebotId: '' }, { entwurfId: '', angebotId: '' })).toBe(false));
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
