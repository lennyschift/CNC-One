// Bestellung des Kunden mit allen Zeichnungen und Modellen auf einmal einlesen (Workbench „Bestellung einlesen“).
// Reine Funktionen, getestet in bestellimport.test.js: welche PDF die Bestellung ist und welche Datei zu welcher Position gehört.

const schluessel = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
const basis = (name) => (/^(.*?)(\.[^.]+)?$/.exec(String(name ?? '').split(/[\\/]/).pop())?.[1] ?? '');

// Welche der gelesenen PDFs ist die Bestellung? [{ name, r }] mit r = bestellungLesen(…) oder null (nicht lesbar).
// Die mit den meisten Positionen; bei Gleichstand die, deren Name nach Bestellung klingt. -1 = keine.
export function bestellungFinden(lesungen) {
  let beste = -1;
  let wert = 0;
  lesungen.forEach((l, i) => {
    const n = l?.r?.positionen?.length ?? 0;
    if (!n) return;
    const w = n * 10 + (/bestell|order|\bpo\b|auftrag/i.test(l.name) ? 5 : 0) + (l.r.kopf?.bestellnr ? 3 : 0);
    if (w > wert) { wert = w; beste = i; }
  });
  return beste;
}

// Nummern einer Position, an denen ihre Dateien zu erkennen sind (mindestens 4 Zeichen)
export const nummernVon = (p) => [p.teilenummer, p.zeichnungsnr, p.bauteil?.teilenummer, p.bauteil?.zeichnungsnr]
  .map(schluessel).filter((k, i, a) => k.length >= 4 && a.indexOf(k) === i);

// Datei → Position: die Position, deren Nummer im Dateinamen steht (die längste Nummer gewinnt, z. B. 10241355 vor 1024).
// Liefert je Datei den Index der Position oder -1.
export function dateienZuordnen(positionen, dateinamen) {
  const nummern = positionen.map(nummernVon);
  return dateinamen.map((name) => {
    const k = schluessel(basis(name));
    let beste = -1;
    let laenge = 0;
    nummern.forEach((liste, i) => {
      for (const n of liste) if (n.length > laenge && k.includes(n)) { laenge = n.length; beste = i; }
    });
    return beste;
  });
}

// Was CNC One über eine Position schon weiß (aus bestellung.vorschlag): { art, text }
//   'auftrag'  – schon einmal in CNC One beauftragt (letzter Auftrag)
//   'angebot'  – angeboten, aber noch nicht beauftragt
//   'bauteil'  – Bauteil angelegt, aber noch kein Angebot/Auftrag
//   'frueher'  – von Hand: schon vor CNC One gefertigt
//   'neu'      – unbekannt
export function bekanntheit(p) {
  const la = p.letzterAuftrag;
  if (la) return { art: 'auftrag', text: `Schon gefertigt: ${la.auftrag}${la.datum ? ` vom ${new Date(la.datum).toLocaleDateString('de-DE')}` : ''}, ${la.menge} Stk` };
  if (p.quellen?.length) return { art: 'angebot', text: `Angeboten in ${p.quellen[0].angebot}` };
  if (p.bauteil?.frueherGefertigt) return { art: 'frueher', text: `Schon gefertigt (vor CNC One)${p.bauteil.frueherNotiz ? `: ${p.bauteil.frueherNotiz}` : ''}` };
  if (p.bauteil) return { art: 'bauteil', text: `Bauteil ${p.bauteil.id} bekannt` };
  return { art: 'neu', text: 'Neues Bauteil' };
}
