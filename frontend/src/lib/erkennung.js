// Allgemeine Erkennung der Schriftfeld-Angaben einer Zeichnung (ohne Regeln je Kunde).
// Eingabe sind die Textstücke einer PDF-Seite mit Lage (siehe zeichnungText.js). Gesucht werden bekannte Stichwörter
// (deutsch und englisch); der Wert steht im selben Textstück nach einem Doppelpunkt, rechts daneben oder darunter.
// Was so nicht gefunden wird, kommt aus Mustern (Werkstoffe, ISO 2768) oder zuletzt aus dem Dateinamen.

export const FELDER = {
  teilenummer: {
    label: 'Teilenummer',
    stichworte: ['sachnummer', 'sach-nr', 'sachnr', 'teilenummer', 'teile-nr', 'teilenr', 'teil-nr', 'artikelnummer', 'artikel-nr', 'artikelnr', 'art.-nr', 'art-nr',
      'materialnummer', 'material-nr', 'ident-nr', 'identnummer', 'id-nr', 'part no', 'part number', 'part-no', 'part nr', 'p/n', 'item no', 'item number'],
    pruefen: (v) => /\d/.test(v) && v.length <= 40 && !/^\d{1,2}\.\d{1,2}\.\d{2,4}$/.test(v),
    ohneDoppelpunkt: true,
  },
  zeichnungsnr: {
    label: 'Zeichnungsnummer',
    stichworte: ['zeichnungsnummer', 'zeichnungs-nr', 'zeichnungsnr', 'zeichn.-nr', 'zeichn.nr', 'zeichn-nr', 'zeich.-nr', 'zchn.-nr', 'zeichnung nr', 'zeichnung-nr',
      'zeichnungs nr', 'drawing no', 'drawing number', 'drawing nr', 'dwg no', 'dwg. no', 'dwg-no', 'dwg nr', 'dwg'],
    pruefen: (v) => /\d/.test(v) && v.length <= 40,
    ohneDoppelpunkt: true,
  },
  bezeichnung: {
    label: 'Bezeichnung',
    stichworte: ['benennung', 'bezeichnung', 'teilebezeichnung', 'artikelbezeichnung', 'titel', 'title', 'description', 'designation', 'part name'],
    pruefen: (v) => /\p{L}{2,}/u.test(v) && v.length <= 80,
  },
  revision: {
    label: 'Revision',
    stichworte: ['änderungsindex', 'aenderungsindex', 'änd.-index', 'index', 'rev', 'revision', 'ausgabe', 'version'],
    pruefen: (v) => v.length <= 6 && /^[\p{L}\d][\p{L}\d.\-]*$/u.test(v),
    ohneDoppelpunkt: true,
  },
  werkstoff: {
    label: 'Werkstoff',
    stichworte: ['werkstoff', 'werkstoffnummer', 'werkstoff-nr', 'material', 'werkstoff/material'],
    pruefen: (v) => v.length >= 2 && v.length <= 60 && /\p{L}|\d/u.test(v),
  },
  oberflaeche: {
    label: 'Oberfläche',
    stichworte: ['oberfläche', 'oberflaeche', 'oberflächenbehandlung', 'beschichtung', 'finish', 'surface', 'surface treatment'],
    pruefen: (v) => v.length >= 2 && v.length <= 60,
  },
  toleranz: {
    label: 'Allgemeintoleranz',
    stichworte: ['allgemeintoleranz', 'allgemeintoleranzen', 'freimaßtoleranz', 'freimasstoleranz', 'general tol', 'general tolerance', 'general tolerances', 'tolerancing'],
    pruefen: (v) => v.length >= 2 && v.length <= 40,
  },
  kunde: {
    label: 'Kunde',
    stichworte: ['kunde', 'auftraggeber', 'customer', 'client'],
    pruefen: (v) => /\p{L}{2,}/u.test(v) && v.length <= 60,
  },
};

// Weitere Schriftfeld-Stichwörter, deren Werte nirgends hingehören (damit sie nicht als Wert eines anderen Feldes gelten)
const ANDERE = ['maßstab', 'massstab', 'blatt', 'datum', 'gez', 'gez.', 'gezeichnet', 'gepr', 'gepr.', 'geprüft', 'norm', 'name', 'format', 'gewicht', 'projektion',
  'scale', 'sheet', 'date', 'drawn', 'checked', 'approved', 'weight', 'size', 'projection'];

const norm = (s) => String(s ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
const ohneZeichen = (s) => norm(s).replace(/[\s\-_.:/]+/g, '');

// Stichwort am Anfang des Textstücks? Liefert { feld, rest } oder null. Das längste passende Stichwort gewinnt.
function stichwortIn(text) {
  const t = norm(text);
  let best = null;
  for (const [feld, f] of Object.entries(FELDER)) {
    for (const s of f.stichworte) {
      if (!t.startsWith(s)) continue;
      const rest = t.slice(s.length);
      if (rest && !/^[\s.:]/.test(rest)) continue; // Wortgrenze: "material" passt nicht auf "materialien"
      if (!best || s.length > best.laenge) best = { feld, laenge: s.length, rest: text.trim().slice(s.length) };
    }
  }
  if (best) return best;
  const nackt = t.replace(/[.:]+$/, '');
  return ANDERE.includes(nackt) ? { feld: null, laenge: nackt.length, rest: '' } : null;
}

// Wert aus dem Rest hinter dem Stichwort: "Werkstoff: 1.4404" oder (bei Nummern) "Rev. A2"
function wertImRest(feld, rest) {
  const r = rest.replace(/^\s*\.?\s*/, '');
  const mitDoppelpunkt = /^:/.test(r);
  const w = r.replace(/^:\s*/, '').split(/\s+[·|;]\s+|\s{3,}/)[0].trim();
  if (!w) return '';
  if (mitDoppelpunkt || FELDER[feld].ohneDoppelpunkt) return w;
  return '';
}

// Ein Textstück ist ein Label, wenn es mit einem Stichwort beginnt und keinen eigenen Wert trägt
function istLabel(e) {
  const s = stichwortIn(e.text);
  return !!s && !(s.feld && wertImRest(s.feld, s.rest));
}

// Wert rechts neben oder unter einem Label suchen. Kleinere Punktzahl = besser.
function wertNeben(label, elemente, feld) {
  let best = null;
  for (const e of elemente) {
    if (e === label || istLabel(e)) continue;
    const text = e.text.trim();
    if (!FELDER[feld].pruefen(text)) continue;
    const zeile = Math.abs(e.y - label.y) < Math.max(e.h, label.h) * 0.8;
    const dx = e.x - (label.x + label.b);
    let punkte = null;
    if (zeile && dx >= -0.005 && dx < 0.3) punkte = dx;
    const dy = e.y - (label.y + label.h);
    if (dy >= -0.004 && dy < 0.04 && Math.abs(e.x - label.x) < 0.03) punkte = Math.min(punkte ?? Infinity, dy * 1.5 + Math.abs(e.x - label.x) * 0.5);
    if (punkte !== null && (!best || punkte < best.punkte)) best = { e, punkte };
  }
  return best?.e ?? null;
}

// ---- Werkstoffe: Synonyme auf eine Werkstoffnummer bzw. Legierungsbezeichnung abbilden
const WERKSTOFFE = [
  ['1.4301', [/1\.4301/, /X5CrNi18-?10/i, /\bV2A\b/i, /\bAISI\s?304\b/i]],
  ['1.4305', [/1\.4305/, /X8CrNiS18-?9/i, /\bAISI\s?303\b/i]],
  ['1.4404', [/1\.4404/, /X2CrNiMo17-?12-?2/i, /\b316L\b/i]],
  ['1.4571', [/1\.4571/, /X6CrNiMoTi17-?12-?2/i, /\b316Ti\b/i]],
  ['1.4542', [/1\.4542/, /17-?4\s?PH/i, /X5CrNiCuNb16-?4/i]],
  ['1.4057', [/1\.4057/, /X17CrNi16-?2/i]],
  ['1.0503', [/1\.0503/, /\bC45E?\b/]],
  ['1.7225', [/1\.7225/, /42CrMo4/i]],
  ['1.0718', [/1\.0718/, /11SMnPb30/i]],
  ['1.0715', [/1\.0715/, /11SMn30/i]],
  ['1.2312', [/1\.2312/, /40CrMnMoS8-?6/i]],
  ['1.0037', [/1\.0037/, /\bS235(JR)?\b/i, /\bSt\s?37\b/i]],
  ['1.0570', [/1\.0570/, /\bS355(J2)?\b/i, /\bSt\s?52\b/i]],
  ['EN AW-7075', [/\b7075\b/, /AlZn\s?5[.,]?5\s?MgCu/i, /AlZnMgCu1[.,]?5/i, /3\.4365/]],
  ['EN AW-6082', [/\b6082\b/, /AlSi1MgMn/i, /AlMgSi1/i, /3\.2315/]],
  ['EN AW-5083', [/\b5083\b/, /AlMg4[.,]?5Mn/i, /3\.3547/]],
  ['EN AW-2007', [/\b2007\b/, /AlCuMgPb/i, /3\.1645/]],
  ['EN AW-6061', [/\b6061\b/, /AlMg1SiCu/i, /3\.3211/]],
  ['CW614N', [/CW614N/i, /CuZn39Pb3/i, /2\.0401/]],
  ['3.7165', [/3\.7165/, /Ti-?6Al-?4V/i, /Grade\s?5/i]],
  ['POM', [/\bPOM\b/]],
  ['PEEK', [/\bPEEK\b/]],
  ['PA6', [/\bPA\s?6\b/]],
];

export function werkstoffNummer(text) {
  for (const [nr, muster] of WERKSTOFFE) if (muster.some((m) => m.test(text ?? ''))) return nr;
  return '';
}

// Rohmaterial aus den Stammdaten zu einem erkannten Werkstoff: gleiche Werkstoffnummer/Legierung im Namen
export function materialFinden(werkstoff, materialien) {
  const nr = werkstoffNummer(werkstoff);
  if (!nr) return null;
  const kern = ohneZeichen(nr.replace(/^EN AW-/, ''));
  return materialien.find((m) => werkstoffNummer(m.name) === nr) ?? materialien.find((m) => ohneZeichen(m.name).includes(kern)) ?? null;
}

// Rückfall aus dem Dateinamen: "ZZ-3D-001_Flansch.pdf" -> Teilenummer ZZ-3D-001, Bezeichnung Flansch
export function ausDateiname(name) {
  const basis = String(name ?? '').replace(/\.[^.]+$/, '');
  const teile = basis.split(/[_\s]+/).filter(Boolean);
  const nr = teile.find((t) => /\d/.test(t) && t.length >= 3) ?? '';
  const rest = teile.filter((t) => t !== nr && !/^(zeichnung|drawing|dwg|pdf|step|stp|rev\w*)$/i.test(t)).join(' ');
  return { teilenummer: nr, bezeichnung: /\p{L}{2,}/u.test(rest) ? rest : '' };
}

const ISO2768 = /ISO\s?2768[\s-]*[fmcv][HKL]?/i;
const ergebnis = (wert, sicherheit, quelle, e = null) => ({ wert, sicherheit, quelle, lage: e ? { x: e.x, y: e.y, b: e.b, h: e.h } : null });

// Erkennt die Angaben einer Zeichnung. `seite`: { elemente: [{ text, x, y, b, h }] }, `dateiname` als Rückfall.
// Liefert { felder: { feld: { wert, sicherheit: 'hoch' | 'mittel' | 'niedrig', quelle, lage } }, werkstoffNr }.
export function erkennen(seite, dateiname = '') {
  const elemente = seite?.elemente ?? [];
  const felder = {};
  for (const e of elemente) {
    const s = stichwortIn(e.text);
    if (!s?.feld || felder[s.feld]) continue;
    const imText = wertImRest(s.feld, s.rest);
    if (imText && FELDER[s.feld].pruefen(imText)) { felder[s.feld] = ergebnis(imText, 'hoch', 'Schriftfeld', e); continue; }
    if (s.rest.replace(/^[\s.:]+/, '')) continue; // Stichwort mitten im Satz ohne erkennbaren Wert
    const w = wertNeben(e, elemente, s.feld);
    if (w) felder[s.feld] = ergebnis(w.text.trim(), 'hoch', 'Schriftfeld', w);
  }
  const alles = elemente.map((e) => e.text).join('\n');
  if (!felder.toleranz) {
    const m = ISO2768.exec(alles);
    if (m) felder.toleranz = ergebnis(m[0].replace(/\s+/g, ' '), 'mittel', 'Muster');
  }
  if (!felder.werkstoff) {
    const e = elemente.find((x) => werkstoffNummer(x.text));
    if (e) felder.werkstoff = ergebnis(e.text.trim(), 'mittel', 'Muster', e);
  }
  const datei = ausDateiname(dateiname);
  if (!felder.teilenummer && datei.teilenummer) felder.teilenummer = ergebnis(datei.teilenummer, 'niedrig', 'Dateiname');
  if (!felder.bezeichnung && datei.bezeichnung) felder.bezeichnung = ergebnis(datei.bezeichnung, 'niedrig', 'Dateiname');
  return { felder, werkstoffNr: werkstoffNummer(felder.werkstoff?.wert) };
}
