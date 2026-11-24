// Angebote der Lieferanten vergleichen. Anfragen, die zusammen verschickt wurden (eine Mail, Lieferanten in BCC), bilden
// einen Vorgang mit gemeinsamer Nummer. Reine Funktionen, getestet in vergleich.test.js.
import { isoAusName } from './iso.js';

const r2 = (x) => Math.round(x * 100) / 100;

export const vorgangVon = (a) => a.vorgang || a.id;

// Alle Anfragen eines Vorgangs, nach Nummer
export const imVorgang = (liste, vorgang) => liste.filter((a) => vorgangVon(a) === vorgang).sort((x, y) => x.id.localeCompare(y.id));

// Vorgänge der Liste: [{ vorgang, anfragen }], neueste zuerst wie die Liste
export function vorgaenge(liste) {
  const map = new Map();
  for (const a of liste) {
    const v = vorgangVon(a);
    if (!map.has(v)) map.set(v, []);
    map.get(v).push(a);
  }
  return [...map.entries()].map(([vorgang, anfragen]) => ({ vorgang, anfragen: anfragen.sort((x, y) => x.id.localeCompare(y.id)) }));
}

// Preis eines Lieferanten für eine Position und Menge: { proStk, einmalig, gesamt } oder null (kein Preis)
function zelle(a, posKey, menge) {
  const q = (a.antwort?.preise ?? []).find((x) => x.posKey === posKey && Number(x.menge) === Number(menge));
  if (!q || !(Number(q.proStk) > 0 || Number(q.einmalig) > 0)) return null;
  const proStk = Number(q.proStk) || 0;
  const einmalig = Number(q.einmalig) || 0;
  // aus dem PDF eingelesen: hat der Lieferant eine andere Menge angeboten?
  const je = a.antwort?.daten?.je?.[posKey];
  return { proStk, einmalig, gesamt: r2(proStk * menge + einmalig), abweichung: je?.abweichung ? je.angeboten : null };
}

const guenstigster = (zellen) => {
  let best = null;
  for (const [id, z] of Object.entries(zellen)) if (z && (!best || z.gesamt < best.gesamt)) best = { id, gesamt: z.gesamt };
  return best?.id ?? null;
};

// Zu welcher unserer Positionen ist eine nicht zugeordnete Angebotsposition die Alternative? Dieselbe Ware in anderer
// Länge oder Menge: gleicher Werkstoff, möglichst gleiche Form und Maße wie eine zugeordnete Position desselben Angebots.
function bezugVon(o, positionen) {
  let best = '';
  let punkte = 0;
  for (const p of positionen) {
    if (!p.zuordnung || !o.werkstoff || p.werkstoff !== o.werkstoff) continue;
    const n = 1 + (o.form && p.form === o.form ? 1 : 0) + (o.masse ?? []).filter((m, k) => Number(p.masse?.[k]) === Number(m)).length;
    if (n > punkte) { punkte = n; best = p.zuordnung; }
  }
  return best;
}

// Angebotspositionen aus dem eingelesenen PDF, die keiner Position unserer Anfrage zugeordnet sind: Optionen,
// Alternativen und zusätzlich Angebotenes. [{ key, index, lieferantId, o, option, bezug, zuschlag }]; bezug = posKey oder ''.
export function weiterePositionen(anfragen) {
  const out = [];
  for (const a of anfragen) {
    const ps = a.antwort?.daten?.positionen ?? [];
    ps.forEach((o, i) => {
      if (o.zuordnung || !(Number(o.betrag) > 0)) return;
      out.push({ key: `${a.id}|${i}`, index: i, lieferantId: a.id, o, option: !!o.option, bezug: bezugVon(o, ps), zuschlag: !!a.zuschlag && (a.zuschlagAlternativen ?? []).includes(i) });
    });
  }
  return out;
}

// Vergleich der Anfragen eines Vorgangs:
// { lieferanten: [...], zeilen: [{ key, posKey, nr, teil, agName, abmessung, einheit, menge, ersteZeile, zellen: { [anfrageId]: zelle|null }, bester }],
//   weitere: [...weiterePositionen], summen: [{ stufe, je: { [anfrageId]: { betrag, vollstaendig, mitAlternative } }, bester }] }
// Summe je Stufe: die erste (zweite, …) Menge jeder Position zusammen; der Beste zählt nur unter den vollständigen.
// `alternativen`: keys weiterer Positionen, die in die Summe sollen: mit Bezug statt dieser Position, sonst zusätzlich.
export function vergleich(anfragen, { alternativen = [] } = {}) {
  const basis = anfragen[0];
  if (!basis) return { lieferanten: [], zeilen: [], weitere: [], summen: [] };
  const lieferanten = anfragen.map((a) => ({
    id: a.id, name: a.lieferantName, status: a.status, zuschlag: !!a.zuschlag, neueAntwort: !!a.neueAntwort,
    angebotsnr: a.antwort?.angebotsnr ?? '', gueltigBis: a.antwort?.gueltigBis ?? '', lieferzeit: a.antwort?.lieferzeit ?? '',
    hatPreise: (a.antwort?.preise ?? []).some((q) => Number(q.proStk) > 0 || Number(q.einmalig) > 0),
    nebenkosten: Number(a.antwort?.nebenkosten) || 0, nebenkostenText: a.antwort?.nebenkostenText ?? '', pdf: a.antwort?.pdf ?? '',
    netto: Number(a.antwort?.daten?.netto) || 0,
    zuschlagPositionen: a.zuschlag ? (a.zuschlagPositionen ?? []) : [], zuschlagAlternativen: a.zuschlag ? (a.zuschlagAlternativen ?? []) : [],
  }));
  // Zuschlag je Position: an welchen Lieferanten (Anfrage-Id) geht sie, und per Alternative?
  const vergabe = (posKey) => {
    const l = lieferanten.find((x) => x.zuschlagPositionen.includes(posKey));
    return l ? { id: l.id, perAlternative: weiterePositionen(anfragen.filter((a) => a.id === l.id)).some((w) => w.bezug === posKey && l.zuschlagAlternativen.includes(w.index)) } : null;
  };
  const weitere = weiterePositionen(anfragen);
  const gewaehlt = weitere.filter((w) => alternativen.includes(w.key));
  const zeilen = [];
  basis.positionen.forEach((p, i) => {
    p.mengen.forEach((m, stufe) => {
      const zellen = Object.fromEntries(anfragen.map((a) => [a.id, zelle(a, p.key, m)]));
      zeilen.push({
        key: `${p.key}|${m}`, posKey: p.key, nr: i + 1, stufe, teil: p.teil, agName: p.agName, abmessung: p.abmessung ?? '', einheit: p.einheit || 'Stk',
        menge: m, ersteZeile: stufe === 0, stufen: p.mengen.length, zellen, bester: guenstigster(zellen), vergeben: vergabe(p.key),
      });
    });
  });
  const anzahlStufen = Math.max(0, ...basis.positionen.map((p) => p.mengen.length));
  const summen = [];
  // Nebenkosten (Verpackung, Fracht) einmal je Lieferant in jeder Summe
  const neben = Object.fromEntries(lieferanten.map((l) => [l.id, l.nebenkosten]));
  if (basis.positionen.length > 1 || anzahlStufen > 1 || lieferanten.some((l) => l.nebenkosten) || gewaehlt.length) {
    for (let stufe = 0; stufe < anzahlStufen; stufe++) {
      // je Position die Menge dieser Stufe (hat sie weniger Mengen, ihre letzte)
      const teil = basis.positionen.map((p) => zeilen.find((z) => z.posKey === p.key && z.stufe === Math.min(stufe, p.mengen.length - 1)));
      const je = Object.fromEntries(anfragen.map((a) => {
        const alt = gewaehlt.filter((w) => w.lieferantId === a.id);
        const statt = (posKey) => alt.filter((w) => w.bezug === posKey);
        const werte = teil.map((z) => {
          const s = statt(z.posKey);
          return s.length ? { gesamt: s.reduce((x, w) => x + Number(w.o.betrag), 0) } : z.zellen[a.id];
        });
        const dazu = alt.filter((w) => !w.bezug).reduce((x, w) => x + Number(w.o.betrag), 0);
        const summe = werte.reduce((s, z) => s + (z?.gesamt ?? 0), 0) + dazu;
        return [a.id, { betrag: r2(summe + (werte.some(Boolean) ? neben[a.id] : 0)), vollstaendig: werte.every(Boolean), mitAlternative: alt.length > 0 }];
      }));
      const voll = Object.fromEntries(Object.entries(je).map(([id, x]) => [id, x.vollstaendig ? { gesamt: x.betrag } : null]));
      summen.push({ stufe, je, bester: guenstigster(voll) });
    }
  }
  return { lieferanten, zeilen, weitere, summen };
}

// ---------------------------------------------------------------- Vorlagen: Lieferanten je Werkstoff oder Leistung
export const stichwortListe = (v) => String(v?.stichwoerter ?? '').split(/[,\n]/).map((s) => s.trim().toLowerCase()).filter(Boolean);

// Passt eine Vorlage zu einer Anfrage? `texte`: Werkstoffe, Bezeichnungen, Arbeitsgänge der Positionen
export function vorlagePasst(v, { art = '', texte = [] } = {}) {
  if (!v || v.aktiv === false) return false;
  if (v.art && art && v.art !== art) return false;
  const t = texte.filter(Boolean).map((x) => String(x).toLowerCase());
  if (stichwortListe(v).some((w) => t.some((x) => x.includes(w)))) return true;
  return !!v.isoGruppe && texte.some((x) => x && isoAusName(x) === v.isoGruppe);
}

export const passendeVorlagen = (vorlagen, kontext) => (vorlagen ?? []).filter((v) => vorlagePasst(v, kontext));
