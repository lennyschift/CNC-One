// Erkennung der Schriftfeld-Angaben einer Zeichnung.
// Eingabe sind die Textstücke einer PDF-Seite mit Lage (siehe zeichnungText.js). Zuerst gelten die angelernten Regeln des
// Kunden (Kundenvorlage: Stichwort oder Stelle auf der Seite), danach die allgemeine Erkennung: bekannte Stichwörter
// (deutsch und englisch), der Wert steht im selben Textstück nach einem Doppelpunkt, rechts daneben oder darunter.
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
  ['1.1191', [/1\.1191/, /\bC45E\b/i]],
  ['1.0503', [/1\.0503/, /\bC45\b/]],
  ['1.7225', [/1\.7225/, /42CrMo4/i]],
  ['1.0718', [/1\.0718/, /11SMnPb30/i]],
  ['1.0715', [/1\.0715/, /11SMn30/i]],
  ['1.2312', [/1\.2312/, /40CrMnMoS8-?6/i]],
  ['1.0037', [/1\.0037/, /\bS235(JR)?\b/i, /\bSt\s?37\b/i]],
  ['1.0570', [/1\.0570/, /\bS355(J2)?\b/i, /\bSt\s?52\b/i]],
  ['EN AW-7075', [/\b7075\b/, /AlZn\s?5[.,]?5\s?MgCu/i, /AlZnMgCu1[.,]?5/i, /3\.4365/]],
  ['EN AW-6082', [/\b6082\b/, /AlSi1MgMn/i, /AlMgSi1/i, /3\.2315/]],
  ['EN AW-5083', [/\b5083\b/, /AlMg4[.,]?5Mn/i, /3\.3547/]],
  ['EN AW-2007', [/AlCuMgPb/i, /3\.1645/]],
  ['EN AW-6061', [/\b6061\b/, /AlMg1SiCu/i, /3\.3211/]],
  ['CW614N', [/CW614N/i, /CuZn39Pb3/i, /2\.0401/]],
  ['3.7165', [/3\.7165/, /Ti-?6Al-?4V/i, /Grade\s?5/i]],
  ['1.7131', [/1\.7131/, /16MnCr5/i]],
  ['1.7147', [/1\.7147/, /20MnCr5/i]],
  ['1.6587', [/1\.6587/, /18CrNiMo7-?6/i]],
  ['1.6582', [/1\.6582/, /34CrNiMo6/i]],
  ['1.7218', [/1\.7218/, /25CrMo4/i]],
  ['1.7220', [/1\.7220/, /34CrMo4/i]],
  ['1.0711', [/1\.0711/, /9SMn28/i]],
  ['1.0737', [/1\.0737/, /9SMnPb36/i]],
  ['1.3505', [/1\.3505/, /\b100Cr6\b/i]],
  ['1.2379', [/1\.2379/, /X153CrMoV12/i]],
  ['1.2842', [/1\.2842/, /90MnCrV8/i]],
  ['1.4021', [/1\.4021/, /X20Cr13/i]],
  ['1.4034', [/1\.4034/, /X46Cr13/i]],
  ['1.4104', [/1\.4104/, /X14CrMoS17/i]],
  ['1.4112', [/1\.4112/, /X90CrMoV18/i]],
  ['1.4307', [/1\.4307/, /X2CrNi18-?9/i, /\b304L\b/i]],
  ['1.4541', [/1\.4541/, /X6CrNiTi18-?10/i, /\bAISI\s?321\b/i]],
  ['1.4462', [/1\.4462/, /X2CrNiMoN22-?5-?3/i]],
  ['EN AW-5754', [/\b5754\b/, /AlMg3\b/i, /3\.3535/]],
  ['EN AW-6060', [/\b6060\b/, /AlMgSi0[.,]5/i, /3\.3206/]],
  ['EN AW-2017', [/AlCuMg1\b/i, /3\.1325/]],
  ['CW617N', [/CW617N/i, /CuZn40Pb2/i, /2\.0402/]],
  ['CW508L', [/CW508L/i, /CuZn37\b/i, /2\.0321/]],
  ['PTFE', [/\bPTFE\b/i, /Teflon/i]],
  ['PE-HD', [/\bPE-?HD\b/i, /\bHDPE\b/i]],
  ['POM', [/\bPOM\b/]],
  ['PEEK', [/\bPEEK\b/]],
  ['PA6', [/\bPA\s?6\b/]],
];

// Werkstoffnummer zu einem Text: zuerst bekannte Werkstoffe (auch Kurznamen), dann allgemein jede Werkstoffnummer
// (1.xxxx Stahl, 2.xxxx Schwermetalle, 3.xxxx Leichtmetalle), EN AW-xxxx und Kupfer CWxxxN. `allgemein: false` nur bekannte
// (für die Suche im ganzen Zeichnungstext, wo 2.5000 auch ein Maß sein kann).
export function werkstoffNummer(text, { allgemein = true } = {}) {
  const t = text ?? '';
  for (const [nr, muster] of WERKSTOFFE) if (muster.some((m) => m.test(t))) return nr;
  if (!allgemein) return '';
  const nummer = /\b[123]\.\d{4}\b/.exec(t);
  if (nummer) return nummer[0];
  const alu = /\bEN[\s-]?AW[\s-]?(\d{4}[A-Z]?)\b/i.exec(t);
  if (alu) return `EN AW-${alu[1].toUpperCase()}`;
  const kupfer = /\bC[WC]\d{3}[A-Z]\b/i.exec(t);
  return kupfer ? kupfer[0].toUpperCase() : '';
}

// Rohmaterial aus den Stammdaten zu einem erkannten Werkstoff: gleiche Werkstoffnummer/Legierung im Namen
// Zuerst gilt eine gemerkte Schreibweise (oder der gleiche Name), dann die gleiche Werkstoffnummer.
export function materialFinden(werkstoff, materialien) {
  const text = ohneZeichen(werkstoff);
  if (!text) return null;
  const namen = (m) => [m.name, ...(m.schreibweisen ?? [])];
  const gemerkt = materialien.find((m) => namen(m).some((n) => { const x = ohneZeichen(n); return x && (x === text || (x.length >= 4 && text.includes(x))); }));
  if (gemerkt) return gemerkt;
  const nr = werkstoffNummer(werkstoff);
  if (!nr) return null;
  const kern = ohneZeichen(nr.replace(/^EN AW-/, ''));
  return materialien.find((m) => namen(m).some((n) => werkstoffNummer(n) === nr)) ?? materialien.find((m) => ohneZeichen(m.name).includes(kern)) ?? null;
}

// Name für ein neues Rohmaterial aus der Werkstoffangabe: Werkstoffnummer vorne, wenn sie nicht schon im Text steht
export function rohmaterialName(werkstoff) {
  const text = String(werkstoff ?? '').replace(/\s+/g, ' ').trim();
  const nr = werkstoffNummer(text);
  return nr && !ohneZeichen(text).includes(ohneZeichen(nr)) ? `${nr} ${text}` : text;
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

// ---- Kundenvorlage: angelernte Regeln je Feld, { stichwort } oder { bereich: { x, y, b, h } }
// Passt ein Textstück zum gelernten Stichwort? Gleich (ohne abschließende Satzzeichen) oder Stichwort plus Wortgrenze.
function labelPasst(e, stichwort) {
  const t = norm(e.text);
  const ohne = (x) => x.replace(/[\s.:]+$/, '');
  return ohne(t) === ohne(stichwort) || (t.startsWith(stichwort) && /^[\s.:]/.test(t.slice(stichwort.length)));
}

// Wert zu einer Stichwort-Regel. Mit gelerntem Versatz (dx, dy) steht der Wert genau dort, wo er beim Anlernen stand;
// ältere Regeln ohne Versatz suchen rechts daneben oder darunter.
function nachStichwort(regel, elemente, feld) {
  const stichwort = norm(regel.stichwort);
  const labels = elemente.filter((e) => labelPasst(e, stichwort));
  labels.sort((x, y) => (norm(x.text) === stichwort ? 0 : 1) - (norm(y.text) === stichwort ? 0 : 1));
  for (const label of labels) {
    const t = label.text.trim();
    const rest = (t.includes(':') ? t.split(':').slice(1).join(':') : t.slice(stichwort.length)).replace(/^[\s.:]+/, '').split(/\s+[·|;]\s+|\s{3,}/)[0].trim();
    if (rest) {
      if (FELDER[feld].pruefen(rest) || regel.dx !== undefined) return { el: label, wert: rest };
      continue;
    }
    if (regel.dx !== undefined) {
      const zx = label.x + regel.dx;
      const zy = label.y + regel.dy;
      let best = null;
      for (const e of elemente) {
        if (e === label || Math.abs(e.x - zx) > 0.03 || Math.abs(e.y - zy) > 0.015) continue;
        const d = Math.abs(e.x - zx) + Math.abs(e.y - zy) * 1.5;
        if (!best || d < best.d) best = { e, d };
      }
      if (best) return { el: best.e, wert: best.e.text.trim() };
      continue;
    }
    const w = wertNeben(label, elemente, feld);
    if (w) return { el: w, wert: w.text.trim() };
  }
  return null;
}

// Wert, den eine einzelne Regel auf dieser Seite liefert (oder null)
function regelWert(regel, elemente, feld) {
  return regel.stichwort ? nachStichwort(regel, elemente, feld) : regel.bereich ? imBereich(regel.bereich, elemente, feld) : null;
}

// Textstück an der angelernten Stelle: Anfang links im Bereich (längere Werte ragen nach rechts hinaus), Mitte in der Höhe
function imBereich(bereich, elemente, feld) {
  const treffer = elemente.filter((e) => {
    const mitte = e.y + e.h / 2;
    return e.x >= bereich.x - 0.01 && e.x <= bereich.x + bereich.b && mitte >= bereich.y && mitte <= bereich.y + bereich.h && !istLabel(e) && FELDER[feld].pruefen(e.text.trim());
  });
  treffer.sort((a, b) => Math.abs(a.x - bereich.x) + Math.abs(a.y - bereich.y) - Math.abs(b.x - bereich.x) - Math.abs(b.y - bereich.y));
  return treffer[0] ? { el: treffer[0], wert: treffer[0].text.trim() } : null;
}

function nachVorlage(vorlage, elemente) {
  const felder = {};
  for (const [feld, regeln] of Object.entries(vorlage?.felder ?? {})) {
    if (!FELDER[feld]) continue;
    for (const r of regeln) {
      const t = regelWert(r, elemente, feld);
      if (t) { felder[feld] = ergebnis(t.wert, 'hoch', 'Kundenvorlage', t.el); break; }
    }
  }
  return felder;
}

// Textstück an einer Stelle der Seite (Klick in der Zeichnung, Koordinaten 0 bis 1); bei Überlappung das kleinste
export function elementBei(seite, x, y) {
  const rand = 0.003;
  const treffer = (seite?.elemente ?? []).filter((e) => x >= e.x - rand && x <= e.x + e.b + rand && y >= e.y - rand && y <= e.y + e.h + rand);
  treffer.sort((a, b) => a.b * a.h - b.b * b.h);
  return treffer[0] ?? null;
}

// Aus einem angeklickten Wert eine Lernregel ableiten: das Label links daneben oder darüber als Stichwort,
// dazu die Stelle auf der Seite. Steht das Label im selben Textstück ("Ident-Nr.: 4711"), wird es abgetrennt.
// Liefert { wert, lage, stichwort, bereich }.
// Sieht ein Textstück wie ein Label aus? Kleiner geschrieben als der Wert, endet auf "." oder ":" oder enthält keine Ziffer.
const labelArtig = (e, wert) => e.h < wert.h * 0.95 || /[.:]$/.test(e.text.trim()) || !/\d/.test(e.text);

export function lernregel(seite, el) {
  const elemente = seite?.elemente ?? [];
  let wert = el.text.trim();
  let stichwort = '';
  let versatz = null;
  const doppelpunkt = /^([^:]*\p{L}[^:]*):\s*(.+)$/u.exec(wert);
  if (doppelpunkt) { stichwort = norm(doppelpunkt[1]); wert = doppelpunkt[2].trim(); versatz = { dx: 0, dy: 0 }; }
  if (!stichwort) {
    let best = null;
    for (const e of elemente) {
      if (e === el || !/\p{L}{2,}/u.test(e.text) || !labelArtig(e, el)) continue;
      const zeile = Math.abs(e.y - el.y) < Math.max(e.h, el.h) * 0.8 && e.x + e.b <= el.x + 0.005;
      const abstandLinks = el.x - (e.x + e.b);
      // darüber: das Label beginnt links vom Wert oder bündig und reicht bis an seinen Anfang (gleiche Zelle)
      const drueber = e.y + e.h <= el.y + 0.004 && el.y - (e.y + e.h) < 0.04 && e.x <= el.x + 0.005 && (e.x + e.b >= el.x - 0.01 || el.x - e.x < 0.03);
      let punkte = null;
      if (zeile && abstandLinks < 0.3) punkte = abstandLinks;
      if (drueber) punkte = Math.min(punkte ?? Infinity, (el.y - (e.y + e.h)) * 1.5 + Math.abs(e.x - el.x) * 0.5);
      if (punkte !== null && (!best || punkte < best.punkte)) best = { e, punkte };
    }
    if (best) {
      stichwort = norm(best.e.text).replace(/[\s:]+$/, '');
      versatz = { dx: runden(el.x - best.e.x), dy: runden(el.y - best.e.y) };
    }
  }
  const lage = { x: el.x, y: el.y, b: el.b, h: el.h };
  const bereich = { x: Math.max(0, el.x - 0.005), y: Math.max(0, el.y - 0.004), b: Math.min(1 - el.x, Math.max(el.b + 0.01, 0.15)), h: el.h + 0.008 };
  return { wert, lage, stichwort, versatz, bereich };
}

const runden = (v) => Math.round(v * 10000) / 10000;

// Die zu speichernden Regeln aus einer Lernregel: Stichwort mit Versatz (falls es ein Label gibt) und die Stelle auf der Seite
export function regelnAus(regel) {
  return [...(regel.stichwort ? [{ stichwort: regel.stichwort, ...(regel.versatz ?? {}) }] : []), { bereich: regel.bereich }];
}

// Textstück mit einem bestimmten Wert (für getippte Korrekturen): gleicher Text, sonst ein Textstück, das den Wert enthält
export function elementMitWert(seite, wert) {
  const n = norm(wert);
  if (n.length < 1) return null;
  const elemente = seite?.elemente ?? [];
  return elemente.find((e) => norm(e.text) === n)
    ?? (n.length >= 3 ? elemente.filter((e) => norm(e.text).includes(n)).sort((x, y) => x.text.length - y.text.length)[0] : null)
    ?? null;
}

// Neue Regeln eines Feldes vor die alten setzen. Alte Regeln, die auf dieser Zeichnung einen anderen als den bestätigten
// Wert liefern, sind für dieses Schriftfeld falsch und fallen weg; Regeln, die hier gar nicht greifen (andere Zeichnungsart
// desselben Kunden), bleiben. Höchstens vier Regeln je Feld.
export function regelnZusammenfuehren(alte, neue, seite, feld, wert) {
  const elemente = seite?.elemente ?? [];
  const gleich = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  const bleiben = (alte ?? []).filter((r) => {
    if (neue.some((n) => gleich(n, r))) return false;
    const t = regelWert(r, elemente, feld);
    return !t || norm(t.wert) === norm(wert);
  });
  return [...neue, ...bleiben].slice(0, 4);
}

// Kunde aus den Stammdaten zum Namen auf der Zeichnung (der eine enthält den anderen, ohne Satzzeichen)
export function kundeFinden(name, kunden) {
  const n = String(name ?? '').toLowerCase().replace(/[^\p{L}\d]+/gu, '');
  if (n.length < 3) return null;
  return kunden.find((k) => { const m = String(k.name ?? '').toLowerCase().replace(/[^\p{L}\d]+/gu, ''); return m && (m.includes(n) || n.includes(m)); }) ?? null;
}

// Erkennt die Angaben einer Zeichnung. `seite`: { elemente: [{ text, x, y, b, h }] }, `dateiname` als Rückfall,
// `vorlage` die angelernten Regeln des Kunden (gehen vor). Liefert
// { felder: { feld: { wert, sicherheit: 'hoch' | 'mittel' | 'niedrig', quelle, lage } }, werkstoffNr }.
export function erkennen(seite, dateiname = '', vorlage = null) {
  const elemente = seite?.elemente ?? [];
  const felder = nachVorlage(vorlage, elemente);
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
    const e = elemente.find((x) => werkstoffNummer(x.text, { allgemein: false }));
    if (e) felder.werkstoff = ergebnis(e.text.trim(), 'mittel', 'Muster', e);
  }
  const datei = ausDateiname(dateiname);
  if (!felder.teilenummer && datei.teilenummer) felder.teilenummer = ergebnis(datei.teilenummer, 'niedrig', 'Dateiname');
  if (!felder.bezeichnung && datei.bezeichnung) felder.bezeichnung = ergebnis(datei.bezeichnung, 'niedrig', 'Dateiname');
  return { felder, werkstoffNr: werkstoffNummer(felder.werkstoff?.wert) };
}

// Richtwert der Dichte (kg/dm³) aus einer Werkstoffangabe, wenn am Rohmaterial keine gepflegt ist; 0 = unbekannt
export function dichteSchaetzen(werkstoff) {
  const t = String(werkstoff ?? '').toLowerCase();
  const nr = werkstoffNummer(werkstoff);
  const tabelle = { POM: 1.41, PEEK: 1.31, PA6: 1.14, PTFE: 2.2, 'PE-HD': 0.95 };
  if (tabelle[nr]) return tabelle[nr];
  if (nr.startsWith('3.7') || t.includes('titan')) return 4.43;
  if (nr.startsWith('1.4') || t.includes('edelstahl') || t.includes('rostfrei')) return 7.9;
  if (nr.startsWith('1.') || t.includes('stahl')) return 7.85;
  if (nr.startsWith('EN AW') || nr.startsWith('3.') || /\balu/.test(t)) return 2.7;
  if (nr.startsWith('CW') || nr.startsWith('2.0') || t.includes('messing') || t.includes('kupfer') || t.includes('bronze')) return 8.5;
  if (nr.startsWith('2.4') || t.includes('inconel')) return 8.3;
  return 0;
}
