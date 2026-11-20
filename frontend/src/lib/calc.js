// Kalkulation der Workbench: reine Funktionen, keine UI, keine Seiteneffekte.
// Übernimmt die Rechenregeln der bisherigen Workbench (priceForQty,
// staffelStueckpreiseAktualisieren, kleinsteStaffel, baseBetrag) und macht sie testbar.
//
// Hat ein Bauteil einen Arbeitsplan (arbeitsgaenge), kommen Rüst- und Stückkosten aus den internen
// Arbeitsgängen (Zeit × Satz der jeweiligen Maschine). Fremdvergaben liefern Kosten je Stück und einmalig.
// Ohne Arbeitsplan gelten die einfachen Felder (ruestMin, stueckMin, satzRuest, satzStueck).
//
// Fester Stückpreis (preisart 'fest'): ohne Kalkulation. Zeiten, Material, Rüstkosten und Fremdvergabe zählen nicht,
// Mess-, Sonder- und Expresskosten kommen als eigene Zeilen dazu. Bei Staffeln gilt je Stufe der eingegebene Preis
// (leer = der feste Stückpreis).

export const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

export const r2 = (v) => Math.round((num(v) + Number.EPSILON) * 100) / 100;

const alle = (p) => (Array.isArray(p.arbeitsgaenge) ? p.arbeitsgaenge : []);
const internAg = (p) => alle(p).filter((a) => a.typ === 'intern');
const fremdAg = (p) => alle(p).filter((a) => a.typ === 'fremd');

export const hatPlan = (p) => internAg(p).length > 0;
export const festerPreis = (p) => p.preisart === 'fest';

// Kosten eines internen Arbeitsgangs: je Spalte direkt in Euro oder Zeit × Satz
export const agRuest = (a) => (a.ruestDirekt ? num(a.ruestEuro) : (num(a.ruestMin) / 60) * num(a.satz));
export const agStueck = (a) => (a.stueckDirekt ? num(a.stueckEuro) : (num(a.stueckMin) / 60) * num(a.satz));

export const ruestKosten = (p) => (hatPlan(p)
  ? r2(internAg(p).reduce((s, a) => s + agRuest(a), 0))
  : r2((num(p.ruestMin) / 60) * num(p.satzRuest)));

export const stueckKosten = (p) => (hatPlan(p)
  ? r2(internAg(p).reduce((s, a) => s + agStueck(a), 0))
  : r2((num(p.stueckMin) / 60) * num(p.satzStueck)));

// Fremdvergabe: Kosten je Stück (zählen zu den Stückkosten)
export const fremdProStueck = (p) => r2(fremdAg(p).reduce((s, a) => s + num(a.fremdProStk), 0));

export const materialProStueck = (p) => r2(num(p.gewichtKg) * num(p.materialPreisKg));

function basis(p) {
  return {
    setup: ruestKosten(p),
    unit: r2(stueckKosten(p) + fremdProStueck(p)),
    mat: materialProStueck(p),
    pauschal: r2(p.pauschalMaterial),
    mess: r2(p.messkosten),
    sonder: r2(p.sonderkosten),
    express: r2(p.expresskosten),
  };
}

// Einmalige Zusatzkosten. `eingerechnet`: wird durch die Menge geteilt und steckt im Stückpreis.
function extras(p, b) {
  const f = p.inStueckpreis || {};
  const liste = [
    { key: 'mess', label: 'Messkosten', betrag: b.mess, eingerechnet: !!f.mess },
    { key: 'sonder', label: 'Sonderkosten', betrag: b.sonder, eingerechnet: !!f.sonder },
    { key: 'express', label: 'Expresskosten', betrag: b.express, eingerechnet: !!f.express },
  ];
  for (const a of fremdAg(p)) {
    if (num(a.fremdEinmal) > 0) {
      liste.push({ key: 'fremd-' + (a.id ?? a.name), label: `Fremdvergabe ${a.name || ''}`.trim(), betrag: r2(a.fremdEinmal), eingerechnet: false });
    }
  }
  return liste;
}

function fixAufteilung(liste) {
  return {
    eingerechnet: liste.filter((x) => x.eingerechnet).reduce((s, x) => s + x.betrag, 0),
    einzeln: liste.filter((x) => !x.eingerechnet).reduce((s, x) => s + x.betrag, 0),
  };
}

export function gueltigeStufen(p) {
  return (p.staffel?.stufen || [])
    .map((s) => ({ menge: Math.floor(num(s.menge)), extra: num(s.extra), preis: num(s.preis) }))
    .filter((s) => s.menge > 0)
    .sort((a, b) => a.menge - b.menge);
}

// Stückpreis bei beliebiger Menge (Basis ohne Extra) – für die Preiskurve.
export function stueckpreisBei(p, menge) {
  const q = Math.max(1, num(menge));
  const b = basis(p);
  const fix = fixAufteilung(extras(p, b));
  return (b.setup + b.pauschal + fix.eingerechnet) / q + b.unit + b.mat;
}

export function berechne(p) {
  const q = Math.max(1, Math.floor(num(p.menge)) || 1);
  const b = basis(p);
  const liste = extras(p, b);
  const fix = fixAufteilung(liste);
  const f = p.inStueckpreis || {};
  const out = { menge: q, ...b, stufen: [], zeilen: [], gesamt: 0, stueckpreis: 0 };
  const kostenZeilen = () => liste.filter((x) => !x.eingerechnet && x.betrag > 0).map((x) => ({ typ: 'kosten', label: x.label, menge: 1, betrag: x.betrag }));

  if (festerPreis(p)) {
    const preis = r2(p.festpreis);
    const zusatz = [['Messkosten', b.mess], ['Sonderkosten', b.sonder], ['Expresskosten', b.express]]
      .filter(([, betrag]) => betrag > 0)
      .map(([label, betrag]) => ({ typ: 'kosten', label, menge: 1, betrag }));
    const einzeln = zusatz.reduce((s, z) => s + z.betrag, 0);
    if (p.staffel?.aktiv) {
      out.stufen = gueltigeStufen(p).map((s) => {
        const stueck = r2(s.preis > 0 ? s.preis : preis);
        return { menge: s.menge, extra: s.extra, stueckpreis: stueck, gesamt: r2(stueck * s.menge + einzeln) };
      });
      out.gesamt = out.stufen[0]?.gesamt ?? 0;
      out.stueckpreis = out.stufen[0]?.stueckpreis ?? 0;
      out.zeilen.push(...zusatz);
      return out;
    }
    out.zeilen.push({ typ: 'teil', label: p.name || 'Bauteil', menge: q, einzel: preis, betrag: r2(preis * q) }, ...zusatz);
    out.gesamt = r2(out.zeilen.reduce((s, z) => s + z.betrag, 0));
    out.stueckpreis = r2(out.gesamt / q);
    return out;
  }

  if (p.staffel?.aktiv) {
    out.stufen = gueltigeStufen(p).map((s) => {
      const stueck = r2((b.setup + b.pauschal + fix.eingerechnet) / s.menge + b.unit + b.mat + s.extra);
      return { menge: s.menge, extra: s.extra, stueckpreis: stueck, gesamt: r2(stueck * s.menge + fix.einzeln) };
    });
    const kleinste = out.stufen[0];
    out.gesamt = kleinste ? kleinste.gesamt : 0;
    out.stueckpreis = kleinste ? kleinste.stueckpreis : 0;
    out.zeilen.push(...kostenZeilen());
    return out;
  }

  const stueckAnteil =
    b.unit +
    b.mat +
    (p.pauschalAlsZeile ? 0 : b.pauschal / q) +
    (f.ruest ? b.setup / q : 0) +
    fix.eingerechnet / q;
  out.zeilen.push({ typ: 'teil', label: p.name || 'Bauteil', menge: q, einzel: r2(stueckAnteil), betrag: r2(stueckAnteil * q) });
  if (!f.ruest && b.setup > 0) out.zeilen.push({ typ: 'kosten', label: 'Rüstkosten', menge: 1, betrag: b.setup });
  if (p.pauschalAlsZeile && b.pauschal > 0) out.zeilen.push({ typ: 'kosten', label: 'Pauschal Material', menge: 1, betrag: b.pauschal });
  out.zeilen.push(...kostenZeilen());
  out.gesamt = r2(out.zeilen.reduce((s, z) => s + z.betrag, 0));
  out.stueckpreis = r2(out.gesamt / q);
  return out;
}

export const summe = (liste) => r2(liste.reduce((s, r) => s + r.gesamt, 0));

// Kalkulationstabelle der Workbench: Zeile für Zeile, je Spalte (Staffel oder Stückzahl) der Anteil am Stückpreis.
// Einmalige Kosten werden durch die Menge der Spalte geteilt, wenn sie im Stückpreis stecken, sonst stehen sie als
// eigene Zeile im Angebot (einzeln). Stückpreis und Gesamt kommen aus berechne(), damit alles zum Angebot passt.
// Liefert { spalten: [{ i, menge, extra, preis }], zeilen: { key: { je: [...], einzeln } }, selbstkosten: [...],
// stueckpreis: [...], einzeln: [...], gesamt: [...], haupt (Spalte, die für die Summe zählt) }.
export function kostenTabelle(p, ergebnis = berechne(p)) {
  const staffel = !!p.staffel?.aktiv;
  const fest = festerPreis(p);
  const f = p.inStueckpreis || {};
  const spalten = staffel
    ? (p.staffel.stufen || []).map((s, i) => ({ i, menge: Math.max(1, Math.floor(num(s.menge)) || 1), extra: num(s.extra), preis: num(s.preis) }))
    : [{ i: -1, menge: Math.max(1, Math.floor(num(p.menge)) || 1), extra: 0, preis: 0 }];
  const ruestIn = staffel || !!f.ruest;
  const pauschalIn = staffel || !p.pauschalAlsZeile;
  const zeile = (stueck, einmalig, imStueck) => ({ je: spalten.map((s) => stueck + (imStueck ? einmalig / s.menge : 0)), einzeln: imStueck ? 0 : einmalig });
  const zeilen = {};
  zeilen.material = zeile(materialProStueck(p), num(p.pauschalMaterial), pauschalIn);
  if (hatPlan(p)) {
    for (const a of alle(p)) {
      zeilen[`ag-${a.id}`] = a.typ === 'fremd' ? zeile(num(a.fremdProStk), num(a.fremdEinmal), false) : zeile(agStueck(a), agRuest(a), ruestIn);
    }
  } else {
    zeilen.fertigung = zeile((num(p.stueckMin) / 60) * num(p.satzStueck), (num(p.ruestMin) / 60) * num(p.satzRuest), ruestIn);
    for (const a of fremdAg(p)) zeilen[`ag-${a.id}`] = zeile(num(a.fremdProStk), num(a.fremdEinmal), false);
  }
  for (const [key, feld] of [['mess', 'messkosten'], ['sonder', 'sonderkosten'], ['express', 'expresskosten']]) {
    zeilen[key] = fest ? zeile(0, num(p[feld]), false) : zeile(0, num(p[feld]), !!f[key]);
  }
  const werte = Object.values(zeilen);
  const selbstkosten = spalten.map((_s, k) => r2(werte.reduce((s, z) => s + z.je[k], 0)));
  const einzelnKalk = r2(werte.reduce((s, z) => s + z.einzeln, 0));
  const einzelnFest = r2(num(p.messkosten) + num(p.sonderkosten) + num(p.expresskosten));
  const stufe = (s) => ergebnis.stufen.find((x) => x.menge === s.menge && x.extra === s.extra);
  const teilZeile = ergebnis.zeilen.find((z) => z.typ === 'teil');
  const stueckpreis = spalten.map((s, k) => {
    if (staffel) return stufe(s)?.stueckpreis ?? r2(fest ? (s.preis || num(p.festpreis)) : selbstkosten[k] + s.extra);
    return teilZeile?.einzel ?? 0;
  });
  const einzeln = spalten.map(() => (fest ? einzelnFest : einzelnKalk));
  const gesamt = spalten.map((s, k) => (staffel ? stufe(s)?.gesamt ?? r2(stueckpreis[k] * s.menge + einzeln[k]) : ergebnis.gesamt));
  const kleinste = Math.min(...spalten.map((s) => s.menge));
  return { spalten, zeilen, selbstkosten, stueckpreis, einzeln, gesamt, haupt: spalten.findIndex((s) => s.menge === kleinste) };
}
